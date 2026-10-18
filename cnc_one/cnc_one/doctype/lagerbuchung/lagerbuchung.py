import frappe
from frappe import _
from frappe.model.document import Document


class Lagerbuchung(Document):
	"""Lagerbuchungen sind unveränderlich. Fehler werden mit einer Gegenbuchung korrigiert."""

	def validate(self):
		if not self.is_new():
			frappe.throw(_("Lagerbuchungen lassen sich nicht ändern. Bitte eine Korrekturbuchung anlegen."))
		if not self.menge:
			frappe.throw(_("Die Menge einer Lagerbuchung darf nicht null sein."))

	def on_trash(self):
		if not frappe.flags.lagerbuchung_loeschen:
			frappe.throw(_("Lagerbuchungen lassen sich nicht löschen. Bitte eine Korrekturbuchung anlegen."))
