import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, auftrag, bauteil
from cnc_one.logic.beleg import position_fuer_auftrag
from cnc_one.logic.kalkulation import berechne
from cnc_one.tests.test_angebot import teil


class TestAuftrag(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Auftragskunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def gesendet(self, teile):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": teile})
		return angebot.senden(a["id"])

	def test_auftrag_aus_einzelangebot(self):
		t = teil("t1")
		a = self.gesendet([t])
		r = auftrag.aus_angebot(a["id"], "PO-1", [{"angebotKey": "t1", "menge": 10, "termin": "2026-12-01"}])
		erwartet = position_fuer_auftrag(t, berechne(t), None, 10)
		self.assertTrue(r["id"].startswith("AUF-"))
		self.assertEqual(r["status"], "Offen")
		self.assertEqual(r["kundenbestellnr"], "PO-1")
		self.assertEqual(r["angebotId"], a["id"])
		self.assertEqual(r["kundeName"], "ZZ Auftragskunde")
		p = r["positionen"][0]
		self.assertEqual(p["menge"], 10)
		self.assertEqual(p["einzelpreis"], erwartet["einzelpreis"])
		self.assertEqual(p["kosten"], erwartet["kosten"])
		self.assertEqual(p["summe"], erwartet["summe"])
		self.assertEqual(p["termin"], "2026-12-01")
		self.assertEqual(p["angebotKey"], "t1")
		self.assertAlmostEqual(r["netto"], erwartet["summe"], places=2)

	def test_staffel_menge_und_abgewaehlte_kosten(self):
		t = teil("t1", staffel={"aktiv": True, "stufen": [{"menge": 5, "extra": 0}, {"menge": 25, "extra": 1}]})
		a = self.gesendet([t])
		r = auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "optionId": "25", "menge": 30, "kostenAus": ["Messkosten"]}])
		erwartet = position_fuer_auftrag(t, berechne(t), "25", 30, ["Messkosten"])
		p = r["positionen"][0]
		self.assertEqual(p["staffelMenge"], 25)
		self.assertEqual(p["menge"], 30)
		self.assertEqual(p["summe"], erwartet["summe"])
		self.assertNotIn("Messkosten", [k["label"] for k in p["kosten"]])

	def test_dasselbe_angebot_laesst_sich_mehrfach_beauftragen(self):
		a = self.gesendet([teil("t1")])
		eins = auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 4}])
		zwei = auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 6}])
		self.assertNotEqual(eins["id"], zwei["id"])
		self.assertEqual({x["id"] for x in auftrag.liste() if x["angebotId"] == a["id"]}, {eins["id"], zwei["id"]})

	def test_nur_gesendete_angebote_und_bekannte_positionen(self):
		entwurf = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1")]})
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(entwurf["id"], "", [{"angebotKey": "t1", "menge": 1}])
		a = self.gesendet([teil("t1")])
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(a["id"], "", [{"angebotKey": "gibt-es-nicht", "menge": 1}])
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(a["id"], "", [])

	def test_arbeitsplan_wird_am_bauteil_gespeichert(self):
		a = self.gesendet([teil("t1", teilenummer="ZZ-77")])
		plan = [{"id": "x1", "name": "Drehen", "typ": "intern", "satz": 100, "ruestMin": 30, "stueckMin": 2}]
		r = auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 3, "arbeitsgaenge": plan, "planSpeichern": True}])
		self.assertEqual([x["name"] for x in r["positionen"][0]["arbeitsgaenge"]], ["Drehen"])
		b = bauteil.finden(self.kunde, "ZZ-77")
		self.assertEqual([x["name"] for x in bauteil.bauteil_ui(frappe.get_doc("Bauteil", b))["arbeitsgaenge"]], ["Drehen"])

	def test_ohne_haken_bleibt_der_plan_nur_im_auftrag(self):
		a = self.gesendet([teil("t1", teilenummer="ZZ-78")])
		plan = [{"id": "x1", "name": "Fräsen", "typ": "intern"}]
		auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 3, "arbeitsgaenge": plan, "planSpeichern": False}])
		b = bauteil.finden(self.kunde, "ZZ-78")
		self.assertEqual(frappe.get_doc("Bauteil", b).arbeitsplan, [])

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			auftrag.liste()
