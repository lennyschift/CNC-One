import frappe
from frappe import _
from frappe.model.document import Document


class Rechnung(Document):
	"""Ein Entwurf ist frei änderbar. Festgeschriebene Rechnungen sind unveränderlich (GoBD), Korrektur nur per Storno."""

	def validate(self):
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		if not self.is_new() and not self.flags.festschreiben:
			vorher = self.get_doc_before_save()
			if vorher and vorher.status != "Entwurf":
				frappe.throw(_("Eine festgeschriebene Rechnung lässt sich nicht mehr ändern. Bitte stornieren und neu erstellen."))

	def on_trash(self):
		if self.status != "Entwurf":
			frappe.throw(_("Festgeschriebene Rechnungen lassen sich nicht löschen, nur stornieren."))
