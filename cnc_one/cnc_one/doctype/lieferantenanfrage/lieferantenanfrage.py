import frappe
from frappe import _
from frappe.model.document import Document


class Lieferantenanfrage(Document):
	"""Eine Anfrage an einen Lieferanten mit mehreren Positionen (Bauteil + Arbeitsgang + Mengen)."""

	def validate(self):
		self.kunde_name = frappe.db.get_value("Angebot", self.angebot, "kunde_name") if self.angebot else ""
		schluessel = set()
		for p in self.positionen:
			if not p.position_key:
				frappe.throw(_("Position {0} hat keine Kennung.").format(p.idx))
			if p.position_key in schluessel:
				frappe.throw(_("Die Position {0} kommt doppelt vor.").format(p.position_key))
			schluessel.add(p.position_key)
		if not self.positionen:
			frappe.throw(_("Die Anfrage braucht mindestens eine Position."))
		for z in self.preise:
			if z.position_key not in schluessel:
				frappe.throw(_("Ein Preis gehört zu keiner Position der Anfrage."))
			if (z.menge or 0) <= 0:
				frappe.throw(_("Die Menge eines Preises muss größer als null sein."))
