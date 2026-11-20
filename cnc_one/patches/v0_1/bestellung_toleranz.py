"""Die neue Toleranz beim Preisabgleich der Bestellungen startet mit 0,5 %, wenn sie noch nie gespeichert wurde."""

import frappe


def execute():
	if not frappe.db.exists("Singles", {"doctype": "Firma", "field": "bestellung_toleranz"}):
		frappe.db.set_single_value("Firma", "bestellung_toleranz", 0.5)
