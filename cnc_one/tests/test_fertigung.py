import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, auftrag, bauteil, fertigung
from cnc_one.tests.test_angebot import teil

PLAN = [
	{"id": "p1", "name": "Drehen", "typ": "intern", "satz": 100, "ruestMin": 30, "stueckMin": 2},
	{"id": "p2", "name": "Härten", "typ": "fremd", "lieferant": "ZZ Härterei", "fremdProStk": 1, "fremdEinmal": 0},
	{"id": "p3", "name": "Prüfen", "typ": "intern", "satz": 80, "ruestMin": 0, "stueckMin": 1},
]


class TestFertigung(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Fertigungskunde"}).insert().name
		frappe.get_doc({"doctype": "Lieferant", "lieferantenname": "ZZ Härterei"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def auftrag(self, plan=None, menge=10, teile=None, **kw):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": teile or [teil("t1", teilenummer="ZZ-F1")]})
		a = angebot.senden(a["id"])
		return auftrag.aus_angebot(a["id"], "", [
			{"angebotKey": p["key"], "menge": menge, "termin": "2026-12-01", "arbeitsgaenge": plan or [], **kw} for p in a["positionen"]
		])

	def start(self, plan=PLAN, menge=10):
		r = fertigung.starten(self.auftrag(plan, menge)["id"])
		return r["fertigung"][0]

	def ag(self, fb, name):
		return next(a for a in fb["arbeitsgaenge"] if a["name"] == name)

	# ------------------------------------------------------------- Starten
	def test_starten_legt_pro_position_ein_fertigungsbauteil_an(self):
		a = self.auftrag(PLAN, 10, teile=[teil("t1", teilenummer="ZZ-F1"), teil("t2", "Welle", "ZZ-F2")])
		self.assertEqual(len(a["positionen"]), 2)
		r = fertigung.starten(a["id"])
		self.assertEqual(len(r["fertigung"]), 2)
		fb = r["fertigung"][0]
		self.assertTrue(fb["id"].startswith("FB-"))
		self.assertEqual(fb["status"], "Offen")
		self.assertEqual(fb["menge"], 10)
		self.assertEqual(fb["termin"], "2026-12-01")
		self.assertEqual(fb["kundeName"], "ZZ Fertigungskunde")
		self.assertEqual(fb["teil"]["teilenummer"], "ZZ-F1")
		self.assertEqual([x["name"] for x in fb["arbeitsgaenge"]], ["Drehen", "Härten", "Prüfen"])
		self.assertEqual([x["typ"] for x in fb["arbeitsgaenge"]], ["intern", "fremd", "intern"])
		self.assertEqual(r["auftrag"]["status"], "In Fertigung")
		self.assertEqual(r["ohnePlan"], 0)

	def test_zweites_starten_wird_abgelehnt(self):
		a = self.auftrag(PLAN)
		fertigung.starten(a["id"])
		with self.assertRaises(frappe.ValidationError):
			fertigung.starten(a["id"])

	def test_ohne_arbeitsgaenge_kommt_das_bauteil_trotzdem_an(self):
		r = fertigung.starten(self.auftrag(None)["id"])
		self.assertEqual(r["fertigung"][0]["arbeitsgaenge"], [])
		self.assertEqual(r["ohnePlan"], 1)

	def test_plan_kommt_vom_bauteil_wenn_der_auftrag_keinen_hat(self):
		b = bauteil.plan_setzen(self.kunde, "ZZ-F1", PLAN[:1], "Flansch")
		self.assertTrue(b)
		r = fertigung.starten(self.auftrag(None)["id"])
		self.assertEqual([x["name"] for x in r["fertigung"][0]["arbeitsgaenge"]], ["Drehen"])

	def test_plan_kommt_aus_dem_angebot_wenn_nichts_anderes_da_ist(self):
		t = teil("t1", teilenummer="ZZ-F1", arbeitsgaenge=PLAN[:2])
		r = fertigung.starten(self.auftrag(None, teile=[t])["id"])
		self.assertEqual([x["name"] for x in r["fertigung"][0]["arbeitsgaenge"]], ["Drehen", "Härten"])

	# ------------------------------------------------------------- Buchen
	def test_buchen_hakt_fruehere_arbeitsgaenge_ab(self):
		fb = self.start()
		pruefen = self.ag(fb, "Prüfen")["id"]
		r = fertigung.buchen(fb["id"], pruefen, 4)
		self.assertEqual(r["nachgeholt"], 2)
		neu = r["fb"]
		self.assertEqual([a["gebucht"] for a in neu["arbeitsgaenge"]], [4, 4, 4])
		haerten = self.ag(neu, "Härten")
		self.assertEqual(len(haerten["sendungen"]), 1)
		self.assertTrue(haerten["sendungen"][0]["abgehakt"])
		self.assertEqual(haerten["sendungen"][0]["menge"], 4)
		self.assertEqual(neu["status"], "In Fertigung")
		self.assertEqual(len(neu["buchungen"]), 3)
		self.assertEqual(sum(1 for b in neu["buchungen"] if b["auto"]), 2)
		self.assertEqual(frappe.db.get_value("Fertigungsbauteil", fb["id"], "produziert"), 4)

	def test_fortschritt_ist_das_minimum_und_ueberproduktion_ist_erlaubt(self):
		fb = self.start()
		ids = [a["id"] for a in fb["arbeitsgaenge"]]
		fertigung.buchen(fb["id"], ids[2], 12)
		d = frappe.get_doc("Fertigungsbauteil", fb["id"])
		self.assertEqual((d.produziert, d.ueberproduktion, d.status), (12, 2, "Fertig"))
		self.assertEqual(frappe.db.get_value("Auftrag", fb["auftragId"], "status"), "Fertig")

	def test_fremdvergabe_wird_nicht_direkt_gebucht(self):
		fb = self.start()
		with self.assertRaises(frappe.ValidationError):
			fertigung.buchen(fb["id"], self.ag(fb, "Härten")["id"], 1)

	def test_menge_null_wird_abgelehnt(self):
		fb = self.start()
		with self.assertRaises(frappe.ValidationError):
			fertigung.buchen(fb["id"], self.ag(fb, "Drehen")["id"], 0)

	def test_buchung_stornieren_nimmt_die_menge_zurueck(self):
		fb = self.start()
		drehen = self.ag(fb, "Drehen")["id"]
		r = fertigung.buchen(fb["id"], drehen, 3)
		buchung = r["fb"]["buchungen"][0]["id"]
		neu = fertigung.buchung_loeschen(fb["id"], buchung)["fb"]
		self.assertEqual(self.ag(neu, "Drehen")["gebucht"], 0)
		self.assertEqual(neu["status"], "Offen")
		self.assertEqual(neu["buchungen"], [])

	# ------------------------------------------------------------- Sendungen
	def test_sendungen_mit_teilmengen(self):
		fb = self.start()
		h = self.ag(fb, "Härten")["id"]
		fb1 = fertigung.sendung_anlegen(fb["id"], h, 6)["fb"]
		s1 = self.ag(fb1, "Härten")["sendungen"][0]["id"]
		fb2 = fertigung.sendung_anlegen(fb["id"], h)["fb"]
		self.assertEqual([s["menge"] for s in self.ag(fb2, "Härten")["sendungen"]], [6, 4])
		with self.assertRaises(frappe.ValidationError):
			fertigung.sendung_anlegen(fb["id"], h)
		fb3 = fertigung.sendung_weg(fb["id"], h, s1)["fb"]
		self.assertEqual(self.ag(fb3, "Härten")["status"], "Läuft")
		self.assertTrue(self.ag(fb3, "Härten")["sendungen"][0]["datumWeg"])
		fb4 = fertigung.sendung_zurueck(fb["id"], h, s1)["fb"]
		self.assertEqual(self.ag(fb4, "Härten")["gebucht"], 6)
		# früherer Arbeitsgang (Drehen) wird mit abgehakt
		self.assertEqual(self.ag(fb4, "Drehen")["gebucht"], 6)
		self.assertEqual(self.ag(fb4, "Prüfen")["gebucht"], 0)

	def test_sendung_braucht_einen_lieferanten(self):
		fb = self.start([{"id": "p1", "name": "Beschichten", "typ": "fremd"}])
		a = fb["arbeitsgaenge"][0]["id"]
		s = fertigung.sendung_anlegen(fb["id"], a, 5)["fb"]["arbeitsgaenge"][0]["sendungen"][0]["id"]
		with self.assertRaises(frappe.ValidationError):
			fertigung.sendung_weg(fb["id"], a, s)

	def test_sendung_loeschen_rechnet_den_stand_neu(self):
		fb = self.start()
		h = self.ag(fb, "Härten")["id"]
		s = self.ag(fertigung.sendung_anlegen(fb["id"], h, 5)["fb"], "Härten")["sendungen"][0]["id"]
		fertigung.sendung_zurueck(fb["id"], h, s)
		neu = fertigung.sendung_loeschen(fb["id"], h, s)["fb"]
		self.assertEqual(self.ag(neu, "Härten")["gebucht"], 0)
		self.assertEqual(self.ag(neu, "Härten")["sendungen"], [])

	# ------------------------------------------------------------- Arbeitsplan
	def test_arbeitsgaenge_hinzu_weg_und_verschieben(self):
		fb = self.start(None)
		self.assertEqual(fb["arbeitsgaenge"], [])
		fb = fertigung.arbeitsgang_hinzu(fb["id"], "intern")["fb"]
		fb = fertigung.arbeitsgang_hinzu(fb["id"], "fremd")["fb"]
		a, b = (x["id"] for x in fb["arbeitsgaenge"])
		self.assertEqual([x["typ"] for x in fb["arbeitsgaenge"]], ["intern", "fremd"])
		fb = fertigung.arbeitsgang_verschieben(fb["id"], b, -1)["fb"]
		self.assertEqual([x["id"] for x in fb["arbeitsgaenge"]], [b, a])
		fb = fertigung.arbeitsgang_verschieben(fb["id"], b, -1)["fb"]
		self.assertEqual([x["id"] for x in fb["arbeitsgaenge"]], [b, a])
		fb = fertigung.arbeitsgang_weg(fb["id"], b)["fb"]
		self.assertEqual([x["id"] for x in fb["arbeitsgaenge"]], [a])

	def test_vorlage_anwenden(self):
		v = frappe.get_doc({"doctype": "Arbeitsplan Vorlage", "vorlagenname": "ZZ Vorlage"})
		v.append("arbeitsgaenge", {"ag_id": "v1", "bezeichnung": "Fräsen", "typ": "Intern", "ruest_min": 10, "stueck_min": 3})
		v.insert()
		fb = self.start(None)
		r = fertigung.vorlage_anwenden(fb["id"], v.name)
		self.assertEqual(r["hinzugefuegt"], 1)
		self.assertEqual(r["fb"]["arbeitsgaenge"][0]["name"], "Fräsen")
		self.assertEqual(r["fb"]["arbeitsgaenge"][0]["stueckMin"], 3)
		self.assertNotEqual(r["fb"]["arbeitsgaenge"][0]["id"], "v1")

	def test_plan_am_bauteil_speichern(self):
		fb = self.start()
		r = fertigung.plan_am_bauteil_speichern(fb["id"])
		self.assertEqual([x["name"] for x in r["bauteil"]["arbeitsgaenge"]], ["Drehen", "Härten", "Prüfen"])

	# ------------------------------------------------------------- Status von Hand
	def test_status_fertig_bucht_den_rest(self):
		fb = self.start()
		neu = fertigung.status_setzen(fb["id"], "Fertig")
		self.assertEqual([a["gebucht"] for a in neu["fb"]["arbeitsgaenge"]], [10, 10, 10])
		self.assertEqual(neu["fb"]["status"], "Fertig")
		self.assertEqual(neu["auftragStatus"], "Fertig")

	def test_status_fertig_braucht_arbeitsgaenge(self):
		fb = self.start(None)
		with self.assertRaises(frappe.ValidationError):
			fertigung.status_setzen(fb["id"], "Fertig")

	def test_zurueck_auf_offen_nur_ohne_buchungen(self):
		fb = self.start()
		fertigung.status_setzen(fb["id"], "In Fertigung")
		self.assertEqual(frappe.db.get_value("Fertigungsbauteil", fb["id"], "status"), "In Fertigung")
		fertigung.buchen(fb["id"], self.ag(fb, "Drehen")["id"], 1)
		with self.assertRaises(frappe.ValidationError):
			fertigung.status_setzen(fb["id"], "Offen")

	def test_auftrag_ist_erst_fertig_wenn_alle_bauteile_fertig_sind(self):
		a = self.auftrag(PLAN, 5, teile=[teil("t1", teilenummer="ZZ-F1"), teil("t2", "Welle", "ZZ-F2")])
		r = fertigung.starten(a["id"])
		erstes, zweites = r["fertigung"]
		self.assertEqual(fertigung.status_setzen(erstes["id"], "Fertig")["auftragStatus"], "In Fertigung")
		self.assertEqual(fertigung.status_setzen(zweites["id"], "Fertig")["auftragStatus"], "Fertig")

	# ------------------------------------------------------------- Felder
	def test_felder_speichern_aendert_nur_bearbeitbares(self):
		fb = self.start()
		drehen = self.ag(fb, "Drehen")
		fertigung.buchen(fb["id"], drehen["id"], 3)
		r = fertigung.felder_speichern(fb["id"], {
			"prioritaet": "Eilig", "termin": "2027-01-15",
			"rohmaterial": {"werkstoff": "1.4301", "charge": "24-1", "lagerplatz": "R2", "info": "Ø30", "verbrauchtMm": 120},
			"notizen": {"pruefmasse": "ok", "bemerkungen": "vorsichtig"},
			"arbeitsgaenge": [{**drehen, "name": "Drehen CNC", "stueckMin": 4.5, "gebucht": 99, "status": "Fertig"}],
		})["fb"]
		self.assertEqual((r["prioritaet"], r["termin"]), ("Eilig", "2027-01-15"))
		self.assertEqual(r["rohmaterial"]["charge"], "24-1")
		self.assertEqual(r["rohmaterial"]["verbrauchtMm"], 120)
		self.assertEqual(r["notizen"]["bemerkungen"], "vorsichtig")
		neu = r["arbeitsgaenge"][0]
		self.assertEqual((neu["name"], neu["stueckMin"]), ("Drehen CNC", 4.5))
		self.assertEqual(neu["gebucht"], 3)
		self.assertEqual(neu["status"], "Läuft")

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			fertigung.liste()
