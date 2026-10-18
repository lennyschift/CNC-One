import frappe
from frappe import _
from frappe.model.document import Document


class Arbeitsgangart(Document):
	def validate(self):
		self.bezeichnung = (self.bezeichnung or "").strip()
		if not self.bezeichnung:
			frappe.throw(_("Bitte eine Bezeichnung angeben."))
		doppelt = frappe.db.sql(
			"select name from `tabArbeitsgangart` where lower(bezeichnung) = %s and name != %s",
			(self.bezeichnung.lower(), self.name or ""),
		)
		if doppelt:
			frappe.throw(_("Die Arbeitsgangart {0} gibt es schon.").format(self.bezeichnung))
