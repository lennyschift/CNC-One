"""Tests dürfen nur Dateien löschen, die sie selbst angelegt haben.

Die Datenbank rollt nach jedem Test zurück, die Dateien auf der Platte nicht: Wer im Test einen fremden Dateieintrag
löscht, löscht die echte Datei endgültig. Deshalb merkt sich jeder Test im setUp, welche Dateieinträge es schon gab.
"""

import frappe


def dateien_vorher():
	return set(frappe.get_all("File", pluck="name"))


def eigene_dateien_loeschen(vorher):
	for name in frappe.get_all("File", filters={"is_folder": 0}, pluck="name"):
		if name not in vorher:
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
