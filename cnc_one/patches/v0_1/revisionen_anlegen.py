"""Revisionshistorie am Bauteil: die bisherige Revision mit ihren Dateien wird die erste Zeile. Angebote, Aufträge und
Fertigung merken sich die Revision der Position (bisher gab es je Bauteil nur eine)."""

import json

import frappe


def execute():
	for b in frappe.get_all("Bauteil", fields=["name", "revision", "zeichnung", "step_datei", "vorschaubild", "modified"]):
		if frappe.db.exists("Bauteil Revision", {"parent": b.name, "parenttype": "Bauteil"}):
			continue
		if not (b.revision or b.zeichnung or b.step_datei or b.vorschaubild):
			continue
		frappe.get_doc({
			"doctype": "Bauteil Revision", "parent": b.name, "parenttype": "Bauteil", "parentfield": "revisionen", "idx": 1,
			"revision": b.revision or "", "zeichnung": b.zeichnung, "step_datei": b.step_datei, "vorschaubild": b.vorschaubild,
			"datum": b.modified,
		}).db_insert()

	aktuell = dict(frappe.get_all("Bauteil", fields=["name", "revision"], as_list=True))
	for p in frappe.get_all("Angebotsposition", filters={"revision": ["is", "not set"]}, fields=["name", "kalkulation", "bauteil"]):
		try:
			rev = (json.loads(p.kalkulation or "{}").get("revision") or "").strip()
		except ValueError:
			rev = ""
		rev = rev or aktuell.get(p.bauteil) or ""
		if rev:
			frappe.db.set_value("Angebotsposition", p.name, "revision", rev, update_modified=False)

	for p in frappe.get_all("Auftragsposition", filters={"revision": ["is", "not set"]}, fields=["name", "parent", "angebot_position_key", "bauteil"]):
		angebot = frappe.db.get_value("Auftrag", p.parent, "angebot")
		rev = frappe.db.get_value("Angebotsposition", {"parent": angebot, "position_key": p.angebot_position_key}, "revision") if angebot else None
		rev = rev or aktuell.get(p.bauteil) or ""
		if rev:
			frappe.db.set_value("Auftragsposition", p.name, "revision", rev, update_modified=False)

	for f in frappe.get_all("Fertigungsbauteil", filters={"revision": ["is", "not set"]}, fields=["name", "auftrag", "auftragsposition_key", "bauteil"]):
		rev = frappe.db.get_value("Auftragsposition", {"parent": f.auftrag, "position_key": f.auftragsposition_key}, "revision")
		rev = rev or aktuell.get(f.bauteil) or ""
		if rev:
			frappe.db.set_value("Fertigungsbauteil", f.name, "revision", rev, update_modified=False)
