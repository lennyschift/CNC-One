"""Angebote. Die Workbench arbeitet auf einem gespeicherten Angebot im Status Entwurf."""

import json
import os

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, now_datetime, nowdate

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
			"kundeName": d.kunde_name or "",
			"kunde": kunde_ui(kunde) if kunde else None,
		},
		"positionen": [
			{
				"key": z.position_key, "teil": _json(z.kalkulation), "ergebnis": _json(z.ergebnis),
				"bauteilId": z.bauteil or "", "herkunft": ("neu" if z.bauteil_neu else "bestand") if z.bauteil else "",
				"seriennummern": bool(z.bauteil and frappe.db.get_value("Bauteil", z.bauteil, "seriennummern")),
				**_revisionen(z.bauteil),
			}
			for z in d.positionen
		],
		"netto": d.netto or 0,
		"entwurfId": "",
		"mailAnfrage": mail_api.zu_angebot(d.name),
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
			rev = bauteil_api.revision_uebernehmen(z.bauteil, json.loads(z.kalkulation or "{}"), doc.name)
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
	return angebot_ui(doc)


def beauftragt(name):
	"""Gibt es zum Angebot einen Auftrag (nicht storniert)? Dann ist es angenommen: nicht mehr ablehnen, nicht neu senden."""
	return bool(frappe.db.exists("Auftrag", {"angebot": name, "status": ["!=", "Storniert"]}))


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
	return "file://" + pfad if os.path.exists(pfad) else ""


def pdf_erzeugen(doc, zu_haenden=""):
	"""Das Angebot als PDF (PDF/A-3, wie die Rechnung). Datum ist der Versandtag, sonst heute."""
	from cnc_one.api.erechnung import _de, _eur
	from cnc_one.api.firma import firma_ui
	from cnc_one.logic import pdf

	a = angebot_ui(doc)
	for p in a["positionen"]:
		t = p["teil"]
		p["bild"] = _bild(t.get("vorschaubild") or bauteil_api.vorschau(p["bauteilId"]))
		zeichnung = f"Zeichnung {t['zeichnungsnr']}" + (f" Rev. {t['revision']}" if t.get("revision") else "") if t.get("zeichnungsnr") else ""
		termin = f"Liefertermin {_de(t['liefertermin'])}" if t.get("liefertermin") else ""
		p["angaben"] = " · ".join(x for x in (f"Teilenummer {t['teilenummer']}" if t.get("teilenummer") else "", zeichnung, t.get("material") or "", termin) if x)
		t.setdefault("staffel", {"aktiv": False})
	datum = get_datetime(doc.versandt_am).date() if doc.versandt_am else getdate(nowdate())
	kunde = a["kopf"]["kunde"] or {"adresse": [], "kontakt": None}
	firma = firma_ui()
	kontext = {
		"a": a, "f": firma, "kunde": kunde, "zu_haenden": zu_haenden or (kunde.get("kontakt") or {}).get("name", ""),
		"datum": datum, "gueltig_bis": add_days(datum, 7 * int(doc.gueltig_wochen or 4)), "mwst": round((doc.netto or 0) * 0.19, 2),
		"staffel": any(p["teil"]["staffel"].get("aktiv") for p in a["positionen"]), "de": _de, "eur": _eur,
	}
	with open(frappe.get_app_path("cnc_one", PDF_VORLAGE), encoding="utf-8") as f:
		html = frappe.render_template(f.read(), kontext)
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
