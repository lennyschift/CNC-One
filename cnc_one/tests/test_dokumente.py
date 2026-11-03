import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen
from cnc_one.api import dokumente as dok_api
from cnc_one.logic import dokumente


def pdf_mit_text(text):
	from weasyprint import HTML

	return HTML(string=f"<p>{text}</p>").write_pdf()


class TestDokumente(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Dokumentkunde"}).insert().name
		self.bauteil = frappe.get_doc({"doctype": "Bauteil", "kunde": self.kunde, "teilenummer": "ZZ-DOK-1", "bezeichnung": "Welle", "revision": "B"}).insert().name
		self.angebot = frappe.get_doc({"doctype": "Angebot", "kunde": self.kunde}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def datei(self, dt, name, dateiname, inhalt, feld=None):
		return frappe.get_doc({"doctype": "File", "file_name": dateiname, "attached_to_doctype": dt, "attached_to_name": name, "attached_to_field": feld, "is_private": 1, "content": inhalt}).insert(ignore_permissions=True)

	def dokument(self, url):
		return frappe.get_doc("Dokument", frappe.db.get_value("Dokument", {"datei": url}, "name"))

	def test_gleicher_inhalt_an_mehreren_belegen_ist_ein_dokument(self):
		f = self.datei("Bauteil", self.bauteil, "zz-dok-welle.pdf", pdf_mit_text("ZZ Suchtext Welle 4711"), "zeichnung")
		frappe.db.set_value("Bauteil", self.bauteil, "zeichnung", f.file_url)
		frappe.get_doc("File", f.name).create_attachment_copy("Angebot", self.angebot, ignore_permissions=True)
		self.datei("Bauteil", self.bauteil, "zz-dok-vorschau.png", b"\x89PNG zz", "vorschaubild")
		dokumente.abgleichen()
		d = self.dokument(f.file_url)
		self.assertEqual((d.art, d.kunde, d.kunde_name, d.teilenummer, d.revision, d.fassung), ("Zeichnung", self.kunde, "ZZ Dokumentkunde", "ZZ-DOK-1", "B", "Aktuell"))
		self.assertEqual(sorted((b.beleg_typ, b.beleg) for b in d.bezuege), [("Angebot", self.angebot), ("Bauteil", self.bauteil)])
		self.assertIn("Suchtext Welle 4711", d.inhalt)
		self.assertFalse(frappe.db.exists("Dokument", {"titel": "zz-dok-vorschau.png"}))
		self.assertEqual(dokumente.abgleichen()["geaendert"], 0)  # nichts mehr zu tun

	def test_suche_filter_und_pflege(self):
		f = self.datei("Bauteil", self.bauteil, "zz-dok-flansch.pdf", pdf_mit_text("Werkstoff ZZ-Sonderstahl 1.4404"), "zeichnung")
		self.datei("Bauteil", self.bauteil, "zz-dok-flansch.step", b"ISO-10303-21; FILE_NAME('ZZ-Flansch-Modell','2026'); PRODUCT('ZZ-FL-77','Flansch');", "step_datei")
		dokumente.abgleichen()
		r = dok_api.liste(suche="sonderstahl")
		self.assertEqual([x["titel"] for x in r["dokumente"]], ["zz-dok-flansch.pdf"])
		self.assertIn("ZZ-Sonderstahl", r["dokumente"][0]["treffer"])
		self.assertEqual([x["titel"] for x in dok_api.liste(suche="ZZ-FL-77")["dokumente"]], ["zz-dok-flansch.step"])
		self.assertEqual({x["art"] for x in dok_api.liste(suche="ZZ-DOK-1")["dokumente"]}, {"Zeichnung", "3D-Modell"})
		self.assertEqual([x["art"] for x in dok_api.liste(suche="zz-dok", art="3D-Modell")["dokumente"]], ["3D-Modell"])
		self.assertEqual(dok_api.liste(suche="zz-dok", kunde=self.kunde)["arten"], {"Zeichnung": 1, "3D-Modell": 1})
		ui = dok_api.pflegen(self.dokument(f.file_url).name, schlagworte="Erstmuster; eilig, Erstmuster", notiz=" Kunde wartet ")
		self.assertEqual((ui["schlagworte"], ui["notiz"]), ("Erstmuster, eilig", "Kunde wartet"))
		self.assertEqual([x["titel"] for x in dok_api.liste(suche="eilig")["dokumente"]], ["zz-dok-flansch.pdf"])
		dokumente.abgleichen()  # Schlagworte bleiben beim Abgleich
		self.assertEqual(self.dokument(f.file_url).schlagworte, "Erstmuster, eilig")

	def test_geloeschte_datei_faellt_weg_und_art_aus_dem_beleg(self):
		f = self.datei("Angebot", self.angebot, "zz-dok-anhang.pdf", pdf_mit_text("ZZ weg"))
		dokumente.abgleichen()
		self.assertEqual(self.dokument(f.file_url).art, "Zeichnung")
		frappe.delete_doc("File", f.name, ignore_permissions=True, force=True)
		self.assertEqual(dokumente.abgleichen()["entfernt"], 1)
		art = lambda dt, name, feld=None: dokumente.art_von(frappe._dict(attached_to_doctype=dt, file_name=name, attached_to_field=feld))
		self.assertEqual(art("Rechnung", "RE-1.pdf"), "Rechnung")
		self.assertEqual(art("Rechnung", "factur-x.xml"), "E-Rechnung (XML)")
		self.assertEqual(art("Angebot", "Angebot ANG-1.pdf"), "Angebot")
		self.assertEqual(art("Mail Anfrage", "anfrage.pdf"), "Mail-Anhang")
		self.assertEqual(art("Mail Anfrage", "teil.stp"), "3D-Modell")
