import io
import os

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, bauteil
from cnc_one.tests.test_angebot import teil


def leeres_pdf():
	from pypdf import PdfWriter

	w, puffer = PdfWriter(), io.BytesIO()
	w.add_blank_page(100, 100)
	w.write(puffer)
	return puffer.getvalue()


def kleines_png():
	from PIL import Image

	puffer = io.BytesIO()
	Image.new("RGBA", (4, 3)).save(puffer, "PNG")
	return puffer.getvalue()


class TestBauteilDateien(IntegrationTestCase):
	"""STEP-Modell, Zeichnung und Vorschaubild kommen aus der Workbench (am Angebot hochgeladen) ins Bauteil."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Dateikunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all("File", filters={"file_name": ["like", "zz-datei-%"]}, pluck="name"):
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
		frappe.db.rollback()

	def hochladen(self, angebot_id, name, inhalt=b"ISO-10303-21;"):
		f = frappe.get_doc({"doctype": "File", "file_name": name, "attached_to_doctype": "Angebot", "attached_to_name": angebot_id, "is_private": 1, "content": inhalt})
		f.insert(ignore_permissions=True)
		return f.file_url

	def entwurf(self, nr="ZZ-D1"):
		return angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Flansch", nr)]})

	def mit_dateien(self, a, nr="ZZ-D1", **extra):
		step = self.hochladen(a["id"], "zz-datei-flansch.step")
		pdf = self.hochladen(a["id"], "zz-datei-flansch.pdf", leeres_pdf())
		bild = self.hochladen(a["id"], "zz-datei-vorschau.png", kleines_png())
		t = teil("t1", "Flansch", nr)
		t.update(dateien=[{"name": "flansch.step", "art": "STEP", "url": step}, {"name": "flansch.pdf", "art": "Zeichnung", "url": pdf}], vorschaubild=bild, **extra)
		return angebot.entwurf_speichern({"id": a["id"], "kopf": {"kundeId": self.kunde}, "teile": [t]}), (step, pdf, bild)

	def test_dateien_kommen_ins_neue_bauteil_und_haengen_daran(self):
		a, (step, pdf, bild) = self.mit_dateien(self.entwurf())
		b = frappe.get_doc("Bauteil", a["positionen"][0]["bauteilId"])
		self.assertEqual((b.step_datei, b.zeichnung, b.vorschaubild), (step, pdf, bild))
		ui = bauteil.bauteil_ui(b)
		self.assertEqual((ui["stepDatei"], ui["zeichnung"], ui["vorschaubild"]), (step, pdf, bild))
		for url in (step, pdf, bild):
			self.assertTrue(frappe.db.exists("File", {"file_url": url, "attached_to_doctype": "Bauteil", "attached_to_name": b.name}), url)
			self.assertEqual(frappe.db.count("File", {"file_url": url}), 1, url)  # umgehängt, nicht kopiert
		self.assertEqual(frappe.db.count("File", {"attached_to_doctype": "Bauteil", "attached_to_name": b.name}), 3)

	def test_dateien_bleiben_wenn_das_angebot_geloescht_wird(self):
		a, (step, _pdf, _bild) = self.mit_dateien(self.entwurf())
		b = a["positionen"][0]["bauteilId"]
		angebot.loeschen(a["id"])
		self.assertTrue(frappe.db.exists("File", {"file_url": step, "attached_to_name": b}))
		self.assertTrue(os.path.exists(frappe.get_site_path(step.lstrip("/"))))

	def test_bestandsbauteil_behaelt_seine_dateien_und_fuellt_nur_leere(self):
		vorher = self.entwurf("ZZ-D2")
		alt = self.hochladen(vorher["id"], "zz-datei-alt.step")
		b = vorher["positionen"][0]["bauteilId"]
		frappe.db.set_value("Bauteil", b, "step_datei", alt)
		a, (_step, pdf, _bild) = self.mit_dateien(self.entwurf("ZZ-D2"), nr="ZZ-D2")
		self.assertEqual(a["positionen"][0]["herkunft"], "bestand")
		self.assertEqual(frappe.db.get_value("Bauteil", b, ["step_datei", "zeichnung"]), (alt, pdf))

	def test_ohne_hochgeladene_datei_bleibt_alles_leer(self):
		t = teil("t1", "Flansch", "ZZ-D3")
		t["dateien"] = [{"name": "alt.step", "art": "STEP", "groesse": 10}]  # nur Name, nicht hochgeladen
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [t]})
		self.assertFalse(frappe.db.get_value("Bauteil", a["positionen"][0]["bauteilId"], "step_datei"))

	def test_vorschaubild_erscheint_in_belegen(self):
		a, (_s, _p, bild) = self.mit_dateien(self.entwurf())
		self.assertEqual(bauteil.vorschau(a["positionen"][0]["bauteilId"]), bild)
		self.assertEqual(bauteil.vorschau(None), "")
