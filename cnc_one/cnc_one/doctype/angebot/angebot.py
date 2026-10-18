import json

import frappe
from frappe import _
from frappe.model.document import Document

from cnc_one.logic.kalkulation import berechne, summe


def als_json(wert):
	"""Inhalt eines JSON-Feldes als Python-Objekt, auch wenn Frappe ihn als Text liefert."""
	if wert in (None, ""):
		return {}
	if isinstance(wert, str):
		return json.loads(wert)
	return wert


class Angebot(Document):
	def validate(self):
		self.nur_entwuerfe_aendern()
		self.kunde_name = frappe.db.get_value("Kunde", self.kunde, "kundenname") if self.kunde else ""
		self.positionen_rechnen()

	def nur_entwuerfe_aendern(self):
		if self.is_new() or self.flags.status_wechsel:
			return
		vorher = self.get_doc_before_save()
		if vorher and vorher.status != "Entwurf":
			frappe.throw(_("Ein Angebot im Status {0} lässt sich nicht mehr ändern.").format(vorher.status))

	def positionen_rechnen(self):
		"""Der Server rechnet jede Position selbst. Der Browser liefert nur die Eingaben."""
		schluessel = set()
		ergebnisse = []
		for z in self.positionen:
			k = als_json(z.kalkulation)
			if not k.get("id"):
				frappe.throw(_("Position {0} hat keine Kennung.").format(z.idx))
			z.position_key = str(k["id"])
			if z.position_key in schluessel:
				frappe.throw(_("Die Position {0} kommt doppelt vor.").format(z.position_key))
			schluessel.add(z.position_key)
			e = berechne(k)
			z.ergebnis = json.dumps(e, ensure_ascii=False)
			z.menge = e["menge"]
			z.netto = e["gesamt"]
			z.bezeichnung = k.get("name") or ""
			z.teilenummer = k.get("teilenummer") or ""
			z.zeichnungsnr = k.get("zeichnungsnr") or ""
			z.material = k.get("material") or ""
			ergebnisse.append(e)
		self.netto = summe(ergebnisse)

	def on_trash(self):
		if self.status != "Entwurf":
			frappe.throw(_("Nur Entwürfe lassen sich löschen."))
		if frappe.db.exists("Lieferantenanfrage", {"angebot": self.name}):
			frappe.throw(_("Zu diesem Angebot gibt es Lieferantenanfragen."))
