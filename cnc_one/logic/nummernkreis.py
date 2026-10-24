"""Lückenlose Nummernkreise (GoBD). Die normale Frappe-Serie ist nicht lückenlos, wenn ein Beleg nach der Vergabe doch nicht gespeichert wird.

Hier wird der Zähler in derselben Datenbank-Transaktion hochgezählt wie der Beleg gespeichert wird: schlägt das Speichern fehl,
fällt auch die Nummer zurück. Die Zeile ist gesperrt, bis die Transaktion endet, zwei Festschreibungen gleichzeitig bekommen verschiedene Nummern.
"""

import frappe


def naechste(schluessel):
	if not frappe.db.exists("Nummernkreis", schluessel):
		frappe.get_doc({"doctype": "Nummernkreis", "schluessel": schluessel, "aktuell": 0}).insert(ignore_permissions=True)
	aktuell = frappe.db.sql("select aktuell from `tabNummernkreis` where name = %s for update", (schluessel,))[0][0] or 0
	neu = int(aktuell) + 1
	frappe.db.set_value("Nummernkreis", schluessel, "aktuell", neu, update_modified=False)
	return neu


def rechnungsnummer(jahr):
	"""RE-JJJJ-NNNN, lückenlos je Jahr. Rechnungen und Stornorechnungen teilen sich den Kreis."""
	return f"RE-{int(jahr)}-{naechste(f'Rechnung-{int(jahr)}'):04d}"
