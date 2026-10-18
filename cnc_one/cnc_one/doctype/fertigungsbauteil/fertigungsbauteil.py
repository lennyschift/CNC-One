import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from cnc_one.logic import fertigung as regel
from cnc_one.logic import lager


class Fertigungsbauteil(Document):
	"""Ein Bauteil einer Auftragsposition in der Fertigung. Die Buchungsregeln stehen hier und in logic/fertigung.py."""

	def validate(self):
		ids = set()
		for a in self.arbeitsgaenge:
			if not a.ag_id:
				a.ag_id = frappe.generate_hash(length=10)
			if a.ag_id in ids:
				frappe.throw(_("Der Arbeitsgang {0} kommt doppelt vor.").format(a.bezeichnung))
			ids.add(a.ag_id)
			a.gebucht = max(0, int(a.gebucht or 0))
		for s in self.sendungen:
			if s.ag_id not in ids:
				frappe.throw(_("Eine Sendung gehört zu keinem Arbeitsgang."))
		self.menge = max(1, int(self.menge or 0))
		if (self.serien_von or 0) and (self.serien_bis or 0) < self.serien_von:
			frappe.throw(_("Der Seriennummern-Bereich ist ungültig."))
		self.produziert = regel.produziert(self.arbeitsgaenge)
		self.ueberproduktion = regel.ueberproduktion(self.menge, self.produziert)

	def on_update(self):
		"""Die gefertigte Menge geht ins Fertigbauteil Lager. Der Auftrag ist fertig, wenn alle seine Fertigungsbauteile fertig sind."""
		lager.fertigung_abgleichen(self)
		if not self.auftrag:
			return
		stati = frappe.get_all("Fertigungsbauteil", filters={"auftrag": self.auftrag}, pluck="status")
		neu = "Fertig" if stati and all(s == "Fertig" for s in stati) else "In Fertigung"
		frappe.db.set_value("Auftrag", self.auftrag, "status", neu, update_modified=False)

	# ------------------------------------------------------------------ Zugriff
	def arbeitsgang(self, ag_id):
		for a in self.arbeitsgaenge:
			if a.ag_id == ag_id:
				return a
		frappe.throw(_("Den Arbeitsgang gibt es nicht."))

	def sendungen_von(self, ag_id):
		return [s for s in self.sendungen if s.ag_id == ag_id]

	def _protokoll(self, ag, menge, auto=False):
		self.append("buchungen", {
			"zeit": now_datetime(), "ag_id": ag.ag_id, "ag_name": ag.bezeichnung,
			"menge": menge, "benutzer": frappe.session.user, "auto": 1 if auto else 0,
		})

	def _ag_neu_bewerten(self, ag):
		ag.status = regel.arbeitsgang_status(ag, self.menge, self.sendungen_von(ag.ag_id))

	def neu_bewerten(self, ag=None):
		if ag:
			self._ag_neu_bewerten(ag)
		self.status = regel.auto_status(self.arbeitsgaenge, self.menge)

	# ------------------------------------------------------------------ Buchen
	def abhaken(self, ag_id, delta):
		"""Frühere Arbeitsgänge gelten als abgehakt: intern wird nachgebucht, Fremdvergabe bekommt eine abgehakte Sendung."""
		ag = self.arbeitsgang(ag_id)
		if delta <= 0:
			return
		if ag.typ == "Fremd":
			self.append("sendungen", {"ag_id": ag.ag_id, "menge": delta, "datum_weg": today(), "datum_zurueck": today(), "abgehakt": 1})
		ag.gebucht = int(ag.gebucht or 0) + delta
		self._protokoll(ag, delta, auto=True)
		self._ag_neu_bewerten(ag)

	def buchen(self, ag_id, menge):
		"""Bucht Stückzahl auf einen internen Arbeitsgang. Liefert die Anzahl der mit abgehakten früheren Arbeitsgänge."""
		ag = self.arbeitsgang(ag_id)
		if ag.typ == "Fremd":
			frappe.throw(_("Eine Fremdvergabe wird über ihre Sendungen gebucht."))
		m = int(menge or 0)
		if m <= 0:
			frappe.throw(_("Die Menge muss größer als null sein."))
		neu = int(ag.gebucht or 0) + m
		nach = regel.nachzuholen(self.arbeitsgaenge, ag_id, neu)
		for k_id, delta in nach:
			self.abhaken(k_id, delta)
		ag.gebucht = neu
		self._protokoll(ag, m)
		self.neu_bewerten(ag)
		return len(nach)

	def buchung_loeschen(self, buchung):
		b = next((x for x in self.buchungen if x.name == buchung), None)
		if not b:
			frappe.throw(_("Die Buchung gibt es nicht."))
		ag = next((a for a in self.arbeitsgaenge if a.ag_id == b.ag_id), None)
		if ag:
			ag.gebucht = max(0, int(ag.gebucht or 0) - int(b.menge or 0))
		self.remove(b)
		self.neu_bewerten(ag)

	# ------------------------------------------------------------------ Arbeitsplan
	def arbeitsgaenge_hinzu(self, zeilen):
		for z in zeilen:
			self.append("arbeitsgaenge", {**z, "ag_id": frappe.generate_hash(length=10), "status": "Offen", "gebucht": 0})
		self.neu_bewerten()

	def arbeitsgang_weg(self, ag_id):
		ag = self.arbeitsgang(ag_id)
		for s in self.sendungen_von(ag_id):
			self.remove(s)
		self.remove(ag)
		self.neu_bewerten()

	def arbeitsgang_verschieben(self, ag_id, richtung):
		zeilen = list(self.arbeitsgaenge)
		i = next((k for k, a in enumerate(zeilen) if a.ag_id == ag_id), -1)
		j = i + int(richtung)
		if i < 0 or j < 0 or j >= len(zeilen):
			return
		zeilen[i], zeilen[j] = zeilen[j], zeilen[i]
		for n, z in enumerate(zeilen, start=1):
			z.idx = n
		self.arbeitsgaenge = zeilen

	# ------------------------------------------------------------------ Sendungen (Fremdvergabe)
	def sendung_anlegen(self, ag_id, menge=None):
		ag = self.arbeitsgang(ag_id)
		if ag.typ != "Fremd":
			frappe.throw(_("Sendungen gibt es nur bei einer Fremdvergabe."))
		m = int(menge) if menge else regel.noch_nicht_gesendet(self.menge, self.sendungen_von(ag_id))
		if m <= 0:
			frappe.throw(_("Es ist schon die ganze Menge versendet."))
		self.append("sendungen", {"ag_id": ag_id, "menge": m})

	def _sendung(self, ag_id, name):
		s = next((x for x in self.sendungen if x.name == name and x.ag_id == ag_id), None)
		if not s:
			frappe.throw(_("Die Sendung gibt es nicht."))
		return s

	def sendung_weg(self, ag_id, sendung):
		ag = self.arbeitsgang(ag_id)
		s = self._sendung(ag_id, sendung)
		if not ag.lieferant:
			frappe.throw(_("Bitte zuerst einen Lieferanten wählen."))
		s.datum_weg = today()
		self.neu_bewerten(ag)

	def sendung_zurueck(self, ag_id, sendung):
		ag = self.arbeitsgang(ag_id)
		s = self._sendung(ag_id, sendung)
		if not s.datum_weg:
			s.datum_weg = today()
		s.datum_zurueck = today()
		neu = regel.fremd_gebucht(self.sendungen_von(ag_id))
		for k_id, delta in regel.nachzuholen(self.arbeitsgaenge, ag_id, neu):
			self.abhaken(k_id, delta)
		delta = neu - int(ag.gebucht or 0)
		ag.gebucht = neu
		if delta > 0:
			self._protokoll(ag, delta)
		self.neu_bewerten(ag)

	def sendung_loeschen(self, ag_id, sendung):
		ag = self.arbeitsgang(ag_id)
		self.remove(self._sendung(ag_id, sendung))
		ag.gebucht = regel.fremd_gebucht(self.sendungen_von(ag_id))
		self.neu_bewerten(ag)

	# ------------------------------------------------------------------ Status von Hand (Board)
	def status_setzen(self, status):
		"""Fertig bucht den Rest in allen Arbeitsgängen, Offen geht nur ohne Buchungen."""
		if status not in ("Offen", "In Fertigung", "Fertig"):
			frappe.throw(_("Unbekannter Status {0}.").format(status))
		if self.status == status:
			return
		if status == "Offen" and regel.produziert(self.arbeitsgaenge) + len(self.buchungen) > 0:
			frappe.throw(_("Mit vorhandenen Buchungen kann das Bauteil nicht auf „Offen“ zurück."))
		if status == "Fertig":
			if not self.arbeitsgaenge:
				frappe.throw(_("Ohne Arbeitsgänge lässt sich nichts fertig buchen. Bitte zuerst Arbeitsgänge anlegen."))
			for ag in list(self.arbeitsgaenge):
				self.abhaken(ag.ag_id, self.menge - int(ag.gebucht or 0))
			for ag in self.arbeitsgaenge:
				self._ag_neu_bewerten(ag)
		elif status == "In Fertigung":
			erster = next((a for a in self.arbeitsgaenge if a.status == "Offen"), None)
			if erster:
				erster.status = "Läuft"
		self.status = status
