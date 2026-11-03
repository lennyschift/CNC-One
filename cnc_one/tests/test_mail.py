import re
from email.message import EmailMessage
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen
from cnc_one.api import mail as mail_api
from cnc_one.logic import mail
from cnc_one.tests.test_dateien import leeres_pdf


def zz_mail(betreff="Anfrage ZZ Flansch", von="Max Mustermann <einkauf@zz-kunde.de>", mid="<zz-1@zz-kunde.de>", antwort_auf="", text="Bitte um Angebot für 10 Stück.", anhaenge=(), html=False, signatur=False):
	m = EmailMessage()
	m["Subject"] = betreff
	m["From"] = von
	m["To"] = "info@zz-cnc.de"
	m["Cc"] = "Erika Muster <erika@zz-kunde.de>"
	m["Date"] = "Sun, 01 Nov 2026 09:30:00 +0000"
	m["Message-ID"] = mid
	if antwort_auf:
		m["In-Reply-To"] = antwort_auf
		m["References"] = antwort_auf
	if html:
		m.set_content("<p>Hallo,</p><p><b>" + text + "</b></p>", subtype="html")
	else:
		m.set_content(text)
	for name, inhalt in anhaenge:
		haupt, unter = ("application", "pdf") if name.endswith(".pdf") else ("application", "octet-stream")
		m.add_attachment(inhalt, maintype=haupt, subtype=unter, filename=name)
	if signatur:
		m.add_attachment(b"\x89PNG zz-logo", maintype="image", subtype="png", filename="logo.png", disposition="inline", cid="<logo@zz>")
	return m.as_bytes()


class FakeImap:
	"""Postfach im Speicher: SEARCH nach Betreff, FETCH von Kopfzeilen oder ganzer Mail. Merkt sich, was geladen wurde."""

	def __init__(self, mails):
		self.mails = dict(enumerate(mails, start=1))
		self.geladen = []
		self.literal = None
		self.nur_lesen = None

	def select(self, ordner, readonly=False):
		self.nur_lesen = readonly
		return "OK", [str(len(self.mails)).encode()]

	def uid(self, befehl, *args):
		if befehl == "SEARCH":
			wort = (self.literal.decode() if self.literal else args[-1].strip('"')).lower()
			self.literal = None
			treffer = [str(u).encode() for u, roh in self.mails.items() if wort in re.search(rb"^Subject: (.*)$", roh, re.M).group(1).decode().lower()]
			return "OK", [b" ".join(treffer)]
		uids = [int(u) for u in args[0].split(",")]
		if "HEADER.FIELDS" in args[1]:
			return "OK", [(f"1 (UID {u} BODY[HEADER.FIELDS (MESSAGE-ID FROM)] {{0}}".encode(), self.mails[u].split(b"\n\n")[0]) for u in uids]
		self.geladen += uids
		return "OK", [(f"{uids[0]} (UID {uids[0]} BODY[] {{0}}".encode(), self.mails[uids[0]]), b")"]

	def logout(self):
		pass


class TestMailAnfragen(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Mailkunde", "kontakte": [{"nachname": "Einkauf", "email": "Einkauf@zz-kunde.de"}]}).insert().name
		s = frappe.get_single("Mail Einstellungen")
		s.update({"benutzer": "info@zz-cnc.de", "imap_server": "zz.invalid", "stichwoerter": "Anfrage\nRFQ", "abholen_ab": None, "aktiv": 0})
		s.passwort = "zz-geheim"
		s.save()

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def test_mail_wird_anfrage_mit_text_anhaengen_und_kunde(self):
		d = mail.verarbeiten(zz_mail(anhaenge=[("zz-flansch.pdf", leeres_pdf("zz-flansch")), ("zz-flansch.step", b"ISO-10303-21; zz")], signatur=True))
		ui = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))
		self.assertEqual((ui["status"], ui["betreff"], ui["vonEmail"], ui["vonName"], ui["kundeId"]), ("Neu", "Anfrage ZZ Flansch", "einkauf@zz-kunde.de", "Max Mustermann", self.kunde))
		n = ui["nachrichten"][0]
		self.assertEqual(n["text"], "Bitte um Angebot für 10 Stück.")
		self.assertEqual(n["cc"], "Erika Muster <erika@zz-kunde.de>")
		self.assertEqual([(a["name"], a["art"]) for a in n["anhaenge"]], [("zz-flansch.pdf", "Zeichnung"), ("zz-flansch.step", "STEP")])  # Signaturbild fehlt
		self.assertEqual(ui["datum"], "2026-11-01T10:30:00")  # in Ortszeit
		self.assertEqual(ui["kontaktVorschlag"], {"anrede": "", "vorname": "Max", "nachname": "Mustermann"})
		self.assertIsNone(mail.verarbeiten(zz_mail()))  # schon da

	def test_antwort_im_verlauf_kommt_zur_anfrage(self):
		d = mail.verarbeiten(zz_mail())
		self.assertIsNotNone(mail.verarbeiten(zz_mail(betreff="AW: Anfrage ZZ Flansch", mid="<zz-2@zz-kunde.de>", antwort_auf="<zz-1@zz-kunde.de>", text="Noch eine Zeichnung.")))
		doc = frappe.get_doc("Mail Anfrage", d.name)
		self.assertEqual(([n.message_id for n in doc.nachrichten], doc.neue_antwort), (["<zz-1@zz-kunde.de>", "<zz-2@zz-kunde.de>"], 1))
		self.assertEqual(frappe.db.count("Mail Anfrage", {"von_email": "einkauf@zz-kunde.de"}), 1)
		self.assertEqual(mail_api.anzahl(), frappe.db.count("Mail Anfrage", {"status": "Neu"}))
		self.assertFalse(mail_api.gelesen(d.name)["neueAntwort"])

	def test_html_mail_und_unbekannter_absender_mit_domainvorschlag(self):
		d = mail.verarbeiten(zz_mail(von="Mustermann, Petra <petra@zz-kunde.de>", mid="<zz-3@zz>", html=True))
		ui = mail_api.anfrage_ui(d)
		self.assertEqual((ui["kundeId"], ui["kundeVorschlag"]["id"]), ("", self.kunde))
		self.assertIn("Bitte um Angebot", ui["nachrichten"][0]["text"])
		self.assertNotIn("<p>", ui["nachrichten"][0]["text"])
		self.assertEqual(ui["kontaktVorschlag"], {"anrede": "", "vorname": "Petra", "nachname": "Mustermann"})
		frei = mail.verarbeiten(zz_mail(von="jemand@gmail.com", mid="<zz-4@zz>"))
		self.assertIsNone(mail_api.anfrage_ui(frei)["kundeVorschlag"])

	def test_kunde_zuordnen_legt_kontakt_an_oder_neuen_kunden(self):
		d = mail.verarbeiten(zz_mail(von="Petra Neu <petra@zz-kunde.de>", mid="<zz-5@zz>"))
		ui = mail_api.kunde_zuordnen(d.name, kunde=self.kunde, kontakt={"anrede": "Frau", "vorname": "Petra", "nachname": "Neu"})
		self.assertEqual((ui["kundeId"], ui["kundeName"], ui["kundeVorschlag"]), (self.kunde, "ZZ Mailkunde", None))
		k = frappe.get_doc("Kunde", self.kunde)
		self.assertEqual([(x.anrede, x.vorname, x.nachname, x.email) for x in k.kontakte][-1], ("Frau", "Petra", "Neu", "petra@zz-kunde.de"))
		mail_api.kunde_zuordnen(d.name, kunde=self.kunde)  # Kontakt gibt es schon
		self.assertEqual(len(frappe.get_doc("Kunde", self.kunde).kontakte), 2)
		e = mail.verarbeiten(zz_mail(von="info@zz-neu.de", mid="<zz-6@zz>"))
		ui = mail_api.kunde_zuordnen(e.name, neuer_kunde="ZZ Neukunde GmbH", kontakt={"nachname": "Info"})
		self.assertEqual(frappe.db.get_value("Kunde", ui["kundeId"], "kundenname"), "ZZ Neukunde GmbH")
		with self.assertRaises(frappe.ValidationError):
			mail_api.kunde_zuordnen(e.name)

	def test_keine_anfrage_loescht_inhalt_und_wird_nicht_wieder_geholt(self):
		d = mail.verarbeiten(zz_mail(mid="<zz-7@zz>", anhaenge=[("zz-x.pdf", leeres_pdf("zz-x"))]))
		mail_api.keine_anfrage(d.name)
		doc = frappe.get_doc("Mail Anfrage", d.name)
		self.assertEqual((doc.status, doc.nachrichten[0].text, doc.nachrichten[0].message_id), ("Keine Anfrage", "", "<zz-7@zz>"))
		self.assertFalse(frappe.db.exists("File", {"attached_to_name": d.name}))
		self.assertNotIn(d.name, [x["id"] for x in mail_api.liste()])
		# Antwort im verworfenen Verlauf: nur gemerkt, keine neue Anfrage
		self.assertIsNone(mail.verarbeiten(zz_mail(betreff="AW: Anfrage", mid="<zz-8@zz>", antwort_auf="<zz-7@zz>")))

	def test_abholen_laedt_nur_mails_mit_stichwort_und_aendert_nichts_im_postfach(self):
		postfach = FakeImap([
			zz_mail(betreff="Rechnung 4711", mid="<zz-r@zz>"),
			zz_mail(betreff="Preisanfrage Welle", mid="<zz-a@zz>"),
			zz_mail(betreff="RFQ shaft", mid="<zz-b@zz>"),
			zz_mail(betreff="Anfrage von uns selbst", von="info@zz-cnc.de", mid="<zz-c@zz>"),
		])
		# abholen() schreibt jede Mail einzeln fest; im Test bleibt alles in der Transaktion (Rollback)
		with patch.object(mail, "imap_verbinden", return_value=postfach), patch.object(frappe.db, "commit"):
			self.assertEqual(mail.abholen(), 2)
			self.assertEqual(mail.abholen(), 0)  # schon da: nichts mehr geladen
		self.assertEqual(postfach.geladen, [2, 3])
		self.assertTrue(postfach.nur_lesen)
		self.assertFalse(frappe.db.exists("Mail Nachricht", {"message_id": "<zz-r@zz>"}))
		self.assertTrue(frappe.get_single("Mail Einstellungen").letzter_abruf)

	def test_einstellungen_ohne_passwort_zurueck_und_ordnername(self):
		ui = mail_api.einstellungen_speichern({"stichwoerter": " Anfrage \n\n RFQ ", "imapPort": "993", "aktiv": True})
		self.assertEqual((ui["stichwoerter"], ui["imapPort"], ui["aktiv"], ui["passwortGesetzt"]), ("Anfrage\nRFQ", 993, True, True))
		self.assertNotIn("passwort", ui)
		with self.assertRaises(frappe.ValidationError):
			mail_api.einstellungen_speichern({"stichwoerter": "  "})
		self.assertEqual(mail.ordnername("Gesendete Objekte"), '"Gesendete Objekte"')
		self.assertEqual(mail.ordnername("Entwürfe"), '"Entw&APw-rfe"')

	def test_angebot_aus_anfrage_mit_dateien_und_rueckweg(self):
		import os

		from cnc_one.api import angebot

		ohne = mail.verarbeiten(zz_mail(von="fremd@zz-andere.de", mid="<zz-9@zz>"))
		with self.assertRaises(frappe.ValidationError):
			mail_api.angebot_anlegen(ohne.name)  # erst Kunde zuordnen
		d = mail.verarbeiten(zz_mail(betreff="Anfrage Nr. 4711-B: ZZ Flansch", mid="<zz-10@zz>", anhaenge=[("zz-a.pdf", leeres_pdf("zz-a")), ("zz-a.step", b"ISO-10303-21; zz-a"), ("zz-mengen.xlsx", b"PK zz")]))
		r = mail_api.angebot_anlegen(d.name)
		a = r["angebot"]
		self.assertTrue(r["neu"])
		self.assertEqual((a["kopf"]["kundeId"], a["kopf"]["anfrageNr"], a["mailAnfrage"]["id"]), (self.kunde, "4711-B", d.name))
		self.assertEqual([(x["name"], x["art"]) for x in r["dateien"]], [("zz-a.pdf", "Zeichnung"), ("zz-a.step", "STEP")])
		self.assertIn("Bitte um Angebot", r["text"])
		for x in r["dateien"]:
			self.assertTrue(frappe.db.exists("File", {"name": x["id"], "attached_to_doctype": "Angebot", "attached_to_name": a["id"]}))
			self.assertEqual(frappe.db.count("File", {"file_url": x["url"]}), 2)  # Mail und Angebot, eine Datei auf der Platte
		m = frappe.get_doc("Mail Anfrage", d.name)
		self.assertEqual((m.status, m.angebot), ("In Bearbeitung", a["id"]))
		self.assertFalse(mail_api.angebot_anlegen(d.name)["neu"])
		with self.assertRaises(frappe.ValidationError):
			mail_api.keine_anfrage(d.name)
		# Entwurf gelöscht: Anfrage wieder offen, die Dateien der Mail bleiben
		angebot.loeschen(a["id"])
		m.reload()
		self.assertEqual((m.status, m.angebot), ("Neu", None))
		self.assertTrue(os.path.exists(frappe.get_site_path(r["dateien"][0]["url"].lstrip("/"))))

	def test_anfrage_nummer_aus_dem_betreff(self):
		self.assertEqual(mail_api.anfrage_nummer("Anfrage Nr. 4711-B: Flansch"), "4711-B")
		self.assertEqual(mail_api.anfrage_nummer("RFQ 2026-118 shafts"), "2026-118")
		self.assertEqual(mail_api.anfrage_nummer("AW: Preisanfrage #A-77."), "A-77")
		self.assertEqual(mail_api.anfrage_nummer("Anfrage ZZ Flansch"), "")


class FakeSmtp:
	"""SMTP-Server im Speicher: merkt sich Anmeldung und verschickte Mails."""

	gesendet = []

	def __init__(self, server, port, **kw):
		self.server, self.port = server, port
		self.anmeldung = None

	def login(self, benutzer, passwort):
		self.anmeldung = (benutzer, passwort)

	def send_message(self, msg, from_addr=None, to_addrs=None):
		FakeSmtp.gesendet.append({"msg": msg, "von": from_addr, "an": to_addrs, "anmeldung": self.anmeldung, "server": (self.server, self.port)})

	def quit(self):
		pass


class TestAngebotPerMail(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Antwortkunde", "kontakte": [{"anrede": "Herr", "nachname": "Einkauf", "email": "einkauf@zz-kunde.de"}]}).insert().name
		s = frappe.get_single("Mail Einstellungen")
		s.update({"benutzer": "info@zz-cnc.de", "absender_name": "ZZ CNC", "imap_server": "zz.invalid", "smtp_server": "smtp.zz.invalid", "smtp_port": 465, "verschluesselung": "SSL/TLS", "stichwoerter": "Anfrage", "gesendet_ordner": "Gesendete Objekte", "antwort_vorlage": None})
		s.passwort = "zz-geheim"
		s.save()
		FakeSmtp.gesendet = []

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def angebot_aus_mail(self):
		from cnc_one.api import angebot
		from cnc_one.tests.test_angebot import teil

		d = mail.verarbeiten(zz_mail(betreff="Anfrage Nr. 77: Flansch", mid="<zz-a1@zz-kunde.de>", anhaenge=[("zz-f.pdf", leeres_pdf("zz-f"))]))
		r = mail_api.angebot_anlegen(d.name)
		a = angebot.entwurf_speichern({"id": r["angebot"]["id"], "kopf": {"kundeId": self.kunde, "anfrageNr": "77"}, "teile": [teil("t1", "Flansch", "ZZ-AM-1")]})
		return d, a

	def test_angebot_als_pdf(self):
		from cnc_one.api import angebot

		_d, a = self.angebot_aus_mail()
		r = angebot.pdf(a["id"])
		self.assertEqual(r["name"], f"Angebot {a['id']}.pdf")
		inhalt = frappe.get_doc("File", {"file_url": r["url"]}).get_content()
		self.assertTrue(inhalt.startswith(b"%PDF"))
		angebot.pdf(a["id"])  # Entwurf: neu erzeugt, nicht doppelt
		self.assertEqual(frappe.db.count("File", {"attached_to_name": a["id"], "file_name": r["name"]}), 1)

	def test_vorschlag_ist_antwort_auf_die_anfrage(self):
		_d, a = self.angebot_aus_mail()
		v = mail_api.antwort_vorschlag(a["id"])
		self.assertEqual((v["an"], v["cc"], v["betreff"], v["bereit"]), ("einkauf@zz-kunde.de", "erika@zz-kunde.de", "AW: Anfrage Nr. 77: Flansch", True))
		self.assertTrue(v["text"].startswith("Sehr geehrter Herr Einkauf,\n\nvielen Dank für Ihre Anfrage 77. Anbei erhalten Sie unser Angebot " + a["id"]))
		self.assertTrue(v["zitat"]["kopf"].endswith("schrieb Max Mustermann <einkauf@zz-kunde.de>:"))
		self.assertEqual(v["zitat"]["text"], "Bitte um Angebot für 10 Stück.")
		self.assertEqual(mail_api.antwort_betreff("RE: Anfrage"), "RE: Anfrage")

	def test_senden_im_verlauf_mit_kopie_in_gesendet(self):
		_d, a = self.angebot_aus_mail()
		v = mail_api.antwort_vorschlag(a["id"])
		abgelegt = []
		with patch.object(mail.smtplib, "SMTP_SSL", FakeSmtp), patch.object(mail, "gesendet_ablegen", side_effect=lambda s, m: abgelegt.append(m) or ""):
			r = mail_api.angebot_senden(a["id"], v["an"], v["cc"], v["betreff"], v["text"])
		self.assertEqual((r["angebot"]["status"], r["hinweis"]), ("Gesendet", ""))
		g = FakeSmtp.gesendet[0]
		msg = g["msg"]
		self.assertEqual((g["server"], g["anmeldung"], g["an"]), (("smtp.zz.invalid", 465), ("info@zz-cnc.de", "zz-geheim"), ["einkauf@zz-kunde.de", "erika@zz-kunde.de"]))
		self.assertEqual((msg["In-Reply-To"], msg["References"], msg["Subject"], msg["From"]), ("<zz-a1@zz-kunde.de>", "<zz-a1@zz-kunde.de>", "AW: Anfrage Nr. 77: Flansch", "ZZ CNC <info@zz-cnc.de>"))
		self.assertEqual([x.get_filename() for x in msg.iter_attachments()], [f"Angebot {a['id']}.pdf"])
		self.assertIn("> Bitte um Angebot für 10 Stück.", msg.get_body(("plain",)).get_content())
		self.assertIn("<blockquote", msg.get_body(("html",)).get_content())
		self.assertIs(abgelegt[0], msg)
		m = frappe.get_doc("Mail Anfrage", r["mailAnfrage"])
		self.assertEqual((m.status, m.nachrichten[-1].richtung, m.nachrichten[-1].message_id), ("Beantwortet", "Ausgang", msg["Message-ID"]))
		# Der Kunde antwortet auf unsere Mail: kommt in denselben Verlauf
		antwort = mail.verarbeiten(zz_mail(betreff="AW: AW: Anfrage Nr. 77", mid="<zz-a2@zz-kunde.de>", antwort_auf=msg["Message-ID"], text="Wir bestellen."))
		self.assertEqual(antwort.name, m.name)
		self.assertEqual(frappe.db.get_value("Mail Anfrage", m.name, "neue_antwort"), 1)

	def test_senden_prueft_empfaenger_und_zugang(self):
		_d, a = self.angebot_aus_mail()
		with self.assertRaises(frappe.ValidationError):
			mail_api.angebot_senden(a["id"], "kein-empfaenger", "", "Betreff", "Text")
		frappe.db.set_single_value("Mail Einstellungen", "smtp_server", "")
		with self.assertRaises(frappe.ValidationError):
			mail_api.angebot_senden(a["id"], "einkauf@zz-kunde.de", "", "Betreff", "Text")
		self.assertEqual(frappe.db.get_value("Angebot", a["id"], "status"), "Entwurf")


def zz_html_mail(mid="<zz-h1@zz-kunde.de>"):
	m = EmailMessage()
	m["Subject"], m["From"], m["To"], m["Date"], m["Message-ID"] = "Anfrage ZZ Tabelle", "Max Mustermann <einkauf@zz-kunde.de>", "info@zz-cnc.de", "Sun, 01 Nov 2026 09:30:00 +0000", mid
	m.set_content("Bitte bieten Sie an (Textfassung)")
	html = (
		"<html><head><style>p{color:red}</style><script>alert(1)</script></head><body><p>Bitte bieten Sie uns folgende Bauteile an!</p>"
		'<table border="1"><tr><th>Nr.</th><th>Partnumber</th><th>Description</th><th>Quantity</th></tr>'
		'<tr><td>1</td><td>ZZ-H-001</td><td onclick="alert(2)">PLATE</td><td>2</td></tr>'
		"<tr><td>2</td><td>ZZ-H-002</td><td>PLATE</td><td>10/25</td></tr></table>"
		'<img src="cid:zz-shot@zz"><img src="https://tracker.zz.invalid/pixel.gif"></body></html>'
	)
	m.add_alternative(html, subtype="html")
	m.get_payload()[1].add_related(b"\x89PNG zz-shot", maintype="image", subtype="png", cid="<zz-shot@zz>")
	return m.as_bytes()


class TestMailHtml(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Htmlkunde", "kontakte": [{"nachname": "Einkauf", "email": "einkauf@zz-kunde.de"}]}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def test_html_mit_tabelle_bild_und_ohne_gefaehrliches(self):
		d = mail.verarbeiten(zz_html_mail())
		n = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))["nachrichten"][0]
		self.assertIn("<table", n["html"])
		for verboten in ("<script", "onclick", "alert", "tracker.zz.invalid", "<style", "cid:"):
			self.assertNotIn(verboten, n["html"])
		bild = frappe.get_all("File", filters={"attached_to_name": d.name, "file_name": ["like", "bild-%"]}, pluck="file_url")
		self.assertEqual(len(bild), 1)
		self.assertIn(f'src="{bild[0]}"', n["html"])
		self.assertEqual(n["anhaenge"], [])  # eingebettetes Bild ist kein Anhang
		self.assertIn("1 | ZZ-H-001 | PLATE | 2", n["text"])  # Tabellenzeile bleibt eine Zeile
		self.assertEqual(mail.tabellen(n["html"]), [[["Nr.", "Partnumber", "Description", "Quantity"], ["1", "ZZ-H-001", "PLATE", "2"], ["2", "ZZ-H-002", "PLATE", "10/25"]]])

	def test_tabellen_bei_der_uebernahme_und_html_antwort_mit_bild(self):
		from cnc_one.api import angebot
		from cnc_one.tests.test_angebot import teil

		d = mail.verarbeiten(zz_html_mail(mid="<zz-h2@zz-kunde.de>"))
		r = mail_api.angebot_anlegen(d.name)
		self.assertEqual(r["tabellen"][0][1], ["1", "ZZ-H-001", "PLATE", "2"])
		angebot.entwurf_speichern({"id": r["angebot"]["id"], "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Platte", "ZZ-H-001")]})
		s = frappe.get_single("Mail Einstellungen")
		s.update({"benutzer": "info@zz-cnc.de", "smtp_server": "smtp.zz.invalid", "smtp_port": 465, "verschluesselung": "SSL/TLS"})
		s.passwort = "zz-geheim"
		s.save()
		FakeSmtp.gesendet = []
		with patch.object(mail.smtplib, "SMTP_SSL", FakeSmtp), patch.object(mail, "gesendet_ablegen", return_value=""):
			mail_api.angebot_senden(r["angebot"]["id"], "einkauf@zz-kunde.de", "", "AW: Anfrage ZZ Tabelle", "Guten Tag,\n\nanbei das Angebot.")
		msg = FakeSmtp.gesendet[0]["msg"]
		html = msg.get_body(("html",)).get_content()
		self.assertIn("<table", html)
		self.assertIn('<p style="margin:0 0 12px">Guten Tag,</p>', html)
		eingebettet = [t for t in msg.walk() if t.get("Content-ID")]
		self.assertEqual(len(eingebettet), 1)
		self.assertIn("cid:" + eingebettet[0]["Content-ID"].strip("<>"), html)
		self.assertIn("1 | ZZ-H-001 | PLATE | 2", msg.get_body(("plain",)).get_content())
		ausgang = frappe.get_doc("Mail Anfrage", d.name).nachrichten[-1]
		self.assertIn("<blockquote", ausgang.html)
		# ohne Zitat
		FakeSmtp.gesendet = []
		with patch.object(mail.smtplib, "SMTP_SSL", FakeSmtp), patch.object(mail, "gesendet_ablegen", return_value=""):
			mail_api.angebot_senden(r["angebot"]["id"], "einkauf@zz-kunde.de", "", "AW", "Nur Text", zitieren=0)
		self.assertNotIn("blockquote", FakeSmtp.gesendet[0]["msg"].get_body(("html",)).get_content())


class TestTabellenvorlage(IntegrationTestCase):
	"""Spalten der Anfrage-Tabellen je Kontakt und Kunde anlernen; Lieferzeit des Angebots aus den Liefertermin."""

	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Tabellenkunde", "kontakte": [{"nachname": "Einkauf", "email": "einkauf@zz-kunde.de"}, {"nachname": "Zwei", "email": "zwei@zz-kunde.de"}]}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def test_vorlage_je_kontakt_sonst_vom_kunden(self):
		d = mail.verarbeiten(zz_html_mail(mid="<zz-t1@zz-kunde.de>"))
		ui = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))
		self.assertEqual(ui["tabellen"][0][0], ["Nr.", "Partnumber", "Description", "Quantity"])
		self.assertEqual(ui["tabellenVorlage"], {"spalten": {}, "quelle": ""})
		v = mail_api.tabellenvorlage_lernen(d.name, {"teilenummer": " Partnumber ", "menge": "Quantity", "liefertermin": "", "fremd": "x"})
		self.assertEqual(v, {"spalten": {"teilenummer": "partnumber", "menge": "quantity"}, "quelle": "Kontakt"})
		self.assertEqual(mail_api.tabellenvorlage(self.kunde, "ZWEI@zz-kunde.de")["quelle"], "Kunde")
		self.assertEqual(mail_api.tabellenvorlage(self.kunde, "zwei@zz-kunde.de")["spalten"]["menge"], "quantity")
		with self.assertRaises(frappe.ValidationError):
			mail_api.tabellenvorlage_lernen(d.name, {"menge": "Quantity"})
		self.assertEqual(mail_api.tabellenvorlage_vergessen(d.name), {"spalten": {}, "quelle": ""})

	def test_lieferzeit_ist_der_frueheste_liefertermin(self):
		from cnc_one.api import angebot
		from cnc_one.tests.test_angebot import teil

		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde, "lieferzeit": "Nach Absprache"}, "teile": [
			teil("t1", "Platte", "ZZ-T-1", liefertermin="2026-12-04"), teil("t2", "Welle", "ZZ-T-2", liefertermin="2026-11-20"), teil("t3", "Ohne", "ZZ-T-3"),
		]})
		self.assertEqual(a["kopf"]["lieferzeit"], "20.11.2026")
		b = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde, "lieferzeit": "3 Wochen"}, "teile": [teil("t1", "Ohne", "ZZ-T-4")]})
		self.assertEqual(b["kopf"]["lieferzeit"], "3 Wochen")


class TestTabellenRaster(IntegrationTestCase):
	def test_verbundene_zellen_ergeben_ein_gleichmaessiges_raster(self):
		html = (
			"<table><tr><td>Nr.</td><td>Partnumber</td><td colspan='2'>Description</td><td>Quantity</td></tr>"
			"<tr><td rowspan='2'>1</td><td>ZZ-R-1</td><td>PLATE</td><td>MOUNT</td><td>2</td></tr>"
			"<tr><td>ZZ-R-2</td><td>PLATE</td><td>RAIL</td><td>4</td></tr></table>"
		)
		self.assertEqual(mail.tabellen(html), [[
			["Nr.", "Partnumber", "Description", "", "Quantity"],
			["1", "ZZ-R-1", "PLATE", "MOUNT", "2"],
			["1", "ZZ-R-2", "PLATE", "RAIL", "4"],
		]])


def zz_zip(dateien):
	import io
	import zipfile

	puffer = io.BytesIO()
	with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
		for name, inhalt in dateien:
			z.writestr(name, inhalt)
	return puffer.getvalue()


class TestZipAnhang(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Zipkunde", "kontakte": [{"nachname": "Einkauf", "email": "einkauf@zz-zip.de"}]}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def test_zip_wird_ausgepackt_und_bleibt_als_original(self):
		from cnc_one.logic import dokumente

		innen = zz_zip([("Zeichnung.pdf", leeres_pdf("zz-zip-innen"))])
		zip_daten = zz_zip([
			("4711-A/Zeichnung.pdf", leeres_pdf("zz-zip-a")), ("4711-A/Modell.stp", b"ISO-10303-21; zz-zip-a"),
			("__MACOSX/4711-A/._Zeichnung.pdf", b"mac"), ("4711-A/.DS_Store", b"mac"), ("Thumbs.db", b"win"),
			("stueckliste.xlsx", b"PK zz"), ("4712-B.zip", innen),
		])
		d = mail.verarbeiten(zz_mail(von="einkauf@zz-zip.de", mid="<zz-zip-1@zz>", anhaenge=[("zz-anfrage.zip", zip_daten)]))
		n = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))["nachrichten"][0]
		self.assertEqual(
			[(a["name"], a["art"], a.get("aus", ""), a.get("ordner", "")) for a in n["anhaenge"]],
			[
				("zz-anfrage.zip", "ZIP", "", ""),
				("Zeichnung.pdf", "Zeichnung", "zz-anfrage.zip", "4711-A"),
				("Modell.stp", "STEP", "zz-anfrage.zip", "4711-A"),
				("Zeichnung.pdf", "Zeichnung", "zz-anfrage.zip", "4712-B"),  # aus der ZIP in der ZIP, ihr Name ist der Ordner
			],
		)
		self.assertEqual(n["hinweis"], "zz-anfrage.zip: in der ZIP belassen: stueckliste.xlsx")
		abgelegt = frappe.get_all("File", filters={"attached_to_doctype": "Mail Anfrage", "attached_to_name": d.name}, pluck="file_name", order_by="creation")
		self.assertEqual(sorted(abgelegt), ["4711-A Modell.stp", "4711-A Zeichnung.pdf", "4712-B Zeichnung.pdf", "zz-anfrage.zip"])

		r = mail_api.angebot_anlegen(d.name)
		self.assertEqual([(x["name"], x["ordner"]) for x in r["dateien"]], [("Zeichnung.pdf", "4711-A"), ("Modell.stp", "4711-A"), ("Zeichnung.pdf", "4712-B")])

		dokumente.abgleichen()
		url = n["anhaenge"][1]["url"]
		doc = frappe.get_doc("Dokument", {"datei": ["in", [url, r["dateien"][0]["url"]]]})
		self.assertEqual(doc.herkunft, "aus zz-anfrage.zip")
		self.assertEqual(frappe.db.get_value("Dokument", {"titel": "zz-anfrage.zip"}, ["art", "herkunft"]), ("Mail-Anhang", ""))

	def test_kaputte_oder_zu_grosse_zip_kommt_trotzdem_als_anhang(self):
		d = mail.verarbeiten(zz_mail(von="einkauf@zz-zip.de", mid="<zz-zip-2@zz>", anhaenge=[("zz-kaputt.zip", b"PK kein zip")]))
		n = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))["nachrichten"][0]
		self.assertEqual([a["name"] for a in n["anhaenge"]], ["zz-kaputt.zip"])
		self.assertIn("kein gültiges ZIP-Archiv", n["hinweis"])
		with patch.object(mail, "ZIP_MAX_DATEIEN", 1):
			dateien, hinweise = mail.zip_auspacken("zz-gross.zip", zz_zip([("a.pdf", b"a"), ("b.pdf", b"b")]))
		self.assertEqual(dateien, [])
		self.assertIn("zu groß zum Auspacken", hinweise[0])

	def test_pfade_und_umlaute_im_zip(self):
		from types import SimpleNamespace

		dateien, _h = mail.zip_auspacken("zz.zip", zz_zip([("../../etc/zz-teil.pdf", b"%PDF zz"), ("Gehäuse/Gehäuse.step", b"ISO zz")]))
		self.assertEqual([(n, o) for n, o, _x in dateien], [("zz-teil.pdf", "etc"), ("Gehäuse.step", "Gehäuse")])
		# ohne UTF-8-Kennzeichen: UTF-8 (manche Packer) oder DOS-Zeichensatz (Windows)
		utf8 = SimpleNamespace(flag_bits=0, filename="Gehäuse.pdf".encode("utf-8").decode("cp437"))
		dos = SimpleNamespace(flag_bits=0, filename="Gehäuse.pdf".encode("cp850").decode("cp437"))
		self.assertEqual((mail._zip_name(utf8), mail._zip_name(dos)), ("Gehäuse.pdf", "Gehäuse.pdf"))
