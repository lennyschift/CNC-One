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
		# Checkliste vor dem Start in diesen Tests aus (eigener Test in test_fertigung)
		fertigung.vorlage_checkliste_speichern([])
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

	def zeiten(self, fb, ruest=30, bearb=60):
		"""Ist-Zeiten für alle internen Arbeitsgänge (beim Abschließen Pflicht)."""
		return [{"agId": a["id"], "ruestMin": ruest, "bearbMin": bearb} for a in fb["arbeitsgaenge"] if a["typ"] == "intern"]

	# ------------------------------------------------------------- Rohmaterial aus dem Lager
	def roh_vorbereiten(self):
		from cnc_one.api import werkstoff

		werkstoff.werkstoff_anlegen("ZZ 7075", "N", formen=["Rund"])
		abm = werkstoff.abmessung_hinzu("Rund", 41)
		gut = werkstoff.charge_speichern({"werkstoff": "ZZ 7075", "abmessung": abm["id"], "chargennr": "ZZ-S1", "laenge": 3000, "stueck": 2, "zeugnis": "3.1", "lagerplatz": "ZZ-R1"})
		ohne = werkstoff.charge_speichern({"werkstoff": "ZZ 7075", "abmessung": abm["id"], "chargennr": "ZZ-S2", "laenge": 3000, "stueck": 5})
		roh = {"form": "Rund", "abmessungId": abm["id"], "abmessung": "Ø41", "laenge": 82, "saege": 3, "anforderungen": {"zeugnis": "3.1", "pruefungen": []}, "gewichtAuto": True}
		t = teil("t1", teilenummer="ZZ-F1", material="ZZ 7075", roh=roh)
		fb = fertigung.starten(self.auftrag([PLAN[0]], 10, teile=[t])["id"])["fertigung"][0]
		return fb, gut, ohne

	def test_rohmaterial_lagerstand_entnahme_und_fertigmelden(self):
		fb, gut, ohne = self.roh_vorbereiten()
		r = fb["roh"]
		self.assertEqual(r["spez"]["werkstoff"], "ZZ 7075")
		self.assertNotIn("gewichtAuto", r["spez"])
		self.assertEqual(r["status"], "lager")
		# die Charge mit Zeugnis 3.1 zuerst, die ohne Zeugnis erfüllt die Anforderung nicht
		self.assertEqual([c["id"] for c in r["passend"]], [gut["id"], ohne["id"]])
		self.assertEqual(r["passend"][0]["reicht"], 70)  # 3000 // 85 = 35 je Stange, 2 Stangen
		self.assertEqual(r["passend"][1]["fehlt"], ["Zeugnis 3.1"])
		fb = fertigung.roh_setzen(fb["id"], charge=gut["id"])["fb"]
		self.assertEqual((fb["roh"]["status"], fb["rohmaterial"]["lagerplatz"]), ("reserviert", "ZZ-R1"))

		# fertig melden geht erst, wenn feststeht, welches Material verwendet wurde
		drehen = fb["arbeitsgaenge"][0]["id"]
		with self.assertRaises(frappe.ValidationError):
			fertigung.buchen(fb["id"], drehen, 10, self.zeiten(fb))
		fb = fertigung.material_entnehmen(fb["id"], gut["id"], 1, rest_laenge=2100, notiz="ZZ")["fb"]
		e = fb["roh"]["entnahmen"][0]
		self.assertEqual((e["charge"], e["stueck"], e["verbraucht"], e["jeStueck"], e["einheit"]), (gut["id"], 1, 900, 90, "mm"))
		self.assertEqual(fb["roh"]["status"], "entnommen")
		self.assertEqual(frappe.db.get_value("Rohmaterialcharge", gut["id"], "stueck"), 1)
		rest = frappe.get_doc("Rohmaterialcharge", e["restCharge"])
		self.assertEqual((rest.laenge, rest.stueck, rest.chargennr, rest.zeugnis, rest.lagerplatz), (2100, 1, "ZZ-S1", "3.1", "ZZ-R1"))
		fb = fertigung.buchen(fb["id"], drehen, 10, self.zeiten(fb))["fb"]
		self.assertEqual(fb["status"], "Fertig")

		# falsch gebucht: zurücknehmen, das unbenutzte Reststück verschwindet wieder
		fb = fertigung.entnahme_zurueck(fb["id"], e["id"])["fb"]
		self.assertEqual(fb["roh"]["entnahmen"], [])
		self.assertEqual(frappe.db.get_value("Rohmaterialcharge", gut["id"], "stueck"), 2)
		self.assertFalse(frappe.db.exists("Rohmaterialcharge", e["restCharge"]))

	def test_rohmaterial_ohne_lager_und_letzte_stange(self):
		fb, gut, ohne = self.roh_vorbereiten()
		with self.assertRaises(frappe.ValidationError):
			fertigung.material_entnehmen(fb["id"], gut["id"], 3)  # nur 2 Stangen da
		with self.assertRaises(frappe.ValidationError):
			fertigung.material_entnehmen(fb["id"], gut["id"], 1, rest_laenge=3500)
		fb = fertigung.material_entnehmen(fb["id"], gut["id"], 2)["fb"]
		self.assertEqual(frappe.db.get_value("Rohmaterialcharge", gut["id"], "status"), "Aufgebraucht")
		fb = fertigung.entnahme_zurueck(fb["id"], fb["roh"]["entnahmen"][0]["id"])["fb"]
		# Beistellung des Kunden: ohne Lagerentnahme fertig melden, mit Grund
		fb = fertigung.status_setzen(fb["id"], "Fertig", self.zeiten(fb), ohne_material="Beistellung ZZ")["fb"]
		self.assertEqual(fb["status"], "Fertig")
		self.assertIn("Beistellung ZZ", fb["roh"]["ohneLager"])

	# ------------------------------------------------------------- Checkliste vor dem Start
	def test_checkliste_vor_dem_start(self):
		fertigung.vorlage_checkliste_speichern([
			{"id": "material", "text": "Material", "pflicht": 1},
			{"id": "werkzeug", "text": "Werkzeug", "pflicht": 1},
			{"id": "programm", "text": "NC-Programm", "pflicht": 0},
			{"id": "aus", "text": "Abgeschaltet", "pflicht": 1, "aktiv": False},
		])
		fb = self.start()
		self.assertEqual([p["id"] for p in fb["checkliste"]], ["material", "werkzeug", "programm"])
		drehen = self.ag(fb, "Drehen")["id"]
		# Start mit offenen Pflichtpunkten geht nicht, weder über den Status noch über die erste Buchung
		with self.assertRaises(frappe.ValidationError):
			fertigung.status_setzen(fb["id"], "In Fertigung")
		with self.assertRaises(frappe.ValidationError):
			fertigung.buchen(fb["id"], drehen, 1)
		fb = fertigung.check_setzen(fb["id"], "material", 1, "Charge 24-0815")["fb"]
		m = fb["checkliste"][0]
		self.assertTrue(m["erledigt"])
		self.assertEqual(m["notiz"], "Charge 24-0815")
		self.assertTrue(m["von"] and m["am"])
		# eigener Punkt nur für dieses Bauteil, als Pflicht
		fb = fertigung.check_eigen(fb["id"], "Prüfvorrichtung vom Kunden", 1)["fb"]
		eigen = fb["checkliste"][-1]
		self.assertTrue(eigen["eigen"])
		fb = fertigung.check_setzen(fb["id"], "werkzeug", 1)["fb"]
		with self.assertRaises(frappe.ValidationError):
			fertigung.status_setzen(fb["id"], "In Fertigung")
		fb = fertigung.check_setzen(fb["id"], eigen["id"], 1)["fb"]
		# NC-Programm ist keine Pflicht: jetzt geht der Start
		fb = fertigung.status_setzen(fb["id"], "In Fertigung")["fb"]
		self.assertEqual(fb["status"], "In Fertigung")
		self.assertEqual(fb["checklisteTrotzdem"], "")

	def test_checkliste_trotzdem_starten_wird_vermerkt(self):
		fertigung.vorlage_checkliste_speichern([{"id": "material", "text": "Material", "pflicht": 1}])
		fb = self.start()
		fb = fertigung.buchen(fb["id"], self.ag(fb, "Drehen")["id"], 1, trotzdem=1)["fb"]
		self.assertEqual(fb["status"], "In Fertigung")
		self.assertIn("Material", fb["checklisteTrotzdem"])
		# eigener Punkt lässt sich wieder entfernen, feste nicht
		fb = fertigung.check_eigen(fb["id"], "ZZ Sonderwerkzeug")["fb"]
		fb = fertigung.check_weg(fb["id"], fb["checkliste"][-1]["id"])["fb"]
		fb = fertigung.check_weg(fb["id"], "material")["fb"]
		self.assertEqual([p["id"] for p in fb["checkliste"]], ["material"])

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
		fertigung.buchen(fb["id"], ids[2], 12, self.zeiten(fb))
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
		neu = fertigung.status_setzen(fb["id"], "Fertig", self.zeiten(fb))
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
		self.assertEqual(fertigung.status_setzen(erstes["id"], "Fertig", self.zeiten(erstes))["auftragStatus"], "In Fertigung")
		self.assertEqual(fertigung.status_setzen(zweites["id"], "Fertig", self.zeiten(zweites))["auftragStatus"], "Fertig")

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

	# ------------------------------------------------------------- Ist-Zeiten und Planung
	def test_abschliessen_ohne_zeiten_wird_abgelehnt(self):
		fb = self.start()
		with self.assertRaises(frappe.ValidationError):
			fertigung.status_setzen(fb["id"], "Fertig")
		# Teilbuchung braucht noch keine Zeiten, erst das Fertigwerden
		fertigung.buchen(fb["id"], self.ag(fb, "Drehen")["id"], 4)
		with self.assertRaises(frappe.ValidationError):
			fertigung.buchen(fb["id"], self.ag(fb, "Drehen")["id"], 6)

	def test_zeiten_beim_abschliessen_werden_gespeichert(self):
		fb = self.start()
		drehen = self.ag(fb, "Drehen")
		r = fertigung.buchen(fb["id"], drehen["id"], 10, [{"agId": drehen["id"], "ruestMin": 45, "bearbMin": 25}])["fb"]
		neu = self.ag(r, "Drehen")
		self.assertEqual((neu["status"], neu["istRuestMin"], neu["istBearbMin"], neu["istVon"]), ("Fertig", 45, 25, "Administrator"))
		self.assertTrue(neu["istAm"])
		# korrigieren
		r = fertigung.zeiten_melden(fb["id"], [{"agId": drehen["id"], "ruestMin": 40, "bearbMin": 30}])["fb"]
		self.assertEqual(self.ag(r, "Drehen")["istBearbMin"], 30)
		with self.assertRaises(frappe.ValidationError):
			fertigung.zeiten_melden(fb["id"], [{"agId": drehen["id"], "ruestMin": -1, "bearbMin": 0}])

	def test_intern_extern_und_planung_aendern(self):
		fb = self.start()
		pruefen = self.ag(fb, "Prüfen")
		r = fertigung.felder_speichern(fb["id"], {"arbeitsgaenge": [{**pruefen, "typ": "fremd", "geplantAm": "2026-12-03"}]})["fb"]
		neu = self.ag(r, "Prüfen")
		self.assertEqual((neu["typ"], neu["geplantAm"]), ("fremd", "2026-12-03"))
		drehen = self.ag(r, "Drehen")
		fertigung.buchen(fb["id"], drehen["id"], 1)
		with self.assertRaises(frappe.ValidationError):
			fertigung.felder_speichern(fb["id"], {"arbeitsgaenge": [{**drehen, "typ": "fremd"}]})

	def test_arbeitsgang_hinzu_nimmt_den_standard_der_art(self):
		frappe.get_doc({"doctype": "Arbeitsgangart", "bezeichnung": "ZZ Eloxieren", "typ": "Fremd"}).insert()
		fb = self.start()
		r = fertigung.arbeitsgang_hinzu(fb["id"], "", "ZZ Eloxieren")["fb"]
		self.assertEqual(self.ag(r, "ZZ Eloxieren")["typ"], "fremd")
		r = fertigung.arbeitsgang_hinzu(fb["id"], "intern", "ZZ Eloxieren")["fb"]
		self.assertEqual([a["typ"] for a in r["arbeitsgaenge"] if a["name"] == "ZZ Eloxieren"], ["fremd", "intern"])
		with self.assertRaises(frappe.ValidationError):
			fertigung.arbeitsgang_hinzu(fb["id"], "", "ZZ gibt es nicht")

	def test_maschine_mit_arbeitsgaengen_und_stunden(self):
		from cnc_one.api import stammdaten
		frappe.get_doc({"doctype": "Maschine", "maschinenname": "ZZ C42 Auto", "satz": 60}).insert()
		d = frappe.get_doc("Maschine", "ZZ C42 Auto")
		stammdaten.maschine_setzen(d, {"satz": 60, "arbeitsgaenge": ["Fräsen", "Drehfräsen"], "automation": "ja", "stundenTag": 20})
		d.save()
		ui = stammdaten.maschine_ui(frappe.get_doc("Maschine", "ZZ C42 Auto"))
		self.assertEqual((ui["arbeitsgaenge"], ui["automation"], ui["stundenTag"]), (["Fräsen", "Drehfräsen"], "ja", 20))

	def test_fertigung_zeigt_keine_preise_und_behaelt_sie(self):
		fb = self.start()
		for ag in fb["arbeitsgaenge"]:
			for k in ("satz", "ruestEuro", "stueckEuro", "fremdProStk", "fremdEinmal"):
				self.assertNotIn(k, ag)
		drehen = self.ag(fb, "Drehen")
		fertigung.felder_speichern(fb["id"], {"arbeitsgaenge": [{**drehen, "maschine": "CTX400"}]})
		d = frappe.get_doc("Fertigungsbauteil", fb["id"])
		self.assertEqual(next(a.satz for a in d.arbeitsgaenge if a.bezeichnung == "Drehen"), 100)
		self.assertEqual(next(a.fremd_pro_stk for a in d.arbeitsgaenge if a.bezeichnung == "Härten"), 1)

	def test_bestellnummer_im_laufenden_auftrag_aendern(self):
		fb = self.start()
		r = auftrag.bestellnr_setzen(fb["auftragId"], "  B-4711 ")
		self.assertEqual(r["kundenbestellnr"], "B-4711")
		self.assertEqual(frappe.db.get_value("Auftrag", fb["auftragId"], "kundenbestellnr"), "B-4711")

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			fertigung.liste()
