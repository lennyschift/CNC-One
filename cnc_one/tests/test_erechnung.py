import io

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from lxml import etree

from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen
from cnc_one.api import angebot, auftrag, erechnung as ablage, firma, lieferschein, rechnung
from cnc_one.logic import erechnung
from cnc_one.logic.pdf import pdf_a3
from cnc_one.tests.test_angebot import teil

PLAN = [{"id": "p1", "name": "Drehen", "typ": "intern"}]
SPARKASSE = "DE64 6225 0030 0005 4437 72"
NS = erechnung.NS
FIRMA = {
	"firmenname": "ZZ Firma", "strasse": "Hauptstraße 1", "plz": "74523", "ort": "Schwäbisch Hall", "land": "Deutschland", "telefon": "+49 791 12345",
	"email": "info@zz-firma.de", "ustId": "DE224416172", "steuernummer": "DE224416172", "ansprechpartner": "Max Muster",
	"banken": [{"bezeichnung": "Sparkasse SHA", "iban": SPARKASSE, "bic": "SOLADES1SHA"}],
}


def beispiel():
	return {
		"nummer": "RE-2026-0099", "art": "Teilrechnung", "datum": "2026-10-24", "faellig": "2026-11-07", "leistung_von": "2026-10-20", "leistung_bis": "2026-10-22",
		"waehrung": "EUR", "bestellnr": "B-4711", "kaeufer_referenz": "B-4711", "lieferscheine": ["LS-0010", "LS-0011"], "vorgaenger": None, "bemerkung": "",
		"zahlungsbedingung": "Zahlbar innerhalb von 14 Tagen ohne Abzug bis 07.11.2026",
		"verkaeufer": {
			"name": "CNC Hohenstein", "strasse": "Hauptstraße 1", "plz": "74523", "ort": "Schwäbisch Hall", "land": "DE", "ust_id": "DE224416172",
			"steuernummer": "DE224416172", "ansprechpartner": "Max Muster", "telefon": "+49 791 12345", "email": "info@cnc-hohenstein.de",
			"iban": "DE64622500300005443772", "bic": "SOLADES1SHA",
		},
		"kaeufer": {"name": "Muster GmbH", "strasse": "Kundenweg 5", "plz": "70173", "ort": "Stuttgart", "land": "DE", "email": "einkauf@muster.de", "ust_id": "DE123456789"},
		"steuersatz": 19, "steuerkategorie": "S",
		"zeilen": [
			{"id": "1", "name": "Welle A", "teilenummer": "T-100", "zeichnungsnr": "Z-9", "menge": 4, "einheit": "C62", "einzelpreis": 12.5, "netto": 150.0,
				"hinweis": "Geliefert mit LS-0010 (4 Stk) · Seriennummern 0001–0004",
				"zuschlaege": [{"text": "Rüstkosten (Welle A) – Sonderkosten zu Position 1", "betrag": 100.0}]},
		],
		"netto": 150.0, "steuer": 28.5, "brutto": 178.5,
	}


def wert(baum, pfad):
	return baum.xpath(pfad, namespaces=NS)


class TestERechnungLogik(UnitTestCase):
	def test_laendercode(self):
		self.assertEqual(erechnung.laendercode(""), "DE")
		self.assertEqual(erechnung.laendercode("de"), "DE")
		self.assertEqual(erechnung.laendercode("Deutschland"), "DE")
		self.assertEqual(erechnung.laendercode("Österreich"), "AT")
		self.assertIsNone(erechnung.laendercode("Atlantis"))

	def test_betraege_kaufmaennisch_mit_fester_nachkommastelle(self):
		self.assertEqual(erechnung.betrag(2.675), "2.68")
		self.assertEqual(erechnung.betrag(12), "12.00")
		self.assertEqual(erechnung.betrag(4, 4), "4.0000")
		self.assertEqual(erechnung.betrag(None), "0.00")

	def test_vollstaendige_angaben_fehlen_nichts(self):
		self.assertEqual(erechnung.fehlende_angaben(beispiel()), [])

	def test_pflichtangaben_fuer_zugferd(self):
		d = beispiel()
		d["verkaeufer"].update(ansprechpartner="", telefon="", email="", iban="")  # Kontakt und Bank sind keine Pflicht
		d["kaeufer"]["email"] = ""
		self.assertEqual(erechnung.fehlende_angaben(d), [])
		d["verkaeufer"].update(ust_id="", steuernummer="", plz="")
		d["kaeufer"]["ort"] = ""
		self.assertEqual(erechnung.fehlende_angaben(d), ["PLZ und Ort der Firma", "USt-IdNr. oder Steuernummer der Firma", "PLZ und Ort des Kunden"])

	def test_rechnung_ist_typ_380_mit_leitfaden_und_betraegen(self):
		b = etree.fromstring(erechnung.baue_cii(beispiel()))
		self.assertEqual(wert(b, "//rsm:ExchangedDocument/ram:ID/text()"), ["RE-2026-0099"])
		self.assertEqual(wert(b, "//rsm:ExchangedDocument/ram:TypeCode/text()"), ["380"])
		self.assertEqual(wert(b, "//ram:GuidelineSpecifiedDocumentContextParameter/ram:ID/text()"), [erechnung.LEITFADEN])
		self.assertEqual(wert(b, "//ram:BusinessProcessSpecifiedDocumentContextParameter"), [])
		self.assertEqual(wert(b, "//ram:GrandTotalAmount/text()"), ["178.50"])
		self.assertEqual(wert(b, "//ram:TaxBasisTotalAmount/text()"), ["150.00"])
		self.assertEqual(wert(b, "//ram:BilledQuantity/text()"), ["4.0000"])
		self.assertEqual(wert(b, "//ram:PayeePartyCreditorFinancialAccount/ram:IBANID/text()"), ["DE64622500300005443772"])
		self.assertEqual(wert(b, "//ram:BuyerReference/text()"), ["B-4711"])
		self.assertEqual(wert(b, "//ram:DespatchAdviceReferencedDocument/ram:IssuerAssignedID/text()"), ["LS-0010, LS-0011"])
		self.assertEqual(wert(b, "//ram:IncludedSupplyChainTradeLineItem[1]//ram:IncludedNote/ram:Content/text()"), ["Geliefert mit LS-0010 (4 Stk) · Seriennummern 0001–0004"])

	def test_leistungszeitraum_nur_wenn_er_sich_erstreckt(self):
		b = etree.fromstring(erechnung.baue_cii(beispiel()))
		self.assertEqual(wert(b, "//ram:BillingSpecifiedPeriod/ram:StartDateTime/udt:DateTimeString/text()"), ["20261020"])
		self.assertEqual(wert(b, "//ram:BillingSpecifiedPeriod/ram:EndDateTime/udt:DateTimeString/text()"), ["20261022"])
		d = dict(beispiel(), leistung_von="2026-10-22")
		self.assertEqual(wert(etree.fromstring(erechnung.baue_cii(d)), "//ram:BillingSpecifiedPeriod"), [])

	def test_zeilennummern_sind_fortlaufend_ganzzahlig(self):
		d = beispiel()
		d["zeilen"].append(dict(d["zeilen"][0], id="2", zuschlaege=[]))
		b = etree.fromstring(erechnung.baue_cii(d))
		self.assertEqual(wert(b, "//ram:AssociatedDocumentLineDocument/ram:LineID/text()"), ["1", "2"])

	def test_sonderkosten_sind_zuschlaege_an_der_position(self):
		b = etree.fromstring(erechnung.baue_cii(beispiel()))
		self.assertEqual(wert(b, "//ram:SpecifiedTradeAllowanceCharge/ram:ChargeIndicator/udt:Indicator/text()"), ["true"])
		self.assertEqual(wert(b, "//ram:SpecifiedTradeAllowanceCharge/ram:ActualAmount/text()"), ["100.00"])
		self.assertEqual(wert(b, "//ram:SpecifiedTradeAllowanceCharge/ram:Reason/text()"), ["Rüstkosten (Welle A) – Sonderkosten zu Position 1"])
		self.assertEqual(wert(b, "//ram:IncludedSupplyChainTradeLineItem//ram:LineTotalAmount/text()"), ["150.00"])

	def test_storno_ist_gutschrift_typ_381_mit_positiven_betraegen_und_bezug(self):
		d = beispiel()
		d.update(art="Storno", nummer="RE-2026-0100", vorgaenger={"nummer": "RE-2026-0099", "datum": "2026-10-24"}, netto=-150.0, steuer=-28.5, brutto=-178.5)
		d["zeilen"] = [dict(z, menge=-z["menge"], netto=-z["netto"], zuschlaege=[dict(x, betrag=-x["betrag"]) for x in z["zuschlaege"]]) for z in d["zeilen"]]
		b = etree.fromstring(erechnung.baue_cii(d))
		self.assertEqual(wert(b, "//rsm:ExchangedDocument/ram:TypeCode/text()"), ["381"])
		self.assertEqual(wert(b, "//ram:GrandTotalAmount/text()"), ["178.50"])
		self.assertEqual(wert(b, "//ram:BilledQuantity/text()"), ["4.0000"])
		self.assertEqual(wert(b, "//ram:LineTotalAmount/text()"), ["150.00", "150.00"])
		self.assertEqual(wert(b, "//ram:SpecifiedTradeAllowanceCharge/ram:ActualAmount/text()"), ["100.00"])
		self.assertEqual(wert(b, "//ram:InvoiceReferencedDocument/ram:IssuerAssignedID/text()"), ["RE-2026-0099"])
		self.assertEqual(wert(b, "//ram:SpecifiedTradePaymentTerms"), [])

	def test_pdf_a3_mit_eingebettetem_xml_und_factur_x_metadaten(self):
		from pypdf import PdfReader

		xml = erechnung.baue_cii(beispiel())
		inhalt = pdf_a3("<html><body><p>Rechnung ä ö ü €</p></body></html>", xml, titel="Rechnung")
		leser = PdfReader(io.BytesIO(inhalt))
		self.assertEqual(list(leser.attachments), ["factur-x.xml"])
		self.assertEqual(leser.attachments["factur-x.xml"][0], xml)
		xmp = leser.trailer["/Root"]["/Metadata"].get_object().get_data().decode()
		for stueck in ("fx:DocumentFileName>factur-x.xml<", "fx:ConformanceLevel>EN 16931<", 'pdfaid:part="3"', "pdfaExtension:schemas"):
			self.assertIn(stueck, xmp)
		self.assertEqual(list(PdfReader(io.BytesIO(pdf_a3("<html><body>x</body></html>"))).attachments), [])


class TestERechnung(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		frappe.flags.erechnung_testen = True
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ E-Kunde", "zahlungsziel_tage": 30, "ust_id": "DE999", "leitweg_id": ""}).insert().name
		k = frappe.get_doc("Kunde", self.kunde)
		k.append("adressen", {"typ": "Rechnung und Lieferung", "strasse": "Weg 1", "plz": "72461", "ort": "Albstadt", "land": "DE", "standard": 1})
		k.append("kontakte", {"nachname": "Meier", "email": "meier@kunde.de", "ist_rechnungskontakt": 1})
		k.save()
		firma.speichern(FIRMA)

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.flags.erechnung_testen = False
		frappe.db.rollback()

	def auftrag(self, menge=10):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Flansch", "ZZ-E1")]})
		a = angebot.senden(a["id"])
		return auftrag.aus_angebot(a["id"], "PO-9", [{"angebotKey": "t1", "menge": menge, "arbeitsgaenge": PLAN}])

	def festgeschrieben(self, menge=10, liefern=10):
		auf = self.auftrag(menge)
		lieferschein.anlegen(self.kunde, [{"auftrag": auf["id"], "auftragsposition": auf["positionen"][0]["key"], "menge": liefern}])
		return rechnung.festschreiben(rechnung.anlegen(auf["id"], "Gesamtrechnung")["id"])

	def pdf(self, r):
		name = ablage._datei_suchen(frappe.get_doc("Rechnung", r["id"]))
		inhalt = frappe.get_doc("File", name).get_content()
		return inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt

	def xml(self, r):
		"""Das ZUGFeRD-XML, das im PDF steckt (None, wenn keins eingebettet ist)."""
		from pypdf import PdfReader

		anhang = PdfReader(io.BytesIO(self.pdf(r))).attachments.get("factur-x.xml")
		return etree.fromstring(anhang[0]) if anhang else None

	def test_empfaenger_wird_beim_anlegen_festgehalten(self):
		auf = self.auftrag()
		r = frappe.get_doc("Rechnung", rechnung.anlegen(auf["id"], "Gesamtrechnung")["id"])
		self.assertEqual((r.kunde_email, r.kunde_strasse, r.kunde_plz, r.kunde_ort, r.kunde_land), ("meier@kunde.de", "Weg 1", "72461", "Albstadt", "DE"))

	def test_festschreiben_erzeugt_zugferd_pdf(self):
		from pypdf import PdfReader

		r = self.festgeschrieben()
		self.assertEqual(r["eRechnung"], {"status": "ZUGFeRD", "hinweis": "", "pdf": True, "zugferd": True})
		xr = self.xml(r)
		self.assertEqual(wert(xr, "//rsm:ExchangedDocument/ram:ID/text()"), [r["nummer"]])
		self.assertEqual(wert(xr, "//ram:GrandTotalAmount/text()"), [f"{r['brutto']:.2f}"])
		self.assertIn("info@zz-firma.de", wert(xr, "//ram:SellerTradeParty//ram:URIID/text()"))
		self.assertIn("meier@kunde.de", wert(xr, "//ram:BuyerTradeParty//ram:URIID/text()"))
		self.assertEqual(wert(xr, "//ram:BuyerReference/text()"), ["PO-9"])
		self.assertEqual(wert(xr, "//ram:GuidelineSpecifiedDocumentContextParameter/ram:ID/text()"), [erechnung.LEITFADEN])
		leser = PdfReader(io.BytesIO(self.pdf(r)))
		text = "".join(s.extract_text() for s in leser.pages)
		self.assertIn(r["nummer"], text)
		self.assertIn("Flansch", text)

	def test_fehlen_pflichtangaben_gibt_es_nur_pdf_und_einen_hinweis(self):
		firma.speichern({**FIRMA, "ustId": "", "steuernummer": ""})
		r = self.festgeschrieben()
		self.assertEqual(r["eRechnung"]["status"], "Nur PDF")
		self.assertIn("USt-IdNr. oder Steuernummer der Firma", r["eRechnung"]["hinweis"])
		self.assertEqual((r["eRechnung"]["pdf"], r["eRechnung"]["zugferd"]), (True, False))
		self.assertIsNone(self.xml(r))

	def test_ansprechpartner_und_kontakt_sind_keine_pflicht(self):
		firma.speichern({**FIRMA, "ansprechpartner": "", "telefon": "", "email": ""})
		self.assertEqual(self.festgeschrieben()["eRechnung"]["status"], "ZUGFeRD")

	def test_nachtraeglich_ergaenzte_firmendaten_gelten_beim_neu_erzeugen(self):
		firma.speichern({**FIRMA, "ustId": "", "steuernummer": ""})
		r = self.festgeschrieben()
		self.assertEqual(r["eRechnung"]["status"], "Nur PDF")
		firma.speichern(FIRMA)
		r = ablage.neu_erzeugen(r["id"])
		self.assertEqual(r["eRechnung"]["status"], "ZUGFeRD")
		self.assertEqual(wert(self.xml(r), "//ram:SellerTradeParty//ram:SpecifiedTaxRegistration/ram:ID/text()"), ["DE224416172"])
		dateien = sorted(frappe.get_all("File", filters={"attached_to_doctype": "Rechnung", "attached_to_name": r["id"]}, pluck="file_name"))
		self.assertEqual(dateien, [f"{r['nummer']}.pdf", f"{r['nummer']}_v2.pdf"])  # die ältere Fassung bleibt erhalten

	def test_sonderkosten_stehen_als_zuschlaege_an_der_bauteilzeile(self):
		r = self.festgeschrieben()
		xr = self.xml(r)
		self.assertEqual(wert(xr, "//ram:IncludedSupplyChainTradeLineItem/ram:AssociatedDocumentLineDocument/ram:LineID/text()"), ["1"])
		self.assertEqual(wert(xr, "//ram:SpecifiedTradeAllowanceCharge/ram:ActualAmount/text()"), ["100.00", "20.00"])
		self.assertEqual(wert(xr, "//ram:IncludedSupplyChainTradeLineItem//ram:LineTotalAmount/text()"), ["260.00"])
		self.assertEqual(wert(xr, "//ram:ApplicableHeaderTradeSettlement//ram:LineTotalAmount/text()"), ["260.00"])

	def test_entwurf_hat_keine_e_rechnung(self):
		r = rechnung.anlegen(self.auftrag()["id"], "Gesamtrechnung")
		self.assertEqual(r["eRechnung"]["status"], "")
		with self.assertRaises(frappe.ValidationError):
			ablage.erzeugen(frappe.get_doc("Rechnung", r["id"]))

	def test_storno_wird_als_gutschrift_mit_bezug_ausgestellt(self):
		r = self.festgeschrieben()
		s = rechnung.stornieren(r["id"], "Fehler")["storno"]
		self.assertEqual(s["eRechnung"]["status"], "ZUGFeRD")
		xr = self.xml(s)
		self.assertEqual(wert(xr, "//rsm:ExchangedDocument/ram:TypeCode/text()"), ["381"])
		self.assertEqual(wert(xr, "//ram:InvoiceReferencedDocument/ram:IssuerAssignedID/text()"), [r["nummer"]])
		self.assertEqual(wert(xr, "//ram:GrandTotalAmount/text()"), [f"{r['brutto']:.2f}"])

	def test_fehler_beim_erzeugen_haelt_das_festschreiben_nicht_auf(self):
		original = ablage.pdf.pdf_a3
		ablage.pdf.pdf_a3 = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaputt"))
		try:
			r = self.festgeschrieben()
		finally:
			ablage.pdf.pdf_a3 = original
		self.assertEqual(r["status"], "Offen")
		self.assertEqual(r["eRechnung"]["status"], "Fehler")
		self.assertTrue(r["nummer"])
