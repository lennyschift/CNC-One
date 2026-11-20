import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import einstellung


class TestListenfilter(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_je_benutzer_und_liste(self):
		self.assertIsNone(einstellung.filter_holen("zz-liste"))
		daten = {"filter": [{"pfad": "status", "typ": "auswahl", "wert": ["Offen"]}], "angeheftet": ["kundeName"], "ansichten": [], "fremd": 1}
		einstellung.filter_speichern("zz-liste", daten)
		einstellung.filter_speichern("zz-liste", {**daten, "angeheftet": ["status"]})  # ersetzt, kein zweiter Eintrag
		r = einstellung.filter_holen("zz-liste")
		self.assertEqual((r["angeheftet"], r["filter"][0]["wert"]), (["status"], ["Offen"]))
		self.assertNotIn("fremd", r)
		self.assertEqual(frappe.db.count("Listenfilter", {"modul": "zz-liste"}), 1)
		# ein anderer Benutzer sieht sie nicht
		frappe.set_user("Guest")
		frappe.session.user = "Guest"
		self.assertIsNone(frappe.db.get_value("Listenfilter", {"benutzer": "Guest", "modul": "zz-liste"}, "daten"))

	def test_sortierung(self):
		einstellung.filter_speichern("zz-sort", {"filter": [], "sortierung": {"pfad": "termin", "richtung": "ab", "x": 1}})
		self.assertEqual(einstellung.filter_holen("zz-sort")["sortierung"], {"pfad": "termin", "richtung": "ab"})
		einstellung.filter_speichern("zz-sort", {"filter": [], "sortierung": {"richtung": "ab"}})
		self.assertIsNone(einstellung.filter_holen("zz-sort")["sortierung"])
