from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import druckvorlage
from cnc_one.logic import briefbogen, vorlagen

DATEI = "beleg_kopf.html"


class TestDruckvorlage(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_ohne_aenderung_gilt_der_code(self):
		self.assertEqual(vorlagen.lesen(DATEI), vorlagen.aus_code(DATEI))
		self.assertFalse(druckvorlage.holen(DATEI)["geaendert"])

	def test_speichern_gilt_und_steht_im_verlauf(self):
		neu = vorlagen.aus_code(DATEI) + "\n<!-- ZZ-Probe -->"
		r = druckvorlage.speichern(DATEI, neu, "ZZ Test")
		self.assertTrue(r["geaendert"])
		self.assertIn("ZZ-Probe", vorlagen.lesen(DATEI))
		self.assertIn("ZZ-Probe", briefbogen.rahmen({"firmenname": "ZZ"})["kopf"])  # wird beim Druck verwendet
		self.assertEqual(r["staende"][0]["notiz"], "ZZ Test")
		self.assertIn("ZZ-Probe", druckvorlage.stand_inhalt(r["staende"][0]["id"]))
		# zurück auf den Code-Stand; der geänderte bleibt im Verlauf
		r = druckvorlage.zuruecksetzen(DATEI)
		self.assertFalse(r["geaendert"])
		self.assertEqual(vorlagen.lesen(DATEI), vorlagen.aus_code(DATEI))
		self.assertEqual(r["staende"][0]["aktion"], "vor dem Zurücksetzen")

	def test_gleich_dem_code_entfernt_die_aenderung(self):
		code = vorlagen.aus_code(DATEI)
		druckvorlage.speichern(DATEI, code + "x")
		self.assertFalse(druckvorlage.speichern(DATEI, code)["geaendert"])
		self.assertFalse(frappe.db.exists("Druckvorlage", DATEI))

	def test_syntaxfehler_wird_nicht_gespeichert(self):
		with self.assertRaises(frappe.ValidationError):
			druckvorlage.speichern(DATEI, "{% if a %}offen")
		self.assertFalse(frappe.db.exists("Druckvorlage", DATEI))
		self.assertIn("Zeile", druckvorlage.vorschau(DATEI, "{{ a. }}", "Firma")["fehler"])

	def test_unbekannte_datei(self):
		with self.assertRaises(frappe.ValidationError):
			druckvorlage.holen("../hooks.py")

	def test_vorschau_mit_ungespeichertem_stand(self):
		gesehen = {}
		from cnc_one.logic import pdf

		with patch.object(pdf, "pdf_a3", side_effect=lambda html, **kw: gesehen.setdefault("html", html) and b"%PDF"):
			r = druckvorlage.vorschau("briefbogen_muster.html", vorlagen.aus_code("briefbogen_muster.html") + "<p>ZZ-Vorschau</p>", "Firma")
		self.assertIn("pdf", r)
		self.assertIn("ZZ-Vorschau", gesehen["html"])
		self.assertNotIn("ZZ-Vorschau", vorlagen.lesen("briefbogen_muster.html"))  # nichts gespeichert

	def test_in_den_code_nur_auf_dem_testsystem(self):
		neu = vorlagen.aus_code(DATEI) + "\n<!-- ZZ-Code -->"
		druckvorlage.speichern(DATEI, neu)
		geschrieben = {}
		with patch.object(vorlagen, "in_datei_schreiben", side_effect=lambda d, i: geschrieben.update({d: i})):
			with patch.dict(frappe.conf, {"developer_mode": 0}):
				with self.assertRaises(frappe.ValidationError):
					druckvorlage.in_den_code(DATEI)
			with patch.dict(frappe.conf, {"developer_mode": 1}):
				r = druckvorlage.in_den_code(DATEI)
		self.assertEqual(geschrieben, {DATEI: neu})
		self.assertFalse(frappe.db.exists("Druckvorlage", DATEI))
		self.assertEqual(r["staende"][0]["aktion"], "in den Code übernommen")

	def test_nur_administratoren_aendern(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			druckvorlage.speichern(DATEI, "x")
