import frappe
from frappe import _
from frappe.model.document import Document


class Mahnung(Document):
	def validate(self):
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		if not self.is_new():
			frappe.throw(_("Eine angelegte Mahnung lässt sich nicht ändern. Sie lässt sich zurückziehen."))

	def on_trash(self):
		frappe.throw(_("Mahnungen lassen sich nicht löschen, nur zurückziehen."))
