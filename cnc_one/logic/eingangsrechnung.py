"""Eingangsrechnungen: E-Rechnungen der Lieferanten einlesen.

Erkannt werden ZUGFeRD/Factur-X (PDF mit eingebetteter XML) und XRechnung (reine XML), jeweils in der Syntax CII
(UN/CEFACT Cross Industry Invoice) oder UBL (Invoice/CreditNote). Gelesen werden die Angaben, die für Prüfung und
Buchhaltung zählen: Rechnungssteller, Nummer, Datum, Fälligkeit, Beträge, IBAN, Bestellreferenz und Positionen.
Die XML wird ohne Netz und ohne externe Entitäten gelesen (keine XXE). Ein PDF ohne XML bleibt eine PDF-Rechnung,
die Angaben trägt man dann von Hand ein.
"""

import io
import re

import frappe
from frappe import _
from lxml import etree

# Dateinamen der eingebetteten XML in ZUGFeRD/Factur-X/XRechnung-PDFs
XML_NAMEN = ("factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml", "zugferd_invoice.xml")
MAX_XML = 20 * 1024 * 1024


def _parser():
	return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False, remove_comments=True)


def _baum(daten):
	if not daten or len(daten) > MAX_XML:
		return None
	try:
		return etree.fromstring(daten, _parser())
	except (etree.XMLSyntaxError, ValueError):
		return None


def syntax(baum):
	"""'CII', 'UBL' oder None."""
	if baum is None:
		return None
	name = etree.QName(baum).localname
	if name == "CrossIndustryInvoice":
		return "CII"
	if name in ("Invoice", "CreditNote") and "ubl" in (etree.QName(baum).namespace or "").lower():
		return "UBL"
	return None


def xml_aus_pdf(daten):
	"""Die eingebettete Rechnungs-XML eines PDFs (bytes) oder None."""
	if not daten or not daten.startswith(b"%PDF"):
		return None
	try:
		from pypdf import PdfReader

		anhaenge = PdfReader(io.BytesIO(daten)).attachments or {}
	except Exception:
		return None
	kandidaten = sorted(anhaenge, key=lambda n: (n.lower() not in XML_NAMEN, n))
	for name in kandidaten:
		if not name.lower().endswith(".xml"):
			continue
		for inhalt in anhaenge[name] or []:
			if syntax(_baum(inhalt)):
				return inhalt
	return None


def erkennen(name, daten):
	"""(format, xml) einer Datei: ('ZUGFeRD', xml) für ein PDF mit Rechnungs-XML, ('XRechnung', xml) für eine XML-Rechnung,
	sonst (None, None)."""
	n = (name or "").lower()
	if n.endswith(".pdf") or (daten or b"")[:4] == b"%PDF":
		xml = xml_aus_pdf(daten)
		return ("ZUGFeRD", xml) if xml else (None, None)
	if n.endswith(".xml") and syntax(_baum(daten)):
		return "XRechnung", daten
	return None, None


# ----------------------------------------------------------------- Lesen
def _x(el, pfad):
	"""Erster Text unter `pfad` (Elementnamen ohne Namensraum, mit / getrennt)."""
	if el is None:
		return ""
	treffer = el.xpath("./" + "/".join(f"*[local-name()='{t}']" for t in pfad.split("/")))
	return (treffer[0].text or "").strip() if treffer else ""


def _el(el, pfad):
	treffer = el.xpath("./" + "/".join(f"*[local-name()='{t}']" for t in pfad.split("/"))) if el is not None else []
	return treffer[0] if treffer else None


def _alle(el, pfad):
	return el.xpath("./" + "/".join(f"*[local-name()='{t}']" for t in pfad.split("/"))) if el is not None else []


def _zahl(text):
	try:
		return round(float((text or "0").replace(",", ".")), 4)
	except ValueError:
		return 0.0


def _datum(text):
	t = (text or "").strip()
	if re.fullmatch(r"\d{8}", t):
		return f"{t[:4]}-{t[4:6]}-{t[6:]}"
	if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", t):
		return t[:10]
	return None


def _cii(b):
	doc = _el(b, "ExchangedDocument")
	tx = _el(b, "SupplyChainTradeTransaction")
	agr = _el(tx, "ApplicableHeaderTradeAgreement")
	sett = _el(tx, "ApplicableHeaderTradeSettlement")
	seller = _el(agr, "SellerTradeParty")
	summe = _el(sett, "SpecifiedTradeSettlementHeaderMonetarySummation")
	ust = ""
	for reg in _alle(seller, "SpecifiedTaxRegistration/ID"):
		if (reg.get("schemeID") or "").upper() == "VA":
			ust = (reg.text or "").strip()
	steuer = sum(_zahl(t.text) for t in _alle(summe, "TaxTotalAmount") if not t.get("currencyID") or t.get("currencyID") == _x(sett, "InvoiceCurrencyCode"))
	positionen = []
	for z in _alle(tx, "IncludedSupplyChainTradeLineItem"):
		menge_el = _el(z, "SpecifiedLineTradeDelivery/BilledQuantity")
		positionen.append({
			"bezeichnung": _x(z, "SpecifiedTradeProduct/Name"),
			"menge": _zahl(menge_el.text if menge_el is not None else "0"),
			"einheit": menge_el.get("unitCode", "") if menge_el is not None else "",
			"einzelpreis": _zahl(_x(z, "SpecifiedLineTradeAgreement/NetPriceProductTradePrice/ChargeAmount")),
			"betrag": _zahl(_x(z, "SpecifiedLineTradeSettlement/SpecifiedTradeSettlementLineMonetarySummation/LineTotalAmount")),
			"steuersatz": _zahl(_x(z, "SpecifiedLineTradeSettlement/ApplicableTradeTax/RateApplicablePercent")),
		})
	return {
		"rechnungsnr": _x(doc, "ID"),
		"art": "Gutschrift" if _x(doc, "TypeCode") == "381" else "Rechnung",
		"rechnungsdatum": _datum(_x(doc, "IssueDateTime/DateTimeString")),
		"faellig_am": _datum(_x(sett, "SpecifiedTradePaymentTerms/DueDateDateTime/DateTimeString")),
		"lieferant_name": _x(seller, "Name"),
		"lieferant_ust_id": ust,
		"email": _x(seller, "URIUniversalCommunication/URIID") or _x(seller, "DefinedTradeContact/EmailURIUniversalCommunication/URIID"),
		"bestellreferenz": _x(agr, "BuyerOrderReferencedDocument/IssuerAssignedID"),
		"waehrung": _x(sett, "InvoiceCurrencyCode") or "EUR",
		"netto": _zahl(_x(summe, "TaxBasisTotalAmount")),
		"steuer": round(steuer, 2),
		"brutto": _zahl(_x(summe, "GrandTotalAmount")),
		"iban": _x(sett, "SpecifiedTradeSettlementPaymentMeans/PayeePartyCreditorFinancialAccount/IBANID"),
		"positionen": positionen,
	}


def _ubl(b):
	gutschrift = etree.QName(b).localname == "CreditNote"
	party = _el(b, "AccountingSupplierParty/Party")
	summe = _el(b, "LegalMonetaryTotal")
	positionen = []
	for z in _alle(b, "CreditNoteLine" if gutschrift else "InvoiceLine"):
		menge_el = _el(z, "CreditedQuantity" if gutschrift else "InvoicedQuantity")
		positionen.append({
			"bezeichnung": _x(z, "Item/Name"),
			"menge": _zahl(menge_el.text if menge_el is not None else "0"),
			"einheit": menge_el.get("unitCode", "") if menge_el is not None else "",
			"einzelpreis": _zahl(_x(z, "Price/PriceAmount")),
			"betrag": _zahl(_x(z, "LineExtensionAmount")),
			"steuersatz": _zahl(_x(z, "Item/ClassifiedTaxCategory/Percent")),
		})
	steuer = sum(_zahl(t.text) for t in _alle(b, "TaxTotal/TaxAmount"))
	return {
		"rechnungsnr": _x(b, "ID"),
		"art": "Gutschrift" if gutschrift or _x(b, "InvoiceTypeCode") == "381" else "Rechnung",
		"rechnungsdatum": _datum(_x(b, "IssueDate")),
		"faellig_am": _datum(_x(b, "DueDate")) or _datum(_x(b, "PaymentMeans/PaymentDueDate")),
		"lieferant_name": _x(party, "PartyLegalEntity/RegistrationName") or _x(party, "PartyName/Name"),
		"lieferant_ust_id": _x(party, "PartyTaxScheme/CompanyID"),
		"email": _x(party, "Contact/ElectronicMail") or (_x(party, "EndpointID") if "@" in _x(party, "EndpointID") else ""),
		"bestellreferenz": _x(b, "OrderReference/ID"),
		"waehrung": _x(b, "DocumentCurrencyCode") or "EUR",
		"netto": _zahl(_x(summe, "TaxExclusiveAmount")),
		"steuer": round(steuer, 2),
		"brutto": _zahl(_x(summe, "TaxInclusiveAmount")) or _zahl(_x(summe, "PayableAmount")),
		"iban": _x(b, "PaymentMeans/PayeeFinancialAccount/ID"),
		"positionen": positionen,
	}


def lesen(xml):
	"""Die Angaben einer Rechnungs-XML (CII oder UBL) als dict; wirft bei unbekanntem Format."""
	b = _baum(xml)
	art = syntax(b)
	if art == "CII":
		return _cii(b)
	if art == "UBL":
		return _ubl(b)
	frappe.throw(_("Die Datei ist keine E-Rechnung (CII oder UBL)."))


# ----------------------------------------------------------------- Lieferant und Anlegen
def _ust(text):
	return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def lieferant_finden(ust_id="", email="", name="", freemail=()):
	"""Lieferant zur Rechnung: USt-IdNr., dann E-Mail-Adresse (auch weitere Adressen), dann Domain, dann gleicher Name."""
	if _ust(ust_id):
		for l, u in frappe.get_all("Lieferant", filters={"ust_id": ["is", "set"]}, fields=["name", "ust_id"], as_list=True):
			if _ust(u) == _ust(ust_id):
				return l
	from cnc_one.logic.mail import lieferant_zur_adresse

	l = lieferant_zur_adresse(email, freemail) if email else None
	if l:
		return l
	if (name or "").strip():
		r = frappe.db.sql("select name from `tabLieferant` where lower(lieferantenname) = %s limit 1", ((name or "").strip().lower(),))
		if r:
			return r[0][0]
	return None


def doppelt(lieferant, lieferant_name, rechnungsnr):
	"""Gibt es diese Rechnung schon (gleicher Rechnungssteller und gleiche Nummer)?"""
	if not rechnungsnr:
		return None
	filters = {"rechnungsnr": rechnungsnr}
	if lieferant:
		filters["lieferant"] = lieferant
	else:
		filters["lieferant_name"] = lieferant_name
	return frappe.db.get_value("Eingangsrechnung", filters, "name")


def anlegen(format, xml=None, pdf_url="", xml_url="", mail=None, absender="", freemail=()):
	"""Legt eine Eingangsrechnung an (Status Neu). Mit `xml` werden die Angaben gelesen; ohne (PDF-Rechnung) bleibt sie zum
	Ausfüllen. Liefert (doc, hinweis); eine schon vorhandene Rechnung wird nicht doppelt angelegt (doc ist dann None)."""
	daten, hinweise = {}, []
	if xml:
		daten = lesen(xml)
	lieferant = lieferant_finden(daten.get("lieferant_ust_id"), daten.get("email") or absender, daten.get("lieferant_name"), freemail) if daten else (
		lieferant_finden("", absender, "", freemail) if absender else None)
	vorhanden = doppelt(lieferant, daten.get("lieferant_name"), daten.get("rechnungsnr"))
	if vorhanden:
		return None, _("Rechnung {0} gibt es schon ({1}).").format(daten.get("rechnungsnr"), vorhanden)
	if daten and not lieferant:
		hinweise.append(_("Rechnungssteller {0} ist noch kein Lieferant.").format(daten.get("lieferant_name") or "?"))
	if daten:
		summe = round(sum(p["betrag"] for p in daten["positionen"]), 2)
		if daten["positionen"] and abs(summe - daten["netto"]) > 0.02:
			hinweise.append(_("Summe der Positionen ({0}) weicht vom Nettobetrag ({1}) ab, z. B. wegen Zu- oder Abschlägen.").format(summe, daten["netto"]))
		if abs(round(daten["netto"] + daten["steuer"], 2) - daten["brutto"]) > 0.02:
			hinweise.append(_("Netto + Steuer ergibt nicht den Bruttobetrag."))
	doc = frappe.get_doc({
		"doctype": "Eingangsrechnung", "status": "Neu", "format": format, "lieferant": lieferant,
		**{k: daten.get(k) for k in ("lieferant_name", "lieferant_ust_id", "rechnungsnr", "rechnungsdatum", "faellig_am", "art", "netto", "steuer", "brutto", "waehrung", "iban", "bestellreferenz") if daten.get(k) not in (None, "")},
		"lieferant_name": daten.get("lieferant_name") or (frappe.db.get_value("Lieferant", lieferant, "lieferantenname") if lieferant else ""),
		"mail": mail, "pdf_datei": pdf_url, "xml_datei": xml_url, "pruefhinweise": "\n".join(hinweise),
	})
	for p in daten.get("positionen") or []:
		doc.append("positionen", p)
	doc.insert(ignore_permissions=True)
	# die Dateien hängen auch an der Eingangsrechnung (DMS: Art Rechnung, Aufbewahrung wie Buchungsbelege)
	neu = {f: datei_anhaengen(doc, u) for f, u in (("pdf_datei", pdf_url), ("xml_datei", xml_url)) if u}
	if neu:
		doc.db_set(neu, update_modified=False)
	return doc, ""


def datei_anhaengen(doc, url):
	"""Eine vorhandene Datei (z. B. Mail-Anhang) zusätzlich an die Eingangsrechnung hängen; liefert deren Adresse."""
	quelle = frappe.db.get_value("File", {"file_url": url}, "name")
	if not quelle:
		return url
	vorhanden = frappe.db.get_value("File", {"file_url": url, "attached_to_doctype": doc.doctype, "attached_to_name": doc.name}, "file_url")
	if vorhanden:
		return vorhanden
	return frappe.get_doc("File", quelle).create_attachment_copy(doc.doctype, doc.name, ignore_permissions=True).file_url
