import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import anfrage, angebot, stamm
from cnc_one.tests.test_angebot import teil


def position(teil_id="t1", ag="a1", name="Flansch", nr="ZZ-A1", mengen=(10, 25)):
	return {
		"teilId": teil_id, "agId": ag, "agName": "Härten", "mengen": list(mengen),
		"teil": {"name": name, "teilenummer": nr, "zeichnungsnr": "Z-1", "material": "1.4301"},
	}


class TestAnfrage(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Anfragekunde"}).insert().name
		for n in ("ZZ Härterei A", "ZZ Härterei B"):
			frappe.get_doc({"doctype": "Lieferant", "lieferantenname": n}).insert()
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", teilenummer="ZZ-A1")]})
		self.angebot = a["id"]

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_pro_lieferant_eine_anfrage_mit_allen_positionen(self):
		neu = anfrage.anlegen(self.angebot, ["ZZ Härterei A", "ZZ Härterei B"], [position(), position("t2", "a2", "Welle", "ZZ-A2", (5,))], "bitte maskieren")
		self.assertEqual(len(neu), 2)
		self.assertEqual(len({x["id"] for x in neu}), 2)
		a = neu[0]
		self.assertTrue(a["id"].startswith("LA-"))
		self.assertEqual((a["status"], a["angebotId"], a["kundeName"], a["notiz"]), ("Gesendet", self.angebot, "ZZ Anfragekunde", "bitte maskieren"))
		self.assertEqual(a["lieferantName"], "ZZ Härterei A")
		self.assertEqual([p["key"] for p in a["positionen"]], ["t1:a1", "t2:a2"])
		self.assertEqual(a["positionen"][0]["mengen"], [10, 25])
		self.assertEqual(a["positionen"][0]["teil"]["teilenummer"], "ZZ-A1")
		self.assertEqual(a["positionen"][0]["agName"], "Härten")
		self.assertIsNone(a["antwort"])

	def test_mengen_werden_bereinigt(self):
		a = anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position(mengen=(25, 10, 10, 0))])[0]
		self.assertEqual(a["positionen"][0]["mengen"], [10, 25])

	def test_eingaben_werden_geprueft(self):
		with self.assertRaises(frappe.ValidationError):
			anfrage.anlegen(self.angebot, [], [position()])
		with self.assertRaises(frappe.ValidationError):
			anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [])
		with self.assertRaises(frappe.ValidationError):
			anfrage.anlegen(self.angebot, ["Gibt es nicht"], [position()])
		with self.assertRaises(frappe.ValidationError):
			anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position(mengen=())])

	def test_antwort_erfassen_und_aktualisieren(self):
		a = anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position()])[0]
		preise = [{"posKey": "t1:a1", "menge": 10, "proStk": 1.5, "einmalig": 40}, {"posKey": "t1:a1", "menge": 25, "proStk": 1.1, "einmalig": 40}]
		r = anfrage.antwort_erfassen(a["id"], {"angebotsnr": "AN-5521", "gueltigBis": "2026-12-31", "preise": preise})
		self.assertEqual(r["status"], "Angebot erhalten")
		self.assertEqual(r["antwort"], {"angebotsnr": "AN-5521", "gueltigBis": "2026-12-31", "preise": preise})
		neu = anfrage.antwort_erfassen(a["id"], {"angebotsnr": "AN-5521b", "gueltigBis": "", "preise": preise[:1]})
		self.assertEqual(len(neu["antwort"]["preise"]), 1)
		self.assertEqual(neu["antwort"]["gueltigBis"], "")

	def test_antwort_braucht_preise_zu_bekannten_positionen(self):
		a = anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position()])[0]
		with self.assertRaises(frappe.ValidationError):
			anfrage.antwort_erfassen(a["id"], {"preise": [{"posKey": "t1:a1", "menge": 10, "proStk": 0, "einmalig": 0}]})
		with self.assertRaises(frappe.ValidationError):
			anfrage.antwort_erfassen(a["id"], {"preise": [{"posKey": "x:y", "menge": 10, "proStk": 2, "einmalig": 0}]})

	def test_absagen_nur_wenn_gesendet(self):
		a = anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position()])[0]
		self.assertEqual(anfrage.absagen(a["id"])["status"], "Abgesagt")
		with self.assertRaises(frappe.ValidationError):
			anfrage.absagen(a["id"])

	def test_liste_und_bootstrap(self):
		a = anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position()])[0]
		self.assertIn(a["id"], [x["id"] for x in anfrage.liste()])
		self.assertIn(a["id"], [x["id"] for x in stamm.bootstrap()["anfragen"]])

	def test_angebot_mit_anfragen_laesst_sich_nicht_loeschen(self):
		anfrage.anlegen(self.angebot, ["ZZ Härterei A"], [position()])
		with self.assertRaises(frappe.ValidationError):
			angebot.loeschen(self.angebot)

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			anfrage.liste()
