"""Angebote. Die Workbench arbeitet auf einem gespeicherten Angebot im Status Entwurf."""

import json
import os

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, now_datetime, nowdate

from cnc_one.api import aehnlich as aehnlich_api
from cnc_one.api import bauteil as bauteil_api
from cnc_one.api import mail as mail_api
from cnc_one.api.stamm import kunde_ui, nur_cnc


def _iso(wert):
	return get_datetime(wert).isoformat() if wert else None


def _json(wert):
	if wert in (None, ""):
		return {}
	return json.loads(wert) if isinstance(wert, str) else wert


def _revisionen(bauteil):
	"""Aktuelle Revision des Bauteils und alle bekannten (neueste zuerst), für den Hinweis in der Workbench."""
	if not bauteil:
		return {"bauteilRevision": "", "bauteilRevisionen": []}
	namen = frappe.get_all("Bauteil Revision", filters={"parent": bauteil, "parenttype": "Bauteil"}, pluck="revision", order_by="idx desc")
	return {"bauteilRevision": frappe.db.get_value("Bauteil", bauteil, "revision") or "", "bauteilRevisionen": list(dict.fromkeys(r for r in namen if r))}


def _frueher(bauteil):
	"""Von Hand vermerkt: das Bauteil wurde schon vor CNC One gefertigt."""
	if not bauteil:
		return {"gefertigt": False, "notiz": ""}
	w = frappe.db.get_value("Bauteil", bauteil, ["frueher_gefertigt", "frueher_notiz"], as_dict=True) or {}
	return {"gefertigt": bool(w.get("frueher_gefertigt")), "notiz": w.get("frueher_notiz") or ""}


def angebot_ui(d):
	"""Das Angebot in der Form, die die Oberfläche erwartet."""
	kunde = frappe.get_doc("Kunde", d.kunde) if d.kunde else None
	return {
		"id": d.name,
		"status": d.status,
		"erstellt": _iso(d.creation),
		"versandt": _iso(d.versandt_am),
		"geaendert": _iso(d.modified),
		"kopf": {
			"kundeId": d.kunde or "",
			"anfrageNr": d.anfrage_nr or "",
			"gueltigWochen": d.gueltig_wochen or 4,
			"lieferzeit": d.lieferzeit or "",
			"materialDrucken": bool(d.material_drucken),
			"projekt": d.projekt or "",
			"kontaktName": d.kontakt_name or "",
			"kontaktEmail": d.kontakt_email or "",
			"bestellung": _json(d.bestellung) or None,
			"kundeName": d.kunde_name or "",
			"kunde": kunde_ui(kunde) if kunde else None,
		},
		"positionen": [
			{
				"key": z.position_key, "teil": _json(z.kalkulation), "ergebnis": _json(z.ergebnis),
				"bauteilId": z.bauteil or "", "herkunft": ("neu" if z.bauteil_neu else "bestand") if z.bauteil else "",
				"seriennummern": bool(z.bauteil and frappe.db.get_value("Bauteil", z.bauteil, "seriennummern")),
				"bauteilNotiz": (frappe.db.get_value("Bauteil", z.bauteil, "notiz_intern") or "") if z.bauteil else "",
				"bauteilFrueher": _frueher(z.bauteil),
				**_revisionen(z.bauteil),
			}
			for z in d.positionen
		],
		"netto": d.netto or 0,
		"entwurfId": "",
		# eine Überarbeitung gehört zur Mail-Anfrage des ursprünglichen Angebots
		"mailAnfrage": mail_api.zu_angebot(d.name) or (mail_api.zu_angebot(d.ursprung) if d.ursprung else None),
		**fassung_ui(d),
	}


def fassung_ui(d):
	"""Fassung des Angebots: ursprüngliches Angebot (0) oder Überarbeitung (-1, -2 …), dazu alle Fassungen der Reihe."""
	wurzel = d.ursprung or d.name
	reihe = []
	if d.ursprung or d.ersetzt_durch or (d.name and frappe.db.exists("Angebot", {"ursprung": d.name})):
		reihe = [
			{"id": r.name, "fassung": r.fassung or 0, "status": r.status, "versandt": _iso(r.versandt_am), "grund": r.aenderungsgrund or ""}
			for r in frappe.get_all("Angebot", or_filters={"name": wurzel, "ursprung": wurzel}, fields=["name", "fassung", "status", "versandt_am", "aenderungsgrund"], order_by="fassung asc")
		]
	return {
		"fassung": d.fassung or 0, "ursprung": d.ursprung or "", "vorgaenger": d.vorgaenger or "", "ersetztDurch": d.ersetzt_durch or "",
		"aenderungsgrund": d.aenderungsgrund or "", "fassungen": reihe,
	}


def alle_ui():
	namen = frappe.get_list("Angebot", pluck="name", order_by="creation desc", limit_page_length=0)
	return [angebot_ui(frappe.get_doc("Angebot", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


@frappe.whitelist(methods=["POST"])
def entwurf_speichern(angebot):
	"""Legt einen Entwurf an oder aktualisiert ihn. `angebot`: { id, kopf, teile } wie in der Workbench."""
	nur_cnc()
	if isinstance(angebot, str):
		angebot = frappe.parse_json(angebot)
	kopf = angebot.get("kopf") or {}
	teile = angebot.get("teile") or []

	if angebot.get("id") and frappe.db.exists("Angebot", angebot["id"]):
		doc = frappe.get_doc("Angebot", angebot["id"])
	else:
		doc = frappe.new_doc("Angebot")

	kunde = kopf.get("kundeId") or None
	if kunde and not frappe.db.exists("Kunde", kunde):
		frappe.throw(_("Der Kunde {0} gibt es nicht.").format(kunde))
	doc.kunde = kunde
	doc.anfrage_nr = kopf.get("anfrageNr") or ""
	doc.gueltig_wochen = int(kopf.get("gueltigWochen") or 4)
	doc.lieferzeit = kopf.get("lieferzeit") or ""
	doc.material_drucken = 1 if kopf.get("materialDrucken") else 0
	doc.projekt = (kopf.get("projekt") or "").strip()
	doc.kontakt_name = (kopf.get("kontaktName") or "").strip()
	doc.kontakt_email = (kopf.get("kontaktEmail") or "").strip().lower()
	if "bestellung" in kopf:
		b = kopf.get("bestellung")
		doc.bestellung = frappe.as_json({k: b.get(k) or "" for k in ("nr", "datum", "datei")}) if b else None

	# Was dieses Angebot an Bauteilen schon verknüpft hat: Position -> (Bauteil, mit diesem Angebot neu angelegt)
	alt = {z.position_key: (z.bauteil, bool(z.bauteil_neu)) for z in doc.positionen if z.bauteil}
	doc.set("positionen", [])
	behalten = set()
	for t in teile:
		zeile = doc.append("positionen", {"kalkulation": json.dumps(t, ensure_ascii=False)})
		# Bauteil des Kunden wiederfinden oder neu anlegen, sobald Kunde und Teilenummer da sind. Nie doppelt.
		b, neu = bauteil_api.fuer_position(kunde, t, alt.get(str(t.get("id"))))
		zeile.bauteil = b.name if b else None
		zeile.bauteil_neu = 1 if neu else 0
		if b:
			behalten.add(b.name)

	doc.save() if not doc.is_new() else doc.insert()
	# Revision und Dateien am Bauteil ablegen; die Position merkt sich die Revision (auch die aktuelle, wenn keine angegeben ist)
	for z in doc.positionen:
		if z.bauteil:
			kalk = json.loads(z.kalkulation or "{}")
			# Geometrie-Fingerabdruck aus dem STEP-Modell (rechnet die Workbench) für „ähnliche Bauteile“
			aehnlich_api.geo_uebernehmen(z.bauteil, kalk.get("geo"))
			rev = bauteil_api.revision_uebernehmen(z.bauteil, kalk, doc.name)
			if rev != (z.revision or ""):
				z.db_set("revision", rev, update_modified=False)
	# Bauteile, die dieses Angebot neu angelegt hatte und die nicht mehr vorkommen, wieder entfernen
	for name, neu in alt.values():
		if neu and name not in behalten:
			bauteil_api.aufraeumen(name)
	return angebot_ui(doc)


def _geladen(name):
	doc = frappe.get_doc("Angebot", name)
	doc.check_permission("write")
	return doc


@frappe.whitelist(methods=["POST"])
def senden(id):
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Entwurf":
		frappe.throw(_("Nur ein Entwurf lässt sich senden."))
	if not doc.kunde:
		frappe.throw(_("Bitte zuerst einen Kunden wählen."))
	if not doc.positionen:
		frappe.throw(_("Das Angebot enthält noch kein Bauteil."))
	doc.flags.status_wechsel = True
	doc.status = "Gesendet"
	doc.versandt_am = now_datetime()
	doc.save()
	# Eine Überarbeitung ersetzt mit dem Senden die vorige Fassung; die bleibt unverändert (nur ansehen)
	if doc.vorgaenger and frappe.db.exists("Angebot", doc.vorgaenger):
		alt = frappe.get_doc("Angebot", doc.vorgaenger)
		if alt.status != "Ersetzt":
			alt.flags.status_wechsel = True
			alt.status = "Ersetzt"
			alt.ersetzt_durch = doc.name
			alt.save(ignore_permissions=True)
	return angebot_ui(doc)


@frappe.whitelist(methods=["POST"])
def ueberarbeiten(id, grund=""):
	"""Neue Fassung eines gesendeten (oder abgelehnten) Angebots als Entwurf: gleiche Nummer mit -1, -2 … Das Original
	bleibt unverändert; mit dem Senden der neuen Fassung gilt es als ersetzt. Gibt es schon eine offene Überarbeitung,
	kommt diese zurück."""
	nur_cnc()
	alt = _geladen(id)
	offen = frappe.db.get_value("Angebot", {"vorgaenger": alt.name, "status": "Entwurf"}, "name")
	if offen:
		return angebot_ui(frappe.get_doc("Angebot", offen))
	if alt.status not in ("Gesendet", "Abgelehnt"):
		frappe.throw(_("Überarbeiten lässt sich nur ein gesendetes oder abgelehntes Angebot."))
	if alt.ersetzt_durch:
		frappe.throw(_("Dieses Angebot ist schon durch {0} ersetzt.").format(alt.ersetzt_durch))
	if beauftragt(alt.name):
		frappe.throw(_("Zu diesem Angebot gibt es schon einen Auftrag. Änderungen bitte im Auftrag vornehmen („Auftrag ändern“)."))
	wurzel = alt.ursprung or alt.name
	nr = int(frappe.db.sql("select coalesce(max(fassung), 0) from `tabAngebot` where ursprung = %s", (wurzel,))[0][0] or 0) + 1
	neu = frappe.new_doc("Angebot")
	for f in ("kunde", "anfrage_nr", "projekt", "kontakt_name", "kontakt_email", "gueltig_wochen", "lieferzeit", "material_drucken"):
		neu.set(f, alt.get(f))
	neu.update({"status": "Entwurf", "ursprung": wurzel, "vorgaenger": alt.name, "fassung": nr, "aenderungsgrund": (grund or "").strip()})
	for z in alt.positionen:
		# Bauteile gehören schon dem ursprünglichen Angebot: die Überarbeitung legt keine neuen an und räumt keine ab
		neu.append("positionen", {"kalkulation": z.kalkulation, "bauteil": z.bauteil, "bauteil_neu": 0, "revision": z.revision})
	neu.insert(set_name=f"{wurzel}-{nr}")
	return angebot_ui(neu)


@frappe.whitelist(methods=["POST"])
def grund_setzen(id, grund=""):
	"""Grund der Überarbeitung (intern) auch nach dem Senden ändern."""
	nur_cnc()
	doc = _geladen(id)
	doc.db_set("aenderungsgrund", (grund or "").strip())
	return angebot_ui(doc)


@frappe.whitelist(methods=["POST"])
def projekt_setzen(id, projekt=""):
	"""Projektname (intern) auch nach dem Senden ändern; er steht nicht auf dem Angebot."""
	nur_cnc()
	doc = _geladen(id)
	doc.check_permission("write")
	doc.db_set("projekt", (projekt or "").strip())
	return angebot_ui(doc)


def beauftragt(name):
	"""Gibt es zum Angebot einen Auftrag (nicht storniert)? Dann ist es angenommen: nicht mehr ablehnen, nicht neu senden."""
	if frappe.db.exists("Auftrag", {"angebot": name, "status": ["!=", "Storniert"]}):
		return True
	# auch Aufträge aus einer Bestellung, deren Positionen auf dieses Angebot verweisen
	return bool(frappe.db.sql("""select 1 from `tabAuftragsposition` p join `tabAuftrag` a on a.name = p.parent
		where p.angebot = %s and a.status != 'Storniert' limit 1""", (name,)))


@frappe.whitelist(methods=["POST"])
def ablehnen(id):
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Gesendet":
		frappe.throw(_("Nur ein gesendetes Angebot lässt sich als abgelehnt markieren."))
	if beauftragt(doc.name):
		frappe.throw(_("Zu diesem Angebot gibt es schon einen Auftrag, es lässt sich nicht mehr ablehnen."))
	doc.flags.status_wechsel = True
	doc.status = "Abgelehnt"
	doc.save()
	return angebot_ui(doc)


@frappe.whitelist(methods=["POST"])
def loeschen(id):
	nur_cnc()
	frappe.delete_doc("Angebot", id)
	return {"id": id}


# ----------------------------------------------------------------- PDF
PDF_VORLAGE = "templates/angebot_pdf.html"


def mit_bildern(doc):
	"""Bauteilbilder im PDF? Je Beleg einstellbar (Angebot und AB mit, Lieferschein und Rechnung ohne als Standard)."""
	wert = doc.get("mit_bildern")
	return bool(wert) if wert is not None else doc.doctype in ("Angebot", "Auftrag")


def _bild(url):
	"""Vorschaubild als lokaler Dateipfad für den PDF-Druck (nur Dateien dieser Site)."""
	if not url:
		return ""
	if url.startswith("/private/files/"):
		pfad = frappe.get_site_path(url.lstrip("/"))
	elif url.startswith("/files/"):
		pfad = frappe.get_site_path("public", url.lstrip("/"))
	else:
		return ""
	pfad = os.path.abspath(pfad)
	# nur Dateien unterhalb von files/ bzw. private/files/ (kein „../“ aus einer manipulierten Adresse)
	erlaubt = [os.path.abspath(frappe.get_site_path(*t)) + os.sep for t in (("private", "files"), ("public", "files"))]
	if not any(pfad.startswith(e) for e in erlaubt):
		return ""
	return "file://" + pfad if os.path.exists(pfad) else ""


def _preiszeilen(e, t):
	"""Spalten Menge, Stückpreis und Betrag einer Position: { haupt: [...], kosten: [...], summen: [{menge, betrag}], staffel }.
	Ohne Staffel: Bauteilzeile, die einzelnen Kosten mit „+“ und darunter die Summe der Position (wenn es Kosten gibt).
	Mit Staffel: je Stufe eine Zeile, darunter die Kosten; ohne Summenzeile (sie würde die Staffeln nur wiederholen)."""
	zeilen = e.get("zeilen") or []
	kosten = [{"label": z["label"], "betrag": z["betrag"]} for z in zeilen if z.get("typ") == "kosten"]
	if (t.get("staffel") or {}).get("aktiv"):
		haupt = [{"menge": s["menge"], "einzel": s["stueckpreis"], "betrag": round(s["stueckpreis"] * s["menge"], 2)} for s in e.get("stufen") or []]
		return {"haupt": haupt, "kosten": kosten, "summen": [], "staffel": True}
	teil = next((z for z in zeilen if z.get("typ") == "teil"), None)
	haupt = [{"menge": teil["menge"], "einzel": teil["einzel"], "betrag": teil["betrag"]}] if teil else []
	summen = [{"menge": None, "betrag": e.get("gesamt", 0)}] if kosten and haupt else []
	return {"haupt": haupt, "kosten": kosten, "summen": summen, "staffel": False}


def werkstoff_drucken(teil, angebot=None):
	"""Ob der Werkstoff dieser Position im PDF steht: Schalter an der Position; ältere Angebote hatten ihn
	nur für das ganze Angebot (material_drucken)."""
	if "werkstoffDrucken" in (teil or {}):
		return bool(teil["werkstoffDrucken"])
	return bool(angebot and angebot.get("material_drucken"))


def pdf_erzeugen(doc, zu_haenden=""):
	"""Das Angebot als PDF (PDF/A-3, wie die Rechnung). Datum ist der Versandtag, sonst heute."""
	from cnc_one.api.erechnung import _de, _eur
	from cnc_one.api.firma import firma_ui
	from cnc_one.logic import briefbogen, pdf

	a = angebot_ui(doc)
	for nr, p in enumerate(a["positionen"], 1):
		t = p["teil"]
		p["nr"] = nr
		p["bild"] = _bild(t.get("vorschaubild") or bauteil_api.vorschau(p["bauteilId"])) if mit_bildern(doc) else ""
		zeichnung = f"Zeichnung {t['zeichnungsnr']}" + (f" Rev. {t['revision']}" if t.get("revision") else "") if t.get("zeichnungsnr") else ""
		# Liefertermin je Position bleibt intern (geht in Auftrag und Fertigung); im Angebot steht die Lieferzeit im Kopf
		werkstoff = f"Werkstoff {t['material']}" if werkstoff_drucken(t, doc) and t.get("material") else ""
		p["angaben"] = [x for x in (f"Teilenummer {t['teilenummer']}" if t.get("teilenummer") else "", zeichnung, werkstoff) if x]
		p["info"] = (t.get("infoKunde") or "").strip()
		t.setdefault("staffel", {"aktiv": False})
		p["preis"] = _preiszeilen(p["ergebnis"], t)
	datum = get_datetime(doc.versandt_am).date() if doc.versandt_am else getdate(nowdate())
	kunde = a["kopf"]["kunde"] or {"adresse": [], "kontakt": None}
	firma = firma_ui()
	kontext = {
		"a": a, "f": firma, "kunde": kunde, "zu_haenden": zu_haenden or doc.kontakt_name or (kunde.get("kontakt") or {}).get("name", ""),
		"datum": datum, "gueltig_bis": add_days(datum, 7 * int(doc.gueltig_wochen or 4)), "mwst": round((doc.netto or 0) * 0.19, 2),
		"staffel": any(p["teil"]["staffel"].get("aktiv") for p in a["positionen"]), "de": _de, "eur": _eur,
		"rahmen": briefbogen.rahmen(firma), "posten": briefbogen.posten(a["positionen"]),
	}
	from cnc_one.logic import vorlagen

	html = frappe.render_template(vorlagen.lesen("angebot_pdf.html"), kontext)
	return pdf.pdf_a3(html, titel=f"Angebot {doc.name}", autor=firma.get("firmenname", ""))


def pdf_ablegen(doc, zu_haenden=""):
	"""Legt das PDF am Angebot ab und liefert die Datei. Solange das Angebot Entwurf ist, wird es jedes Mal neu erzeugt;
	ein gesendetes Angebot behält das PDF, das verschickt wurde."""
	name = f"Angebot {doc.name}.pdf"
	vorhanden = frappe.get_all("File", filters={"attached_to_doctype": "Angebot", "attached_to_name": doc.name, "file_name": name}, pluck="name")
	if vorhanden and doc.status != "Entwurf":
		return frappe.get_doc("File", vorhanden[0])
	for f in vorhanden:
		frappe.delete_doc("File", f, ignore_permissions=True)
	return frappe.get_doc({
		"doctype": "File", "file_name": name, "attached_to_doctype": "Angebot", "attached_to_name": doc.name, "is_private": 1,
		"content": pdf_erzeugen(doc, zu_haenden),
	}).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def pdf(id):
	"""PDF des Angebots ansehen: { url, name }."""
	nur_cnc()
	doc = frappe.get_doc("Angebot", id)
	doc.check_permission("read")
	if not doc.kunde:
		frappe.throw(_("Bitte zuerst einen Kunden wählen."))
	f = pdf_ablegen(doc)
	return {"url": f.file_url, "name": f.file_name}
