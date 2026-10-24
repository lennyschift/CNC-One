import frappe


def execute():
	"""Die XRechnung gibt es nicht mehr (nur B2B): Der Stand „ZUGFeRD und XRechnung“ wird zu „ZUGFeRD“, Hinweise zur XRechnung entfallen.
	Schon abgelegte XML-Dateien bleiben als Archiv an der Rechnung."""
	frappe.db.sql("update `tabRechnung` set erechnung_status = 'ZUGFeRD', erechnung_hinweis = '' where erechnung_status = 'ZUGFeRD und XRechnung'")
	frappe.db.sql("update `tabRechnung` set erechnung_hinweis = '' where erechnung_status = 'ZUGFeRD'")
