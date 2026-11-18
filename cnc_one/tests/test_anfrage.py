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
		self.assertEqual(r["antwort"], {"angebotsnr": "AN-5521", "gueltigBis": "2026-12-31", "lieferzeit": "", "preise": preise})
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

	def test_vorlage_ueber_stammdaten(self):
		from cnc_one.api import stammdaten

		v = stammdaten.speichern("anfragevorlage", {"name": "ZZ Aluminium", "stichwoerter": "alu,\n en aw ", "isoGruppe": "N", "art": "Material", "lieferanten": ["ZZ Alu A", "ZZ gibt es nicht"], "hinweis": "mit Zeugnis"})
		self.assertEqual((v["stichwoerter"], v["isoGruppe"], v["lieferanten"], v["aktiv"]), ("alu, en aw", "N", ["ZZ Alu A"], True))
		self.assertIn("ZZ Aluminium", [x["name"] for x in stammdaten.liste("anfragevorlage")])
