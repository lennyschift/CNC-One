import re
from email.message import EmailMessage
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

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
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Mailkunde", "kontakte": [{"nachname": "Einkauf", "email": "Einkauf@zz-kunde.de"}]}).insert().name
		s = frappe.get_single("Mail Einstellungen")
		s.update({"benutzer": "info@zz-cnc.de", "imap_server": "zz.invalid", "stichwoerter": "Anfrage\nRFQ", "abholen_ab": None, "aktiv": 0})
		s.passwort = "zz-geheim"
		s.save()

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all("File", filters={"attached_to_doctype": "Mail Anfrage"}, pluck="name"):
			if frappe.db.get_value("File", name, "file_name").startswith("zz-"):
				frappe.delete_doc("File", name, ignore_permissions=True, force=True)
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
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Antwortkunde", "kontakte": [{"anrede": "Herr", "nachname": "Einkauf", "email": "einkauf@zz-kunde.de"}]}).insert().name
		s = frappe.get_single("Mail Einstellungen")
		s.update({"benutzer": "info@zz-cnc.de", "absender_name": "ZZ CNC", "imap_server": "zz.invalid", "smtp_server": "smtp.zz.invalid", "smtp_port": 465, "verschluesselung": "SSL/TLS", "stichwoerter": "Anfrage", "gesendet_ordner": "Gesendete Objekte", "antwort_vorlage": None})
		s.passwort = "zz-geheim"
		s.save()
		FakeSmtp.gesendet = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all("File", filters={"attached_to_doctype": ["in", ["Mail Anfrage", "Angebot"]]}, fields=["name", "file_name"]):
			if name.file_name.startswith(("zz-", "Angebot ANG-")) and frappe.db.get_value("File", name.name, "creation") and frappe.db.exists("File", name.name):
				frappe.delete_doc("File", name.name, ignore_permissions=True, force=True)
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
		self.assertIn("schrieb Max Mustermann <einkauf@zz-kunde.de>:\n> Bitte um Angebot für 10 Stück.", v["text"])
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
