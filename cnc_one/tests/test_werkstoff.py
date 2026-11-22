import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import stamm, stammdaten, werkstoff


class TestWerkstoffbaum(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_grundbestand_im_bootstrap(self):
		daten = stamm.bootstrap()
		b = daten["werkstoffbaum"]
		self.assertIn("T651", [z["code"] for z in b["zustaende"]])
		self.assertIn("Ultraschallgeprüft", [a["name"] for a in b["anforderungen"]])
		rund = [a for a in b["abmessungen"] if a["form"] == "Rund"]
		self.assertEqual([a["m1"] for a in rund], sorted(a["m1"] for a in rund))  # Reihe aufsteigend
		self.assertIn("Ø40", [a["text"] for a in rund])
		gepresst = next(a for a in b["ausfuehrungen"] if a["form"] == "Rund" and a["name"] == "gepresst")
		self.assertEqual(gepresst["iso"], ["N"])
		w = next(m for m in daten["materialien"] if m["name"] == "EN AW-7075")
		self.assertEqual((w["isoGruppe"], w["kurz"], w["zustaende"]), ("N", "AlZn5,5MgCu", ["T6", "T651", "T7351"]))
		self.assertIn("3.4365", w["schreibweisen"])

	def test_in_jeder_stufe_neu_anlegen(self):
		w = werkstoff.werkstoff_anlegen("ZZ 1.9999", "P", kurz="ZZStahl", dichte=7.8, preisKg=3, formen=["Rund", "Quatsch"])
		self.assertEqual((w["isoGruppe"], w["kurz"], w["formen"], w["zustaende"]), ("P", "ZZStahl", ["Rund"], []))
		with self.assertRaises(frappe.ValidationError):
			werkstoff.werkstoff_anlegen("ZZ 1.9999", "P")
		with self.assertRaises(frappe.ValidationError):
			werkstoff.werkstoff_anlegen("ZZ 2", "X")
		r = werkstoff.zustand_hinzu("ZZ 1.9999", "ZZ+QT900", "vergütet 900")
		self.assertEqual(r["werkstoff"]["zustaende"], ["ZZ+QT900"])
		self.assertEqual(werkstoff.zustand_hinzu("ZZ 1.9999", "+QT")["werkstoff"]["zustaende"], ["ZZ+QT900", "+QT"])
		self.assertEqual(werkstoff.form_freigeben("ZZ 1.9999", "Platte")["formen"], ["Rund", "Platte"])
		a = werkstoff.ausfuehrung_hinzu("Rund", "ZZ geschliffen h6", "p x")
		self.assertEqual((a["form"], a["iso"]), ("Rund", ["P"]))
		self.assertEqual(werkstoff.ausfuehrung_hinzu("Rund", "ZZ geschliffen h6", "M")["id"], a["id"])  # kein Doppel
		m = werkstoff.abmessung_hinzu("Rohr", 43, 4.5)
		self.assertEqual(m["text"], "Ø43 × 4,5")
		self.assertEqual(werkstoff.abmessung_hinzu("Rohr", 43, 4.5)["id"], m["id"])
		with self.assertRaises(frappe.ValidationError):
			werkstoff.abmessung_hinzu("Rohr", 10, 5)
		with self.assertRaises(frappe.ValidationError):
			werkstoff.abmessung_hinzu("Flach", 40, 0)
		self.assertEqual(werkstoff.abmessung_hinzu("Rund", 43, 9)["m2"], 0)
		werkstoff.anforderung_hinzu("ZZ Röntgengeprüft")
		self.assertIn("ZZ Röntgengeprüft", [x["name"] for x in werkstoff.baum()["anforderungen"]])

	def test_pflege_aktiv_und_loeschen(self):
		werkstoff.werkstoff_anlegen("ZZ W", "N")
		werkstoff.zustand_hinzu("ZZ W", "ZZ-T9")
		b = werkstoff.eintrag_setzen("zustand", "ZZ-T9", aktiv=0, beschreibung="Test")
		z = next(x for x in b["zustaende"] if x["code"] == "ZZ-T9")
		self.assertEqual((z["aktiv"], z["beschreibung"]), (False, "Test"))
		self.assertNotIn("ZZ-T9", [x["code"] for x in werkstoff.baum()["zustaende"]])
		werkstoff.eintrag_loeschen("zustand", "ZZ-T9")
		self.assertEqual(stammdaten.material_ui(frappe.get_doc("Material", "ZZ W"))["zustaende"], [])

	def test_charge_und_kundenvorgabe(self):
		abm = werkstoff.abmessung_hinzu("Rund", 40)
		c = werkstoff.charge_speichern({
			"werkstoff": "EN AW-7075", "zustand": "T7351", "abmessung": abm["id"], "ausfuehrung": "gezogen h11", "chargennr": "S-4711",
			"laenge": 3000, "stueck": 2, "zeugnis": "3.1", "pruefungen": ["Ultraschallgeprüft", "Gibt es nicht"], "lagerplatz": "R-03",
		})
		self.assertEqual((c["form"], c["abmessungText"], c["pruefungen"], c["status"]), ("Rund", "Ø40", ["Ultraschallgeprüft"], "Vorrätig"))
		self.assertIn(c["id"], [x["id"] for x in werkstoff.chargen("EN AW-7075")])
		werkstoff.charge_speichern({"id": c["id"], "status": "Aufgebraucht"})
		self.assertNotIn(c["id"], [x["id"] for x in werkstoff.chargen("EN AW-7075")])
		self.assertIn(c["id"], [x["id"] for x in werkstoff.chargen("EN AW-7075", alle=1)])
		with self.assertRaises(frappe.ValidationError):
			werkstoff.eintrag_loeschen("abmessung", abm["id"])
		with self.assertRaises(frappe.ValidationError):
			werkstoff.charge_speichern({"werkstoff": "EN AW-7075", "abmessung": abm["id"]})  # Länge fehlt
		k = stammdaten.speichern("kunde", {"name": "ZZ Luftfahrt", "materialZeugnis": "3.1", "materialPruefungen": ["Ultraschallgeprüft", "Quatsch"]})
		self.assertEqual((k["materialZeugnis"], k["materialPruefungen"]), ("3.1", ["Ultraschallgeprüft"]))
		ui = stamm.kunde_ui(frappe.get_doc("Kunde", k["id"]))
		self.assertEqual(ui["materialVorgabe"], {"zeugnis": "3.1", "pruefungen": ["Ultraschallgeprüft"]})

	def test_roh_angaben_fuer_die_fertigung(self):
		teil = {"roh": {
			"form": "Rund", "abmessung": "Ø40", "zustand": "T7351", "ausfuehrung": "gezogen h11", "laenge": 82, "saege": 3,
			"anforderungen": {"zeugnis": "3.1", "pruefungen": ["Ultraschallgeprüft"]},
		}}
		self.assertEqual(werkstoff.roh_angaben(teil), ("Rund Ø40 · T7351 · gezogen h11 · Zuschnitt 82 mm · Zeugnis 3.1, Ultraschallgeprüft", "", ""))
		self.assertEqual(werkstoff.roh_angaben({}), ("", "", ""))
		platte = {"roh": {"form": "Platte", "abmessung": "20 mm", "laenge": 120.5, "breite": 48, "zeugnis": "2.2"}}
		self.assertEqual(werkstoff.roh_angaben(platte)[0], "Platte 20 mm · Zuschnitt 48 × 120,5 mm · Zeugnis 2.2")

	def test_materialanfrage_mit_anforderungen(self):
		from cnc_one.api import anfrage

		if not frappe.db.exists("Lieferant", "ZZ Metallhandel"):
			frappe.get_doc({"doctype": "Lieferant", "lieferantenname": "ZZ Metallhandel", "aktiv": 1}).insert()
		neu = anfrage.anlegen(lieferanten=["ZZ Metallhandel"], art="Material", positionen=[{
			"teil": {"name": "EN AW-7075 T7351 · Rund Ø40", "material": "EN AW-7075 T7351"}, "abmessung": "Rund Ø40 · gezogen h11",
			"anforderungen": "Zeugnis 3.1, Ultraschallgeprüft", "einheit": "m", "mengen": [3, 6],
		}])
		p = neu[0]["positionen"][0]
		self.assertEqual((p["key"], p["anforderungen"], p["einheit"], p["mengen"]), ("frei:1", "Zeugnis 3.1, Ultraschallgeprüft", "m", [3, 6]))
