import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, auftrag, bestellung, historie
from cnc_one.logic import bestellabgleich
from cnc_one.logic.beleg import position_fuer_auftrag
from cnc_one.logic.kalkulation import berechne
from cnc_one.tests.test_angebot import teil


class TestBestellabgleich(IntegrationTestCase):
	"""Preisabgleich ohne Datenbank."""

	def erwartet(self, t, menge=10):
		return position_fuer_auftrag(t, berechne(t), None, menge)

	def test_wie_angeboten(self):
		t = teil()
		e = self.erwartet(t)
		kosten = sum(k["betrag"] for k in e["kosten"])
		r = bestellabgleich.vergleichen(e, 10, e["einzelpreis"], kosten)
		self.assertEqual(r["status"], bestellabgleich.GLEICH)

	def test_kosten_auf_stueckpreis_umgelegt(self):
		t = teil()
		e = self.erwartet(t)
		umgelegt = round(e["summe"] / 10, 2)
		r = bestellabgleich.vergleichen(e, 10, umgelegt)
		self.assertEqual(r["status"], bestellabgleich.UMGELEGT)
		self.assertIn("umgelegt", r["hinweis"])

	def test_umgelegt_mit_rundung(self):
		t = teil(menge=7)
		e = self.erwartet(t, 7)
		# der Kunde rundet den umgelegten Stückpreis ab: einige Cent Unterschied sind in Ordnung
		r = bestellabgleich.vergleichen(e, 7, int(e["summe"] / 7 * 100) / 100)
		self.assertEqual(r["status"], bestellabgleich.UMGELEGT)

	def test_kosten_fehlen(self):
		t = teil()
		e = self.erwartet(t)
		r = bestellabgleich.vergleichen(e, 10, e["einzelpreis"])
		self.assertEqual(r["status"], bestellabgleich.ABWEICHEND)
		self.assertIn("fehlen", r["hinweis"])
		self.assertLess(r["differenz"], 0)

	def test_ohne_preis(self):
		e = self.erwartet(teil())
		self.assertEqual(bestellabgleich.vergleichen(e, 10, None)["status"], bestellabgleich.OHNE_PREIS)

	def test_staffel_zur_menge_und_andere_staffel(self):
		t = teil(staffel={"aktiv": True, "stufen": [{"menge": 10, "extra": 0}, {"menge": 50, "extra": 0}]})
		r = bestellabgleich.mit_angebot(t, 60, None)
		self.assertEqual(r["optionId"], "50")
		r10 = bestellabgleich.mit_angebot(t, 10, None)
		# 40 Stück zum Preis der 50er-Staffel bestellt: wird erkannt und genannt
		e50 = position_fuer_auftrag(t, berechne(t), "50", 40)
		r = bestellabgleich.mit_angebot(t, 40, round(e50["summe"] / 40, 2))
		self.assertEqual(r["optionId"], "50")
		self.assertIn("Staffel 50", r["abgleich"]["hinweis"])
		self.assertNotEqual(r10["erwartet"]["einzelpreis"], r["erwartet"]["einzelpreis"])


class TestBestellung(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Bestellkunde GmbH", "kuerzel": "ZZBK"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def gesendet(self, teile):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": teile})
		return angebot.senden(a["id"])

	def test_kunde_aus_dem_text(self):
		self.assertEqual(bestellung.kunde_erkennen("Bestellung\nZZ Bestellkunde GmbH · Musterstraße 1"), self.kunde)
		self.assertEqual(bestellung.kunde_erkennen("Einkauf zz bestellkunde, Werk 2"), self.kunde)
		self.assertEqual(bestellung.kunde_erkennen("nichts Bekanntes"), "")

	def test_bauteil_aus_dem_text_der_position(self):
		a = self.gesendet([teil("t1", teilenummer="ZZ-4711-01")])
		b = frappe.get_doc("Angebot", a["id"]).positionen[0].bauteil
		self.assertTrue(b)
		self.assertEqual(bestellung.bauteil_finden(self.kunde, "zz 4711.01"), b)
		self.assertEqual(bestellung.bauteil_finden(self.kunde, "", "10 Flansch Ihre Mat.-Nr. ZZ4711-01 Rev B"), b)
		self.assertIsNone(bestellung.bauteil_finden(self.kunde, "", "ganz anderes Teil"))

	def test_vorschlag_mit_umgelegtem_preis(self):
		t = teil("t1", teilenummer="ZZ-200")
		a = self.gesendet([t])
		e = position_fuer_auftrag(t, berechne(t), None, 10)
		r = bestellung.vorschlag(self.kunde, [{"bestellposition": "10", "teilenummer": "ZZ-200", "menge": 10, "preis": round(e["summe"] / 10, 2)}], "PO-ZZ-1")
		p = r["positionen"][0]
		self.assertEqual(p["bauteil"]["teilenummer"], "ZZ-200")
		q = p["quellen"][p["quelle"]]
		self.assertEqual(q["angebot"], a["id"])
		self.assertEqual(q["abgleich"]["status"], bestellabgleich.UMGELEGT)
		self.assertEqual(r["vorhanden"], [])

	def test_auftrag_aus_bestellung_preisform_bestellung(self):
		t = teil("t1", teilenummer="ZZ-300")
		a = self.gesendet([t])
		e = position_fuer_auftrag(t, berechne(t), None, 10)
		preis = round(e["summe"] / 10, 2)
		r = bestellung.auftrag_anlegen(self.kunde, [{
			"angebot": a["id"], "angebotKey": "t1", "menge": 10, "termin": "2026-12-20", "bestellposition": "00010",
			"bestellpreis": preis, "preisform": "Bestellung",
		}], "PO-ZZ-2", "2026-11-19")
		self.assertEqual(r["angebotId"], a["id"])
		self.assertEqual(r["bestelldatum"], "2026-11-19")
		p = r["positionen"][0]
		self.assertEqual(p["preisform"], "Bestellung")
		self.assertEqual(p["einzelpreis"], preis)
		self.assertEqual(p["kosten"], [])
		self.assertEqual(p["bestellposition"], "00010")
		self.assertEqual(p["termin"], "2026-12-20")
		self.assertTrue(angebot.beauftragt(a["id"]))
		# dieselbe Bestellnummer noch einmal: Hinweis auf den vorhandenen Auftrag
		self.assertEqual(bestellung.vorschlag(self.kunde, [], "PO-ZZ-2")["vorhanden"], [r["id"]])

	def test_auftrag_aus_bestellung_preisform_angebot(self):
		t = teil("t1", teilenummer="ZZ-301")
		a = self.gesendet([t])
		r = bestellung.auftrag_anlegen(self.kunde, [{"angebot": a["id"], "angebotKey": "t1", "menge": 10, "bestellpreis": 99, "preisform": "Angebot"}])
		e = position_fuer_auftrag(t, berechne(t), None, 10)
		p = r["positionen"][0]
		self.assertEqual(p["einzelpreis"], e["einzelpreis"])
		self.assertEqual(p["kosten"], e["kosten"])
		self.assertEqual(p["bestellpreis"], 99)

	def test_wiederholbestellung_ohne_angebot(self):
		t = teil("t1", teilenummer="ZZ-400", arbeitsgaenge=[])
		a = self.gesendet([t])
		erster = auftrag.aus_angebot(a["id"], "PO-A", [{"angebotKey": "t1", "menge": 10}])
		b = erster["positionen"][0]["teil"]["bauteilId"]
		r = bestellung.auftrag_anlegen(self.kunde, [{"bauteil": b, "menge": 5, "bestellpreis": 31.5}], "PO-B")
		p = r["positionen"][0]
		self.assertEqual(r["angebotId"], "")
		self.assertEqual(p["teil"]["bauteilId"], b)
		self.assertEqual(p["einzelpreis"], 31.5)
		self.assertEqual(p["preisform"], "Bestellung")
		self.assertAlmostEqual(r["netto"], 157.5, places=2)
		# ohne Preis geht es ohne Angebot nicht
		with self.assertRaises(frappe.ValidationError):
			bestellung.auftrag_anlegen(self.kunde, [{"bauteil": b, "menge": 5}])

	def test_workbench_aus_bestellung_direkt_zum_auftrag(self):
		# früheres Angebot zum Wiederholteil: Quelle für die Kalkulation, auch wenn es aus einer Bestellung kam
		alt = self.gesendet([teil("t1", teilenummer="ZZ-WB-1")])
		t = {**teil("w1", teilenummer="ZZ-WB-1", menge=5), "preisart": "fest", "festpreis": 373,
			"bestellung": {"position": "1", "preis": 373, "menge": 5, "termin": "2026-12-11"}, "frueher": {"gefertigt": True, "notiz": "2022"}}
		neu = {**teil("w2", teilenummer="ZZ-WB-2", menge=10), "bestellung": {"position": "2", "preis": 38, "menge": 10, "termin": ""}}
		kopf = {"kundeId": self.kunde, "projekt": "Bestellung 20260050", "bestellung": {"nr": "20260050", "datum": "2026-11-05", "datei": "/private/files/zz-bestellung.pdf"}}
		a = angebot.entwurf_speichern({"id": None, "kopf": kopf, "teile": [t, neu]})
		self.assertEqual(a["kopf"]["bestellung"]["nr"], "20260050")
		b1 = a["positionen"][0]["bauteilId"]
		self.assertEqual(a["positionen"][0]["herkunft"], "bestand")
		self.assertEqual(a["positionen"][0]["bauteilFrueher"], {"gefertigt": True, "notiz": "2022"})
		self.assertEqual(frappe.db.get_value("Bauteil", b1, ["frueher_gefertigt", "frueher_notiz"]), (1, "2022"))
		self.assertEqual(bestellung.vorschlag(self.kunde, [{"teilenummer": "ZZ-WB-1", "menge": 5, "preis": 373}])["positionen"][0]["bauteil"]["frueherGefertigt"], True)
		# Auftrag direkt aus dem Entwurf (ohne Senden), Preis und Positionsnummer laut Bestellung
		r = auftrag.aus_angebot(a["id"], "", [
			{"angebotKey": "w1", "menge": 5, "termin": "2026-12-11", "bestellposition": "1", "bestellpreis": 373, "preisform": "Bestellung"},
			{"angebotKey": "w2", "menge": 10, "bestellposition": "2", "bestellpreis": 38, "preisform": "Bestellung"},
		])
		self.assertEqual((r["kundenbestellnr"], r["bestelldatum"]), ("20260050", "2026-11-05"))
		self.assertEqual([(p["bestellposition"], p["einzelpreis"], p["kosten"]) for p in r["positionen"]], [("1", 373, []), ("2", 38, [])])
		self.assertAlmostEqual(r["netto"], 5 * 373 + 10 * 38, places=2)
		self.assertEqual(frappe.db.get_value("Angebot", a["id"], "status"), "Bestellt")
		self.assertEqual(frappe.db.get_value("Auftrag", r["id"], "bestellung_datei"), "/private/files/zz-bestellung.pdf")
		# zweimal geht nicht, und ein gewöhnlicher Entwurf bleibt ohne Senden gesperrt
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(a["id"], "", [{"angebotKey": "w1", "menge": 5}])
		e = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("x1", teilenummer="ZZ-WB-3")]})
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(e["id"], "", [{"angebotKey": "x1", "menge": 1}])
		# der Haken lässt sich wieder nehmen
		angebot.entwurf_speichern({"id": e["id"], "kopf": {"kundeId": self.kunde}, "teile": [{**teil("x1", teilenummer="ZZ-WB-1"), "frueher": {"gefertigt": False, "notiz": ""}}]})
		self.assertEqual(frappe.db.get_value("Bauteil", b1, "frueher_gefertigt"), 0)
		self.assertTrue(alt["id"])

	def test_neues_bauteil_aus_bestellung(self):
		r = bestellung.auftrag_anlegen(self.kunde, [{"teilenummer": "ZZ-NEU-1", "bezeichnung": "Hülse", "menge": 3, "bestellpreis": 12}])
		self.assertTrue(frappe.db.exists("Bauteil", {"kunde": self.kunde, "teilenummer": "ZZ-NEU-1"}))
		self.assertEqual(r["positionen"][0]["teil"]["name"], "Hülse")

	def test_fremdes_angebot_abgelehnt(self):
		andere = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Anderer"}).insert().name
		a = self.gesendet([teil("t1", teilenummer="ZZ-500")])
		with self.assertRaises(frappe.ValidationError):
			bestellung.auftrag_anlegen(andere, [{"angebot": a["id"], "angebotKey": "t1", "menge": 1}])

	def test_an_auftrag_koppeln_und_abgleichen(self):
		t = teil("t1", teilenummer="ZZ-600")
		a = self.gesendet([t])
		auf = auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 10}])
		pos = auf["positionen"][0]
		umgelegt = round(pos["summe"] / 10, 2)
		v = bestellung.vorschlag("", [{"teilenummer": "ZZ-600", "menge": 10, "preis": umgelegt}], "PO-K", auftrag=auf["id"])
		self.assertEqual(v["positionen"][0]["auftragKey"], pos["key"])
		self.assertEqual(v["positionen"][0]["abgleich"]["status"], bestellabgleich.UMGELEGT)
		r = bestellung.koppeln(auf["id"], [{"auftragKey": pos["key"], "bestellposition": "20", "bestellpreis": umgelegt, "termin": "2027-01-15"}], "PO-K", "2026-11-18")
		self.assertEqual(r["kundenbestellnr"], "PO-K")
		self.assertEqual(r["positionen"][0]["bestellposition"], "20")
		self.assertEqual(r["positionen"][0]["termin"], "2027-01-15")
		self.assertEqual(r["positionen"][0]["einzelpreis"], pos["einzelpreis"])  # Preise bleiben
		self.assertIsNone(r["positionen"][0]["bestellung"])

		# alle Angaben aus dem PDF bleiben an der Position
		angaben = {"bezeichnung": "ZZ RING", "teilenummer": "ZZ-600", "einheit": "ST", "betrag": 130.5, "zeichnungsdatum": "2026-03-24", "x": "weg",
			"angaben": [{"spalte": "Details / Materialnummer", "wert": "ZZ RING / ZZ-600"}, {"spalte": "leer", "wert": ""}]}
		r = bestellung.koppeln(auf["id"], [{"auftragKey": pos["key"], "bestellung": angaben}])
		b = r["positionen"][0]["bestellung"]
		self.assertEqual(b["zeichnungsdatum"], "2026-03-24")
		self.assertEqual(b["betrag"], 130.5)
		self.assertNotIn("x", b)
		self.assertEqual(b["angaben"], [{"spalte": "Details / Materialnummer", "wert": "ZZ RING / ZZ-600"}])

	def test_vorlage_lernen(self):
		bestellung.vorlage_lernen(self.kunde, {"spalten": {"material": "teilenummer", "menge": "menge"}, "kopf": {"bestellnr": "Bestellung Nr."}})
		self.assertEqual(bestellung.erkennen("ZZ Bestellkunde GmbH")["vorlage"]["spalten"]["material"], "teilenummer")
		bestellung.vorlage_vergessen(self.kunde)
		self.assertEqual(bestellung.vorlage(self.kunde), {})


class TestHistorie(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Historienkunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_angebote_und_auftraege_aus_den_belegen(self):
		a1 = angebot.senden(angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", teilenummer="ZZ-H1")]})["id"])
		a2 = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", teilenummer="ZZ-H1", menge=20)]})
		auf = auftrag.aus_angebot(a1["id"], "PO-H", [{"angebotKey": "t1", "menge": 10}])
		b = auf["positionen"][0]["teil"]["bauteilId"]
		h = historie.historie(bauteil=b)
		self.assertEqual({x["angebot"] for x in h["angebote"]}, {a1["id"], a2["id"]})
		erstes = next(x for x in h["angebote"] if x["angebot"] == a1["id"])
		self.assertTrue(erstes["beauftragt"])
		self.assertTrue(erstes["preise"])
		self.assertEqual(h["auftraege"][0]["auftrag"], auf["id"])
		self.assertEqual(h["auftraege"][0]["jeStueck"], round(auf["positionen"][0]["summe"] / 10, 2))
		self.assertEqual(h["kennzahlen"]["stueck"], 10)
		# das offene Angebot der Workbench wird nicht mitgezählt; ohne Bauteil über Kunde und Teilenummer
		h = historie.historie(kunde=self.kunde, teilenummer="zz-h1", ohne_angebot=a2["id"])
		self.assertEqual([x["angebot"] for x in h["angebote"]], [a1["id"]])
		self.assertEqual(historie.kalkulation(a1["id"], "t1")["teilenummer"], "ZZ-H1")
