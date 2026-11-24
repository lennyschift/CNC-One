"""Mail-Einstellungen je Benutzer (Signatur, Absendername) und das Wichtig-Kennzeichen im Posteingang."""

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import einstellung
from cnc_one.api import mail as mail_api
from cnc_one.logic import mail
from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen
from cnc_one.tests.test_mail import zz_mail


class TestBenutzerMail(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def test_ohne_einstellungen_bleibt_der_gemeinsame_absender(self):
		frappe.db.delete("Benutzereinstellung", {"benutzer": "Administrator"})
		self.assertEqual(einstellung.absender_fuer("ZZ Firma GmbH", "ZZ CNC"), ("ZZ CNC", "ZZ CNC"))
		self.assertEqual(einstellung.absender_fuer("ZZ Firma GmbH", ""), ("ZZ Firma GmbH", "ZZ Firma GmbH"))

	def test_signatur_und_absendername_je_benutzer(self):
		frappe.db.delete("Benutzereinstellung", {"benutzer": "Administrator"})
		p = einstellung.profil_speichern({"anzeigename": "Max Zett", "funktion": "Vertrieb", "telefon": "07903 3678-12", "mobil": "0171 000", "email": "max@zz-cnc.de", "nameAlsAbsender": True})
		self.assertTrue(p["angelegt"])
		text, name = einstellung.absender_fuer("ZZ Firma GmbH", "ZZ CNC")
		self.assertEqual(text, "Max Zett\nVertrieb\nZZ Firma GmbH\nTelefon 07903 3678-12 · Mobil 0171 000\nmax@zz-cnc.de")
		self.assertEqual(name, "Max Zett | ZZ CNC")
		# eigene Signatur ersetzt die erzeugte, Name als Absender abschaltbar
		einstellung.profil_speichern({"signatur": "Viele Grüße\nMax", "nameAlsAbsender": False})
		# ein Gruß am Anfang fällt weg: die Mailvorlagen grüßen schon selbst (sonst stünde er doppelt da)
		self.assertEqual(einstellung.absender_fuer("ZZ Firma GmbH", "ZZ CNC"), ("Max", "ZZ CNC"))
		with self.assertRaises(frappe.ValidationError):
			einstellung.profil_speichern({"email": "keine-adresse"})

	def test_jeder_hat_seine_eigene(self):
		frappe.db.delete("Benutzereinstellung", {"benutzer": "Administrator"})
		einstellung.profil_speichern({"anzeigename": "Admin Zett"})
		self.assertEqual(einstellung.absender_fuer("ZZ Firma", "", user="Guest"), ("ZZ Firma", "ZZ Firma"))
		self.assertEqual(einstellung.profil()["anzeigename"], "Admin Zett")

	def test_wichtig_setzen(self):
		d = mail.verarbeiten(zz_mail(mid="<zz-w1@zz>"))
		self.assertFalse(mail_api.anfrage_ui(d)["wichtig"])
		self.assertTrue(mail_api.wichtig_setzen(d.name, 1)["wichtig"])
		self.assertTrue(next(x for x in mail_api.liste_ui() if x["id"] == d.name)["wichtig"])
		self.assertFalse(mail_api.wichtig_setzen(d.name, 0)["wichtig"])
