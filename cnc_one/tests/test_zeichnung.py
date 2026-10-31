import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import zeichnung


class TestZeichnungsvorlage(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Vorlagenkunde"}).insert().name

	def tearDown(self):
		frappe.db.rollback()

	def test_ohne_angelerntes_ist_die_vorlage_leer(self):
		self.assertEqual(zeichnung.vorlage(self.kunde)["felder"], {})

	def test_lernen_merkt_stichwort_mit_versatz_und_bereich(self):
		v = zeichnung.lernen(self.kunde, {"teilenummer": [{"stichwort": "  Ident-Nr. Kunde: ", "dx": 0.07412, "dy": -0.002}, {"bereich": {"x": 0.512345, "y": 0.9, "b": 0.1, "h": 0.02}}]})
		self.assertEqual(v["felder"]["teilenummer"], [{"stichwort": "ident-nr. kunde", "dx": 0.0741, "dy": -0.002}, {"bereich": {"x": 0.5123, "y": 0.9, "b": 0.1, "h": 0.02}}])
		self.assertEqual(zeichnung.vorlage(self.kunde)["felder"], v["felder"])
		self.assertTrue(v["geaendert"])

	def test_regeln_eines_feldes_werden_ersetzt_andere_bleiben(self):
		zeichnung.lernen(self.kunde, {"werkstoff": [{"stichwort": "mat"}], "revision": [{"stichwort": "ae"}]})
		v = zeichnung.lernen(self.kunde, {"werkstoff": [{"stichwort": "b"}, {"stichwort": "b"}, {"stichwort": "c"}, {"stichwort": "d"}, {"stichwort": "e"}, {"stichwort": "f"}]})
		self.assertEqual(v["felder"]["werkstoff"], [{"stichwort": "b"}, {"stichwort": "c"}, {"stichwort": "d"}, {"stichwort": "e"}])
		self.assertEqual(v["felder"]["revision"], [{"stichwort": "ae"}])

	def test_vergessen_und_ungueltiges(self):
		zeichnung.lernen(self.kunde, {"werkstoff": [{"stichwort": "mat"}], "revision": [{"stichwort": "ae"}]})
		self.assertEqual(list(zeichnung.vergessen(self.kunde, "werkstoff")["felder"]), ["revision"])
		self.assertEqual(zeichnung.vergessen(self.kunde)["felder"], {})
		with self.assertRaises(frappe.ValidationError):
			zeichnung.lernen(self.kunde, {"preis": [{"stichwort": "x"}]})
		with self.assertRaises(frappe.ValidationError):
			zeichnung.lernen(self.kunde, {"werkstoff": [{"bereich": {"x": 0.1, "y": 0.1, "b": 0, "h": 0.1}}]})
		with self.assertRaises(frappe.ValidationError):
			zeichnung.vorlage("K-GIBTSNICHT")


class TestRohmaterialSchreibweisen(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.m = frappe.get_doc({"doctype": "Material", "materialname": "ZZ 1.4301 Edelstahl", "preis_kg": 7}).insert().name

	def tearDown(self):
		frappe.db.rollback()

	def test_schreibweise_wird_einmal_gemerkt_und_ausgeliefert(self):
		zeichnung.schreibweise_merken(self.m, " X5CrNi18-10 ")
		r = zeichnung.schreibweise_merken(self.m, "x5crni18-10")
		self.assertEqual(r["schreibweisen"], ["X5CrNi18-10"])
		self.assertEqual(zeichnung.schreibweise_merken(self.m, "ZZ 1.4301 Edelstahl")["schreibweisen"], ["X5CrNi18-10"])
		from cnc_one.api.stamm import stammdaten
		m = next(x for x in stammdaten()["materialien"] if x["name"] == self.m)
		self.assertEqual(m["schreibweisen"], ["X5CrNi18-10"])

	def test_rohmaterial_anlegen_oder_vorhandenes_liefern(self):
		r = zeichnung.rohmaterial_anlegen("ZZ 1.7131 16MnCr5", "16MnCr5")
		self.assertEqual((r["name"], r["preisKg"], r["schreibweisen"]), ("ZZ 1.7131 16MnCr5", 0, ["16MnCr5"]))
		self.assertEqual(zeichnung.rohmaterial_anlegen(self.m, "V2A")["schreibweisen"], ["V2A"])
		with self.assertRaises(frappe.ValidationError):
			zeichnung.rohmaterial_anlegen("  ")
