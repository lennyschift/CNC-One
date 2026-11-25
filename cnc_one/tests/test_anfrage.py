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
		self.assertEqual(r["antwort"], {"angebotsnr": "AN-5521", "gueltigBis": "2026-12-31", "lieferzeit": "", "preise": preise, "nebenkosten": 0, "nebenkostenText": "", "pdf": "", "daten": None})
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

	def test_freie_anfrage_fuer_material_ohne_angebot(self):
		pos = [
			{"teil": {"name": "Rundstahl", "material": "42CrMo4"}, "abmessung": "Ø 50 x 3000 mm", "einheit": "Stangen", "mengen": [2, 5]},
			{"teil": {"name": "Flachstahl", "material": "S355"}, "abmessung": "40 x 10 mm", "einheit": "m", "mengen": [12]},
		]
		neu = anfrage.anlegen("", ["ZZ Härterei A"], pos, "bitte mit Zeugnis 3.1")
		a = neu[0]
		self.assertEqual((a["angebotId"], a["art"], a["kundeName"]), ("", "Material", ""))
		self.assertEqual([p["key"] for p in a["positionen"]], ["frei:1", "frei:2"])
		self.assertEqual([p["einheit"] for p in a["positionen"]], ["Stangen", "m"])
		self.assertEqual(a["positionen"][0]["abmessung"], "Ø 50 x 3000 mm")
		self.assertEqual(a["positionen"][0]["teil"]["material"], "42CrMo4")
		# Preise erfassen geht genauso wie bei der Fremdvergabe
		r = anfrage.antwort_erfassen(a["id"], {"angebotsnr": "ZZ-9", "preise": [{"posKey": "frei:1", "menge": 2, "proStk": 88.5, "einmalig": 0}]})
		self.assertEqual(r["status"], "Angebot erhalten")
		# ohne Bezeichnung geht es nicht
		with self.assertRaises(frappe.ValidationError):
			anfrage.anlegen("", ["ZZ Härterei A"], [{"teil": {"name": " "}, "mengen": [1]}])
		# aus der Workbench bleibt es eine Fremdvergabe
		self.assertEqual(anfrage.anlegen(self.angebot, ["ZZ Härterei B"], [position()])[0]["art"], "Fremdvergabe")


class TestAnfrageMail(IntegrationTestCase):
	"""Anfrage als eine Mail mit den Lieferanten in BCC, Antworten landen bei der richtigen Anfrage."""

	def setUp(self):
		from cnc_one.tests.dateischutz import dateien_vorher

		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		for n, m in (("ZZ Alu A", "verkauf@zz-alu-a.de"), ("ZZ Alu B", "info@zz-alu-b.de"), ("ZZ Alu C", "")):
			frappe.get_doc({"doctype": "Lieferant", "lieferantenname": n, "email": m}).insert()
		s = frappe.get_single("Mail Einstellungen")
		s.update({"benutzer": "info@zz-cnc.de", "absender_name": "ZZ CNC", "imap_server": "zz.invalid", "smtp_server": "smtp.zz.invalid", "smtp_port": 465, "verschluesselung": "SSL/TLS", "stichwoerter": "Anfrage"})
		s.passwort = "zz-geheim"
		s.save()
		self.pos = [{"teil": {"name": "Rundstange", "material": "EN AW-6082"}, "abmessung": "Ø 40 x 3000", "einheit": "Stangen", "mengen": [2, 6]}]

	def tearDown(self):
		from cnc_one.tests.dateischutz import eigene_dateien_loeschen

		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def senden(self):
		from unittest.mock import patch

		from cnc_one.logic import mail
		from cnc_one.tests.test_mail import FakeSmtp

		neu = anfrage.anlegen("", ["ZZ Alu A", "ZZ Alu B", "ZZ Alu C"], self.pos)
		vorgang = neu[0]["vorgang"]
		self.assertEqual({x["vorgang"] for x in neu}, {neu[0]["id"]})
		v = anfrage.mail_vorschlag(vorgang)
		FakeSmtp.gesendet = []
		with patch.object(mail.smtplib, "SMTP_SSL", FakeSmtp), patch.object(mail, "gesendet_ablegen", return_value=""):
			r = anfrage.mail_senden(vorgang, v["an"], "", v["bcc"], v["betreff"], v["text"].replace("Mit freundlichen", "Gerne auch Teillieferung.\n\nMit freundlichen"))
		return vorgang, v, r, FakeSmtp.gesendet[0]

	def test_eine_mail_lieferanten_in_bcc_mit_tabelle(self):
		vorgang, v, r, g = self.senden()
		self.assertEqual((v["an"], v["bcc"], v["ohneAdresse"]), ("info@zz-cnc.de", "verkauf@zz-alu-a.de, info@zz-alu-b.de", ["ZZ Alu C"]))
		self.assertIn("{tabelle}", v["text"])
		self.assertEqual(v["tabelle"]["zeilen"][0], ["1", "Rundstange", "EN AW-6082", "Ø 40 x 3000", "2 Stangen / 6 Stangen"])
		msg = g["msg"]
		self.assertEqual(g["an"], ["info@zz-cnc.de", "verkauf@zz-alu-a.de", "info@zz-alu-b.de"])
		self.assertIsNone(msg["Bcc"])  # die Lieferanten sehen sich nicht
		self.assertEqual(msg["To"], "info@zz-cnc.de")
		self.assertIn(vorgang, msg["Subject"])
		plain = msg.get_body(("plain",)).get_content()
		self.assertIn("2 Stangen / 6 Stangen", plain)
		self.assertIn("Gerne auch Teillieferung.", plain)
		self.assertNotIn("{tabelle}", plain)
		self.assertIn("<table", msg.get_body(("html",)).get_content())
		self.assertTrue(all(a["versendetAm"] and a["nachrichten"][-1]["richtung"] == "Ausgang" for a in r["anfragen"]))

	def test_antwort_landet_beim_richtigen_lieferanten(self):
		from cnc_one.logic import mail
		from cnc_one.tests.test_dateien import leeres_pdf
		from cnc_one.tests.test_mail import zz_mail

		vorgang, _v, r, g = self.senden()
		# Antwort im Verlauf (In-Reply-To), Absender ist Lieferant B
		d = mail.verarbeiten(zz_mail(betreff=f"AW: Anfrage {vorgang}: Rundstange", von="Info <info@zz-alu-b.de>", mid="<zz-la1@zz-alu-b.de>", antwort_auf=g["msg"]["Message-ID"], text="Preis 88 € je Stange"))
		self.assertEqual(d.doctype, "Lieferantenanfrage")
		self.assertEqual(d.lieferant, "ZZ Alu B")
		self.assertEqual((d.neue_antwort, d.nachrichten[-1].richtung), (1, "Eingang"))
		# neue Mail nur mit der Nummer im Betreff, Absender aus der Domain von A
		d2 = mail.verarbeiten(zz_mail(betreff=f"Angebot zu Ihrer Anfrage {vorgang}", von="Max <max@zz-alu-a.de>", mid="<zz-la2@zz-alu-a.de>", anhaenge=[("zz-angebot-a.pdf", leeres_pdf("zz-angebot-a"))]))
		self.assertEqual(d2.lieferant, "ZZ Alu A")
		self.assertEqual(frappe.db.count("File", {"attached_to_doctype": "Lieferantenanfrage", "attached_to_name": d2.name}), 1)
		self.assertFalse(frappe.db.exists("Mail Anfrage", {"betreff": f"Angebot zu Ihrer Anfrage {vorgang}"}))
		# eine Kundenanfrage ohne LA-Nummer bleibt eine Kundenanfrage
		k = mail.verarbeiten(zz_mail(betreff="Anfrage ZZ Welle", mid="<zz-k1@zz-kunde.de>"))
		self.assertEqual(k.doctype, "Mail Anfrage")
		# Preise erfassen nimmt die Markierung „neue Antwort“ weg, Zuschlag setzen
		a = anfrage.antwort_erfassen(d.name, {"angebotsnr": "B-1", "lieferzeit": "2 Wochen", "preise": [{"posKey": "frei:1", "menge": 2, "proStk": 88, "einmalig": 0}]})
		self.assertEqual((a["neueAntwort"], a["antwort"]["lieferzeit"]), (False, "2 Wochen"))
		self.assertTrue(anfrage.zuschlag(d.name, 1)["zuschlag"])

	def test_ansprechpartner_bekommen_anfragen_und_ihre_antworten_landen_richtig(self):
		from cnc_one.api import stammdaten
		from cnc_one.logic import mail
		from cnc_one.tests.test_mail import zz_mail

		stammdaten.speichern("lieferant", {"id": "ZZ Alu C", "name": "ZZ Alu C", "aktiv": True, "kontakte": [
			{"vorname": "Eva", "nachname": "Zett", "funktion": "Verkauf", "email": "Eva@zz-alu-c.de", "anfragen": True},
			{"nachname": "Buchhaltung", "email": "rechnung@zz-alu-c.de"},
			{"vorname": "", "nachname": "", "email": ""},
		]})
		self.assertEqual([k["email"] for k in stammdaten.lieferant_ui(frappe.get_doc("Lieferant", "ZZ Alu C"))["kontakte"]], ["eva@zz-alu-c.de", "rechnung@zz-alu-c.de"])
		vorgang, v, _r, g = self.senden()
		self.assertEqual((v["bcc"], v["ohneAdresse"]), ("verkauf@zz-alu-a.de, info@zz-alu-b.de, eva@zz-alu-c.de", []))
		self.assertIn("eva@zz-alu-c.de", g["an"])
		# Antwort von der Buchhaltung (Ansprechpartner ohne Anfragen) wird trotzdem C zugeordnet
		d = mail.verarbeiten(zz_mail(betreff=f"Angebot {vorgang}", von="rechnung@zz-alu-c.de", mid="<zz-la-c@zz-alu-c.de>"))
		self.assertEqual(d.lieferant, "ZZ Alu C")
		self.assertEqual(mail.lieferant_zur_adresse("eva@zz-alu-c.de"), "ZZ Alu C")

	def test_vorschau_genau_wie_beim_senden(self):
		neu = anfrage.anlegen("", ["ZZ Alu A"], self.pos)
		vorgang = neu[0]["vorgang"]
		v = anfrage.mail_vorschlag(vorgang)
		h = anfrage.mail_ansehen(vorgang, v["text"])["html"]
		self.assertIn("<table", h)
		self.assertIn("2 Stangen / 6 Stangen", h)
		self.assertNotIn("{tabelle}", h)
		self.assertIn(anfrage.mail_inhalt(v["text"], anfrage.tabelle(frappe.get_doc("Lieferantenanfrage", vorgang))), anfrage.mail_html(v["text"], anfrage.tabelle(frappe.get_doc("Lieferantenanfrage", vorgang))))
		m = anfrage.mail_muster("Material", "mit Zeugnis", [{"teil": {"name": "Platte", "material": "EN AW-5083"}, "abmessung": "Platte 20 mm · Zuschnitt 500 × 300 mm", "einheit": "Zuschnitte", "mengen": [4]}])
		self.assertTrue(m["betreff"].startswith("Anfrage LA-") and m["betreff"].endswith(": Platte"))
		self.assertIn("Zuschnitt 500 × 300 mm", m["html"])
		self.assertIn("Hinweis: mit Zeugnis", m["html"])

	def test_angebot_kommt_spaeter_dazu(self):
		neu = anfrage.anlegen("", ["ZZ Alu A"], self.pos)
		vorgang = neu[0]["vorgang"]
		b = anfrage.lieferant_dazu(vorgang, "ZZ Alu B")
		self.assertEqual((b["vorgang"], b["lieferantId"]), (vorgang, "ZZ Alu B"))
		self.assertEqual([p["key"] for p in b["positionen"]], [p["key"] for p in neu[0]["positionen"]])
		self.assertEqual(len(anfrage.vorgang_docs(vorgang)), 2)
		# zweimal derselbe Lieferant: keine zweite Anfrage
		self.assertEqual(anfrage.lieferant_dazu(vorgang, "ZZ Alu B")["id"], b["id"])
		self.assertEqual(len(anfrage.vorgang_docs(vorgang)), 2)
		# Preise wie bei jedem anderen Lieferanten
		r = anfrage.antwort_erfassen(b["id"], {"angebotsnr": "B-9", "preise": [{"posKey": b["positionen"][0]["key"], "menge": 2, "proStk": 80, "einmalig": 0}]})
		self.assertEqual(r["antwort"]["angebotsnr"], "B-9")

	def test_tabelle_ohne_doppelungen_mit_anforderungen(self):
		pos = lambda **k: frappe._dict({"bezeichnung": "", "teilenummer": "", "zeichnungsnr": "", "material": "", "ag_name": "", "abmessung": "", "anforderungen": "", "einheit": "Stangen", "mengen": "[20]", **k})
		doc = frappe._dict(positionen=[pos(
			bezeichnung="EN AW-6082 · Flach 20 × 10 · gezogen h11", material="EN AW-6082 T6",
			abmessung="Flach 20 × 10 · gezogen h11 · Stangenlänge 3000 mm", anforderungen="Abnahmeprüfzeugnis 3.1 (EN 10204), RoHS/REACH",
		)])
		t = anfrage.tabelle(doc)
		self.assertEqual(t["kopf"], ["Pos", "Werkstoff", "Abmessung", "Anforderungen", "Menge"])
		self.assertEqual(t["zeilen"][0], ["1", "EN AW-6082 T6", "Flach 20 × 10 · gezogen h11 · Stangenlänge 3000 mm", "Abnahmeprüfzeugnis 3.1 (EN 10204), RoHS/REACH", "20 Stangen"])
		# eine eigene Bezeichnung bleibt stehen; die Vorschau vor dem Anlegen zeigt die Anforderungen auch
		doc.positionen.append(pos(bezeichnung="Rundstange", material="S235", abmessung="Ø 40"))
		self.assertEqual(anfrage.tabelle(doc)["kopf"], ["Pos", "Bezeichnung", "Werkstoff", "Abmessung", "Anforderungen", "Menge"])
		m = anfrage.mail_muster("Material", "", [{"teil": {"name": "x", "material": "S235"}, "abmessung": "Ø 40", "anforderungen": "RoHS/REACH", "einheit": "Stk", "mengen": [1]}])
		self.assertIn("RoHS/REACH", m["html"])
		self.assertIn("Anforderungen", anfrage.tabelle_text(anfrage.tabelle(doc)))

	def test_aendern_legt_neue_fassung_an_und_ersetzt_die_alte(self):
		r = [{**self.pos[0], "roh": {"werkstoff": "EN AW-6082", "form": "Rund", "abmessung": "Ø40", "laenge": 3000, "unbekannt": "x"}}]
		neu = anfrage.anlegen("", ["ZZ Alu A", "ZZ Alu B"], r, notiz="alt", art="Material")
		vorgang = neu[0]["vorgang"]
		self.assertEqual(neu[0]["positionen"][0]["roh"]["laenge"], 3000)
		self.assertNotIn("unbekannt", neu[0]["positionen"][0]["roh"])
		pos = [{**self.pos[0], "mengen": [10]}]
		f1 = anfrage.aendern(vorgang, ["ZZ Alu A", "ZZ Alu C"], pos, notiz="neu", grund="Menge 10")
		namen = {x["lieferantId"]: x for x in f1["neu"]}
		self.assertEqual(namen["ZZ Alu A"]["id"], f"{neu[0]['id']}-1")
		self.assertEqual(namen["ZZ Alu A"]["vorgang"], f"{vorgang}-1")
		self.assertEqual(namen["ZZ Alu C"]["vorgang"], f"{vorgang}-1")  # neuer Lieferant: neue Nummer, gleicher Vorgang
		self.assertEqual((namen["ZZ Alu A"]["fassung"], namen["ZZ Alu A"]["aenderungsgrund"], namen["ZZ Alu A"]["positionen"][0]["mengen"]), (1, "Menge 10", [10]))
		alt = {x["lieferantId"]: x for x in f1["ersetzt"]}
		self.assertEqual((alt["ZZ Alu A"]["status"], alt["ZZ Alu A"]["ersetztDurch"]), ("Ersetzt", f"{neu[0]['id']}-1"))
		self.assertEqual(alt["ZZ Alu B"]["ersetztDurch"], f"{vorgang}-1")
		# die Mail nennt die vorige Anfrage
		self.assertIn(f"unsere Anfrage {vorgang} hat sich geändert", anfrage.mail_vorschlag(f"{vorgang}-1")["text"])
		# die alte lässt sich nicht noch einmal ändern, die neue schon (-2)
		with self.assertRaises(frappe.ValidationError):
			anfrage.aendern(vorgang, ["ZZ Alu A"], pos)
		f2 = anfrage.aendern(f"{vorgang}-1", ["ZZ Alu A"], pos)
		self.assertEqual(f2["neu"][0]["id"], f"{neu[0]['id']}-2")
		self.assertEqual(anfrage.vorgang_stamm(f"{vorgang}-2"), vorgang)
		# Antwort mit der neuen Nummer im Betreff landet bei der neuen Fassung
		from cnc_one.logic import mail

		self.assertEqual(mail.lieferantenanfrage_zur_mail(f"AW: Anfrage {vorgang}-2: Rundstange", "verkauf@zz-alu-a.de", []).name, f"{neu[0]['id']}-2")

	def test_zuschlag_fuer_ausgewaehlte_positionen_jede_position_nur_einmal(self):
		zwei = [*self.pos, {"teil": {"name": "Platte", "material": "EN AW-5083"}, "einheit": "Stk", "mengen": [1]}]
		a, b = anfrage.anlegen("", ["ZZ Alu A", "ZZ Alu B"], zwei)
		for x in (a, b):
			anfrage.antwort_erfassen(x["id"], {"preise": [{"posKey": "frei:1", "menge": 2, "proStk": 50, "einmalig": 0}, {"posKey": "frei:2", "menge": 1, "proStk": 80, "einmalig": 0}]})
		# ohne Auswahl: alle Positionen mit Preis
		r = anfrage.zuschlag(a["id"], 1)
		self.assertEqual((r["zuschlagPositionen"], r["zuschlagAlternativen"], r["geaenderte"]), (["frei:1", "frei:2"], [], []))
		# B bekommt Position 2 und eine Alternative: bei A bleibt nur Position 1
		r = anfrage.zuschlag(b["id"], 1, ["frei:2"], [3])
		self.assertEqual((r["zuschlagPositionen"], r["zuschlagAlternativen"]), (["frei:2"], [3]))
		self.assertEqual([(x["id"], x["zuschlagPositionen"]) for x in r["geaenderte"]], [(a["id"], ["frei:1"])])
		# B bekommt jetzt auch Position 1: A hat keinen Zuschlag mehr
		r = anfrage.zuschlag(b["id"], 1, ["frei:1", "frei:2"])
		self.assertEqual([(x["zuschlag"], x["zuschlagPositionen"]) for x in r["geaenderte"]], [(False, [])])
		self.assertEqual(anfrage.zuschlag(b["id"], 0)["zuschlagPositionen"], [])
		with self.assertRaises(frappe.ValidationError):
			anfrage.zuschlag(a["id"], 1, [])
		with self.assertRaises(frappe.ValidationError):
			anfrage.zuschlag(a["id"], 1, ["frei:9"])

	def test_angebot_aus_pdf_mit_nebenkosten_und_vorlage_des_lieferanten(self):
		a = anfrage.anlegen("", ["ZZ Alu A"], self.pos)[0]
		daten = {"kopf": {"angebotsnr": "945914"}, "positionen": [{"pos": "1", "betrag": 435.04, "zuordnung": "frei:1"}]}
		r = anfrage.antwort_erfassen(a["id"], {
			"angebotsnr": "945914", "preise": [{"posKey": "frei:1", "menge": 2, "proStk": 24.17, "einmalig": 0}],
			"nebenkosten": 118.2, "nebenkostenText": "Verpackung 30,00\nFracht 88,20", "pdf": "/private/files/zz.pdf", "daten": daten,
		})
		self.assertEqual((r["antwort"]["nebenkosten"], r["antwort"]["pdf"], r["antwort"]["daten"]["kopf"]["angebotsnr"]), (118.2, "/private/files/zz.pdf", "945914"))
		self.assertIn("Fracht", r["antwort"]["nebenkostenText"])
		# Vorlage des Lieferanten merken und wieder vergessen
		anfrage.angebotsvorlage_lernen("ZZ Alu A", {"spalten": {"gew. (kg)": "gewicht"}, "preisJe": "kg"})
		self.assertEqual(anfrage.angebotsvorlage("ZZ Alu A"), {"spalten": {"gew. (kg)": "gewicht"}, "preisJe": "kg"})
		anfrage.angebotsvorlage_lernen("ZZ Alu A", {})
		self.assertEqual(anfrage.angebotsvorlage("ZZ Alu A"), {})

	def test_mail_aus_dem_posteingang_zur_anfrage(self):
		from cnc_one.api import mail as mail_api
		from cnc_one.logic import mail
		from cnc_one.tests.test_dateien import leeres_pdf
		from cnc_one.tests.test_mail import zz_mail

		a = anfrage.anlegen("", ["ZZ Alu A"], self.pos)[0]
		vorher = mail_api.anzahl()
		# Antwort ohne Anfragenummer und nicht im Verlauf: landet im Posteingang beim Lieferanten
		m = mail.verarbeiten(zz_mail(betreff="Ihr Angebot 945914", von="Verkauf <verkauf@zz-alu-a.de>", mid="<zz-pe1@zz-alu-a.de>", anhaenge=[("zz-angebot.pdf", leeres_pdf("zz-pe1"))]))
		self.assertEqual((m.doctype, m.lieferant), ("Mail Anfrage", "ZZ Alu A"))
		r = anfrage.mail_uebernehmen(m.name, a["id"])
		self.assertFalse(frappe.db.exists("Mail Anfrage", m.name))
		self.assertTrue(r["neueAntwort"])
		self.assertEqual(r["nachrichten"][-1]["betreff"], "Ihr Angebot 945914")
		self.assertEqual(r["nachrichten"][-1]["anhaenge"][0]["name"], "zz-angebot.pdf")
		self.assertTrue(frappe.db.exists("File", {"attached_to_doctype": "Lieferantenanfrage", "attached_to_name": a["id"], "file_name": "zz-angebot.pdf"}))
		# die Mail wird nicht erneut geholt, das Abzeichen zählt die neue Antwort des Lieferanten
		self.assertIsNone(mail.verarbeiten(zz_mail(betreff="Ihr Angebot 945914", von="verkauf@zz-alu-a.de", mid="<zz-pe1@zz-alu-a.de>")))
		self.assertEqual(mail_api.anzahl(), vorher + 1)

	def test_vorlage_ueber_stammdaten(self):
		from cnc_one.api import stammdaten

		v = stammdaten.speichern("anfragevorlage", {"name": "ZZ Aluminium", "stichwoerter": "alu,\n en aw ", "isoGruppe": "N", "art": "Material", "lieferanten": ["ZZ Alu A", "ZZ gibt es nicht"], "hinweis": "mit Zeugnis"})
		self.assertEqual((v["stichwoerter"], v["isoGruppe"], v["lieferanten"], v["aktiv"]), ("alu, en aw", "N", ["ZZ Alu A"], True))
		self.assertIn("ZZ Aluminium", [x["name"] for x in stammdaten.liste("anfragevorlage")])
