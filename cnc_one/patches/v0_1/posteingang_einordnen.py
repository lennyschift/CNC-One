"""Posteingang mit bekannten Absendern und Einordnung: Grundwerte der neuen Einstellungen setzen (nur wenn noch nie
gespeichert) und bisherige Mails als Anfragen kennzeichnen (bisher kamen nur Anfragen herein)."""

import frappe

GRUNDWERTE = {
	"bekannte_absender": 1,
	"woerter_bestellung": "Bestellung\nOrder\nAbruf",
	"woerter_rechnung": "Rechnung\nInvoice\nGutschrift",
}


def execute():
	for feld, wert in GRUNDWERTE.items():
		if not frappe.db.exists("Singles", {"doctype": "Mail Einstellungen", "field": feld}):
			frappe.db.set_single_value("Mail Einstellungen", feld, wert)
	frappe.db.sql("update `tabMail Anfrage` set kategorie = 'Anfrage' where ifnull(kategorie, '') = ''")
