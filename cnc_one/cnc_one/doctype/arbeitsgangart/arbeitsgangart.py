import frappe
from frappe import _
from frappe.model.document import Document


class Arbeitsgangart(Document):
	def validate(self):
		self.bezeichnung = (self.bezeichnung or "").strip()
		if not self.bezeichnung:
			frappe.throw(_("Bitte eine Bezeichnung angeben."))
		if self.serie:
			vorher = self.get_doc_before_save()
			if vorher and vorher.bezeichnung != self.bezeichnung:
				frappe.throw(_("Der Name der Systemart {0} lässt sich nicht ändern.").format(vorher.bezeichnung))
			self.typ = "Intern"
			self.aktiv = 1
		doppelt = frappe.db.sql(
			"select name from `tabArbeitsgangart` where lower(bezeichnung) = %s and name != %s",
			(self.bezeichnung.lower(), self.name or ""),
		)
		if doppelt:
			frappe.throw(_("Die Arbeitsgangart {0} gibt es schon.").format(self.bezeichnung))

	def on_trash(self):
		if self.serie:
			frappe.throw(_("Die Systemart {0} lässt sich nicht löschen.").format(self.bezeichnung))
