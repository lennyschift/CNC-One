"""Dokumentprotokoll: Dateien von vor seiner Einführung bekommen ihr „Abgelegt“ mit Zeitpunkt und Benutzer der Datei."""

import frappe

from cnc_one.logic import archiv, dokumente


def execute():
	for f in frappe.get_all("File", filters={"is_folder": 0}, fields=["*"], order_by="creation"):
		if not archiv._relevant(f):
			continue
		if frappe.db.exists("Dokument Protokoll", {"aktion": "Abgelegt", "beleg": f.attached_to_name, "titel": f.file_name}):
			continue
		archiv.protokollieren(
			"Abgelegt", f.file_name, dokumente.art_von(f), f.attached_to_doctype, f.attached_to_name, f.content_hash or "",
			"nachgetragen", zeit=f.creation, benutzer=f.owner,
		)
