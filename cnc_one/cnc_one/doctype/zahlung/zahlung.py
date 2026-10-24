import frappe
from frappe import _
from frappe.model.document import Document


class Zahlung(Document):
	"""Zahlungseingänge bleiben stehen. Ein Fehler wird storniert (mit Grund), nicht gelöscht."""

	def validate(self):
		if not self.is_new():
			frappe.throw(_("Eine erfasste Zahlung lässt sich nicht ändern. Bitte stornieren und neu erfassen."))
		if (self.betrag or 0) <= 0:
			frappe.throw(_("Der Betrag muss größer als null sein."))

	def on_trash(self):
		frappe.throw(_("Zahlungen lassen sich nicht löschen, nur stornieren."))
