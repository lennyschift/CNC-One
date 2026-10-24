import json

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, today

from cnc_one.api import angebot, auftrag, bauteil, firma, lieferschein, mahnung, rechnung
from cnc_one.logic.rechnung import euro, faellig_am, iban_gueltig, inhalt_hash, mahntext, naechste_mahnstufe, summen, zuteilen
from cnc_one.tests.test_angebot import teil

PLAN = [{"id": "p1", "name": "Drehen", "typ": "intern"}]
SPARKASSE = "DE64 6225 0030 0005 4437 72"
VR = "DE50 6229 0110 0502 1440 09"


class TestRechnungLogik(UnitTestCase):
	def test_summen_steuer_einmal_auf_die_summe(self):
		self.assertEqual(summen([140, 100, 20]), (260.0, 49.4, 309.4))
		self.assertEqual(summen([0.1, 0.2, 0.3]), (0.6, 0.11, 0.71))
		self.assertEqual(summen([]), (0.0, 0.0, 0.0))

	def test_iban_pruefung(self):
		self.assertTrue(iban_gueltig(SPARKASSE))
		self.assertTrue(iban_gueltig(VR.replace(" ", "")))
		self.assertFalse(iban_gueltig("DE64 0030 0005 4437 72"))  # zu kurz
		self.assertFalse(iban_gueltig("DE65 6225 0030 0005 4437 72"))  # falsche Prüfziffer
		self.assertFalse(iban_gueltig(""))

	def test_zuteilen_in_der_reihenfolge_der_lieferscheine(self):
		self.assertEqual(zuteilen(7, [("a", 4), ("b", 6)]), ([("a", 4), ("b", 3)], 0))
		self.assertEqual(zuteilen(12, [("a", 4), ("b", 6)]), ([("a", 4), ("b", 6)], 2))
		self.assertEqual(zuteilen(3, [("a", 0), ("b", 6)]), ([("b", 3)], 0))
		self.assertEqual(zuteilen(5, []), ([], 5))

	def test_faelligkeit_und_mahnstufen(self):
		self.assertEqual(str(faellig_am("2026-10-01", 14)), "2026-10-15")
		self.assertEqual(naechste_mahnstufe([]), "Zahlungserinnerung")
		self.assertEqual(naechste_mahnstufe(["Zahlungserinnerung"]), "1. Mahnung")
		self.assertEqual(naechste_mahnstufe(["Zahlungserinnerung", "1. Mahnung", "2. Mahnung"]), None)

	def test_pruefsumme_ist_stabil_und_aendert_sich_mit_dem_inhalt(self):
		a = inhalt_hash({"x": 1, "y": [1, 2]})
		self.assertEqual(a, inhalt_hash({"y": [1, 2], "x": 1}))
		self.assertNotEqual(a, inhalt_hash({"x": 2, "y": [1, 2]}))

	def test_euro_und_mahntext(self):
		self.assertEqual(euro(1234.5), "1.234,50 €")
		t = mahntext("1. Mahnung", "RE-2026-0001", "2026-10-01", 309.4, 309.4, "2026-11-01", 5)
		self.assertIn("RE-2026-0001", t)
		self.assertIn("309,40 €", t)
		self.assertIn("Mahngebühr von 5,00 €", t)
		self.assertNotIn("Mahngebühr", mahntext("Zahlungserinnerung", "RE-1", "2026-10-01", 10, 10, "2026-11-01", 0))


class TestRechnung(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Rechnungskunde", "zahlungsziel_tage": 30, "ust_id": "DE999", "leitweg_id": "04-77"}).insert().name
		k = frappe.get_doc("Kunde", self.kunde)
		k.append("adressen", {"typ": "Rechnung und Lieferung", "strasse": "Weg 1", "plz": "72461", "ort": "Albstadt", "standard": 1})
		k.save()
		firma.speichern({"firmenname": "ZZ Firma", "banken": [{"bezeichnung": "Sparkasse SHA", "iban": SPARKASSE}, {"bezeichnung": "VR Bank SHA", "iban": VR}], "mahngebuehr": 5, "mahnfristTage": 7})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def auftrag(self, menge=10, nr="ZZ-R1", serien=False, **kw):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Flansch", nr)]})
		if serien:
			frappe.db.set_value("Bauteil", bauteil.finden(self.kunde, nr), "seriennummern", 1)
		a = angebot.senden(a["id"])
		return auftrag.aus_angebot(a["id"], "PO-9", [{"angebotKey": "t1", "menge": menge, "arbeitsgaenge": PLAN, **kw}])

	def liefern(self, auf, menge):
		return lieferschein.anlegen(self.kunde, [{"auftrag": auf["id"], "auftragsposition": auf["positionen"][0]["key"], "menge": menge}])

	def gesamt(self, auf, **kw):
		return rechnung.anlegen(auf["id"], "Gesamtrechnung", **kw)

	def teil_re(self, auf, *refs):
		pos = auf["positionen"][0]["key"]
		return rechnung.anlegen(auf["id"], "Teilrechnung", [{"lieferschein": ls, "auftragsposition": pos, "menge": n} for ls, n in refs])

	def nummer(self, r):
		return int(r["nummer"].rsplit("-", 1)[1])

	# ------------------------------------------------------------- Firma
	def test_firma_speichert_banken_und_prueft_die_iban(self):
		f = firma.holen()
		self.assertEqual([b["iban"] for b in f["banken"]], [SPARKASSE, VR])
		with self.assertRaises(frappe.ValidationError):
			firma.speichern({"firmenname": "X", "banken": [{"bezeichnung": "Bank", "iban": "DE64 0030 0005 4437 72"}]})
		with self.assertRaises(frappe.ValidationError):
			firma.speichern({"firmenname": " "})

	# ------------------------------------------------------------- Entwurf
	def test_gesamtrechnung_entwurf_mit_sonderkosten_als_eigene_zeilen(self):
		auf = self.auftrag(10)
		r = self.gesamt(auf)
		self.assertEqual((r["status"], r["art"], r["nummer"], r["auftragId"]), ("Entwurf", "Gesamtrechnung", "", auf["id"]))
		self.assertEqual([(p["zeile"], p["art"]) for p in r["positionen"]], [("1", "Bauteil"), ("1.1", "Sonderkosten"), ("1.2", "Sonderkosten")])
		self.assertEqual((r["netto"], r["steuersatz"], r["steuerbetrag"], r["brutto"], r["offen"]), (260.0, 19.0, 49.4, 309.4, 309.4))
		p = r["positionen"][0]
		self.assertEqual((p["menge"], p["einzelpreis"], p["netto"], p["einheit"]), (10, 14.0, 140.0, "Stk"))
		self.assertEqual(r["kundeName"], "ZZ Rechnungskunde")
		self.assertEqual(r["adresse"], ["ZZ Rechnungskunde", "Weg 1", "72461 Albstadt"])
		self.assertEqual((r["kundeUstId"], r["leitwegId"], r["kundenbestellnr"]), ("DE999", "04-77", "PO-9"))
		self.assertEqual(r["zahlungszielTage"], 30)  # vom Kunden, nicht aus der Firma
		self.assertEqual(r["faelligAm"], str(add_days(today(), 30)))

	def test_in_der_rechnung_steht_mit_welchen_lieferscheinen_geliefert_wurde(self):
		auf = self.auftrag(10, serien=True, serienStart=1)
		l1, l2 = self.liefern(auf, 4), self.liefern(auf, 6)
		p = self.gesamt(auf)["positionen"][0]
		self.assertEqual(p["lieferungenText"], f"Geliefert mit {l1['id']} (4 Stk), {l2['id']} (6 Stk)")
		self.assertEqual(p["lieferungen"], [{"lieferschein": l1["id"], "menge": 4}, {"lieferschein": l2["id"], "menge": 6}])
		self.assertEqual(p["serienText"], "0001–0004, 0005–0010")

	def test_noch_nicht_gelieferte_menge_wird_vermerkt(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		p = self.gesamt(auf)["positionen"][0]
		self.assertEqual(p["lieferungenText"], f"Geliefert mit {l1['id']} (4 Stk) · noch nicht geliefert: 6 Stk")
		self.assertEqual(self.gesamt(self.auftrag(5, nr="ZZ-R2"))["positionen"][0]["lieferungenText"], "Noch nicht geliefert")

	# ------------------------------------------------------------- Teilrechnung
	def test_teilrechnung_aus_lieferschein_mit_gewaehlter_menge(self):
		auf = self.auftrag(10)
		l1, l2 = self.liefern(auf, 4), self.liefern(auf, 6)
		r = self.teil_re(auf, (l1["id"], 3))
		self.assertEqual(r["art"], "Teilrechnung")
		p = r["positionen"][0]
		self.assertEqual((p["menge"], p["netto"], p["lieferungenText"]), (3, 42.0, f"Geliefert mit {l1['id']} (3 Stk)"))
		# Sonderkosten kommen vollständig in die erste Rechnung
		self.assertEqual([x["art"] for x in r["positionen"]], ["Bauteil", "Sonderkosten", "Sonderkosten"])
		self.assertEqual(r["netto"], 162.0)
		# zweite Teilrechnung: Rest aus Lieferschein 1 und alles aus Lieferschein 2, ohne Sonderkosten
		r2 = self.teil_re(auf, (l1["id"], 1), (l2["id"], 6))
		self.assertEqual([x["art"] for x in r2["positionen"]], ["Bauteil"])
		self.assertEqual(r2["positionen"][0]["menge"], 7)
		self.assertEqual(r2["netto"], 98.0)

	def test_menge_je_lieferschein_ist_begrenzt(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		self.teil_re(auf, (l1["id"], 3))
		with self.assertRaises(frappe.ValidationError):
			self.teil_re(auf, (l1["id"], 2))  # nur noch 1 frei
		with self.assertRaises(frappe.ValidationError):
			rechnung.anlegen(auf["id"], "Teilrechnung", [])
		with self.assertRaises(frappe.ValidationError):
			rechnung.anlegen(auf["id"], "Teilrechnung", [{"lieferschein": "LS-gibt-es-nicht", "auftragsposition": auf["positionen"][0]["key"], "menge": 1}])

	def test_seriennummern_der_teilrechnung_folgen_den_schon_berechneten(self):
		auf = self.auftrag(10, serien=True, serienStart=1)
		l1 = self.liefern(auf, 6)
		self.assertEqual(self.teil_re(auf, (l1["id"], 2))["positionen"][0]["serienText"], "0001–0002")
		self.assertEqual(self.teil_re(auf, (l1["id"], 3))["positionen"][0]["serienText"], "0003–0005")

	def test_gesamtrechnung_berechnet_nur_den_rest_nach_einer_teilrechnung(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		self.teil_re(auf, (l1["id"], 4))
		r = self.gesamt(auf)
		p = r["positionen"][0]
		self.assertEqual((p["menge"], p["netto"]), (6, 84.0))
		self.assertEqual([x["art"] for x in r["positionen"]], ["Bauteil"])  # Sonderkosten sind schon in der ersten Rechnung

	def test_nichts_mehr_zu_berechnen(self):
		auf = self.auftrag(10)
		self.gesamt(auf)
		with self.assertRaises(frappe.ValidationError):
			self.gesamt(auf)

	def test_vorschlag_zeigt_den_stand(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		self.teil_re(auf, (l1["id"], 3))
		v = rechnung.vorschlag(auf["id"])
		p = v["positionen"][0]
		self.assertEqual((p["bestellt"], p["geliefert"], p["berechnet"], p["offen"]), (10, 4, 3, 7))
		self.assertTrue(all(k["inRechnung"] for k in p["kosten"]))
		self.assertEqual(v["lieferscheine"][0]["positionen"][0], {"auftragPosKey": p["key"], "menge": 4, "berechnet": 3, "frei": 1})

	# ------------------------------------------------------------- Festschreiben
	def test_festschreiben_vergibt_lueckenlose_nummern_und_sperrt(self):
		a1, a2 = self.auftrag(10), self.auftrag(5, nr="ZZ-R2")
		r1 = rechnung.festschreiben(self.gesamt(a1)["id"])
		r2 = rechnung.festschreiben(self.gesamt(a2)["id"])
		self.assertRegex(r1["nummer"], r"^RE-\d{4}-\d{4}$")
		self.assertEqual(self.nummer(r2), self.nummer(r1) + 1)
		self.assertEqual((r1["status"], r1["rechnungsdatum"]), ("Offen", str(today())))
		self.assertEqual(r1["faelligAm"], str(add_days(today(), 30)))
		self.assertEqual(len(r1["inhaltHash"]), 64)
		self.assertEqual(r1["firma"]["firmenname"], "ZZ Firma")
		self.assertIn(SPARKASSE, r1["zahlungshinweis"])
		self.assertIn(VR, r1["zahlungshinweis"])
		self.assertIn(r1["nummer"], r1["zahlungshinweis"])
		# unveränderlich
		doc = frappe.get_doc("Rechnung", r1["id"])
		doc.bemerkung = "geändert"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Rechnung", r1["id"])
		with self.assertRaises(frappe.ValidationError):
			rechnung.festschreiben(r1["id"])
		with self.assertRaises(frappe.ValidationError):
			rechnung.speichern(r1["id"], {"bemerkung": "x"})

	def test_snapshot_bleibt_auch_wenn_die_firma_sich_aendert(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		firma.speichern({"firmenname": "Neuer Name", "banken": []})
		neu = next(x for x in rechnung.liste() if x["id"] == r["id"])
		self.assertEqual(neu["firma"]["firmenname"], "ZZ Firma")

	def test_sonderkosten_werden_beim_festschreiben_markiert(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		r = rechnung.festschreiben(self.teil_re(auf, (l1["id"], 4))["id"])
		kosten = next(a for a in auftrag.liste() if a["id"] == auf["id"])["positionen"][0]["kostenAbgerechnet"]
		self.assertEqual(set(kosten.values()), {r["id"]})
		self.assertEqual(set(kosten), {"Rüstkosten", "Messkosten"})

	def test_derselbe_auftrag_zwei_entwuerfe_nur_einer_wird_festgeschrieben(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		a = self.teil_re(auf, (l1["id"], 4))
		b = self.gesamt(auf)  # Entwurf mit dem Rest, dessen Sonderkosten schon in Entwurf a stehen
		self.assertEqual([x["art"] for x in b["positionen"]], ["Bauteil"])
		rechnung.festschreiben(a["id"])
		rechnung.festschreiben(b["id"])

	def test_entwurf_aendern_und_verwerfen(self):
		r = self.gesamt(self.auftrag())
		neu = rechnung.speichern(r["id"], {"rechnungsdatum": "2026-12-01", "zahlungszielTage": 10, "bemerkung": "Bitte beachten", "kundenbestellnr": "X1"})
		self.assertEqual((neu["faelligAm"], neu["bemerkung"], neu["kundenbestellnr"]), ("2026-12-11", "Bitte beachten", "X1"))
		rechnung.verwerfen(r["id"])
		self.assertFalse(frappe.db.exists("Rechnung", r["id"]))
		self.gesamt(self.auftrag(5, nr="ZZ-R3"))

	# ------------------------------------------------------------- Storno
	def test_storno_erzeugt_gutschrift_und_gibt_alles_wieder_frei(self):
		auf = self.auftrag(10)
		r = rechnung.festschreiben(self.gesamt(auf)["id"])
		ergebnis = rechnung.stornieren(r["id"], "falscher Preis")
		s, o = ergebnis["storno"], ergebnis["original"]
		self.assertEqual((s["art"], s["status"], s["stornoZu"], s["stornoGrund"]), ("Storno", "Gutschrift", r["id"], "falscher Preis"))
		self.assertEqual(self.nummer(s), self.nummer(r) + 1)
		self.assertEqual((s["netto"], s["steuerbetrag"], s["brutto"]), (-260.0, -49.4, -309.4))
		self.assertEqual([p["menge"] for p in s["positionen"]][:1], [-10])
		self.assertEqual((o["status"], o["storniertDurch"], o["offen"]), ("Storniert", s["id"], 0))
		# Menge und Sonderkosten sind wieder frei
		neu = self.gesamt(auf)
		self.assertEqual((neu["positionen"][0]["menge"], len(neu["positionen"])), (10, 3))
		with self.assertRaises(frappe.ValidationError):
			rechnung.stornieren(r["id"], "nochmal")
		with self.assertRaises(frappe.ValidationError):
			rechnung.stornieren(neu["id"], "Entwurf")  # nur festgeschriebene
		with self.assertRaises(frappe.ValidationError):
			rechnung.stornieren(r["id"], " ")

	def test_auftrag_zeigt_den_abrechnungsstand_mit_verweisen(self):
		auf = self.auftrag(10)
		l1 = self.liefern(auf, 4)
		r = rechnung.festschreiben(self.teil_re(auf, (l1["id"], 4))["id"])
		a = next(x for x in auftrag.liste() if x["id"] == auf["id"])
		self.assertEqual(a["abrechnung"]["status"], "Teilweise berechnet")
		self.assertEqual(a["positionen"][0]["berechnet"], 4)
		self.assertEqual([(x["id"], x["menge"]) for x in a["positionen"][0]["rechnungen"]], [(r["id"], 4)])
		self.assertEqual([x["id"] for x in a["abrechnung"]["rechnungen"]], [r["id"]])
		rechnung.festschreiben(self.gesamt(auf)["id"])
		self.assertEqual(next(x for x in auftrag.liste() if x["id"] == auf["id"])["abrechnung"]["status"], "Berechnet")
		self.assertEqual(next(x for x in lieferschein.liste() if x["id"] == l1["id"])["rechnungen"], [r["id"]])

	# ------------------------------------------------------------- Zahlung
	def test_zahlungen_teilweise_ganz_und_storniert(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		x = rechnung.zahlung_erfassen(r["id"], 100, referenz="Anzahlung", konto="Sparkasse SHA")
		self.assertEqual((x["status"], x["bezahlt"], x["offen"]), ("Teilbezahlt", 100.0, 209.4))
		with self.assertRaises(frappe.ValidationError):
			rechnung.zahlung_erfassen(r["id"], 300)  # mehr als offen
		with self.assertRaises(frappe.ValidationError):
			rechnung.zahlung_erfassen(r["id"], 0)
		x = rechnung.zahlung_erfassen(r["id"], 209.4, zahlungsdatum="2026-12-24")
		self.assertEqual((x["status"], x["bezahlt"], x["offen"]), ("Bezahlt", 309.4, 0))
		self.assertEqual([(z["betrag"], z["datum"]) for z in x["zahlungen"]], [(100.0, str(today())), (209.4, "2026-12-24")])
		with self.assertRaises(frappe.ValidationError):
			rechnung.zahlung_erfassen(r["id"], 1)  # schon bezahlt
		zid = x["zahlungen"][1]["id"]
		x = rechnung.zahlung_stornieren(zid, "falsch zugeordnet")
		self.assertEqual((x["status"], x["offen"]), ("Teilbezahlt", 209.4))
		self.assertTrue(x["zahlungen"][1]["storniert"])
		with self.assertRaises(frappe.ValidationError):
			rechnung.zahlung_stornieren(zid, "nochmal")
		with self.assertRaises(frappe.ValidationError):
			doc = frappe.get_doc("Zahlung", zid)
			doc.betrag = 1
			doc.save()

	def test_zahlung_nur_fuer_festgeschriebene_rechnungen(self):
		with self.assertRaises(frappe.ValidationError):
			rechnung.zahlung_erfassen(self.gesamt(self.auftrag())["id"], 10)

	# ------------------------------------------------------------- Mahnwesen
	def ueberfaellig(self, r, tage=10):
		frappe.db.set_value("Rechnung", r["id"], "faellig_am", add_days(today(), -tage))

	def test_mahnung_nur_bei_ueberfaelliger_rechnung(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		with self.assertRaises(frappe.ValidationError):
			mahnung.anlegen(r["id"])
		self.assertEqual(mahnung.vorschlag(), [])

	def test_mahnstufen_der_reihe_nach_mit_frist(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		self.ueberfaellig(r, 10)
		v = next(x for x in mahnung.vorschlag() if x["rechnungId"] == r["id"])
		self.assertEqual((v["naechsteStufe"], v["bereit"], v["tageUeberfaellig"], v["offen"]), ("Zahlungserinnerung", True, 10, 309.4))
		m1 = mahnung.anlegen(r["id"])
		self.assertTrue(m1["id"].startswith("MA-"))
		self.assertEqual((m1["stufe"], m1["status"], m1["gebuehr"], m1["offenerBetrag"], m1["fristBis"]), ("Zahlungserinnerung", "Angelegt", 0, 309.4, str(add_days(today(), 7))))
		self.assertIn(r["nummer"], m1["text"])
		# solange die Frist läuft, ist die nächste Stufe nicht bereit
		v = next(x for x in mahnung.vorschlag() if x["rechnungId"] == r["id"])
		self.assertEqual((v["naechsteStufe"], v["bereit"]), ("1. Mahnung", False))
		with self.assertRaises(frappe.ValidationError):
			mahnung.anlegen(r["id"], "Zahlungserinnerung")  # gibt es schon
		frappe.db.set_value("Mahnung", m1["id"], "frist_bis", add_days(today(), -1))
		v = next(x for x in mahnung.vorschlag() if x["rechnungId"] == r["id"])
		self.assertTrue(v["bereit"])
		m2 = mahnung.anlegen(r["id"])
		self.assertEqual((m2["stufe"], m2["gebuehr"]), ("1. Mahnung", 5.0))
		self.assertIn("Mahngebühr", m2["text"])

	def test_mahnung_versendet_zurueckgezogen_und_erledigt(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		self.ueberfaellig(r)
		m = mahnung.anlegen(r["id"])
		self.assertEqual(mahnung.versendet_setzen(m["id"])["status"], "Versendet")
		with self.assertRaises(frappe.ValidationError):
			mahnung.versendet_setzen(m["id"])
		self.assertEqual(mahnung.zurueckziehen(m["id"])["status"], "Zurückgezogen")
		# nach dem Zurückziehen beginnt die Stufe wieder von vorn
		m2 = mahnung.anlegen(r["id"])
		self.assertEqual(m2["stufe"], "Zahlungserinnerung")
		x = rechnung.zahlung_erfassen(r["id"], 309.4)
		self.assertEqual(x["status"], "Bezahlt")
		self.assertEqual(next(a for a in mahnung.liste() if a["id"] == m2["id"])["status"], "Erledigt")
		self.assertEqual(mahnung.vorschlag(), [])

	def test_storno_zieht_offene_mahnungen_zurueck(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		self.ueberfaellig(r)
		m = mahnung.anlegen(r["id"])
		rechnung.stornieren(r["id"], "Irrtum")
		self.assertEqual(next(a for a in mahnung.liste() if a["id"] == m["id"])["status"], "Zurückgezogen")

	def test_mahnungen_lassen_sich_nicht_aendern_oder_loeschen(self):
		r = rechnung.festschreiben(self.gesamt(self.auftrag())["id"])
		self.ueberfaellig(r)
		m = mahnung.anlegen(r["id"])
		doc = frappe.get_doc("Mahnung", m["id"])
		doc.text = "x"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Mahnung", m["id"])

	def test_bootstrap_und_gast(self):
		from cnc_one.api import stamm

		r = self.gesamt(self.auftrag())
		daten = stamm.bootstrap()
		self.assertIn(r["id"], [x["id"] for x in daten["rechnungen"]])
		self.assertEqual(daten["firma"]["firmenname"], "ZZ Firma")
		self.assertIn("mahnungen", daten)
		frappe.set_user("Guest")
		for fn in (rechnung.liste, mahnung.liste, firma.holen, mahnung.vorschlag):
			with self.assertRaises(frappe.PermissionError):
				fn()
