import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import stamm
from cnc_one.setup import rollen


class TestStamm(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_rollen_sind_angelegt(self):
		for r in rollen.ROLLEN:
			self.assertTrue(frappe.db.exists("Role", r), r)

	def test_bootstrap_liefert_alle_bereiche(self):
		frappe.get_doc({"doctype": "Maschine", "maschinenname": "ZZ Testmaschine", "satz": 99}).insert()
		daten = stamm.bootstrap()
		for key in ("benutzer", "kunden", "lieferanten", "maschinen", "materialien", "arten", "vorlagen"):
			self.assertIn(key, daten)
		self.assertIn({"name": "ZZ Testmaschine", "satz": 99}, daten["maschinen"])
		self.assertEqual(daten["benutzer"]["id"], "Administrator")

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			stamm.bootstrap()

	def test_art_anlegen_aendern_loeschen(self):
		a = stamm.art_speichern("ZZ Testart", "fremd")
		self.assertEqual(a["name"], "ZZ Testart")
		self.assertEqual(a["typ"], "fremd")
		b = stamm.art_speichern("ZZ Testart neu", "intern", id=a["id"])
		self.assertEqual(b["id"], a["id"])
		self.assertEqual((b["name"], b["typ"]), ("ZZ Testart neu", "intern"))
		stamm.art_loeschen(a["id"])
		self.assertFalse(frappe.db.exists("Arbeitsgangart", a["id"]))

	def test_art_name_ist_eindeutig(self):
		stamm.art_speichern("ZZ Doppelt", "intern")
		with self.assertRaises(frappe.ValidationError):
			stamm.art_speichern("zz doppelt", "fremd")

	def test_vorlage_bleibt_beim_speichern_erhalten(self):
		frappe.get_doc({"doctype": "Maschine", "maschinenname": "ZZ M1", "satz": 50}).insert()
		frappe.get_doc({"doctype": "Lieferant", "lieferantenname": "ZZ Lieferant"}).insert()
		v = stamm.vorlage_speichern({
			"name": "ZZ Vorlage",
			"kundeId": "",
			"arbeitsgaenge": [
				{"id": "ag-1", "name": "Drehen", "typ": "intern", "maschine": "ZZ M1", "satz": 50, "ruestMin": 30, "stueckMin": 2.5},
				{"id": "ag-2", "name": "Härten", "typ": "fremd", "lieferant": "ZZ Lieferant", "fremdProStk": 1.2, "fremdEinmal": 40},
			],
		})
		self.assertEqual([a["id"] for a in v["arbeitsgaenge"]], ["ag-1", "ag-2"])
		self.assertEqual(v["arbeitsgaenge"][0], {
			"id": "ag-1", "name": "Drehen", "typ": "intern", "maschine": "ZZ M1", "satz": 50, "ruestMin": 30,
			"stueckMin": 2.5, "lieferant": "", "fremdProStk": 0, "fremdEinmal": 0, "anfrageId": "",
		})
		self.assertEqual(v["arbeitsgaenge"][1]["typ"], "fremd")
		self.assertEqual(v["arbeitsgaenge"][1]["fremdEinmal"], 40)

		# Aktualisieren: eine Zeile weniger, Name geändert
		v["name"] = "ZZ Vorlage 2"
		v["arbeitsgaenge"] = v["arbeitsgaenge"][1:]
		w = stamm.vorlage_speichern(v)
		self.assertEqual(w["id"], v["id"])
		self.assertEqual(w["name"], "ZZ Vorlage 2")
		self.assertEqual([a["id"] for a in w["arbeitsgaenge"]], ["ag-2"])

		stamm.vorlage_loeschen(v["id"])
		self.assertFalse(frappe.db.exists("Arbeitsplan Vorlage", v["id"]))

	def test_vorlage_ohne_namen_bekommt_einen(self):
		v = stamm.vorlage_speichern({"name": "  ", "arbeitsgaenge": []})
		self.assertTrue(v["name"])

	def test_kunde_in_der_form_der_oberflaeche(self):
		k = frappe.get_doc({
			"doctype": "Kunde", "kundenname": "ZZ Kunde GmbH", "lieferantennummer": "777",
			"adressen": [{"typ": "Rechnung und Lieferung", "strasse": "Weg 1", "plz": "72000", "ort": "Stadt", "standard": 1}],
			"kontakte": [{"anrede": "Frau", "vorname": "Eva", "nachname": "Muster", "email": "e@m.example", "ist_rechnungskontakt": 1}],
		}).insert()
		ui = stamm.kunde_ui(k)
		self.assertEqual(ui["name"], "ZZ Kunde GmbH")
		self.assertEqual(ui["lieferantennr"], "777")
		self.assertEqual(ui["adresse"], ["Weg 1", "72000 Stadt"])
		self.assertEqual(ui["kontakt"], {"name": "Frau Eva Muster", "email": "e@m.example"})

	def test_kunde_ohne_adresse_und_kontakt(self):
		k = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Leer"}).insert()
		ui = stamm.kunde_ui(k)
		self.assertEqual(ui["adresse"], [])
		self.assertIsNone(ui["kontakt"])
