import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from cnc_one.api import aehnlich, teilefamilie
from cnc_one.logic import aehnlichkeit as ae


def geo(masse, d2, fuell=0.9):
	a, b, c = masse
	return {"v": 1, "masse": masse, "volumen": a * b * c * fuell, "flaeche": 2 * (a * b + a * c + b * c), "fuell": fuell, "d2": d2}


FORM_A = [0.02, 0.05, 0.1, 0.15, 0.18, 0.17, 0.13, 0.1, 0.06, 0.03, 0.01]
FORM_B = [0.3, 0.25, 0.15, 0.1, 0.08, 0.05, 0.03, 0.02, 0.01, 0.005, 0.005]


class TestAehnlichkeitLogik(UnitTestCase):
	def test_teilenummern(self):
		self.assertEqual(ae.nummer("4711-123A", "4711-123C"), (0.95, "anderer Index (A → C)"))
		self.assertEqual(ae.nummer("8F8-1234", "P28-1234"), (0.9, "andere Baustufe (8F8 → P28)"))
		self.assertEqual(ae.nummer("8f8-1234-a", "P28-1234-A")[1], "andere Baustufe (8F8 → P28)")
		self.assertEqual(ae.nummer("8F81234", "P281234")[0], 0.85)
		self.assertEqual(ae.nummer("ZN-3003-01", "ZN 3003.01"), (1.0, "gleiche Teilenummer"))
		self.assertEqual(ae.nummer("ZN-3003-01", "ZN-3103-01")[1], "eine Stelle anders (3003 → 3103)")
		self.assertIsNone(ae.nummer("4711", "9999"))
		self.assertIsNone(ae.nummer("", "4711"))

	def test_bezeichnung_rohteil_geometrie(self):
		self.assertEqual(ae.bezeichnung("Welle lang", "Welle lang")[1], "gleiche Bezeichnung")
		self.assertIsNotNone(ae.bezeichnung("Gewindebolzen M8 lang", "Gewindebolzen M8 kurz"))
		self.assertIsNone(ae.bezeichnung("Flansch", "Welle"))
		r = ae.rohteil({"form": "Rund", "durchmesser": 40, "laenge": 120}, {"form": "Rund", "durchmesser": 42, "laenge": 125})
		self.assertTrue(r and r[1].startswith("ähnliches Rohteil (Rund 42 × 125"))
		self.assertIsNone(ae.rohteil({"form": "Rund", "durchmesser": 40, "laenge": 120}, {"form": "Rund", "durchmesser": 60, "laenge": 120}))
		self.assertIsNone(ae.rohteil({"form": "Rund", "durchmesser": 40, "laenge": 120}, {"form": "Flach", "laenge": 120, "breite": 40, "hoehe": 40}))
		# gleiche Form und Größe, gleiche Form in doppelter Größe, andere Form
		g = ae.geometrie(geo([100, 40, 20], FORM_A), geo([101, 40, 20], FORM_A))
		self.assertGreater(g["gesamt"], 0.95)
		self.assertTrue(ae.geometrie_grund(g)[1].startswith("ähnliche Geometrie"))
		g2 = ae.geometrie(geo([100, 40, 20], FORM_A), geo([200, 80, 40], FORM_A))
		self.assertTrue(ae.geometrie_grund(g2)[1].startswith("gleiche Form, andere Größe"))
		self.assertIsNone(ae.geometrie_grund(ae.geometrie(geo([100, 40, 20], FORM_A), geo([100, 40, 20], FORM_B, fuell=0.3))))
		self.assertIsNone(ae.geometrie({"v": 2, "d2": FORM_A}, geo([1, 1, 1], FORM_A)))

	def test_bewerten_und_finden(self):
		a = {"teilenummer": "8F8-1234", "material": "EN AW-7075", "geo": geo([100, 40, 20], FORM_A)}
		kandidaten = [
			{"name": "x", "teilenummer": "P28-1234", "material": "EN AW-7075"},
			{"name": "y", "teilenummer": "999-777", "geo": geo([100, 40, 21], FORM_A)},
			{"name": "z", "teilenummer": "555", "material": "EN AW-7075"},
		]
		t = ae.finden(a, kandidaten)
		self.assertEqual([b["name"] for _p, _g, b in t], ["x", "y"])
		self.assertEqual(t[0][1], ["andere Baustufe (8F8 → P28)", "gleicher Werkstoff"])
		self.assertGreater(t[0][0], 0.9)
		self.assertTrue(t[1][1][0].startswith("ähnliche Geometrie"))

	def test_familien_vorschlaege(self):
		b = [
			{"name": "1", "kunde": "k", "teilenummer": "4711-10A", "zeichnungsnr": ""},
			{"name": "2", "kunde": "k", "teilenummer": "4711-10B", "zeichnungsnr": ""},
			{"name": "3", "kunde": "k", "teilenummer": "B-12", "zeichnungsnr": "Z-99"},
			{"name": "4", "kunde": "k", "teilenummer": "B-16", "zeichnungsnr": "Z 99"},
			{"name": "5", "kunde": "k", "teilenummer": "B-20", "zeichnungsnr": "Z-99", "teilefamilie": "TF-1"},
			{"name": "6", "kunde": "j", "teilenummer": "4711-10C", "zeichnungsnr": ""},
		]
		g = ae.familien_vorschlaege(b)
		self.assertEqual([(x["grund"], [y["name"] for y in x["bauteile"]], x["varianten"]) for x in g], [
			("gleiche Zeichnung Z-99", ["3", "4"], ["12", "16"]),
			("gleiche Nummer, verschiedener Index (A, B)", ["1", "2"], ["A", "B"]),
		])


class TestAehnlichUndFamilien(IntegrationTestCase):
	def setUp(self):
		from cnc_one.tests.dateischutz import dateien_vorher

		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Ähnlich GmbH"}).insert().name
		self.b = {}
		for nr, name, z in (("ZZ8F8-1234", "Gewindebolzen M8", "ZZ-Z1"), ("ZZP28-1234", "Gewindebolzen M8", "ZZ-Z1"), ("ZZ-4711-A", "Flansch", ""), ("ZZ-4711-B", "Flansch", "")):
			self.b[nr] = frappe.get_doc({"doctype": "Bauteil", "kunde": self.kunde, "teilenummer": nr, "bezeichnung": name, "zeichnungsnr": z}).insert().name

	def tearDown(self):
		from cnc_one.tests.dateischutz import eigene_dateien_loeschen

		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def test_aehnliche_mit_geometrie(self):
		aehnlich.fingerabdruck_speichern(self.b["ZZ-4711-B"], geo([100, 40, 20], FORM_A))
		self.assertIn(self.b["ZZ-4711-A"], {x["id"] for x in aehnlich.ohne_fingerabdruck()} | {self.b["ZZ-4711-A"]})
		r = aehnlich.aehnliche(bauteil=self.b["ZZ8F8-1234"])
		ids = [x["id"] for x in r["treffer"]]
		self.assertEqual(ids[0], self.b["ZZP28-1234"])
		self.assertIn("andere Baustufe (ZZ8F8 → ZZP28)", r["treffer"][0]["gruende"])
		self.assertNotIn(self.b["ZZ8F8-1234"], ids)
		# Workbench-Bauteil ohne Bauteil: nur über die Geometrie
		r2 = aehnlich.aehnliche(kunde=self.kunde, teilenummer="ZZ-NEU-1", geo=geo([100, 40, 20.5], FORM_A))
		self.assertEqual(r2["treffer"][0]["id"], self.b["ZZ-4711-B"])
		self.assertTrue(r2["mitGeometrie"])
		with self.assertRaises(frappe.ValidationError):
			aehnlich.fingerabdruck_speichern(self.b["ZZ-4711-A"], {"v": 1, "masse": [1]})

	def test_teilefamilie_anlegen_aendern_aufloesen(self):
		vs = {v["schluessel"]: v for v in teilefamilie.vorschlaege()}
		self.assertTrue(any(v["grund"] == "gleiche Zeichnung ZZ-Z1" for v in vs.values()))
		f = teilefamilie.speichern({"bezeichnung": "ZZ Bolzen", "merkmal": "Baustufe", "bauteile": [{"id": self.b["ZZ8F8-1234"], "variante": "8F8"}, {"id": self.b["ZZP28-1234"], "variante": "P28"}]})
		self.assertEqual((f["kundeId"], [v["variante"] for v in f["varianten"]]), (self.kunde, ["8F8", "P28"]))
		self.assertEqual(teilefamilie.fuer_bauteil(self.b["ZZP28-1234"])["id"], f["id"])
		self.assertFalse(any(v["grund"] == "gleiche Zeichnung ZZ-Z1" for v in teilefamilie.vorschlaege()))
		# ein Bauteil wechselt in eine andere Familie; die alte hat dann nur noch eins und löst sich auf
		g = teilefamilie.speichern({"bezeichnung": "ZZ Flansch", "bauteile": [self.b["ZZ-4711-A"], self.b["ZZ-4711-B"], {"id": self.b["ZZP28-1234"], "variante": "x"}]})
		self.assertEqual(len(g["varianten"]), 3)
		self.assertFalse(frappe.db.exists("Teilefamilie", f["id"]))
		self.assertIsNone(frappe.db.get_value("Bauteil", self.b["ZZ8F8-1234"], "teilefamilie"))
		with self.assertRaises(frappe.ValidationError):
			teilefamilie.speichern({"bezeichnung": "ZZ zu klein", "bauteile": [self.b["ZZ8F8-1234"]]})
		teilefamilie.aufloesen(g["id"])
		self.assertIsNone(frappe.db.get_value("Bauteil", self.b["ZZ-4711-A"], "teilefamilie"))
		self.assertIsNone(teilefamilie.fuer_bauteil(self.b["ZZ-4711-A"]))

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			aehnlich.aehnliche(teilenummer="x")
		with self.assertRaises(frappe.PermissionError):
			teilefamilie.liste()
