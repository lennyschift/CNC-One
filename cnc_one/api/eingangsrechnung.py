"""Eingangsrechnungen (Rechnungen der Lieferanten): Liste, ansehen, Angaben ergänzen, prüfen und als bezahlt markieren.

Sie entstehen aus dem Posteingang (E-Rechnungen werden beim Abholen von selbst angelegt, PDF-Rechnungen mit einem Klick)
oder aus einer hochgeladenen Datei. Die Zahlung selbst und DATEV folgen, sobald das mit dem Steuerberater geklärt ist.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import eingangsrechnung as logik
from cnc_one.logic.daten import datum, iso
from cnc_one.logic.kalkulation import num, r2

STATUS = ("Neu", "Geprüft", "Bezahlt", "Abgelehnt")
FELDER = {
	"lieferantId": "lieferant", "lieferantName": "lieferant_name", "lieferantUstId": "lieferant_ust_id", "rechnungsnr": "rechnungsnr",
	"rechnungsdatum": "rechnungsdatum", "faelligAm": "faellig_am", "art": "art", "netto": "netto", "steuer": "steuer", "brutto": "brutto",
	"waehrung": "waehrung", "iban": "iban", "bestellreferenz": "bestellreferenz", "bemerkung": "bemerkung",
}


def er_ui(d, kurz=False):
	out = {
		"id": d.name, "status": d.status, "format": d.format or "", "lieferantId": d.lieferant or "", "lieferantName": d.lieferant_name or "",
		"lieferantUstId": d.lieferant_ust_id or "", "rechnungsnr": d.rechnungsnr or "", "rechnungsdatum": datum(d.rechnungsdatum),
		"faelligAm": datum(d.faellig_am), "art": d.art or "Rechnung", "netto": d.netto or 0, "steuer": d.steuer or 0, "brutto": d.brutto or 0,
		"waehrung": d.waehrung or "EUR", "iban": d.iban or "", "bestellreferenz": d.bestellreferenz or "", "mailId": d.mail or "",
		"pdf": d.pdf_datei or "", "xml": d.xml_datei or "", "hinweise": [x for x in (d.pruefhinweise or "").splitlines() if x.strip()],
		"bemerkung": d.bemerkung or "", "geprueftVon": d.geprueft_von or "", "geprueftAm": iso(d.geprueft_am) if d.geprueft_am else "",
		"erstellt": iso(d.creation),
	}
	if not kurz:
		out["positionen"] = [
			{"bezeichnung": p.bezeichnung or "", "menge": p.menge or 0, "einheit": p.einheit or "", "einzelpreis": p.einzelpreis or 0, "betrag": p.betrag or 0, "steuersatz": p.steuersatz or 0}
			for p in d.positionen
		]
	return out


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	namen = frappe.get_list("Eingangsrechnung", pluck="name", order_by="creation desc", limit_page_length=1000)
	return [er_ui(frappe.get_doc("Eingangsrechnung", n), kurz=True) for n in namen]


@frappe.whitelist(methods=["POST"])
def detail(id):
	nur_cnc()
	d = frappe.get_doc("Eingangsrechnung", id)
	d.check_permission("read")
	return er_ui(d)


def _geladen(id):
	d = frappe.get_doc("Eingangsrechnung", id)
	d.check_permission("write")
	return d


@frappe.whitelist(methods=["POST"])
def speichern(id, daten):
	"""Angaben ergänzen oder korrigieren (z. B. bei PDF-Rechnungen ohne XML). Nach dem Prüfen nur noch die Bemerkung."""
	nur_cnc()
	daten = frappe.parse_json(daten) if isinstance(daten, str) else (daten or {})
	d = _geladen(id)
	if d.status != "Neu" and set(daten) - {"bemerkung"}:
		frappe.throw(_("Eine geprüfte Rechnung lässt sich nicht mehr ändern; bitte zuerst wieder öffnen."))
	for ui, feld in FELDER.items():
		if ui not in daten:
			continue
		wert = daten[ui]
		if feld in ("netto", "steuer", "brutto"):
			wert = r2(num(wert))
		elif feld == "lieferant":
			wert = wert or None
			if wert and not frappe.db.exists("Lieferant", wert):
				frappe.throw(_("Den Lieferanten {0} gibt es nicht.").format(wert))
		elif feld in ("rechnungsdatum", "faellig_am"):
			wert = wert or None
		elif isinstance(wert, str):
			wert = wert.strip()
		d.set(feld, wert)
	if d.lieferant and not d.lieferant_name:
		d.lieferant_name = frappe.db.get_value("Lieferant", d.lieferant, "lieferantenname")
	if "positionen" in daten:
		d.set("positionen", [])
		for p in daten["positionen"] or []:
			if not (p.get("bezeichnung") or "").strip() and not num(p.get("betrag")):
				continue
			d.append("positionen", {
				"bezeichnung": (p.get("bezeichnung") or "").strip(), "menge": num(p.get("menge")), "einheit": (p.get("einheit") or "").strip(),
				"einzelpreis": r2(num(p.get("einzelpreis"))), "betrag": r2(num(p.get("betrag"))), "steuersatz": num(p.get("steuersatz")),
			})
	if d.rechnungsnr and logik.doppelt(d.lieferant, d.lieferant_name, d.rechnungsnr) not in (None, d.name):
		frappe.throw(_("Die Rechnung {0} dieses Lieferanten gibt es schon.").format(d.rechnungsnr))
	d.save()
	return er_ui(d)


@frappe.whitelist(methods=["POST"])
def status_setzen(id, status):
	"""Geprüft (sachlich und rechnerisch richtig), Bezahlt, Abgelehnt oder wieder Neu (öffnen)."""
	nur_cnc()
	if status not in STATUS:
		frappe.throw(_("Den Status {0} gibt es nicht.").format(status))
	d = _geladen(id)
	if status in ("Geprüft", "Bezahlt"):
		fehlt = [n for n, w in ((_("Lieferant"), d.lieferant), (_("Rechnungsnummer"), d.rechnungsnr), (_("Rechnungsdatum"), d.rechnungsdatum), (_("Bruttobetrag"), d.brutto)) if not w]
		if fehlt:
			frappe.throw(_("Bitte zuerst ergänzen: {0}.").format(", ".join(fehlt)))
	if status == "Geprüft" and d.status == "Neu":
		d.geprueft_von = frappe.session.user
		d.geprueft_am = now_datetime()
	if status == "Neu":
		d.geprueft_von, d.geprueft_am = "", None
	d.status = status
	d.save()
	return er_ui(d)


@frappe.whitelist(methods=["POST"])
def aus_datei(file_url, mail=""):
	"""Eingangsrechnung aus einer abgelegten Datei (Mail-Anhang oder Upload): E-Rechnung wird gelesen, ein PDF ohne XML
	wird als PDF-Rechnung zum Ausfüllen angelegt. Liefert { rechnung, hinweis }."""
	nur_cnc()
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		frappe.throw(_("Die Datei gibt es nicht."))
	f = frappe.get_doc("File", name)
	if f.attached_to_doctype and f.attached_to_name:
		frappe.get_doc(f.attached_to_doctype, f.attached_to_name).check_permission("read")
	inhalt = f.get_content()
	if isinstance(inhalt, str):
		inhalt = inhalt.encode("utf-8")
	fmt, xml = logik.erkennen(f.file_name, inhalt)
	if not fmt:
		if not (f.file_name or "").lower().endswith(".pdf"):
			frappe.throw(_("Nur PDF- oder XML-Rechnungen lassen sich übernehmen."))
		fmt = "PDF"
	absender = frappe.db.get_value("Mail Anfrage", mail, "von_email") if mail else ""
	doc, hinweis = logik.anlegen(fmt, xml, pdf_url=file_url if fmt in ("ZUGFeRD", "PDF") else "", xml_url=file_url if fmt == "XRechnung" else "", mail=mail or None, absender=absender or "")
	if not doc:
		frappe.throw(hinweis)
	if mail and frappe.db.exists("Mail Anfrage", mail):
		frappe.db.set_value("Mail Anfrage", mail, "kategorie", "Rechnung")
		if not doc.lieferant and frappe.db.get_value("Mail Anfrage", mail, "lieferant"):
			doc.db_set("lieferant", frappe.db.get_value("Mail Anfrage", mail, "lieferant"))
	return {"rechnung": er_ui(frappe.get_doc("Eingangsrechnung", doc.name)), "hinweis": hinweis}


@frappe.whitelist(methods=["POST"])
def loeschen(id):
	"""Nur neue (ungeprüfte) Eingangsrechnungen, z. B. eine versehentlich übernommene Datei. Die Mail bleibt."""
	nur_cnc()
	d = _geladen(id)
	if d.status != "Neu":
		frappe.throw(_("Nur neue, ungeprüfte Rechnungen lassen sich löschen."))
	frappe.flags.archivsperre_aus = True
	try:
		frappe.delete_doc("Eingangsrechnung", d.name)
	finally:
		frappe.flags.archivsperre_aus = False
	return {"id": id}
