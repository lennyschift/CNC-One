import frappe
from frappe import _
from frappe.model.document import Document

from cnc_one.logic.kalkulation import _summe, r2


class Auftrag(Document):
	def validate(self):
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		self.positionen_rechnen()

	def positionen_rechnen(self):
		"""Summe je Position und Auftragswert rechnet der Server aus Einzelpreis, Menge und Kostenzeilen."""
		schluessel = set()
		for p in self.positionen:
			if not p.position_key:
				frappe.throw(_("Position {0} hat keine Kennung.").format(p.idx))
			if p.position_key in schluessel:
				frappe.throw(_("Die Position {0} kommt doppelt vor.").format(p.position_key))
			schluessel.add(p.position_key)
		for k in self.kosten:
			if k.position_key not in schluessel:
				frappe.throw(_("Die Kostenzeile {0} gehört zu keiner Position.").format(k.bezeichnung))
		for p in self.positionen:
			zeilen = _summe(k.betrag or 0 for k in self.kosten if k.position_key == p.position_key)
			p.summe = r2((p.einzelpreis or 0) * (p.menge or 0) + zeilen)
		self.netto = r2(_summe(p.summe for p in self.positionen))

	def on_trash(self):
		if frappe.db.exists("Fertigungsbauteil", {"auftrag": self.name}):
			frappe.throw(_("Zu diesem Auftrag gibt es schon Fertigungsbauteile."))
