"""Grundausstattung für Rechnungen: Steuerschlüssel Inland 19 % und die Firmendaten (leer, werden in den Stammdaten gepflegt)."""

import frappe


def steuerschluessel_anlegen():
	if frappe.db.exists("Steuerschluessel", {"standard": 1}):
		return
	if not frappe.db.exists("Steuerschluessel", "Inland 19 %"):
		frappe.get_doc({
			"doctype": "Steuerschluessel", "bezeichnung": "Inland 19 %", "satz": 19, "kategorie": "S", "standard": 1, "aktiv": 1,
		}).insert(ignore_permissions=True)
	else:
		frappe.db.set_value("Steuerschluessel", "Inland 19 %", "standard", 1)


def firma_vorbelegen():
	"""Legt die Firma mit sinnvollen Texten an, falls noch nichts drinsteht. Anschrift, Steuer und Bank pflegt der Benutzer."""
	d = frappe.get_single("Firma")
	if d.firmenname:
		return
	d.firmenname = "CNC Hohenstein"
	d.land = "Deutschland"
	d.rechnung_text = "Vielen Dank für Ihren Auftrag. Wir berechnen Ihnen:"
	d.rechnung_fusstext = "Alle Preise netto zuzüglich der gesetzlichen Umsatzsteuer."
	d.zahlungsziel_tage = 14
	d.mahnfrist_tage = 7
	d.save(ignore_permissions=True)
