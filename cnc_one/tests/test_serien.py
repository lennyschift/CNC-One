import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from cnc_one.api import angebot, auftrag, bauteil, fertigung, stamm
from cnc_one.logic.serien import bereich, erledigt, formatiert, hoechste, offen, ueberschneidet
from cnc_one.api import stammdaten as stamm_pflege
from cnc_one.tests.test_angebot import teil


class TestSerienLogik(UnitTestCase):
	def test_bereich_ab_der_startnummer(self):
		self.assertEqual(bereich(1001, 10), (1001, 1010))
		self.assertEqual(bereich(5, 1), (5, 5))

	def test_nummern_stehen_immer_mit_fuehrenden_nullen_da(self):
		self.assertEqual(formatiert(1), "0001")
		self.assertEqual(formatiert(10), "0010")
		self.assertEqual(formatiert(123, 6), "000123")
		self.assertEqual(formatiert(None), "")
		self.assertEqual(hoechste(4), 9999)
		self.assertEqual(hoechste(6), 999999)

	def test_ueberschneidung(self):
		self.assertTrue(ueberschneidet((1, 10), (10, 20)))
		self.assertTrue(ueberschneidet((5, 6), (1, 10)))
		self.assertFalse(ueberschneidet((1, 10), (11, 20)))

	def test_die_ersten_gebuchten_nummern_sind_erledigt(self):
		self.assertEqual(erledigt(1001, 1010, 5), (1001, 1005))
		self.assertEqual(offen(1001, 1010, 5), (1006, 1010))
		self.assertIsNone(erledigt(1001, 1010, 0))
		self.assertEqual(offen(1001, 1010, 0), (1001, 1010))
		self.assertIsNone(offen(1001, 1010, 10))
		self.assertEqual(erledigt(1001, 1010, 12), (1001, 1010))  # Überproduktion bekommt keine Nummer
		self.assertIsNone(erledigt(None, None, 3))


class TestSerien(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Serienkunde"}).insert().name
		b = bauteil.sicherstellen(self.kunde, "ZZ-S1", "Serienteil", "", "")
		b.seriennummern = 1
		b.save()
		self.bt = b.name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def gesendet(self, teile=None):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": teile or [teil("t1", teilenummer="ZZ-S1")]})
		return angebot.senden(a["id"])

	def bestellen(self, a, menge=10, start=None, **kw):
		p = {"angebotKey": a["positionen"][0]["key"], "menge": menge, **kw}
		if start is not None:
			p["serienStart"] = start
		return auftrag.aus_angebot(a["id"], "", [p])

	def letzte(self):
		return frappe.db.get_value("Bauteil", self.bt, "letzte_seriennummer") or 0

	def test_startnummer_ist_pflicht_und_der_bereich_wird_gebildet(self):
		a = self.gesendet()
		with self.assertRaises(frappe.ValidationError):
			self.bestellen(a)
		r = self.bestellen(a, 10, 1001)
		p = r["positionen"][0]
		self.assertEqual((p["serienVon"], p["serienBis"]), (1001, 1010))

	def test_letzte_nummer_wird_ins_bauteil_zurueckgeschrieben(self):
		a = self.gesendet()
		self.bestellen(a, 10, 1001)
		self.assertEqual(self.letzte(), 1010)
		self.bestellen(a, 5, 1011)
		self.assertEqual(self.letzte(), 1015)

	def test_niedrigere_nummern_ueberschreiben_die_letzte_nicht(self):
		a = self.gesendet()
		self.bestellen(a, 5, 2001)
		self.bestellen(a, 5, 1001)
		self.assertEqual(self.letzte(), 2005)

	def test_ueberschneidung_mit_frueherem_auftrag_wird_abgelehnt(self):
		a = self.gesendet()
		self.bestellen(a, 10, 1001)
		with self.assertRaises(frappe.ValidationError):
			self.bestellen(a, 10, 1005)
		self.assertEqual(self.letzte(), 1010)

	def test_ueberschneidung_innerhalb_eines_auftrags_wird_abgelehnt(self):
		a = self.gesendet([teil("t1", teilenummer="ZZ-S1"), teil("t2", "Doppelt", "ZZ-S1")])
		pos = [{"angebotKey": p["key"], "menge": 5, "serienStart": 1} for p in a["positionen"]]
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(a["id"], "", pos)

	def test_bauteil_ohne_seriennummern_braucht_keine_startnummer(self):
		frappe.db.set_value("Bauteil", self.bt, "seriennummern", 0)
		r = self.bestellen(self.gesendet(), 10)
		self.assertEqual((r["positionen"][0]["serienVon"], r["positionen"][0]["serienBis"]), (None, None))

	def test_fertigung_uebernimmt_den_bereich_und_das_serien_kennzeichen(self):
		plan = [
			{"id": "a1", "name": "Drehen", "typ": "intern", "serie": True},  # ein Haken allein macht keinen Serien-Arbeitsgang
			{"id": "a2", "name": "Seriennummern", "typ": "intern"},
		]
		a = self.gesendet()
		r = self.bestellen(a, 10, 1001, arbeitsgaenge=plan)
		fb = fertigung.starten(r["id"])["fertigung"][0]
		self.assertEqual((fb["serienVon"], fb["serienBis"], fb["serienStellen"]), (1001, 1010, 4))
		self.assertEqual([x["serie"] for x in fb["arbeitsgaenge"]], [False, True])
		# 5 Stück gelasert: die ersten fünf Nummern sind erledigt
		laser = fb["arbeitsgaenge"][1]["id"]
		neu = fertigung.buchen(fb["id"], laser, 5)["fb"]
		self.assertEqual(neu["arbeitsgaenge"][1]["gebucht"], 5)
		self.assertEqual((neu["serienVon"], neu["serienBis"]), (1001, 1010))

	def test_serien_arbeitsgang_ergibt_sich_aus_der_arbeitsgangart(self):
		fb = fertigung.starten(self.bestellen(self.gesendet(), 10, 1001, arbeitsgaenge=[{"id": "a1", "name": "Lasern", "typ": "intern"}])["id"])["fertigung"][0]
		ag = fb["arbeitsgaenge"][0]
		self.assertFalse(ag["serie"])
		# anderer Name: kein Serien-Arbeitsgang, auch wenn der Browser es behauptet
		neu = fertigung.felder_speichern(fb["id"], {"arbeitsgaenge": [{**ag, "serie": True}]})["fb"]
		self.assertFalse(neu["arbeitsgaenge"][0]["serie"])
		# Name der Systemart (egal wie geschrieben): Serien-Arbeitsgang
		neu = fertigung.felder_speichern(fb["id"], {"arbeitsgaenge": [{**ag, "name": " seriennummern "}]})["fb"]
		self.assertTrue(neu["arbeitsgaenge"][0]["serie"])

	def test_systemart_gibt_es_und_ist_geschuetzt(self):
		art = frappe.db.get_value("Arbeitsgangart", {"serie": 1}, ["name", "bezeichnung", "typ"], as_dict=True)
		self.assertEqual((art.bezeichnung, art.typ), ("Seriennummern", "Intern"))
		self.assertTrue(next(a for a in stamm.stammdaten()["arten"] if a["id"] == art.name)["serie"])
		with self.assertRaises(frappe.ValidationError):
			stamm.art_loeschen(art.name)
		with self.assertRaises(frappe.ValidationError):
			stamm.art_speichern("Anders", "intern", art.name)

	def test_plan_am_bauteil_kennt_den_serien_arbeitsgang(self):
		b = bauteil.plan_setzen(self.kunde, "ZZ-S1", [{"id": "x", "name": "Seriennummern", "typ": "intern"}, {"id": "y", "name": "Drehen", "typ": "intern"}])
		self.assertEqual([a["serie"] for a in bauteil.bauteil_ui(b)["arbeitsgaenge"]], [True, False])

	def test_seriennummern_bestehen_nur_aus_ziffern(self):
		a = self.gesendet()
		for falsch in ("12a", "0x10", "-5", "1 2", "1,5"):
			with self.assertRaises(frappe.ValidationError, msg=falsch):
				self.bestellen(a, 10, falsch)
		r = self.bestellen(a, 10, "0021")  # führende Nullen sind erlaubt
		self.assertEqual((r["positionen"][0]["serienVon"], r["positionen"][0]["serienBis"]), (21, 30))

	def test_nummern_muessen_in_die_stellenzahl_passen(self):
		a = self.gesendet()
		with self.assertRaises(frappe.ValidationError):
			self.bestellen(a, 10, 9995)  # 9995 bis 10004 hat 5 Stellen
		frappe.db.set_value("Bauteil", self.bt, "serien_stellen", 6)
		r = self.bestellen(a, 10, 9995)
		self.assertEqual((r["positionen"][0]["serienBis"], r["positionen"][0]["serienStellen"]), (10004, 6))

	def test_stellenzahl_am_bauteil_pflegen(self):
		b = stamm_pflege.speichern("bauteil", {"kundeId": self.kunde, "teilenummer": "ZZ-ST", "seriennummern": True, "serienStellen": 5, "letzteSeriennummer": 120})
		self.assertEqual((b["serienStellen"], b["letzteSeriennummer"]), (5, 120))
		with self.assertRaises(frappe.ValidationError):
			stamm_pflege.speichern("bauteil", {**b, "serienStellen": 2, "letzteSeriennummer": 120})
