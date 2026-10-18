"""Systemart der Arbeitsgänge: Seriennummern. Wer sie im Arbeitsplan wählt, bringt die Seriennummer an."""

import frappe

SERIENART = "Seriennummern"


def serienart_anlegen():
	"""Legt die Arbeitsgangart Seriennummern an, falls sie fehlt. Mehrfaches Ausführen ändert nichts."""
	if frappe.db.exists("Arbeitsgangart", {"serie": 1}):
		return
	vorhanden = frappe.db.get_value("Arbeitsgangart", {"bezeichnung": SERIENART})
	if vorhanden:
		frappe.db.set_value("Arbeitsgangart", vorhanden, {"serie": 1, "typ": "Intern", "aktiv": 1})
		return
	frappe.get_doc({"doctype": "Arbeitsgangart", "bezeichnung": SERIENART, "typ": "Intern", "aktiv": 1, "serie": 1}).insert(ignore_permissions=True)
