"""Lieferschein und Mahnung als PDF (PDF/A-3, Stil der Rechnung), abgelegt am Beleg.

Solange der Beleg offen ist (Lieferschein bereit, Mahnung angelegt), wird das PDF bei jedem Abruf neu erzeugt. Mit dem
Abschluss (geliefert bzw. versendet) wird es erzeugt und bleibt danach so, wie es zu diesem Zeitpunkt war.
"""

import frappe
from frappe import _
from frappe.utils import getdate

from cnc_one.api.angebot import _bild, mit_bildern
from cnc_one.api.bauteil import vorschau
from cnc_one.api.firma import firma_ui
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import briefbogen, pdf
from cnc_one.logic.serien import formatiert


def _vorlage(name, kontext):
	from cnc_one.api.erechnung import _de, _eur

	from cnc_one.logic import vorlagen

	return frappe.render_template(vorlagen.lesen(name), {**kontext, "de": _de, "eur": _eur, "rahmen": briefbogen.rahmen(kontext["f"])})


def _ablegen(doctype, doc, dateiname, offen, erzeugen, neu=False):
	"""PDF am Beleg ablegen und liefern. Offen (oder `neu` beim Abschließen): neu erzeugt; abgeschlossen: das vorhandene bleibt."""
	vorhanden = frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": doc.name, "file_name": dateiname}, pluck="name")
	if vorhanden and not offen and not neu:
		return frappe.get_doc("File", vorhanden[0])
	# beim Abschluss ersetzt das endgültige PDF das offene (die Löschsperre gilt erst für das endgültige)
	frappe.flags.archivsperre_aus = True
	try:
		for f in vorhanden:
			frappe.delete_doc("File", f, ignore_permissions=True)
	finally:
		frappe.flags.archivsperre_aus = False
	return frappe.get_doc({
		"doctype": "File", "file_name": dateiname, "attached_to_doctype": doctype, "attached_to_name": doc.name, "is_private": 1, "content": erzeugen(),
	}).insert(ignore_permissions=True)


# ----------------------------------------------------------------- Lieferschein
def _serien(p):
	if not p.serien_von:
		return ""
	von, bis = formatiert(p.serien_von, p.serien_stellen), formatiert(p.serien_bis, p.serien_stellen)
	return von if von == bis else f"{von} – {bis}"


def lieferschein_pdf_erzeugen(doc):
	from cnc_one.api.lieferschein import lieferschein_ui

	l = lieferschein_ui(doc, {})
	for p, z in zip(l["positionen"], doc.positionen):
		t = p["teil"]
		p["bild"] = _bild(vorschau(z.bauteil)) if mit_bildern(doc) else ""
		bestellpos = frappe.db.get_value("Auftragsposition", {"parent": z.auftrag, "position_key": z.auftragsposition_key}, "bestellposition") if z.get("auftrag") and z.get("auftragsposition_key") else ""
		p["angaben"] = " · ".join(x for x in (
			f"Ihre Pos. {bestellpos}" if bestellpos else "",
			f"Teilenummer {t['teilenummer']}" if t.get("teilenummer") else "", f"Zeichnung {t['zeichnungsnr']}" if t.get("zeichnungsnr") else "",
		) if x)
		p["serien"] = _serien(z)
	auftraege = ", ".join(dict.fromkeys(z.auftrag for z in doc.positionen if z.auftrag))
	firma = firma_ui()
	html = _vorlage("lieferschein_pdf.html", {
		"l": l, "f": firma, "auftraege": auftraege, "datum": doc.geliefert_am or doc.lieferdatum or getdate(doc.creation),
		"stempel": "STORNIERT" if doc.status == "Storniert" else "",
	})
	return pdf.pdf_a3(html, titel=f"Lieferschein {doc.name}", autor=firma.get("firmenname", ""))


def lieferschein_pdf_ablegen(doc, neu=False):
	return _ablegen("Lieferschein", doc, f"Lieferschein {doc.name}.pdf", doc.status == "Bereit", lambda: lieferschein_pdf_erzeugen(doc), neu)


# ----------------------------------------------------------------- Mahnung
def mahnung_pdf_erzeugen(doc):
	from cnc_one.api.mahnung import mahnung_ui

	m = mahnung_ui(doc)
	html = _vorlage("mahnung_pdf.html", {"m": m, "f": m["firma"], "stempel": "ZURÜCKGEZOGEN" if doc.status == "Zurückgezogen" else ""})
	return pdf.pdf_a3(html, titel=f"{doc.stufe} {doc.name}", autor=m["firma"].get("firmenname", ""))


def mahnung_pdf_ablegen(doc, neu=False):
	return _ablegen("Mahnung", doc, f"{doc.stufe} {doc.name}.pdf", doc.status == "Angelegt", lambda: mahnung_pdf_erzeugen(doc), neu)


# ----------------------------------------------------------------- Auftragsbestätigung
def _angebotsangaben(doc):
	"""{ (angebot, angebot_position_key): kalkulation } der Angebote des Auftrags, für die Kundeninfo; dazu die Angebote
	(Werkstoff drucken). Positionen aus einer Bestellung können aus verschiedenen Angeboten stammen."""
	import json

	kalk, angebote = {}, {}
	for name in dict.fromkeys(x for x in [doc.angebot] + [z.angebot for z in doc.positionen] if x):
		ang = frappe.get_doc("Angebot", name)
		angebote[name] = ang
		for z in ang.positionen:
			try:
				kalk[(name, z.position_key)] = json.loads(z.kalkulation or "{}") or {}
			except (TypeError, ValueError):
				kalk[(name, z.position_key)] = {}
	return kalk, angebote


def ab_pdf_erzeugen(doc, zu_haenden=""):
	"""Die Auftragsbestätigung als PDF: Positionen wie im Angebot (Bild, Bauteil, Menge, Stückpreis, Betrag, Kosten,
	Summe der Position), dazu Bestellnummer des Kunden und der Liefertermin je Position."""
	from cnc_one.api.auftrag import auftrag_ui
	from cnc_one.api.erechnung import _de

	a = auftrag_ui(doc)
	from cnc_one.api.angebot import werkstoff_drucken

	kalk, angebote = _angebotsangaben(doc)
	for nr, (p, z) in enumerate(zip(a["positionen"], doc.positionen), 1):
		t = p["teil"]
		p["nr"] = nr
		p["bild"] = _bild(t.get("vorschaubild") or vorschau(z.bauteil)) if mit_bildern(doc) else ""
		zeichnung = f"Zeichnung {t['zeichnungsnr']}" + (f" Rev. {z.revision}" if z.revision else "") if t.get("zeichnungsnr") else ""
		ang_name = z.angebot or doc.angebot
		k = kalk.get((ang_name, z.angebot_position_key))
		p["angaben"] = [x for x in (
			f"Ihre Pos. {z.bestellposition}" if z.bestellposition else "",
			f"Teilenummer {t['teilenummer']}" if t.get("teilenummer") else "", zeichnung,
			f"Werkstoff {t['material']}" if werkstoff_drucken(k, angebote.get(ang_name)) and t.get("material") else "",
			f"Liefertermin {_de(z.liefertermin)}" if z.liefertermin else "",
			f"Seriennummern {_serien(z)}" if z.serien_von else "",
		) if x]
		p["info"] = ((k or {}).get("infoKunde") or "").strip()
		if z.menge_urspruenglich and not z.entfallen and z.menge_urspruenglich != z.menge:
			p["angaben"].append(f"Menge geändert, bisher {z.menge_urspruenglich} Stk")
		if z.entfallen:
			p["entfallen"] = True
			p["angaben"] = [x for x in p["angaben"] if not x.startswith(("Liefertermin", "Seriennummern"))]
			p["preis"] = {"haupt": [None], "kosten": [], "summen": [], "staffel": False}
			continue
		einzel = p["einzelpreis"] or 0
		haupt = [{"menge": p["menge"], "einzel": einzel, "betrag": round(einzel * (p["menge"] or 0), 2)}]
		p["preis"] = {"haupt": haupt, "kosten": p["kosten"], "summen": [{"menge": None, "betrag": p["summe"]}] if p["kosten"] else [], "staffel": False}
	kunde = a["kunde"] or {"adresse": []}
	firma = firma_ui()
	html = _vorlage("auftragsbestaetigung_pdf.html", {
		"a": a, "f": firma, "kunde": kunde, "zu_haenden": zu_haenden or doc.kontakt_name or "",
		"aenderung": doc.aenderung_nr or 0, "aenderungen": ab_aenderungen(doc),
		"datum": getdate(doc.ab_gesendet_am) if doc.ab_gesendet_am else getdate(), "mwst": round((doc.netto or 0) * 0.19, 2),
		"posten": briefbogen.posten(a["positionen"]), "stempel": "STORNIERT" if doc.status == "Storniert" else "",
	})
	return pdf.pdf_a3(html, titel=f"Auftragsbestätigung {doc.name}", autor=firma.get("firmenname", ""))


def ab_aenderungen(doc):
	"""Änderungen, die diese Auftragsbestätigung bestätigt: alle seit der zuletzt gesendeten AB (ist die aktuelle schon
	gesendet, die letzte). Je Änderung { nr, datum, zeilen } ohne interne Hinweise (Fertigung)."""
	nr = doc.aenderung_nr or 0
	if not nr:
		return []
	ab = doc.ab_aenderung or 0
	seit = ab if ab < nr else nr - 1
	return [
		{"nr": z.nr, "datum": z.datum, "zeilen": [x for x in (z.details or "").splitlines() if x.strip() and not x.startswith("Fertigung:")]}
		for z in doc.aenderungen if z.nr > seit
	]


def ab_dateiname(doc):
	"""Jede Änderung bekommt ihre eigene AB-Datei; die früheren bleiben am Auftrag."""
	return f"Auftragsbestätigung {doc.name}" + (f" Änderung {doc.aenderung_nr}" if doc.aenderung_nr else "") + ".pdf"


def ab_pdf_ablegen(doc):
	"""Beim Senden: das verschickte PDF am Auftrag ablegen (ein erneutes Senden derselben Änderung ersetzt es)."""
	return _ablegen("Auftrag", doc, ab_dateiname(doc), True, lambda: ab_pdf_erzeugen(doc))


# ----------------------------------------------------------------- Bauteilbilder ein/aus
BILDER = ("Angebot", "Auftrag", "Lieferschein", "Rechnung")


def _bilder_stand(doc):
	festgeschrieben = doc.doctype == "Rechnung" and doc.status != "Entwurf"
	abgelegt = (doc.doctype == "Angebot" and doc.status != "Entwurf") or (doc.doctype == "Lieferschein" and doc.status != "Bereit")
	return {
		"an": mit_bildern(doc), "aenderbar": not festgeschrieben, "abgelegt": abgelegt,
		"hinweis": "Festgeschriebene Rechnung: das PDF bleibt, wie es erzeugt wurde." if festgeschrieben else "",
	}


@frappe.whitelist(methods=["POST"])
def bilder(doctype, id, an=None, neu_erzeugen=0):
	"""Bauteilbilder im PDF eines Belegs: ohne `an` der Stand { an, aenderbar, hinweis }, mit `an` (0/1) umschalten. Ein schon
	abgelegtes PDF (gesendetes Angebot, gelieferter Lieferschein) wird dabei neu erzeugt — Inhalt und Datum bleiben, nur die
	Bilder kommen dazu oder fallen weg. Festgeschriebene Rechnungen bleiben unverändert (GoBD)."""
	nur_cnc()
	if doctype not in BILDER:
		frappe.throw(_("Für {0} gibt es keine Bauteilbilder.").format(doctype))
	doc = frappe.get_doc(doctype, id)
	doc.check_permission("read")
	neu = frappe.utils.cint(neu_erzeugen)
	if (an is None or an == "") and not neu:
		return _bilder_stand(doc)
	doc.check_permission("write")
	if not _bilder_stand(doc)["aenderbar"]:
		frappe.throw(_("Die Rechnung ist festgeschrieben, ihr PDF bleibt unverändert."))
	if an is not None and an != "":
		doc.db_set("mit_bildern", 1 if frappe.utils.cint(an) else 0, update_modified=False)
	if doctype == "Angebot" and doc.status != "Entwurf" and doc.kunde:
		from cnc_one.api.angebot import pdf_erzeugen

		_ablegen("Angebot", doc, f"Angebot {doc.name}.pdf", False, lambda: pdf_erzeugen(doc), neu=True)
	elif doctype == "Lieferschein" and doc.status != "Bereit":
		lieferschein_pdf_ablegen(doc, neu=True)
	return _bilder_stand(doc)


# ----------------------------------------------------------------- Abruf
@frappe.whitelist(methods=["POST"])
def pdf_holen(doctype, id):
	"""PDF eines Lieferscheins oder einer Mahnung ansehen: { url, name }."""
	nur_cnc()
	if doctype not in ("Lieferschein", "Mahnung"):
		frappe.throw(_("Für {0} gibt es hier kein PDF.").format(doctype))
	doc = frappe.get_doc(doctype, id)
	doc.check_permission("read")
	f = lieferschein_pdf_ablegen(doc) if doctype == "Lieferschein" else mahnung_pdf_ablegen(doc)
	return {"url": f.file_url, "name": f.file_name}


# ----------------------------------------------------------------- Ansehen und Drucken in der App
def _inhalt(datei):
	with open(datei.get_full_path(), "rb") as fh:
		return datei.file_name, fh.read()


def _angebot(doc):
	from cnc_one.api.angebot import pdf_ablegen, pdf_erzeugen

	if doc.status != "Entwurf":
		return _inhalt(pdf_ablegen(doc))
	if not doc.kunde:
		frappe.throw(_("Bitte zuerst einen Kunden wählen."))
	return f"Angebot {doc.name}.pdf", pdf_erzeugen(doc)


def _rechnung(doc):
	from cnc_one.api import erechnung

	if doc.status == "Entwurf":
		firma = erechnung._firma(doc)
		return "Rechnung Entwurf.pdf", pdf.pdf_a3(erechnung._html(doc, firma), titel="Rechnung (Entwurf)", autor=firma.get("firmenname", ""))
	name = erechnung._datei_suchen(doc)
	if not name:
		erechnung.erzeugen(doc)
		name = erechnung._datei_suchen(doc)
	return _inhalt(frappe.get_doc("File", name))


def _lieferschein(doc):
	if doc.status == "Bereit":
		return f"Lieferschein {doc.name}.pdf", lieferschein_pdf_erzeugen(doc)
	return _inhalt(lieferschein_pdf_ablegen(doc))


def _mahnung(doc):
	if doc.status == "Angelegt":
		return f"{doc.stufe} {doc.name}.pdf", mahnung_pdf_erzeugen(doc)
	return _inhalt(mahnung_pdf_ablegen(doc))


def _auftrag(doc):
	return ab_dateiname(doc), ab_pdf_erzeugen(doc)


ANSEHEN = {"Auftrag": _auftrag, "Angebot": _angebot, "Rechnung": _rechnung, "Lieferschein": _lieferschein, "Mahnung": _mahnung}


def ansehen_pdf(doctype, id):
	"""(Dateiname, PDF) eines Belegs, so wie er verschickt wird. Offene Belege (Angebotsentwurf, Rechnungsentwurf mit
	Stempel, bereiter Lieferschein, angelegte Mahnung) werden frisch erzeugt und nicht abgelegt; abgelegt wird erst beim
	Senden, Festschreiben, Liefern oder Versenden. Abgeschlossene Belege zeigen ihr abgelegtes PDF."""
	if doctype not in ANSEHEN:
		frappe.throw(_("Für {0} gibt es hier kein PDF.").format(doctype))
	doc = frappe.get_doc(doctype, id)
	doc.check_permission("read")
	return ANSEHEN[doctype](doc)


@frappe.whitelist(methods=["GET"])
def ansehen(doctype, id, v=None):
	"""Das PDF zum Ansehen und Drucken in der App (inline). `v` ändert nur die Adresse, damit nichts Altes aus dem Zwischenspeicher kommt."""
	nur_cnc()
	name, inhalt = ansehen_pdf(doctype, id)
	frappe.local.response.filename = name
	frappe.local.response.filecontent = inhalt
	frappe.local.response.type = "pdf"
