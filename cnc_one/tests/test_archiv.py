import csv
import hashlib
import io
import os
import zipfile
from datetime import date

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot
from cnc_one.api import dokumente as dok_api
from cnc_one.logic import archiv, dokumente
from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen
from cnc_one.tests.test_angebot import teil
from cnc_one.tests.test_dokumente import pdf_mit_text


class TestArchiv(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Archivkunde"}).insert().name
		self.a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Flansch", "ZZ-AR-1")]})["id"]

	def tearDown(self):
		eigene_dateien_loeschen(self._dateien)
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def pdf(self):
		return angebot.pdf_ablegen(frappe.get_doc("Angebot", self.a))

	def test_fristen_vorbelegt_und_aenderbar(self):
		self.assertEqual(archiv.aufbewahren_bis(date(2026, 3, 1), 8), date(2034, 12, 31))
		self.assertIsNone(archiv.aufbewahren_bis(date(2026, 3, 1), 0))
		self.assertEqual((archiv.fristen()["Rechnung"], archiv.fristen()["Angebot"], archiv.fristen()["Sonstiges"]), (8, 6, 0))
		ui = dok_api.fristen_speichern([{"art": "Angebot", "jahre": 7, "grundlage": "ZZ"}, {"art": "Erfunden", "jahre": 3}])
		angebot_zeile = next(z for z in ui["fristen"] if z["art"] == "Angebot")
		self.assertEqual((angebot_zeile["jahre"], angebot_zeile["grundlage"], angebot_zeile["vorbelegt"]), (7, "ZZ", 6))
		self.assertEqual(archiv.fristen()["Rechnung"], 8)  # nicht gepflegt: Vorbelegung

	def test_entwurf_frei_gesendet_gesperrt_und_datei_bleibt(self):
		f = self.pdf()
		self.assertTrue(frappe.db.exists("Dokument Protokoll", {"aktion": "Abgelegt", "beleg": self.a, "titel": f.file_name}))
		angebot.pdf_ablegen(frappe.get_doc("Angebot", self.a))  # Entwurf: altes PDF darf ersetzt werden
		f = frappe.get_doc("File", {"attached_to_name": self.a, "file_name": f"Angebot {self.a}.pdf"})
		self.assertTrue(frappe.db.exists("Dokument Protokoll", {"aktion": "Gelöscht", "beleg": self.a}))
		angebot.senden(self.a)
		pfad = frappe.get_site_path(f.file_url.lstrip("/"))
		with self.assertRaises(frappe.ValidationError) as fehler:
			frappe.delete_doc("File", f.name, ignore_permissions=True, force=True)
		self.assertIn("aufbewahrt werden", str(fehler.exception))
		self.assertTrue(os.path.exists(pfad))  # die Sperre greift, bevor die Datei von der Platte geht
		dokumente.abgleichen()
		d = frappe.get_doc("Dokument", {"datei": f.file_url})
		self.assertEqual((d.abgeschlossen, d.gesperrt, str(d.aufbewahren_bis)), (1, 1, f"{date.today().year + 6}-12-31"))

	def test_zeichnung_gesperrt_wenn_nach_der_revision_bestellt(self):
		b = frappe.get_doc({"doctype": "Bauteil", "kunde": self.kunde, "teilenummer": "ZZ-AR-2", "revision": "A"}).insert()
		f = frappe.get_doc({"doctype": "File", "file_name": "zz-ar-zeichnung.pdf", "attached_to_doctype": "Bauteil", "attached_to_name": b.name, "attached_to_field": "zeichnung", "is_private": 1, "content": pdf_mit_text("ZZ Archiv")}).insert(ignore_permissions=True)
		frappe.db.set_value("Bauteil", b.name, "zeichnung", f.file_url)
		self.assertFalse(archiv.abgeschlossen("Bauteil", b.name, f.file_url))
		frappe.get_doc({"doctype": "Auftragsposition", "parent": "ZZ-AUF", "parenttype": "Auftrag", "parentfield": "positionen", "bauteil": b.name, "revision": "a"}).db_insert()
		self.assertTrue(archiv.abgeschlossen("Bauteil", b.name, f.file_url))
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("File", f.name, ignore_permissions=True, force=True)

	def test_protokoll_bei_pflege_und_export_mit_verzeichnis(self):
		f = self.pdf()
		dokumente.abgleichen()
		d = frappe.get_doc("Dokument", {"datei": f.file_url})
		ui = dok_api.pflegen(d.name, schlagworte="Erstmuster")
		self.assertEqual([v["aktion"] for v in ui["verlauf"]][:2], ["Geändert", "Abgelegt"])
		self.assertIn("Schlagworte", ui["verlauf"][0]["details"])
		name, inhalt, anzahl = dok_api.export_zip(kunde=self.kunde)
		self.assertTrue(name.endswith(".zip"))
		self.assertEqual(anzahl, 1)
		z = zipfile.ZipFile(io.BytesIO(inhalt))
		zeilen = list(csv.reader(io.StringIO(z.read("Verzeichnis.csv").decode("utf-8-sig")), delimiter=";"))
		self.assertEqual(zeilen[1][:3], [f"ZZ Archivkunde/Angebot/{f.file_name}", f.file_name, "Angebot"])
		with open(frappe.get_site_path(f.file_url.lstrip("/")), "rb") as fh:
			self.assertEqual(zeilen[1][11], hashlib.sha256(fh.read()).hexdigest())
		self.assertEqual(z.read(zeilen[1][0])[:4], b"%PDF")

	def test_protokoll_fuer_alte_dateien_nachgetragen(self):
		from cnc_one.patches.v0_1 import protokoll_nachtragen

		f = self.pdf()
		frappe.db.delete("Dokument Protokoll", {"beleg": self.a})
		protokoll_nachtragen.execute()
		protokoll_nachtragen.execute()  # ein zweiter Lauf trägt nichts doppelt ein
		eintraege = frappe.get_all("Dokument Protokoll", filters={"beleg": self.a}, fields=["aktion", "zeit", "benutzer", "details", "content_hash"])
		self.assertEqual(len(eintraege), 1)
		self.assertEqual((eintraege[0].aktion, eintraege[0].details, eintraege[0].content_hash), ("Abgelegt", "nachgetragen", f.content_hash))
		self.assertEqual((str(eintraege[0].zeit), eintraege[0].benutzer), (str(f.creation), f.owner))
