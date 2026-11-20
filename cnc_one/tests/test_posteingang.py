"""Posteingang: bekannte Absender, Einordnung, Schutz vor gefährlichen Anhängen, Prüfung des Absenders und
Eingangsrechnungen aus E-Rechnungen (ZUGFeRD/Factur-X und XRechnung in CII und UBL)."""

import io
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import eingangsrechnung as er_api
from cnc_one.api import mail as mail_api
from cnc_one.logic import eingangsrechnung, mail
from cnc_one.tests.dateischutz import dateien_vorher, eigene_dateien_loeschen
from cnc_one.tests.test_dateien import leeres_pdf
from cnc_one.tests.test_mail import FakeImap, zz_mail

CII = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
 xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
 xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
 <rsm:ExchangedDocument><ram:ID>{nr}</ram:ID><ram:TypeCode>380</ram:TypeCode>
  <ram:IssueDateTime><udt:DateTimeString format="102">20261115</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
 <rsm:SupplyChainTradeTransaction>
  <ram:IncludedSupplyChainTradeLineItem>
   <ram:SpecifiedTradeProduct><ram:Name>Eloxieren schwarz</ram:Name></ram:SpecifiedTradeProduct>
   <ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice><ram:ChargeAmount>2.50</ram:ChargeAmount></ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>
   <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="H87">40</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
   <ram:SpecifiedLineTradeSettlement><ram:ApplicableTradeTax><ram:RateApplicablePercent>19</ram:RateApplicablePercent></ram:ApplicableTradeTax>
    <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>100.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement>
  </ram:IncludedSupplyChainTradeLineItem>
  <ram:ApplicableHeaderTradeAgreement>
   <ram:SellerTradeParty><ram:Name>ZZ Eloxal GmbH</ram:Name>
    <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">DE 999 888 777</ram:ID></ram:SpecifiedTaxRegistration></ram:SellerTradeParty>
   <ram:BuyerOrderReferencedDocument><ram:IssuerAssignedID>LA-2026-0099</ram:IssuerAssignedID></ram:BuyerOrderReferencedDocument>
  </ram:ApplicableHeaderTradeAgreement>
  <ram:ApplicableHeaderTradeSettlement><ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
   <ram:SpecifiedTradeSettlementPaymentMeans><ram:PayeePartyCreditorFinancialAccount><ram:IBANID>DE02120300000000202051</ram:IBANID></ram:PayeePartyCreditorFinancialAccount></ram:SpecifiedTradeSettlementPaymentMeans>
   <ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime><udt:DateTimeString format="102">20261215</udt:DateTimeString></ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>
   <ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:LineTotalAmount>100.00</ram:LineTotalAmount><ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
    <ram:TaxTotalAmount currencyID="EUR">19.00</ram:TaxTotalAmount><ram:GrandTotalAmount>119.00</ram:GrandTotalAmount><ram:DuePayableAmount>119.00</ram:DuePayableAmount></ram:SpecifiedTradeSettlementHeaderMonetarySummation>
  </ram:ApplicableHeaderTradeSettlement>
 </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""

UBL = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cbc:ID>ZZ-UBL-7</cbc:ID><cbc:IssueDate>2026-11-10</cbc:IssueDate><cbc:DueDate>2026-11-24</cbc:DueDate><cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
 <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
 <cac:OrderReference><cbc:ID>B-77</cbc:ID></cac:OrderReference>
 <cac:AccountingSupplierParty><cac:Party><cbc:EndpointID schemeID="EM">rechnung@zz-stahl.de</cbc:EndpointID>
  <cac:PartyTaxScheme><cbc:CompanyID>DE111222333</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>
  <cac:PartyLegalEntity><cbc:RegistrationName>ZZ Stahlhandel KG</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>
 <cac:PaymentMeans><cbc:PaymentMeansCode>58</cbc:PaymentMeansCode><cac:PayeeFinancialAccount><cbc:ID>DE02500105170137075030</cbc:ID></cac:PayeeFinancialAccount></cac:PaymentMeans>
 <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">38.00</cbc:TaxAmount></cac:TaxTotal>
 <cac:LegalMonetaryTotal><cbc:LineExtensionAmount currencyID="EUR">200.00</cbc:LineExtensionAmount><cbc:TaxExclusiveAmount currencyID="EUR">200.00</cbc:TaxExclusiveAmount>
  <cbc:TaxInclusiveAmount currencyID="EUR">238.00</cbc:TaxInclusiveAmount><cbc:PayableAmount currencyID="EUR">238.00</cbc:PayableAmount></cac:LegalMonetaryTotal>
 <cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="KGM">50</cbc:InvoicedQuantity><cbc:LineExtensionAmount currencyID="EUR">200.00</cbc:LineExtensionAmount>
  <cac:Item><cbc:Name>Rundstahl 42CrMo4 D40</cbc:Name><cac:ClassifiedTaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>19</cbc:Percent></cac:ClassifiedTaxCategory></cac:Item>
  <cac:Price><cbc:PriceAmount currencyID="EUR">4.00</cbc:PriceAmount></cac:Price></cac:InvoiceLine>
</Invoice>"""


def zugferd_pdf(nr="ZZ-RE-1"):
	"""PDF mit eingebetteter factur-x.xml (wie ZUGFeRD/Factur-X)."""
	from pypdf import PdfReader, PdfWriter

	w = PdfWriter()
	w.append(PdfReader(io.BytesIO(leeres_pdf("zz-rechnung"))))
	w.add_attachment("factur-x.xml", CII.format(nr=nr).encode())
	out = io.BytesIO()
	w.write(out)
	return out.getvalue()


def mail_mit_kopf(roh, **kopf):
	kopfzeilen = "".join(f"{k.replace('_', '-')}: {v}\n" for k, v in kopf.items()).encode()
	return kopfzeilen + roh


class TestPosteingang(IntegrationTestCase):
	def setUp(self):
		self._dateien = dateien_vorher()
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Postkunde", "kontakte": [{"nachname": "Einkauf", "email": "einkauf@zz-kunde.de"}]}).insert().name
		self.lieferant = frappe.get_doc({"doctype": "Lieferant", "lieferantenname": "ZZ Eloxal GmbH", "email": "info@zz-eloxal.de", "weitere_emails": "buchhaltung@zz-eloxal-rechnung.de", "ust_id": "DE999888777"}).insert().name
		s = frappe.get_single("Mail Einstellungen")
		s.update({
			"benutzer": "info@zz-cnc.de", "imap_server": "zz.invalid", "stichwoerter": "Anfrage\nRFQ", "abholen_ab": None, "aktiv": 0,
			"bekannte_absender": 1, "woerter_bestellung": "Bestellung\nOrder", "woerter_rechnung": "Rechnung\nInvoice", "freemail_domains": "", "gesperrte_endungen": "",
		})
		s.passwort = "zz-geheim"
		s.save()

	def tearDown(self):
		frappe.set_user("Administrator")
		eigene_dateien_loeschen(self._dateien)
		frappe.db.rollback()

	# --------------------------------------------------------------- Einordnen
	def test_einordnen(self):
		s = mail.einstellungen()
		self.assertEqual(mail.einordnen(s, "Anfrage Flansch", [], kunde=self.kunde), "Anfrage")
		self.assertEqual(mail.einordnen(s, "Bestellung 4500123", [], kunde=self.kunde), "Bestellung")
		self.assertEqual(mail.einordnen(s, "Unterlagen", ["Order_4711.pdf"], kunde=self.kunde), "Bestellung")
		self.assertEqual(mail.einordnen(s, "Neue Teile", ["4711.stp"], kunde=self.kunde), "Anfrage")  # Kunde mit CAD ohne Stichwort
		self.assertEqual(mail.einordnen(s, "Frage zur Lieferung", [], kunde=self.kunde), "Sonstiges")
		self.assertEqual(mail.einordnen(s, "Ihre Rechnung RE-1", [], kunde=self.kunde), "Sonstiges")  # Kunde fragt zu unserer Rechnung
		self.assertEqual(mail.einordnen(s, "Rechnungen November", [], lieferant=self.lieferant), "Rechnung")
		self.assertEqual(mail.einordnen(s, "Lieferschein", [], lieferant=self.lieferant), "Lieferant")
		self.assertEqual(mail.einordnen(s, "x", [], erechnung=True), "Rechnung")
		self.assertEqual(mail.einordnen(s, "Ordner", [], kunde=self.kunde), "Sonstiges")  # „Order“ nur am Wortanfang

	def test_mail_vom_lieferanten_und_bestellung_vom_kunden(self):
		d = mail.verarbeiten(zz_mail(betreff="Lieferschein 55", von="info@zz-eloxal.de", mid="<zz-p1@zz>"))
		self.assertEqual((d.kategorie, d.lieferant, d.kunde), ("Lieferant", self.lieferant, None))
		d = mail.verarbeiten(zz_mail(betreff="Bestellung 4500123", mid="<zz-p2@zz>"))
		self.assertEqual((d.kategorie, d.kunde), ("Bestellung", self.kunde))
		ui = mail_api.kategorie_setzen(d.name, "Anfrage")
		self.assertEqual(ui["kategorie"], "Anfrage")
		self.assertEqual(mail_api.erledigt(d.name)["status"], "Erledigt")
		with self.assertRaises(frappe.ValidationError):
			mail_api.kategorie_setzen(d.name, "Quatsch")

	def test_lieferant_zuordnen_merkt_sich_die_adresse(self):
		d = mail.verarbeiten(zz_mail(betreff="Angebot Härten", von="vertrieb@zz-haerterei.de", mid="<zz-p3@zz>"))
		ui = mail_api.lieferant_zuordnen(d.name, self.lieferant)
		self.assertEqual((ui["lieferantId"], ui["kategorie"]), (self.lieferant, "Lieferant"))
		self.assertIn("vertrieb@zz-haerterei.de", frappe.db.get_value("Lieferant", self.lieferant, "weitere_emails"))
		self.assertEqual(mail.lieferant_zur_adresse("vertrieb@zz-haerterei.de"), self.lieferant)

	def test_bekannte_absender_und_freemail(self):
		adressen, domains = mail.bekannte_absender()
		self.assertIn("einkauf@zz-kunde.de", adressen)
		self.assertIn("buchhaltung@zz-eloxal-rechnung.de", adressen)
		self.assertIn("zz-kunde.de", domains)
		self.assertTrue(mail.ist_bekannt("kollege@zz-kunde.de", adressen, domains))
		self.assertFalse(mail.ist_bekannt("fremd@zz-spam.de", adressen, domains))
		k = frappe.get_doc("Kunde", self.kunde)
		k.append("kontakte", {"nachname": "Privat", "email": "zz-privat@gmail.com"})
		k.save()
		adressen, domains = mail.bekannte_absender()
		self.assertTrue(mail.ist_bekannt("zz-privat@gmail.com", adressen, domains))
		self.assertFalse(mail.ist_bekannt("irgendwer@gmail.com", adressen, domains))  # Freemail: nur die genaue Adresse

	def test_abholen_laedt_bekannte_absender_ohne_stichwort(self):
		class Imap(FakeImap):
			def uid(self, befehl, *args):
				if befehl == "SEARCH" and args[0] == "SINCE" and len(args) == 2:
					return "OK", [b" ".join(str(u).encode() for u in self.mails)]
				return super().uid(befehl, *args)

		imap = Imap([
			zz_mail(betreff="Zeichnungen neue Teile", mid="<zz-a1@zz>"),  # bekannter Kunde, ohne Stichwort
			zz_mail(betreff="Newsletter", von="werbung@zz-spam.de", mid="<zz-a2@zz>"),  # unbekannt, ohne Stichwort
			zz_mail(betreff="Anfrage Welle", von="neu@zz-neukunde.de", mid="<zz-a3@zz>"),  # unbekannt mit Stichwort
		])
		# abholen() schreibt je Mail fest: im Test nie (sonst bleiben Testdaten und Testeinstellungen stehen)
		with patch.object(mail, "imap_verbinden", return_value=imap), patch.object(frappe.db, "commit"):
			self.assertEqual(mail.abholen(), 2)
		self.assertEqual(sorted(imap.geladen), [1, 3])
		self.assertFalse(frappe.db.exists("Mail Anfrage", {"von_email": "werbung@zz-spam.de"}))

	# --------------------------------------------------------------- Schutz
	def test_gefaehrliche_anhaenge_werden_nicht_uebernommen(self):
		z = io.BytesIO()
		with zipfile.ZipFile(z, "w") as zf:
			zf.writestr("teile/zeichnung.pdf", leeres_pdf("zz-z"))
			zf.writestr("teile/setup.exe", b"MZ zz")
		d = mail.verarbeiten(zz_mail(mid="<zz-s1@zz>", anhaenge=[
			("zz-ok.pdf", leeres_pdf("zz-ok")), ("rechner.exe", b"MZ zz"), ("liste.xlsm", b"PK zz"), ("tarnung.pdf", b"MZ zz-getarnt"), ("paket.zip", z.getvalue()),
		]))
		n = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))["nachrichten"][0]
		self.assertEqual([a["name"] for a in n["anhaenge"]], ["zz-ok.pdf"])
		for x in ("rechner.exe", "liste.xlsm", "tarnung.pdf", "paket.zip"):
			self.assertIn(x, n["hinweis"])
		self.assertIn("ausführbares Programm", n["hinweis"])

	def test_gefaelschter_absender_wird_nicht_zugeordnet(self):
		roh = mail_mit_kopf(zz_mail(mid="<zz-f1@zz>"), Authentication_Results="mx.ionos.de; spf=fail smtp.mailfrom=zz-kunde.de; dkim=none; dmarc=fail header.from=zz-kunde.de")
		d = mail.verarbeiten(roh)
		self.assertEqual((d.absender_warnung, d.kunde), (1, None))
		self.assertIn("DMARC fail", d.absender_pruefung)
		ok = mail.verarbeiten(mail_mit_kopf(zz_mail(mid="<zz-f2@zz>"), Authentication_Results="mx.ionos.de; spf=pass; dkim=pass; dmarc=pass"))
		self.assertEqual((ok.absender_warnung, ok.kunde), (0, self.kunde))

	# --------------------------------------------------------------- E-Rechnungen
	def test_zugferd_aus_mail_wird_eingangsrechnung(self):
		d = mail.verarbeiten(zz_mail(betreff="Unterlagen", von="info@zz-eloxal.de", mid="<zz-r1@zz>", anhaenge=[("RE-1.pdf", zugferd_pdf())]))
		self.assertEqual(d.kategorie, "Rechnung")
		r = frappe.get_doc("Eingangsrechnung", {"mail": d.name})
		self.assertEqual((r.format, r.lieferant, r.rechnungsnr, str(r.rechnungsdatum), str(r.faellig_am)), ("ZUGFeRD", self.lieferant, "ZZ-RE-1", "2026-11-15", "2026-12-15"))
		self.assertEqual((r.netto, r.steuer, r.brutto, r.iban, r.bestellreferenz), (100, 19, 119, "DE02120300000000202051", "LA-2026-0099"))
		self.assertEqual([(p.bezeichnung, p.menge, p.einheit, p.einzelpreis, p.betrag) for p in r.positionen], [("Eloxieren schwarz", 40, "H87", 2.5, 100)])
		self.assertTrue(r.pdf_datei)
		self.assertTrue(frappe.db.exists("File", {"attached_to_doctype": "Eingangsrechnung", "attached_to_name": r.name}))  # DMS
		self.assertIn(r.name, mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))["eingangsrechnungen"])
		# dieselbe Rechnung noch einmal: keine Dublette
		mail.verarbeiten(zz_mail(betreff="Erinnerung", von="info@zz-eloxal.de", mid="<zz-r2@zz>", anhaenge=[("RE-1.pdf", zugferd_pdf())]))
		self.assertEqual(frappe.db.count("Eingangsrechnung", {"rechnungsnr": "ZZ-RE-1"}), 1)
		with self.assertRaises(frappe.ValidationError):
			mail_api.keine_anfrage(d.name)

	def test_xrechnung_ubl_lesen(self):
		x = eingangsrechnung.lesen(UBL.encode())
		self.assertEqual((x["rechnungsnr"], x["rechnungsdatum"], x["faellig_am"], x["lieferant_name"], x["lieferant_ust_id"], x["email"]),
			("ZZ-UBL-7", "2026-11-10", "2026-11-24", "ZZ Stahlhandel KG", "DE111222333", "rechnung@zz-stahl.de"))
		self.assertEqual((x["netto"], x["steuer"], x["brutto"], x["bestellreferenz"]), (200, 38, 238, "B-77"))
		self.assertEqual(x["positionen"][0]["bezeichnung"], "Rundstahl 42CrMo4 D40")
		self.assertEqual(eingangsrechnung.erkennen("re.xml", UBL.encode())[0], "XRechnung")
		self.assertEqual(eingangsrechnung.erkennen("plan.pdf", leeres_pdf("zz-plan"))[0], None)
		self.assertEqual(eingangsrechnung.erkennen("daten.xml", b"<liste/>")[0], None)

	def test_xml_mit_entitaet_wird_nicht_aufgeloest(self):
		boese = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"><ID>&e;</ID></Invoice>'
		self.assertNotIn("root:", str(eingangsrechnung._baum(boese) is not None and eingangsrechnung.lesen(boese).get("rechnungsnr")))

	def test_pdf_rechnung_von_hand_pruefen(self):
		d = mail.verarbeiten(zz_mail(betreff="Rechnung 812", von="info@zz-eloxal.de", mid="<zz-r3@zz>", anhaenge=[("RE-812.pdf", leeres_pdf("zz-re812"))]))
		self.assertEqual(d.kategorie, "Rechnung")
		self.assertFalse(frappe.db.exists("Eingangsrechnung", {"mail": d.name}))  # kein XML: erst auf Klick
		url = mail_api.anfrage_ui(frappe.get_doc("Mail Anfrage", d.name))["nachrichten"][0]["anhaenge"][0]["url"]
		r = er_api.aus_datei(url, d.name)["rechnung"]
		self.assertEqual((r["format"], r["lieferantId"], r["status"]), ("PDF", self.lieferant, "Neu"))
		with self.assertRaises(frappe.ValidationError):
			er_api.status_setzen(r["id"], "Geprüft")  # Nummer, Datum, Betrag fehlen
		er_api.speichern(r["id"], {"rechnungsnr": "812", "rechnungsdatum": "2026-11-18", "netto": 100, "steuer": 19, "brutto": 119, "positionen": [{"bezeichnung": "Härten", "menge": 1, "betrag": 100}]})
		r = er_api.status_setzen(r["id"], "Geprüft")
		self.assertEqual((r["status"], r["geprueftVon"]), ("Geprüft", "Administrator"))
		with self.assertRaises(frappe.ValidationError):
			er_api.speichern(r["id"], {"netto": 1})
		with self.assertRaises(frappe.ValidationError):
			er_api.loeschen(r["id"])
		self.assertEqual(er_api.status_setzen(r["id"], "Bezahlt")["status"], "Bezahlt")
