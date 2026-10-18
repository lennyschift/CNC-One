"""Bauteile (Stammdaten) und ihr Arbeitsplan."""

import frappe
from frappe import _

from cnc_one.api.stamm import arbeitsgang_ui, arbeitsgang_zeile, nur_cnc


def bauteil_ui(d):
	return {
		"id": d.name,
		"kundeId": d.kunde,
		"teilenummer": d.teilenummer,
		"name": d.bezeichnung or "",
		"zeichnungsnr": d.zeichnungsnr or "",
		"material": d.material or "",
		"arbeitsgaenge": [arbeitsgang_ui(r) for r in d.arbeitsplan],
		"seriennummern": bool(d.seriennummern),
		"letzteSeriennummer": d.letzte_seriennummer or 0,
	}


def alle_ui():
	namen = frappe.get_list("Bauteil", pluck="name", order_by="creation asc", limit_page_length=0)
	return [bauteil_ui(frappe.get_doc("Bauteil", n)) for n in namen]


def finden(kunde, teilenummer):
	"""Name des Bauteils eines Kunden zu einer Teilenummer, ohne Rücksicht auf Groß- und Kleinschreibung."""
	t = (teilenummer or "").strip().lower()
	if not kunde or not t:
		return None
	r = frappe.db.sql("select name from `tabBauteil` where kunde = %s and lower(teilenummer) = %s", (kunde, t))
	return r[0][0] if r else None


def sicherstellen(kunde, teilenummer, name="", zeichnungsnr="", material=""):
	"""Legt das Bauteil an, wenn es fehlt, und füllt leere Angaben auf. Liefert das Dokument oder None."""
	n = finden(kunde, teilenummer)
	if not kunde or not (teilenummer or "").strip():
		return None
	if n:
		doc = frappe.get_doc("Bauteil", n)
		geaendert = False
		for feld, wert in (("bezeichnung", name), ("zeichnungsnr", zeichnungsnr)):
			if wert and not doc.get(feld):
				doc.set(feld, wert)
				geaendert = True
		if material and not doc.material and frappe.db.exists("Material", material):
			doc.material = material
			geaendert = True
		if geaendert:
			doc.save()
		return doc
	doc = frappe.new_doc("Bauteil")
	doc.kunde = kunde
	doc.teilenummer = teilenummer.strip()
	doc.bezeichnung = name or ""
	doc.zeichnungsnr = zeichnungsnr or ""
	doc.material = material if material and frappe.db.exists("Material", material) else None
	doc.insert()
	return doc


def _material(name):
	return name if name and frappe.db.exists("Material", name) else None


def _angaben_setzen(doc, teil):
	"""Bezeichnung, Zeichnung, Werkstoff und Seriennummern-Kennzeichen aus der Workbench ins Bauteil übernehmen."""
	doc.bezeichnung = (teil.get("name") or "").strip()
	doc.zeichnungsnr = (teil.get("zeichnungsnr") or "").strip()
	doc.material = _material(teil.get("material"))
	doc.seriennummern = 1 if teil.get("seriennummern") else 0


def fuer_position(kunde, teil, alt=None):
	"""Das Bauteil zu einem Workbench-Bauteil: wiederfinden oder neu anlegen, nie doppelt.

	`alt` ist (Bauteil, neu) dieser Position aus dem letzten Speichern. Ein Bauteil, das dieses Angebot neu angelegt hat,
	folgt den Änderungen in der Workbench (auch einer geänderten Teilenummer). Ein Bestandsbauteil bleibt unverändert.
	Liefert (Dokument oder None, neu).
	"""
	nr = (teil.get("teilenummer") or "").strip()
	if not kunde or not nr:
		return None, False
	alt_name, alt_neu = alt or (None, False)
	vorhanden = finden(kunde, nr)
	if vorhanden:
		doc = frappe.get_doc("Bauteil", vorhanden)
		neu = bool(alt_neu and vorhanden == alt_name)
		if neu:
			_angaben_setzen(doc, teil)
			doc.save()
		return doc, neu
	if alt_neu and alt_name and frappe.db.get_value("Bauteil", alt_name, "kunde") == kunde and not _anderweitig_verwendet(alt_name):
		doc = frappe.get_doc("Bauteil", alt_name)
		doc.teilenummer = nr
		_angaben_setzen(doc, teil)
		doc.save()
		return doc, True
	doc = frappe.new_doc("Bauteil")
	doc.kunde = kunde
	doc.teilenummer = nr
	_angaben_setzen(doc, teil)
	doc.insert()
	return doc, True


def _anderweitig_verwendet(name):
	"""Wird das Bauteil außerhalb des eben bearbeiteten Angebots schon gebraucht (Aufträge, Fertigung, Anfragen, andere Angebote)?"""
	for dt in ("Auftragsposition", "Fertigungsbauteil", "Anfrageposition"):
		if frappe.db.exists(dt, {"bauteil": name}):
			return True
	return frappe.db.count("Angebotsposition", {"bauteil": name}) > 1


def aufraeumen(name):
	"""Löscht ein von einem Angebot neu angelegtes Bauteil wieder, wenn es nirgends gebraucht wird."""
	try:
		frappe.delete_doc("Bauteil", name)
	except frappe.LinkExistsError:
		frappe.clear_messages()


def plan_setzen(kunde, teilenummer, arbeitsgaenge, name="", zeichnungsnr="", material=""):
	"""Setzt den Arbeitsplan am Bauteil des Kunden. Fehlt das Bauteil, wird es angelegt. Ohne Kunde oder Teilenummer: None."""
	doc = sicherstellen(kunde, teilenummer, name, zeichnungsnr, material)
	if not doc:
		return None
	doc.set("arbeitsplan", [])
	for a in arbeitsgaenge or []:
		doc.append("arbeitsplan", arbeitsgang_zeile(a))
	doc.save()
	return doc


@frappe.whitelist(methods=["POST"])
def plan_speichern(kunde, teilenummer, arbeitsgaenge, name="", zeichnungsnr="", material=""):
	"""Speichert den Arbeitsplan am Bauteil. Fehlt das Bauteil, wird es angelegt."""
	nur_cnc()
	if isinstance(arbeitsgaenge, str):
		arbeitsgaenge = frappe.parse_json(arbeitsgaenge)
	doc = plan_setzen(kunde, teilenummer, arbeitsgaenge, name, zeichnungsnr, material)
	if not doc:
		frappe.throw(_("Für den Arbeitsplan braucht das Bauteil einen Kunden und eine Teilenummer."))
	return bauteil_ui(doc)
