import json

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, bauteil, stamm
from cnc_one.logic.kalkulation import berechne


def teil(id="t1", name="Flansch", teilenummer="ZZ-100", **extra):
	t = {
		"id": id, "name": name, "teilenummer": teilenummer, "zeichnungsnr": "Z-1", "material": "",
		"menge": 10, "ruestMin": 60, "satzRuest": 100, "stueckMin": 6, "satzStueck": 100,
		"gewichtKg": 0.5, "materialPreisKg": 8, "pauschalMaterial": 0, "pauschalAlsZeile": False,
		"messkosten": 20, "sonderkosten": 0, "expresskosten": 0,
		"inStueckpreis": {"ruest": False, "mess": False, "sonder": False, "express": False},
		"staffel": {"aktiv": False, "stufen": []}, "arbeitsgaenge": [], "dateien": [],
	}
	t.update(extra)
	return t


class TestAngebot(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Angebotskunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def speichern(self, teile, id=None, kunde="__standard__", **kopf):
		return angebot.entwurf_speichern({
			"id": id,
			"kopf": {"kundeId": self.kunde if kunde == "__standard__" else kunde, "anfrageNr": "RFQ-1", "gueltigWochen": 6, "lieferzeit": "4 Wochen", **kopf},
			"teile": teile,
		})

	def test_entwurf_wird_angelegt_und_vom_server_gerechnet(self):
		a = teil("t1")
		b = teil("t2", "Welle", "ZZ-200", menge=25, staffel={"aktiv": True, "stufen": [{"menge": 5, "extra": 0}, {"menge": 25, "extra": 1}]})
		r = self.speichern([a, b])
		self.assertTrue(r["id"].startswith("ANG-"))
		self.assertEqual(r["status"], "Entwurf")
		self.assertEqual(r["kopf"]["kundeName"], "ZZ Angebotskunde")
		self.assertEqual(r["kopf"]["gueltigWochen"], 6)
		self.assertEqual([p["key"] for p in r["positionen"]], ["t1", "t2"])
		self.assertEqual(r["positionen"][0]["ergebnis"], berechne(a))
		self.assertEqual(r["positionen"][1]["ergebnis"], berechne(b))
		self.assertAlmostEqual(r["netto"], berechne(a)["gesamt"] + berechne(b)["gesamt"], places=2)
		self.assertEqual(r["positionen"][0]["teil"]["name"], "Flansch")

	def test_vom_browser_gelieferte_ergebnisse_werden_ignoriert(self):
		t = teil("t1", ergebnis={"gesamt": 1})
		r = self.speichern([t])
		self.assertEqual(r["positionen"][0]["ergebnis"], berechne(t))
		self.assertNotEqual(r["netto"], 1)

	def test_bauteile_werden_angelegt_und_wiedergefunden(self):
		r = self.speichern([teil("t1", "Flansch", "ZZ-100"), teil("t2", "Welle", "zz-200")])
		self.assertEqual(frappe.db.count("Bauteil", {"kunde": self.kunde}), 2)
		doc = frappe.get_doc("Angebot", r["id"])
		self.assertTrue(all(z.bauteil for z in doc.positionen))
		# zweites Speichern findet dieselben Bauteile, auch bei anderer Schreibweise
		self.speichern([teil("t1", "Flansch", "zz-100")], id=r["id"])
		# das Bauteil der entfernten Position war neu und wird nicht mehr gebraucht
		self.assertEqual(frappe.db.count("Bauteil", {"kunde": self.kunde}), 1)

	def test_aktualisieren_ersetzt_die_positionen(self):
		r = self.speichern([teil("t1"), teil("t2", "Welle", "ZZ-200")])
		w = self.speichern([teil("t2", "Welle", "ZZ-200", menge=3)], id=r["id"], anfrageNr="RFQ-2")
		self.assertEqual(w["id"], r["id"])
		self.assertEqual([p["key"] for p in w["positionen"]], ["t2"])
		self.assertEqual(w["positionen"][0]["ergebnis"]["menge"], 3)
		self.assertEqual(w["kopf"]["anfrageNr"], "RFQ-2")

	def test_entwurf_ohne_kunde_ist_moeglich(self):
		r = self.speichern([teil("t1")], kunde="")
		self.assertEqual(r["kopf"]["kundeId"], "")
		self.assertEqual(frappe.db.count("Bauteil", {"kunde": self.kunde}), 0)

	def test_leerer_entwurf_ist_moeglich(self):
		r = self.speichern([])
		self.assertEqual(r["positionen"], [])
		self.assertEqual(r["netto"], 0)

	def test_doppelte_positionskennung_wird_abgelehnt(self):
		with self.assertRaises(frappe.ValidationError):
			self.speichern([teil("t1"), teil("t1", "Welle", "ZZ-200")])

	def test_unbekannter_kunde_wird_abgelehnt(self):
		with self.assertRaises(frappe.ValidationError):
			self.speichern([teil("t1")], kunde="K-GIBT-ES-NICHT")

	def test_senden_braucht_kunde_und_bauteil(self):
		ohne_kunde = self.speichern([teil("t1")], kunde="")
		with self.assertRaises(frappe.ValidationError):
			angebot.senden(ohne_kunde["id"])
		leer = self.speichern([])
		with self.assertRaises(frappe.ValidationError):
			angebot.senden(leer["id"])

	def test_gesendetes_angebot_ist_gesperrt(self):
		r = self.speichern([teil("t1")])
		g = angebot.senden(r["id"])
		self.assertEqual(g["status"], "Gesendet")
		self.assertTrue(g["versandt"])
		with self.assertRaises(frappe.ValidationError):
			self.speichern([teil("t1", menge=99)], id=r["id"])
		with self.assertRaises(frappe.ValidationError):
			angebot.senden(r["id"])
		with self.assertRaises(frappe.ValidationError):
			angebot.loeschen(r["id"])

	def test_ablehnen_nur_nach_dem_senden(self):
		r = self.speichern([teil("t1")])
		with self.assertRaises(frappe.ValidationError):
			angebot.ablehnen(r["id"])
		angebot.senden(r["id"])
		self.assertEqual(angebot.ablehnen(r["id"])["status"], "Abgelehnt")

	def test_entwurf_laesst_sich_loeschen(self):
		r = self.speichern([teil("t1")])
		angebot.loeschen(r["id"])
		self.assertFalse(frappe.db.exists("Angebot", r["id"]))

	def test_liste_und_bootstrap_enthalten_das_angebot(self):
		r = self.speichern([teil("t1")])
		self.assertIn(r["id"], [a["id"] for a in angebot.liste()])
		daten = stamm.bootstrap()
		self.assertIn(r["id"], [a["id"] for a in daten["angebote"]])
		self.assertIn("bauteile", daten)

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			angebot.liste()
		with self.assertRaises(frappe.PermissionError):
			angebot.entwurf_speichern({"kopf": {}, "teile": []})


class TestBauteil(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Bauteilkunde"}).insert().name
		self.maschine = frappe.get_doc({"doctype": "Maschine", "maschinenname": "ZZ BM", "satz": 70}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def plan(self):
		return [
			{"id": "a1", "name": "Drehen", "typ": "intern", "maschine": self.maschine, "satz": 70, "ruestMin": 20, "stueckMin": 2},
			{"id": "a2", "name": "Härten", "typ": "fremd", "fremdProStk": 0.8, "fremdEinmal": 25},
		]

	def test_plan_speichern_legt_das_bauteil_an(self):
		b = bauteil.plan_speichern(self.kunde, "ZZ-1", self.plan(), name="Welle", zeichnungsnr="Z-9")
		self.assertTrue(b["id"].startswith("BT-"))
		self.assertEqual((b["name"], b["zeichnungsnr"], b["teilenummer"]), ("Welle", "Z-9", "ZZ-1"))
		self.assertEqual([a["id"] for a in b["arbeitsgaenge"]], ["a1", "a2"])
		self.assertEqual(b["arbeitsgaenge"][1]["typ"], "fremd")
		self.assertEqual(b["arbeitsgaenge"][1]["fremdEinmal"], 25)

	def test_zweites_speichern_aktualisiert_dasselbe_bauteil(self):
		a = bauteil.plan_speichern(self.kunde, "ZZ-1", self.plan())
		b = bauteil.plan_speichern(self.kunde, "zz-1", self.plan()[:1])
		self.assertEqual(a["id"], b["id"])
		self.assertEqual([x["id"] for x in b["arbeitsgaenge"]], ["a1"])
		self.assertEqual(frappe.db.count("Bauteil", {"kunde": self.kunde}), 1)

	def test_teilenummer_ist_je_kunde_eindeutig(self):
		frappe.get_doc({"doctype": "Bauteil", "kunde": self.kunde, "teilenummer": "ZZ-7"}).insert()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Bauteil", "kunde": self.kunde, "teilenummer": "zz-7 "}).insert()
		anderer = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Anderer"}).insert().name
		frappe.get_doc({"doctype": "Bauteil", "kunde": anderer, "teilenummer": "ZZ-7"}).insert()

	def test_ohne_kunde_oder_teilenummer_kein_plan(self):
		with self.assertRaises(frappe.ValidationError):
			bauteil.plan_speichern("", "ZZ-1", self.plan())
		with self.assertRaises(frappe.ValidationError):
			bauteil.plan_speichern(self.kunde, "  ", self.plan())

	def test_bootstrap_liefert_die_arbeitsplaene(self):
		b = bauteil.plan_speichern(self.kunde, "ZZ-5", self.plan())
		gefunden = [x for x in stamm.bootstrap()["bauteile"] if x["id"] == b["id"]]
		self.assertEqual(len(gefunden), 1)
		self.assertEqual(gefunden[0]["kundeId"], self.kunde)
		self.assertEqual(len(gefunden[0]["arbeitsgaenge"]), 2)


class TestBauteilZuordnung(IntegrationTestCase):
	"""Workbench-Bauteile: Bestandsbauteile wiederfinden, neue in den Stammdaten anlegen, nie doppelt."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Zuordnungskunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def speichern(self, teile, id=None):
		return angebot.entwurf_speichern({"id": id, "kopf": {"kundeId": self.kunde}, "teile": teile})

	def bauteile(self, nr=None):
		f = {"kunde": self.kunde}
		if nr:
			f["teilenummer"] = nr
		return frappe.get_all("Bauteil", filters=f, pluck="name")

	def test_neues_bauteil_entsteht_in_den_stammdaten_und_ist_als_neu_gekennzeichnet(self):
		r = self.speichern([teil("t1", "Flansch", "ZZ-N1", seriennummern=True)])
		p = r["positionen"][0]
		self.assertEqual(p["herkunft"], "neu")
		b = frappe.get_doc("Bauteil", p["bauteilId"])
		self.assertEqual((b.teilenummer, b.bezeichnung, b.seriennummern), ("ZZ-N1", "Flansch", 1))
		# bleibt auch beim nächsten Speichern "neu" und folgt den Änderungen
		r2 = self.speichern([teil("t1", "Flansch neu", "ZZ-N1")], r["id"])
		self.assertEqual(r2["positionen"][0]["herkunft"], "neu")
		b.reload()
		self.assertEqual((b.bezeichnung, b.seriennummern), ("Flansch neu", 0))

	def test_bestandsbauteil_wird_wiedergefunden_und_nicht_veraendert(self):
		vorhanden = bauteil.sicherstellen(self.kunde, "ZZ-B1", "Altes Bauteil", "Z-1", "")
		r = self.speichern([teil("t1", "Anderer Name", "zz-b1")])
		p = r["positionen"][0]
		self.assertEqual((p["bauteilId"], p["herkunft"]), (vorhanden.name, "bestand"))
		self.assertEqual(len(self.bauteile()), 1)
		self.assertEqual(frappe.db.get_value("Bauteil", vorhanden.name, "bezeichnung"), "Altes Bauteil")

	def test_keine_dubletten_bei_zwei_positionen_mit_derselben_nummer(self):
		r = self.speichern([teil("t1", "A", "ZZ-D1"), teil("t2", "B", "ZZ-D1")])
		self.assertEqual(len(self.bauteile("ZZ-D1")), 1)
		self.assertEqual(r["positionen"][0]["bauteilId"], r["positionen"][1]["bauteilId"])

	def test_geaenderte_teilenummer_benennt_das_neue_bauteil_um_statt_ein_zweites_anzulegen(self):
		r = self.speichern([teil("t1", "Flansch", "ZZ-T")])
		b1 = r["positionen"][0]["bauteilId"]
		r = self.speichern([teil("t1", "Flansch", "ZZ-T2")], r["id"])
		self.assertEqual(r["positionen"][0]["bauteilId"], b1)
		self.assertEqual(len(self.bauteile()), 1)
		self.assertEqual(frappe.db.get_value("Bauteil", b1, "teilenummer"), "ZZ-T2")

	def test_wechsel_auf_ein_bestandsbauteil_raeumt_das_neue_auf(self):
		bestand = bauteil.sicherstellen(self.kunde, "ZZ-BEST", "Bestand", "", "")
		r = self.speichern([teil("t1", "Neu", "ZZ-TMP")])
		r = self.speichern([teil("t1", "Neu", "ZZ-BEST")], r["id"])
		p = r["positionen"][0]
		self.assertEqual((p["bauteilId"], p["herkunft"]), (bestand.name, "bestand"))
		self.assertEqual(self.bauteile(), [bestand.name])

	def test_entferntes_bauteil_wird_aus_den_stammdaten_entfernt_wenn_es_neu_war(self):
		bestand = bauteil.sicherstellen(self.kunde, "ZZ-STAY", "Bleibt", "", "")
		r = self.speichern([teil("t1", "Neu", "ZZ-GONE"), teil("t2", "Alt", "ZZ-STAY")])
		self.assertEqual(len(self.bauteile()), 2)
		self.speichern([teil("t2", "Alt", "ZZ-STAY")], r["id"])
		self.assertEqual(self.bauteile(), [bestand.name])

	def test_ohne_teilenummer_gibt_es_noch_kein_bauteil(self):
		r = self.speichern([teil("t1", "Skizze", "")])
		self.assertEqual((r["positionen"][0]["bauteilId"], r["positionen"][0]["herkunft"]), ("", ""))
		self.assertEqual(self.bauteile(), [])
