import io

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import firma as firma_api
from cnc_one.logic import briefbogen, pdf
from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen

FIRMA = {
	"firmenname": "ZZ Hohenstein GmbH", "rechtsform": "GmbH", "adresse": ["ZZ-Weg 1", "12345 ZZ-Stadt"],
	"telefon": "09999 / 99", "email": "info@zz.invalid", "web": "https://www.zz.invalid/",
	"steuernummer": "99/999", "ustId": "DE999999999", "handelsregister": "HRB 9 ZZ", "geschaeftsfuehrer": "ZZ Muster",
	"banken": [{"bezeichnung": "Sparkasse ZZ", "iban": "DE99 9999 9999 9999 9999 99", "bic": "ZZSPDE99"}, {"bezeichnung": "VR Bank ZZ", "iban": "DE88 8888 8888 8888 8888 88", "bic": ""}],
}


def zz_png(farbe):
	from PIL import Image

	puffer = io.BytesIO()
	Image.new("RGB", (210, 30), farbe).save(puffer, "PNG")
	return puffer.getvalue()


class TestBriefbogen(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")

	def tearDown(self):
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def bild(self, farbe):
		return frappe.get_doc({"doctype": "File", "file_name": f"zz-kopfzeile-{farbe}.png", "attached_to_doctype": "Firma", "attached_to_name": "Firma", "is_private": 1, "content": zz_png(farbe)}).insert(ignore_permissions=True)

	def test_fuss_in_drei_spalten_wie_der_entwurf_des_users(self):
		frappe.db.set_single_value("Firma", "briefkopf", "")
		r = briefbogen.rahmen(FIRMA)
		self.assertIn("<strong>ZZ Hohenstein GmbH</strong><br>ZZ-Weg 1<br>12345 ZZ-Stadt<br>HRB 9 ZZ<br>USt-ID-Nr.: DE999999999</div>", r["fuss"])
		self.assertNotIn("GmbH GmbH", r["fuss"])
		self.assertNotIn("Steuernummer", r["fuss"])
		for text in ("Telefon 09999 / 99", "info@zz.invalid", ">www.zz.invalid</div>", "Geschäftsführer: ZZ Muster"):
			self.assertIn(text, r["fuss"])
		self.assertEqual(r["fuss"].count('<img src="data:image/svg+xml'), 4)  # Symbol vor jeder Kontaktangabe
		self.assertIn('<div class="bank"><strong>Sparkasse ZZ</strong><br>IBAN DE99 9999 9999 9999 9999 99</div>', r["fuss"])
		self.assertIn('<div class="bank"><strong>VR Bank ZZ</strong><br>IBAN DE88 8888 8888 8888 8888 88</div>', r["fuss"])
		self.assertIn('class="kopf"', r["kopf"])  # ohne Bild: Firmenname mit Anschrift

	def test_kopfzeile_als_bild_nur_auf_seite_1_und_fuss_auf_jeder_seite(self):
		from pypdf import PdfReader

		f = self.bild("red")
		frappe.db.set_single_value("Firma", "briefkopf", f.file_url)
		r = briefbogen.rahmen(FIRMA)
		self.assertIn("<img", r["kopf"])
		self.assertNotIn('class="kopf"', r["kopf"])
		seiten = PdfReader(io.BytesIO(pdf.pdf_a3(briefbogen.muster_html(FIRMA)))).pages
		self.assertEqual(len(seiten), 2)
		for i, s in enumerate(seiten, start=1):
			text = s.extract_text()
			self.assertIn("USt-ID-Nr.: DE999999999", text)
			self.assertIn(f"Seite {i} von 2", text)

	def test_neue_kopfzeile_ersetzt_die_alte(self):
		alt, neu = self.bild("red"), self.bild("blue")
		frappe.db.set_single_value("Firma", "briefkopf", alt.file_url)
		d = frappe.get_single("Firma")
		ui = firma_api.speichern({"firmenname": d.firmenname or "ZZ Firma", "briefkopf": neu.file_url})
		self.assertEqual(ui["briefkopf"], neu.file_url)
		self.assertFalse(frappe.db.exists("File", alt.name))
		self.assertTrue(frappe.db.exists("File", neu.name))


class TestBelegAnsehen(IntegrationTestCase):
	"""Detailansicht und Drucken in der App zeigen das PDF vom Server. Offene Belege werden dabei nicht abgelegt."""

	def setUp(self):
		from cnc_one.api import angebot
		from cnc_one.tests.test_angebot import teil

		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		k = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Ansehkunde"}).insert()
		k.append("adressen", {"typ": "Rechnung und Lieferung", "strasse": "ZZ-Weg 2", "plz": "72461", "ort": "Albstadt", "standard": 1})
		k.save()
		self.kunde = k.name
		self.angebot = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Flansch", "ZZ-AN-1")]})["id"]

	def tearDown(self):
		eigene_dateien_loeschen(self._dateien)
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def abgelegt(self, doctype, name):
		return frappe.db.count("File", {"attached_to_doctype": doctype, "attached_to_name": name})

	def test_angebot_entwurf_frisch_gesendet_das_abgelegte(self):
		from pypdf import PdfReader

		from cnc_one.api import angebot
		from cnc_one.api.belegdruck import ansehen_pdf

		name, inhalt = ansehen_pdf("Angebot", self.angebot)
		self.assertEqual((name, inhalt[:4]), (f"Angebot {self.angebot}.pdf", b"%PDF"))
		self.assertEqual(self.abgelegt("Angebot", self.angebot), 0)  # Ansehen legt nichts ab
		angebot.senden(self.angebot)
		name, inhalt = ansehen_pdf("Angebot", self.angebot)
		f = frappe.get_doc("File", {"attached_to_doctype": "Angebot", "attached_to_name": self.angebot, "file_name": name})
		with open(f.get_full_path(), "rb") as fh:
			self.assertEqual(inhalt, fh.read())
		self.assertIn("ZZ Ansehkunde", PdfReader(io.BytesIO(inhalt)).pages[0].extract_text())

	def test_rechnung_entwurf_mit_stempel_und_lieferschein_bereit_ohne_ablage(self):
		from pypdf import PdfReader

		from cnc_one.api import angebot, auftrag, bauteil, lieferschein, rechnung
		from cnc_one.api.belegdruck import ansehen_pdf
		from cnc_one.tests.test_rechnung import PLAN

		# Bauteilbild wie in Angebot und Lieferschein
		teil_id = bauteil.finden(self.kunde, "ZZ-AN-1")
		bild = frappe.get_doc({"doctype": "File", "file_name": "zz-vorschau-an.png", "attached_to_doctype": "Bauteil", "attached_to_name": teil_id, "is_private": 1, "content": zz_png("green")}).insert(ignore_permissions=True)
		frappe.db.set_value("Bauteil", teil_id, "vorschaubild", bild.file_url)
		angebot.senden(self.angebot)
		auf = auftrag.aus_angebot(self.angebot, "PO-ZZ", [{"angebotKey": "t1", "menge": 5, "arbeitsgaenge": PLAN}])
		r = rechnung.anlegen(auf["id"], "Gesamtrechnung")
		name, inhalt = ansehen_pdf("Rechnung", r["id"])
		self.assertEqual(name, "Rechnung Entwurf.pdf")
		seite = PdfReader(io.BytesIO(inhalt)).pages[0]
		self.assertEqual(seite.extract_text().count("ENTWURF"), 1)
		self.assertIn("ZZ-AN-1 · Zeichnung Z-1", seite.extract_text())
		self.assertGreaterEqual(len(seite.images), 1)  # Bauteilbild
		self.assertEqual(self.abgelegt("Rechnung", r["id"]), 0)
		ls = lieferschein.anlegen(self.kunde, [{"auftrag": auf["id"], "auftragsposition": auf["positionen"][0]["key"], "menge": 5}])
		name, inhalt = ansehen_pdf("Lieferschein", ls["id"])
		self.assertEqual((name, inhalt[:4]), (f"Lieferschein {ls['id']}.pdf", b"%PDF"))
		self.assertEqual(self.abgelegt("Lieferschein", ls["id"]), 0)
		with self.assertRaises(frappe.ValidationError):
			ansehen_pdf("Kunde", self.kunde)
