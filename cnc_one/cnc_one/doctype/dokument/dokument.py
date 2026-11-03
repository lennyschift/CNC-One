import frappe
from frappe.model.document import Document


class Dokument(Document):
	def validate(self):
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		if self.schlagworte:
			self.schlagworte = ", ".join(dict.fromkeys(w.strip() for w in self.schlagworte.replace(";", ",").split(",") if w.strip()))
