import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, stammdaten
from cnc_one.tests.test_angebot import teil


class TestStammdaten(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_kunde_mit_adressen_und_kontakten(self):
		k = stammdaten.speichern("kunde", {
			"name": "ZZ Neukunde", "kuerzel": "ZZN", "ustId": "DE123", "zahlungsbedingung": "14 Tage", "leitwegId": "04-1234",
			"adressen": [{"strasse": "Weg 1", "plz": "72461", "ort": "Albstadt"}, {"strasse": "", "plz": "", "ort": ""}],
			"kontakte": [{"anrede": "Frau", "vorname": "Anja", "nachname": "Test", "email": "a@test.example", "rechnungskontakt": True}, {"nachname": ""}],
		})
		self.assertTrue(k["id"].startswith("K-"))
		self.assertEqual((k["name"], k["kuerzel"], k["ustId"], k["leitwegId"], k["aktiv"]), ("ZZ Neukunde", "ZZN", "DE123", "04-1234", True))
		self.assertEqual(len(k["adressen"]), 1)
		self.assertTrue(k["adressen"][0]["standard"])
		self.assertEqual(len(k["kontakte"]), 1)
		self.assertTrue(k["kontakte"][0]["rechnungskontakt"])
		k["name"] = "ZZ Neukunde GmbH"
		k["aktiv"] = False
		k["adressen"] = []
		neu = stammdaten.speichern("kunde", k)
		self.assertEqual((neu["id"], neu["name"], neu["aktiv"], neu["adressen"]), (k["id"], "ZZ Neukunde GmbH", False, []))
		self.assertIn(k["id"], [x["id"] for x in stammdaten.liste("kunde")])

	def test_deaktivierte_kunden_stehen_nicht_in_den_auswahllisten(self):
		k = stammdaten.speichern("kunde", {"name": "ZZ Inaktiv", "aktiv": False})
		self.assertNotIn(k["id"], [x["id"] for x in stammdaten.aktuell()["kunden"]])
		self.assertIn(k["id"], [x["id"] for x in stammdaten.liste("kunde")])

	def test_lieferant_maschine_material(self):
		l = stammdaten.speichern("lieferant", {"name": "ZZ Härterei", "leistung": "Härten", "email": "h@x.example", "adresse": "Weg 2"})
		self.assertEqual((l["id"], l["leistung"], l["aktiv"]), ("ZZ Härterei", "Härten", True))
		l["leistung"] = "Härten und Anlassen"
		l["name"] = "wird ignoriert"
		self.assertEqual(stammdaten.speichern("lieferant", l)["leistung"], "Härten und Anlassen")
		m = stammdaten.speichern("maschine", {"name": "ZZ Fräse", "satz": 99.5, "bemerkung": "5-Achs"})
		self.assertEqual((m["id"], m["satz"]), ("ZZ Fräse", 99.5))
		w = stammdaten.speichern("material", {"name": "ZZ Stahl", "preisKg": 4.2, "dichte": 7.85})
		self.assertEqual((w["preisKg"], w["dichte"]), (4.2, 7.85))
		aktuell = stammdaten.aktuell()
		self.assertIn({"name": "ZZ Fräse", "satz": 99.5}, aktuell["maschinen"])
		self.assertIn({"name": "ZZ Stahl", "preisKg": 4.2}, aktuell["materialien"])

	def test_name_ist_pflicht(self):
		with self.assertRaises(frappe.ValidationError):
			stammdaten.speichern("maschine", {"name": "  ", "satz": 1})

	def test_bauteil_mit_arbeitsplan(self):
		k = stammdaten.speichern("kunde", {"name": "ZZ Bauteilkunde"})
		b = stammdaten.speichern("bauteil", {
			"kundeId": k["id"], "teilenummer": "ZZ-B1", "name": "Flansch", "zeichnungsnr": "Z-9", "revision": "B", "status": "Aktiv",
			"arbeitsgaenge": [{"id": "a1", "name": "Drehen", "typ": "intern", "satz": 90, "ruestMin": 30, "stueckMin": 2}],
		})
		self.assertTrue(b["id"].startswith("BT-"))
		self.assertEqual((b["revision"], b["status"], [a["name"] for a in b["arbeitsgaenge"]]), ("B", "Aktiv", ["Drehen"]))
		b["status"] = "Gesperrt"
		b["arbeitsgaenge"] = []
		neu = stammdaten.speichern("bauteil", b)
		self.assertEqual((neu["status"], neu["arbeitsgaenge"]), ("Gesperrt", []))

	def test_bauteil_braucht_kunde_und_eindeutige_teilenummer(self):
		with self.assertRaises(frappe.ValidationError):
			stammdaten.speichern("bauteil", {"kundeId": "", "teilenummer": "ZZ-B2"})
		k = stammdaten.speichern("kunde", {"name": "ZZ Doppelkunde"})
		stammdaten.speichern("bauteil", {"kundeId": k["id"], "teilenummer": "ZZ-B3"})
		with self.assertRaises(frappe.ValidationError):
			stammdaten.speichern("bauteil", {"kundeId": k["id"], "teilenummer": "zz-b3"})

	def test_loeschen_und_schutz_bei_verwendung(self):
		frei = stammdaten.speichern("maschine", {"name": "ZZ Frei", "satz": 1})
		stammdaten.loeschen("maschine", frei["id"])
		self.assertFalse(frappe.db.exists("Maschine", "ZZ Frei"))
		k = stammdaten.speichern("kunde", {"name": "ZZ Verwendet"})
		angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": k["id"]}, "teile": [teil("t1")]})
		with self.assertRaises(frappe.ValidationError):
			stammdaten.loeschen("kunde", k["id"])
		self.assertTrue(frappe.db.exists("Kunde", k["id"]))

	def test_unbekannte_art_und_gast(self):
		with self.assertRaises(frappe.ValidationError):
			stammdaten.liste("gibtsnicht")
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			stammdaten.liste("kunde")
