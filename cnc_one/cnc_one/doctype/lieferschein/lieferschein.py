import frappe
from frappe import _
from frappe.model.document import Document


class Lieferschein(Document):
	def validate(self):
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		if not self.positionen:
			frappe.throw(_("Der Lieferschein braucht mindestens eine Position."))
		for p in self.positionen:
			if (p.menge or 0) <= 0:
				frappe.throw(_("Die Liefermenge muss größer als null sein."))

	def on_trash(self):
		frappe.throw(_("Lieferscheine werden storniert, nicht gelöscht."))
