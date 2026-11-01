import frappe
from frappe.model.document import Document


class MailAnfrage(Document):
	def validate(self):
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		if self.kunde:
			self.kunde_vorschlag = None
