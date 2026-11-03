"""Lieferschein und Mahnung als PDF (PDF/A-3, Stil der Rechnung), abgelegt am Beleg.

Solange der Beleg offen ist (Lieferschein bereit, Mahnung angelegt), wird das PDF bei jedem Abruf neu erzeugt. Mit dem
Abschluss (geliefert bzw. versendet) wird es erzeugt und bleibt danach so, wie es zu diesem Zeitpunkt war.
"""

import frappe
from frappe import _
from frappe.utils import getdate

from cnc_one.api.angebot import _bild
from cnc_one.api.bauteil import vorschau
from cnc_one.api.firma import firma_ui
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import pdf
from cnc_one.logic.serien import formatiert


def _vorlage(name, kontext):
	from cnc_one.api.erechnung import _de, _eur

	with open(frappe.get_app_path("cnc_one", "templates", "beleg_basis.css"), encoding="utf-8") as f:
		basis = f.read()
	with open(frappe.get_app_path("cnc_one", "templates", name), encoding="utf-8") as f:
		return frappe.render_template(f.read(), {**kontext, "basis": basis, "de": _de, "eur": _eur})


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
		p["bild"] = _bild(vorschau(z.bauteil))
		p["angaben"] = " · ".join(x for x in (
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
