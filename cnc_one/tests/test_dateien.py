import io
import os

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, bauteil
from cnc_one.tests.test_angebot import teil


def leeres_pdf(titel=""):
	from pypdf import PdfWriter

	w, puffer = PdfWriter(), io.BytesIO()
	w.add_blank_page(100, 100)
	if titel:
		w.add_metadata({"/Title": titel})  # eigener Inhalt, sonst erkennt Frappe die Datei als schon vorhanden
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

	def hochladen(self, angebot_id, name, inhalt=None):
		inhalt = inhalt or f"ISO-10303-21; {name}".encode()
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

	def test_bestandsbauteil_neue_datei_gleicher_revision_ersetzt_die_alte_bleibt_sichtbar(self):
		vorher, (alt_step, alt_pdf, _b) = self.mit_dateien(self.entwurf("ZZ-D2"), nr="ZZ-D2")
		b = vorher["positionen"][0]["bauteilId"]
		zweites = self.entwurf("ZZ-D2")
		step = self.hochladen(zweites["id"], "zz-datei-neu.step")
		t = teil("t1", "Flansch", "ZZ-D2", dateien=[{"name": "alt.pdf", "art": "Zeichnung", "url": alt_pdf}, {"name": "neu.step", "art": "STEP", "url": step}])
		a = angebot.entwurf_speichern({"id": zweites["id"], "kopf": {"kundeId": self.kunde}, "teile": [t]})
		self.assertEqual(a["positionen"][0]["herkunft"], "bestand")
		self.assertEqual(frappe.db.get_value("Bauteil", b, ["step_datei", "zeichnung"]), (step, alt_pdf))
		rev = bauteil.bauteil_ui(frappe.get_doc("Bauteil", b))["revisionen"]
		self.assertEqual([(r["stepDatei"], r["aktuell"], r["aeltereFassung"]) for r in rev], [(step, True, False), (alt_step, False, True)])
		self.assertTrue(frappe.db.exists("File", {"file_url": step, "attached_to_doctype": "Bauteil", "attached_to_name": b}))
		# erneutes Speichern ändert nichts mehr
		angebot.entwurf_speichern({"id": zweites["id"], "kopf": {"kundeId": self.kunde}, "teile": [t]})
		self.assertEqual(len(frappe.get_doc("Bauteil", b).revisionen), 2)

	def test_ohne_hochgeladene_datei_bleibt_alles_leer(self):
		t = teil("t1", "Flansch", "ZZ-D3")
		t["dateien"] = [{"name": "alt.step", "art": "STEP", "groesse": 10}]  # nur Name, nicht hochgeladen
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [t]})
		self.assertFalse(frappe.db.get_value("Bauteil", a["positionen"][0]["bauteilId"], "step_datei"))

	def test_vorschaubild_erscheint_in_belegen(self):
		a, (_s, _p, bild) = self.mit_dateien(self.entwurf())
		self.assertEqual(bauteil.vorschau(a["positionen"][0]["bauteilId"]), bild)
		self.assertEqual(bauteil.vorschau(None), "")


class TestBauteilErkennung(IntegrationTestCase):
	"""Vorhandene Bauteile zu den aus der Zeichnung erkannten Nummern finden; Revision aus der Workbench."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.k1 = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Erkennung Eins"}).insert().name
		self.k2 = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Erkennung Zwei"}).insert().name
		self.b1 = frappe.get_doc({"doctype": "Bauteil", "kunde": self.k1, "teilenummer": "ZZ-E-100", "zeichnungsnr": "ZN 4711-01"}).insert().name
		self.b2 = frappe.get_doc({"doctype": "Bauteil", "kunde": self.k2, "teilenummer": "zz e 100"}).insert().name
		self.b3 = frappe.get_doc({"doctype": "Bauteil", "kunde": self.k2, "teilenummer": "ZZ-E-300", "zeichnungsnr": "ZN4711.01"}).insert().name

	def tearDown(self):
		frappe.db.rollback()

	def test_teilenummer_ohne_trennzeichen_und_eigener_kunde_zuerst(self):
		r = bauteil.passende(teilenummer="ZZ E-100", kunde=self.k2)
		self.assertEqual([(x["id"], x["grund"]) for x in r], [(self.b2, "teilenummer"), (self.b1, "teilenummer")])
		self.assertEqual(r[1]["kundeName"], "ZZ Erkennung Eins")

	def test_zeichnungsnummer_nach_der_teilenummer(self):
		r = bauteil.passende(teilenummer="ZZ-E-100", zeichnungsnr="zn-4711-01", kunde=self.k1)
		self.assertEqual([(x["id"], x["grund"]) for x in r], [(self.b1, "teilenummer"), (self.b2, "teilenummer"), (self.b3, "zeichnungsnr")])
		self.assertEqual(bauteil.passende(), [])

	def test_revision_kommt_ins_neue_bauteil(self):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.k1}, "teile": [teil("t1", "Hülse", "ZZ-E-900", revision="A2")]})
		b = a["positionen"][0]["bauteilId"]
		self.assertEqual(frappe.db.get_value("Bauteil", b, "revision"), "A2")
		self.assertEqual(bauteil.bauteil_ui(frappe.get_doc("Bauteil", b))["revision"], "A2")


class TestBauteilRevisionen(IntegrationTestCase):
	"""Neue Revisionen am selben Bauteil mit Historie; Aufträge und Fertigung behalten die bestellte Revision."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Revisionskunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all("File", filters={"file_name": ["like", "zz-rev-%"]}, pluck="name"):
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
		frappe.db.rollback()

	def speichern(self, angebot_id, revision, dateien=()):
		"""Angebot mit Bauteil ZZ-R1 in einer Revision; `dateien` sind (Art, Dateiname), die frisch am Angebot hochgeladen werden."""
		if not angebot_id:
			angebot_id = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Welle", "ZZ-R1")]})["id"]
		liste = []
		for art, name in dateien:
			inhalt = leeres_pdf(name) if art == "Zeichnung" else f"ISO-10303-21; {name}".encode()
			f = frappe.get_doc({"doctype": "File", "file_name": name, "attached_to_doctype": "Angebot", "attached_to_name": angebot_id, "is_private": 1, "content": inhalt}).insert(ignore_permissions=True)
			liste.append({"name": name, "art": art, "url": f.file_url})
		t = teil("t1", "Welle", "ZZ-R1", revision=revision, dateien=liste)
		a = angebot.entwurf_speichern({"id": angebot_id, "kopf": {"kundeId": self.kunde}, "teile": [t]})
		return a, [d["url"] for d in liste]

	def bauteil(self, a):
		return frappe.get_doc("Bauteil", a["positionen"][0]["bauteilId"])

	def test_neue_revision_wird_aktuell_die_alte_bleibt_mit_ihren_dateien(self):
		a1, (pdf_a, step_a) = self.speichern(None, "A", [("Zeichnung", "zz-rev-a.pdf"), ("STEP", "zz-rev-a.step")])
		a2, (pdf_b,) = self.speichern(None, "B", [("Zeichnung", "zz-rev-b.pdf")])
		b = self.bauteil(a2)
		self.assertEqual(b.name, self.bauteil(a1).name)
		self.assertEqual((b.revision, b.zeichnung, b.step_datei), ("B", pdf_b, ""))
		rev = bauteil.bauteil_ui(b)["revisionen"]
		self.assertEqual([(r["revision"], r["zeichnung"], r["stepDatei"], r["aktuell"], r["angebot"]) for r in rev], [("B", pdf_b, "", True, a2["id"]), ("A", pdf_a, step_a, False, a1["id"])])
		self.assertEqual(frappe.db.get_value("Angebotsposition", {"parent": a1["id"]}, "revision"), "A")
		# eine ältere Revision in einem neuen Angebot macht sie nicht wieder zur aktuellen
		self.speichern(None, "a")
		self.assertEqual(frappe.db.get_value("Bauteil", b.name, "revision"), "B")

	def test_vertippte_revision_im_selben_angebot_hinterlaesst_keine_zeile(self):
		a, _ = self.speichern(None, "A", [("Zeichnung", "zz-rev-a.pdf")])
		a2, _ = self.speichern(None, "C")
		self.speichern(a2["id"], "C1")
		self.speichern(a2["id"], "C2")
		b = self.bauteil(a)
		self.assertEqual([z.revision for z in b.revisionen], ["A", "C2"])
		self.assertEqual(b.revision, "C2")
		# zurück auf die bekannte Revision: die Zeile des Angebots fällt weg, A ist wieder aktuell
		self.speichern(a2["id"], "A")
		b.reload()
		self.assertEqual(([z.revision for z in b.revisionen], b.revision, b.zeichnung), (["A"], "A", self.bauteil(a).revisionen[0].zeichnung))

	def test_ohne_revision_gilt_die_aktuelle(self):
		a, _ = self.speichern(None, "B")
		a2, _ = self.speichern(None, "")
		self.assertEqual(frappe.db.get_value("Angebotsposition", {"parent": a2["id"]}, "revision"), "B")
		self.assertEqual(len(self.bauteil(a).revisionen), 1)

	def test_auftrag_und_fertigung_behalten_die_bestellte_revision(self):
		from cnc_one.api import auftrag, fertigung

		a1, (pdf_a,) = self.speichern(None, "A", [("Zeichnung", "zz-rev-a.pdf")])
		angebot.senden(a1["id"])
		auf = auftrag.aus_angebot(a1["id"], "PO-R", [{"angebotKey": "t1", "menge": 10}])
		self.speichern(None, "B", [("Zeichnung", "zz-rev-b.pdf")])
		t = auftrag.auftrag_ui(frappe.get_doc("Auftrag", auf["id"]))["positionen"][0]["teil"]
		self.assertEqual((t["revision"], t["zeichnung"], t["aktuelleRevision"]), ("A", pdf_a, "B"))
		fb = fertigung.starten(auf["id"])["fertigung"][0]["teil"]
		self.assertEqual((fb["revision"], fb["zeichnung"], fb["aktuelleRevision"]), ("A", pdf_a, "B"))
		# Revision A wird gebraucht: ein neues Angebot mit A und anderer Zeichnung legt eine neue Fassung an, statt A zu ändern
		a3, (pdf_a2,) = self.speichern(None, "A", [("Zeichnung", "zz-rev-a2.pdf")])
		self.assertEqual([(z.revision, z.zeichnung) for z in self.bauteil(a3).revisionen], [("A", pdf_a), ("B", self.bauteil(a3).revisionen[1].zeichnung), ("A", pdf_a2)])

	def test_revision_in_den_stammdaten_wechseln(self):
		a, (pdf_a,) = self.speichern(None, "A", [("Zeichnung", "zz-rev-a.pdf")])
		self.speichern(None, "B", [("Zeichnung", "zz-rev-b.pdf")])
		b = self.bauteil(a)
		bauteil.revision_setzen(b, "A")
		self.assertEqual((b.revision, b.zeichnung), ("A", pdf_a))
		bauteil.revision_setzen(b, "D")
		self.assertEqual((b.revision, b.zeichnung, b.revisionen[-1].revision), ("D", "", "D"))
