import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, auftrag, bauteil, fertigung, lager as lager_api, lieferschein
from cnc_one.logic import lager
from cnc_one.tests.test_angebot import teil

PLAN = [{"id": "p1", "name": "Drehen", "typ": "intern"}, {"id": "p2", "name": "Prüfen", "typ": "intern"}]


class TestLieferschein(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Lieferkunde"}).insert().name
		self.andere = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Anderer Kunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def auftrag(self, menge=10, nr="ZZ-L1", serien=False, **kw):
		t = teil("t1", "Flansch", nr)
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [t]})
		if serien:
			frappe.db.set_value("Bauteil", bauteil.finden(self.kunde, nr), "seriennummern", 1)
		a = angebot.senden(a["id"])
		pos = {"angebotKey": a["positionen"][0]["key"], "menge": menge, "arbeitsgaenge": PLAN, **kw}
		return auftrag.aus_angebot(a["id"], "PO-7", [pos])

	def fertigen(self, auf, menge):
		"""Startet die Fertigung (falls nötig) und bucht `menge` Stück durch alle Arbeitsgänge."""
		fbs = frappe.get_all("Fertigungsbauteil", filters={"auftrag": auf["id"]}, pluck="name")
		if not fbs:
			fertigung.starten(auf["id"])
			fbs = frappe.get_all("Fertigungsbauteil", filters={"auftrag": auf["id"]}, pluck="name")
		fb = fertigung.liste()
		fb = next(x for x in fb if x["id"] == fbs[0])
		return fertigung.buchen(fb["id"], fb["arbeitsgaenge"][-1]["id"], menge)["fb"]

	def liefern(self, auf, menge, **kw):
		pos = auf["positionen"][0]
		return lieferschein.anlegen(self.kunde, [{"auftrag": auf["id"], "auftragsposition": pos["key"], "menge": menge, **kw}])

	def bestand(self, nr="ZZ-L1"):
		return lager.bestand(bauteil.finden(self.kunde, nr))

	# ------------------------------------------------------------- Lager
	def test_fertigung_bucht_die_gefertigte_menge_ins_fertigbauteil_lager(self):
		auf = self.auftrag()
		self.assertEqual(self.bestand(), 0)
		self.fertigen(auf, 4)
		self.assertEqual(self.bestand(), 4)
		self.fertigen(auf, 3)
		self.assertEqual(self.bestand(), 7)
		buchungen = lager_api.buchungen(bauteil.finden(self.kunde, "ZZ-L1"))
		self.assertEqual([(b["art"], b["menge"]) for b in buchungen], [("Fertigung", 3), ("Fertigung", 4)])

	def test_ueberproduktion_kommt_ins_lager(self):
		auf = self.auftrag(10)
		self.fertigen(auf, 12)
		self.assertEqual(self.bestand(), 12)

	def test_stornierte_fertigungsbuchung_wird_im_lager_gegengebucht(self):
		auf = self.auftrag()
		fb = self.fertigen(auf, 5)
		self.assertEqual(self.bestand(), 5)
		for b in fb["buchungen"]:
			fb = fertigung.buchung_loeschen(fb["id"], b["id"])["fb"]
		self.assertEqual(self.bestand(), 0)

	def test_lagerbuchungen_sind_unveraenderlich(self):
		auf = self.auftrag()
		self.fertigen(auf, 2)
		name = frappe.get_all("Lagerbuchung", pluck="name")[0]
		doc = frappe.get_doc("Lagerbuchung", name)
		doc.menge = 99
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Lagerbuchung", name)

	def test_korrektur_braucht_einen_grund(self):
		auf = self.auftrag()
		bt = bauteil.finden(self.kunde, "ZZ-L1")
		with self.assertRaises(frappe.ValidationError):
			lager_api.korrigieren(bt, 3, " ")
		with self.assertRaises(frappe.ValidationError):
			lager_api.korrigieren(bt, 0, "Zählung")
		self.assertEqual(lager_api.korrigieren(bt, 3, "Inventur")["bestand"], 3)
		self.assertEqual(lager_api.buchungen(bt)[0]["art"], "Korrektur")

	def test_bestandsliste_je_bauteil(self):
		self.fertigen(self.auftrag(), 4)
		zeile = next(z for z in lager_api.bestand()["bestand"] if z["teil"]["teilenummer"] == "ZZ-L1")
		self.assertEqual((zeile["bestand"], zeile["kundeName"]), (4, "ZZ Lieferkunde"))

	# ------------------------------------------------------------- Lieferschein aus Auftrag
	def test_vorschlag_ist_gefertigt_minus_geliefert(self):
		auf = self.auftrag(10)
		p = lieferschein.vorschlag(auf["id"])["positionen"][0]
		self.assertEqual((p["bestellt"], p["gefertigt"], p["geliefert"], p["offen"], p["vorschlag"]), (10, 0, 0, 10, 0))
		self.fertigen(auf, 5)
		p = lieferschein.vorschlag(auf["id"])["positionen"][0]
		self.assertEqual((p["gefertigt"], p["vorschlag"]), (5, 5))
		self.liefern(auf, 3)
		p = lieferschein.vorschlag(auf["id"])["positionen"][0]
		self.assertEqual((p["geliefert"], p["offen"], p["vorschlag"]), (3, 7, 2))

	def test_lieferschein_vor_der_fertigung_bucht_minus_und_gleicht_sich_aus(self):
		auf = self.auftrag(10)
		ls = self.liefern(auf, 4)
		self.assertEqual((ls["status"], ls["kundeName"], ls["kundenbestellnr"]), ("Bereit", "ZZ Lieferkunde", ""))
		self.assertTrue(ls["id"].startswith("LS-"))
		self.assertEqual(self.bestand(), -4)
		self.fertigen(auf, 4)
		self.assertEqual(self.bestand(), 0)
		self.fertigen(auf, 6)
		self.assertEqual(self.bestand(), 6)

	def test_teillieferungen_nur_bis_zur_bestellmenge(self):
		auf = self.auftrag(10)
		self.liefern(auf, 6)
		self.liefern(auf, 4)
		with self.assertRaises(frappe.ValidationError):
			self.liefern(auf, 1)
		with self.assertRaises(frappe.ValidationError):
			self.liefern(auf, 0)

	def test_auftrag_zeigt_den_lieferstand_mit_verweisen(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 6)
		l2 = self.liefern(auf, 2)
		neu = next(a for a in auftrag.liste() if a["id"] == auf["id"])
		p = neu["positionen"][0]
		self.assertEqual(p["geliefert"], 8)
		self.assertEqual([(x["id"], x["menge"]) for x in p["lieferscheine"]], [(l1["id"], 6), (l2["id"], 2)])
		self.assertEqual(neu["lieferung"], {"bestellt": 10, "geliefert": 8, "status": "Teilweise geliefert"})
		self.liefern(auf, 2)
		neu = next(a for a in auftrag.liste() if a["id"] == auf["id"])
		self.assertEqual(neu["lieferung"]["status"], "Geliefert")

	def test_storno_bucht_zurueck_und_gibt_die_menge_im_auftrag_frei(self):
		auf = self.auftrag(10)
		ls = self.liefern(auf, 6)
		self.assertEqual(self.bestand(), -6)
		r = lieferschein.stornieren(ls["id"])
		self.assertEqual(r["status"], "Storniert")
		self.assertEqual(self.bestand(), 0)
		neu = next(a for a in auftrag.liste() if a["id"] == auf["id"])
		self.assertEqual(neu["positionen"][0]["geliefert"], 0)
		self.liefern(auf, 10)  # die Menge ist wieder frei
		with self.assertRaises(frappe.ValidationError):
			lieferschein.stornieren(ls["id"])

	def test_geliefert_markieren(self):
		ls = self.liefern(self.auftrag(), 2)
		r = lieferschein.geliefert_setzen(ls["id"])
		self.assertEqual(r["status"], "Geliefert")
		self.assertTrue(r["gelieferAm"])
		with self.assertRaises(frappe.ValidationError):
			lieferschein.geliefert_setzen(ls["id"])

	def test_lieferschein_hat_keine_preise_und_laesst_sich_nicht_loeschen(self):
		ls = self.liefern(self.auftrag(), 2)
		text = str(ls).lower()
		for wort in ("preis", "betrag", "summe", "netto", "kosten"):
			self.assertNotIn(wort, text)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Lieferschein", ls["id"])

	def test_lieferadresse_ist_ein_snapshot_des_kunden(self):
		k = frappe.get_doc("Kunde", self.kunde)
		k.append("adressen", {"typ": "Lieferung", "strasse": "Hallenweg 2", "plz": "72461", "ort": "Albstadt", "standard": 1})
		k.save()
		ls = self.liefern(self.auftrag(), 1)
		self.assertEqual(ls["adresse"], ["ZZ Lieferkunde", "Hallenweg 2", "72461 Albstadt"])

	# ------------------------------------------------------------- Seriennummern
	def test_teillieferungen_nehmen_die_naechsten_seriennummern(self):
		auf = self.auftrag(10, serien=True, serienStart=1001)
		self.assertEqual(auf["positionen"][0]["serienVon"], 1001)
		l1 = self.liefern(auf, 4)
		p1 = l1["positionen"][0]
		self.assertEqual((p1["serienVon"], p1["serienBis"], p1["serienStellen"]), (1001, 1004, 4))
		self.assertEqual(lieferschein.vorschlag(auf["id"])["positionen"][0]["serienVon"], 1005)
		l2 = self.liefern(auf, 6)
		self.assertEqual((l2["positionen"][0]["serienVon"], l2["positionen"][0]["serienBis"]), (1005, 1010))

	# ------------------------------------------------------------- bauteilunabhängig
	def test_lieferschein_frei_aus_bauteilen_des_kunden(self):
		auf = self.auftrag(10)
		bt = bauteil.finden(self.kunde, "ZZ-L1")
		ls = lieferschein.anlegen(self.kunde, [{"bauteilId": bt, "menge": 3}], bemerkung="Muster", kundenbestellnr="X-1")
		p = ls["positionen"][0]
		self.assertEqual((p["bauteilId"], p["menge"], p["auftragId"]), (bt, 3, ""))
		self.assertEqual((ls["bemerkung"], ls["kundenbestellnr"]), ("Muster", "X-1"))
		self.assertEqual(self.bestand(), -3)

	def test_freie_position_braucht_ein_bauteil_des_richtigen_kunden(self):
		self.auftrag(10)
		bt = bauteil.finden(self.kunde, "ZZ-L1")
		with self.assertRaises(frappe.ValidationError):
			lieferschein.anlegen(self.andere, [{"bauteilId": bt, "menge": 1}])
		with self.assertRaises(frappe.ValidationError):
			lieferschein.anlegen(self.kunde, [{"menge": 1}])
		with self.assertRaises(frappe.ValidationError):
			lieferschein.anlegen(self.kunde, [])

	def test_seriennummern_bei_freier_lieferung_von_hand(self):
		self.auftrag(10, serien=True, serienStart=1)
		bt = bauteil.finden(self.kunde, "ZZ-L1")
		ls = lieferschein.anlegen(self.kunde, [{"bauteilId": bt, "menge": 3, "serienStart": "0050"}])
		self.assertEqual((ls["positionen"][0]["serienVon"], ls["positionen"][0]["serienBis"]), (50, 52))
		with self.assertRaises(frappe.ValidationError):
			lieferschein.anlegen(self.kunde, [{"bauteilId": bt, "menge": 3, "serienStart": "5x"}])
		with self.assertRaises(frappe.ValidationError):
			lieferschein.anlegen(self.kunde, [{"bauteilId": bt, "menge": 3, "serienStart": "9999"}])

	def test_auftrag_eines_anderen_kunden_wird_abgelehnt(self):
		auf = self.auftrag(10)
		with self.assertRaises(frappe.ValidationError):
			lieferschein.anlegen(self.andere, [{"auftrag": auf["id"], "auftragsposition": auf["positionen"][0]["key"], "menge": 1}])

	def test_liste_bootstrap_und_gast(self):
		from cnc_one.api import stamm

		ls = self.liefern(self.auftrag(), 1)
		self.assertIn(ls["id"], [x["id"] for x in lieferschein.liste()])
		daten = stamm.bootstrap()
		self.assertIn(ls["id"], [x["id"] for x in daten["lieferscheine"]])
		self.assertIn("lager", daten)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			lieferschein.liste()
		with self.assertRaises(frappe.PermissionError):
			lager_api.bestand()
