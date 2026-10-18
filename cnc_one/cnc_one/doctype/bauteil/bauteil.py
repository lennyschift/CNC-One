import frappe
from frappe import _
from frappe.model.document import Document


class Bauteil(Document):
	def validate(self):
		self.teilenummer = (self.teilenummer or "").strip()
		if not self.teilenummer:
			frappe.throw(_("Bitte eine Teilenummer angeben."))
		# Ein Kunde hat jede Teilenummer nur einmal, ohne Rücksicht auf Groß- und Kleinschreibung.
		doppelt = frappe.db.sql(
			"select name from `tabBauteil` where kunde = %s and lower(teilenummer) = %s and name != %s",
			(self.kunde, self.teilenummer.lower(), self.name or ""),
		)
		if doppelt:
			frappe.throw(_("Der Kunde {0} hat die Teilenummer {1} schon: {2}").format(self.kunde, self.teilenummer, doppelt[0][0]))
