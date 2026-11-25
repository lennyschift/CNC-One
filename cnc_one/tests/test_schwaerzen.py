import base64
import hashlib
import json

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import anfrage, schwaerzen


def _pdf(objekte):
	"""Minimale PDF aus Objekt-Texten (1-basiert), mit korrekter xref-Tabelle. Nur erfundene Inhalte."""
	teile = [b"%PDF-1.7\n"]
	offsets = []
	for i, o in enumerate(objekte, 1):
		offsets.append(sum(len(t) for t in teile))
		teile.append(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
	xref = sum(len(t) for t in teile)
	teile.append(f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n".encode())
	for off in offsets:
		teile.append(f"{off:010d} 00000 n \n".encode())
	teile.append(f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R /Info {len(objekte)} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
	return b"".join(teile)


def _stream(d, inhalt):
	return d + b"\nstream\n" + inhalt + b"\nendstream"


def bild_pdf(info=b"<< /Producer (CNC One) >>"):
	"""So sieht eine geschwärzte Datei aus: eine Seite, ein Bild, sonst nichts."""
	pixel = b"\xff" * 16
	inhalt = b"q\n100 0 0 50 0 0 cm\n/Im0-7098 Do\nQ\n"
	return _pdf([
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 50] /Contents 4 0 R /Annots [] /Resources << /Font << >> /ExtGState << >> /XObject << /Im0-7098 5 0 R >> >> >>",
		_stream(f"<< /Length {len(inhalt)} >>".encode(), inhalt),
		_stream(b"<< /Type /XObject /Subtype /Image /Width 4 /Height 4 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 16 >>", pixel),
		info,
	])


def text_pdf(text=b"ZZ Geheim GmbH"):
	"""Eine Datei mit Schrift und Text (darf nie als „geschwärzt“ durchgehen)."""
	inhalt = b"BT /F1 12 Tf 10 20 Td (" + text + b") Tj ET"
	return _pdf([
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 50] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
		_stream(f"<< /Length {len(inhalt)} >>".encode(), inhalt),
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
		b"<< /Producer (x) >>",
	])


class TestSchwaerzen(IntegrationTestCase):
	def setUp(self):
		from cnc_one.tests.dateischutz import dateien_vorher

		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		k = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Geheim GmbH", "kuerzel": "ZZG"})
		k.append("kontakte", {"vorname": "Erika", "nachname": "Zettmann", "email": "erika@zz-geheim.de"})
		self.kunde = k.insert().name
		self.bauteil = frappe.get_doc({"doctype": "Bauteil", "kunde": self.kunde, "teilenummer": "ZZ-SW-1", "bezeichnung": "ZZ Welle"}).insert().name
		self.original = frappe.get_doc({"doctype": "File", "file_name": "zz-original.pdf", "is_private": 1, "content": text_pdf(), "attached_to_doctype": "Bauteil", "attached_to_name": self.bauteil}).insert()
		frappe.db.set_value("Bauteil", self.bauteil, "zeichnung", self.original.file_url)

	def tearDown(self):
		from cnc_one.tests.dateischutz import eigene_dateien_loeschen

		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	def _speichern(self, pdf, released=True):
		return schwaerzen.speichern({
			"bauteil": self.bauteil, "originalUrl": self.original.file_url, "originalSha": hashlib.sha256(self.original.get_content()).hexdigest(),
			"bereiche": [{"page": 1, "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.3, "kind": "keyword", "source": "auto", "reason": "Stichwort"}],
			"protokoll": {"sha256": hashlib.sha256(pdf).hexdigest(), "pageCount": 1, "released": released, "checks": []}, "automatisch": 1, "regelsatz": "Standard",
		}, base64.b64encode(pdf).decode())

	def test_server_pruefung(self):
		self.assertEqual(schwaerzen.ergebnis_pruefen(bild_pdf()), [])
		fehler = schwaerzen.ergebnis_pruefen(text_pdf(), ["ZZ Geheim GmbH"])
		self.assertTrue(any("Ressourcen" in f for f in fehler))
		self.assertTrue(any("mehr als nur das Bild" in f for f in fehler))
		self.assertTrue(any("Begriff" in f for f in fehler))
		self.assertTrue(any("Metadaten" in f for f in schwaerzen.ergebnis_pruefen(bild_pdf(b"<< /Producer (x) /Author (ZZ Erika) >>"))))
		self.assertTrue(any("Begriff" in f for f in schwaerzen.ergebnis_pruefen(bild_pdf(b"<< /Producer (zz geheim gmbh) >>"), ["ZZ Geheim GmbH"])))
		self.assertEqual(schwaerzen.ergebnis_pruefen(b"kein pdf"), ["Die Datei lässt sich nicht als PDF lesen."])

	def test_kunden_begriffe_und_regeln(self):
		b = schwaerzen.kunden_begriffe(self.kunde)
		for x in ("ZZ Geheim GmbH", "ZZ Geheim", "ZZG", "Erika Zettmann", "Zettmann", "erika@zz-geheim.de", "zz-geheim.de"):
			self.assertIn(x, b)
		r = schwaerzen.regeln_fuer(self.kunde)
		self.assertEqual(r["regelsatz"], "Standard")
		self.assertIn("Gez.", r["regeln"]["labelRightKeywords"])
		eigen = schwaerzen.regelsatz_speichern({"bezeichnung": "ZZ Regeln", "kundeId": self.kunde, "regeln": {"directKeywords": ["ZZ Projekt X", "ZZ Projekt X"], "headerKeywords": ["Name"], "changeTableKeywords": ["Name", "gibt es nicht"], "logos": [{"dataUrl": "https://fremd.example/x.png"}]}})
		self.assertEqual(eigen["regeln"]["directKeywords"], ["ZZ Projekt X"])
		self.assertEqual(eigen["regeln"]["logos"], [])  # nur eigene private Dateien
		r = schwaerzen.regeln_fuer(self.kunde)
		self.assertEqual((r["regelsatz"], r["regeln"]["directKeywords"], r["regeln"]["headerKeywords"]), ("ZZ Regeln", ["ZZ Projekt X"], ["Name"]))
		self.assertIn("Gez.", r["regeln"]["labelRightKeywords"])  # Standard bleibt dabei
		with self.assertRaises(frappe.ValidationError):
			schwaerzen.regelsatz_speichern({"bezeichnung": "ZZ Doppelt", "kundeId": self.kunde})
		with self.assertRaises(frappe.ValidationError):
			schwaerzen.regelsatz_loeschen("Standard")

	def test_speichern_freigeben_und_mail(self):
		# ohne freigegebene Fassung geht die Zeichnung nicht hinaus
		frappe.get_doc({"doctype": "Lieferant", "lieferantenname": "ZZ Härterei SW", "email": "info@zz-haerterei-sw.de"}).insert()
		ang = frappe.get_doc({"doctype": "Angebot", "kunde": self.kunde, "status": "Entwurf"}).insert(ignore_mandatory=True)
		neu = anfrage.anlegen(ang.name, ["ZZ Härterei SW"], [{"teilId": "t1", "teil": {"name": "ZZ Welle", "teilenummer": "ZZ-SW-1"}, "agId": "a1", "agName": "Härten", "mengen": [5]}])
		docs = anfrage.vorgang_docs(neu[0]["vorgang"])
		self.assertEqual([z["url"] for z in anfrage.mail_vorschlag(neu[0]["vorgang"])["zeichnungenListe"]], [self.original.file_url])
		with self.assertRaises(frappe.ValidationError):
			anfrage._anhaenge(docs, zeichnungen=True)
		self.assertEqual(anfrage._anhaenge(docs, zeichnungen=False), [])

		# eine Fassung, die die Server-Prüfung nicht besteht, lässt sich nicht freigeben
		schlecht = self._speichern(text_pdf(b"ZZ Anders GmbH"))
		self.assertFalse(schlecht["pruefungBestanden"])
		self.assertFalse(schlecht["protokoll"]["serverPruefung"]["bestanden"])
		with self.assertRaises(frappe.ValidationError):
			schwaerzen.freigeben(schlecht["id"])

		gut = self._speichern(bild_pdf())
		self.assertEqual(frappe.db.get_value("Schwaerzung", schlecht["id"], "status"), "Verworfen")  # ältere ungeprüfte weg
		self.assertTrue(gut["pruefungBestanden"])
		self.assertEqual(gut["regelsatz"], "Standard")
		self.assertIn("zz-original_M01", gut["ergebnisUrl"])  # Frappe hängt bei gleichem Namen etwas an
		self.assertEqual(schwaerzen.status([self.original.file_url])[self.original.file_url]["status"], "Ungeprüft")
		with self.assertRaises(frappe.ValidationError):
			anfrage._anhaenge(docs, zeichnungen=True)  # ungeprüft reicht nicht

		f = schwaerzen.freigeben(gut["id"])
		self.assertEqual((f["status"], f["geprueftVon"] != ""), ("Freigegeben", True))
		anh = anfrage._anhaenge(docs, zeichnungen=True)
		self.assertEqual([n for n, _i in anh], ["zz-original_M01.pdf"])
		self.assertEqual(anh[0][1], bild_pdf())  # die geschwärzte Fassung, nie das Original

		# Original geändert (neue Datei unter derselben Adresse): die alte Freigabe gilt nicht mehr
		frappe.db.set_value("Schwaerzung", gut["id"], "original_sha", "0" * 64)
		self.assertIsNone(schwaerzen.freigegebene_datei(self.original.file_url))

	def test_falsche_pruefsumme_oder_geaendertes_original(self):
		with self.assertRaises(frappe.ValidationError):
			schwaerzen.speichern({"originalUrl": self.original.file_url, "originalSha": "0" * 64, "protokoll": {}}, base64.b64encode(bild_pdf()).decode())
		with self.assertRaises(frappe.ValidationError):
			schwaerzen.speichern({"originalUrl": self.original.file_url, "originalSha": hashlib.sha256(self.original.get_content()).hexdigest(), "protokoll": {"sha256": "1" * 64}}, base64.b64encode(bild_pdf()).decode())

	def test_gast_hat_keinen_zugriff(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			schwaerzen.status([self.original.file_url])
		with self.assertRaises(frappe.PermissionError):
			schwaerzen.regeln_fuer(self.kunde)
