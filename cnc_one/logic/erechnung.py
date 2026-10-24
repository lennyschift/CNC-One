"""E-Rechnung: XML nach EN 16931 im Format UN/CEFACT Cross Industry Invoice (CII), ohne Datenbankzugriff.

Zwei Ausprägungen aus denselben Daten:
- "xrechnung": XRechnung 3.0 (eigenständige XML-Datei, z. B. für Behörden)
- "zugferd":   ZUGFeRD / Factur-X, Profil EN 16931 (XML, das in das PDF/A-3 eingebettet wird)

Eingabe ist ein Dictionary (siehe `api/erechnung.py`, `daten_aus_rechnung`). `fehlende_angaben` nennt, was für die jeweilige
Ausprägung noch fehlt, bevor sie erzeugt werden kann.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from lxml import etree

NS = {
	"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
	"ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
	"udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
	"qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}

LEITFADEN = {
	"xrechnung": "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
	"zugferd": "urn:cen.eu:en16931:2017",
}

PROZESS_XRECHNUNG = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"  # Geschäftsprozess nach Peppol BIS Billing 3.0, Pflicht in XRechnung

LAENDER = {
	"DEUTSCHLAND": "DE", "GERMANY": "DE", "ÖSTERREICH": "AT", "OESTERREICH": "AT", "AUSTRIA": "AT", "SCHWEIZ": "CH", "SWITZERLAND": "CH",
	"FRANKREICH": "FR", "ITALIEN": "IT", "NIEDERLANDE": "NL", "BELGIEN": "BE", "LUXEMBURG": "LU", "POLEN": "PL", "TSCHECHIEN": "CZ",
	"SPANIEN": "ES", "DÄNEMARK": "DK", "DAENEMARK": "DK", "UNGARN": "HU", "SLOWENIEN": "SI", "SCHWEDEN": "SE", "GROSSBRITANNIEN": "GB",
}

EINHEIT_STUECK = "C62"  # UN/ECE Rec. 20: "one", gilt für Stück und Pauschalen


def laendercode(land):
	"""Zweistelliger Ländercode (ISO 3166) aus Eingabe wie 'DE', 'Deutschland', leer = Deutschland. Unbekannt: None."""
	s = (land or "").strip()
	if not s:
		return "DE"
	if len(s) == 2 and s.isalpha():
		return s.upper()
	return LAENDER.get(s.upper())


def _q(wert, stellen=2):
	return Decimal(str(wert or 0)).quantize(Decimal(1).scaleb(-stellen), rounding=ROUND_HALF_UP)


def betrag(wert, stellen=2):
	return f"{_q(wert, stellen):.{stellen}f}"


def _d102(d):
	if isinstance(d, datetime):
		d = d.date()
	if not isinstance(d, date):
		d = datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
	return d.strftime("%Y%m%d")


def fehlende_angaben(d):
	"""Was für welche Ausprägung noch fehlt: { 'zugferd': [...], 'xrechnung': [...] }. `xrechnung` enthält auch die Punkte von `zugferd`."""
	v, k = d["verkaeufer"], d["kaeufer"]
	zug = []
	if not (v.get("name") or "").strip():
		zug.append("Name der Firma")
	if not ((v.get("ust_id") or "").strip() or (v.get("steuernummer") or "").strip()):
		zug.append("USt-IdNr. oder Steuernummer der Firma")
	if not laendercode(v.get("land")):
		zug.append("Land der Firma (z. B. Deutschland)")
	if not (k.get("name") or "").strip():
		zug.append("Name des Kunden")
	if not laendercode(k.get("land")):
		zug.append("Land des Kunden (Ländercode wie DE)")
	if not d["zeilen"]:
		zug.append("Rechnungspositionen")
	xr = list(zug)
	if not (v.get("plz") or "").strip() or not (v.get("ort") or "").strip():
		xr.append("PLZ und Ort der Firma")
	if not (v.get("ansprechpartner") or "").strip():
		xr.append("Ansprechpartner der Firma")
	if not (v.get("telefon") or "").strip():
		xr.append("Telefonnummer der Firma")
	if not (v.get("email") or "").strip():
		xr.append("E-Mail der Firma")
	if not (v.get("iban") or "").strip():
		xr.append("IBAN der Firma")
	if not (k.get("plz") or "").strip() or not (k.get("ort") or "").strip():
		xr.append("PLZ und Ort des Kunden")
	if not (k.get("email") or "").strip():
		xr.append("E-Mail des Rechnungsempfängers (Ansprechpartner beim Kunden)")
	return {"zugferd": zug, "xrechnung": xr}


class _Baum:
	"""Kleine Hilfe zum Aufbau des XML mit Präfixen."""

	@staticmethod
	def neu(eltern, name, text=None, **attribute):
		praefix, lokal = name.split(":")
		el = etree.SubElement(eltern, f"{{{NS[praefix]}}}{lokal}") if eltern is not None else etree.Element(f"{{{NS[praefix]}}}{lokal}", nsmap=NS)
		if text is not None:
			el.text = str(text)
		for k, v in attribute.items():
			el.set(k, str(v))
		return el


def _partei(eltern, name, p, kontakt=False, steuer=True):
	t = _Baum.neu(eltern, name)
	_Baum.neu(t, "ram:Name", p["name"])
	if kontakt and (p.get("ansprechpartner") or p.get("telefon") or p.get("email")):
		c = _Baum.neu(t, "ram:DefinedTradeContact")
		if p.get("ansprechpartner"):
			_Baum.neu(c, "ram:PersonName", p["ansprechpartner"])
		if p.get("telefon"):
			_Baum.neu(_Baum.neu(c, "ram:TelephoneUniversalCommunication"), "ram:CompleteNumber", p["telefon"])
		if p.get("email"):
			_Baum.neu(_Baum.neu(c, "ram:EmailURIUniversalCommunication"), "ram:URIID", p["email"])
	a = _Baum.neu(t, "ram:PostalTradeAddress")
	if p.get("plz"):
		_Baum.neu(a, "ram:PostcodeCode", p["plz"])
	if p.get("strasse"):
		_Baum.neu(a, "ram:LineOne", p["strasse"])
	if p.get("ort"):
		_Baum.neu(a, "ram:CityName", p["ort"])
	_Baum.neu(a, "ram:CountryID", laendercode(p.get("land")))
	if p.get("email"):
		_Baum.neu(_Baum.neu(t, "ram:URIUniversalCommunication"), "ram:URIID", p["email"], schemeID="EM")
	if steuer:
		if p.get("ust_id"):
			_Baum.neu(_Baum.neu(t, "ram:SpecifiedTaxRegistration"), "ram:ID", p["ust_id"], schemeID="VA")
		if p.get("steuernummer") and p.get("steuernummer") != p.get("ust_id"):
			_Baum.neu(_Baum.neu(t, "ram:SpecifiedTaxRegistration"), "ram:ID", p["steuernummer"], schemeID="FC")
	return t


def baue_cii(d, profil):
	"""Erzeugt das CII-XML (bytes, UTF-8) für `profil` 'xrechnung' oder 'zugferd'. Stornorechnungen werden als Gutschrift (Typ 381) mit
	positiven Beträgen und Verweis auf die stornierte Rechnung ausgegeben."""
	storno = d["art"] == "Storno"
	satz = d.get("steuersatz", 19)
	kat = d.get("steuerkategorie", "S")

	def pos(x):
		return abs(x) if storno else x

	wurzel = _Baum.neu(None, "rsm:CrossIndustryInvoice")

	# --- Kontext und Kopf
	ctx = _Baum.neu(wurzel, "rsm:ExchangedDocumentContext")
	if profil == "xrechnung":
		_Baum.neu(_Baum.neu(ctx, "ram:BusinessProcessSpecifiedDocumentContextParameter"), "ram:ID", PROZESS_XRECHNUNG)
	_Baum.neu(_Baum.neu(ctx, "ram:GuidelineSpecifiedDocumentContextParameter"), "ram:ID", LEITFADEN[profil])
	dok = _Baum.neu(wurzel, "rsm:ExchangedDocument")
	_Baum.neu(dok, "ram:ID", d["nummer"])
	_Baum.neu(dok, "ram:TypeCode", "381" if storno else "380")
	_Baum.neu(_Baum.neu(dok, "ram:IssueDateTime"), "udt:DateTimeString", _d102(d["datum"]), format="102")
	if d.get("bemerkung"):
		_Baum.neu(_Baum.neu(dok, "ram:IncludedNote"), "ram:Content", d["bemerkung"])

	handel = _Baum.neu(wurzel, "rsm:SupplyChainTradeTransaction")

	# --- Positionen
	for nr, z in enumerate(d["zeilen"], 1):
		li = _Baum.neu(handel, "ram:IncludedSupplyChainTradeLineItem")
		adl = _Baum.neu(li, "ram:AssociatedDocumentLineDocument")
		_Baum.neu(adl, "ram:LineID", nr)  # fortlaufend ganzzahlig; die Gliederung 1.1 der Rechnung steht nur im PDF
		if z.get("hinweis"):
			_Baum.neu(_Baum.neu(adl, "ram:IncludedNote"), "ram:Content", z["hinweis"])
		prod = _Baum.neu(li, "ram:SpecifiedTradeProduct")
		if z.get("teilenummer"):
			_Baum.neu(prod, "ram:SellerAssignedID", z["teilenummer"])
		_Baum.neu(prod, "ram:Name", z["name"])
		if z.get("zeichnungsnr"):
			_Baum.neu(prod, "ram:Description", f"Zeichnung {z['zeichnungsnr']}")
		agr = _Baum.neu(li, "ram:SpecifiedLineTradeAgreement")
		_Baum.neu(_Baum.neu(agr, "ram:NetPriceProductTradePrice"), "ram:ChargeAmount", betrag(pos(z["einzelpreis"]), 4))
		lief = _Baum.neu(li, "ram:SpecifiedLineTradeDelivery")
		_Baum.neu(lief, "ram:BilledQuantity", betrag(pos(z["menge"]), 4), unitCode=z.get("einheit") or EINHEIT_STUECK)
		abr = _Baum.neu(li, "ram:SpecifiedLineTradeSettlement")
		st = _Baum.neu(abr, "ram:ApplicableTradeTax")
		_Baum.neu(st, "ram:TypeCode", "VAT")
		_Baum.neu(st, "ram:CategoryCode", kat)
		_Baum.neu(st, "ram:RateApplicablePercent", betrag(satz))
		_Baum.neu(_Baum.neu(abr, "ram:SpecifiedTradeSettlementLineMonetarySummation"), "ram:LineTotalAmount", betrag(pos(z["netto"])))

	# --- Vereinbarung (Parteien, Referenzen)
	agr = _Baum.neu(handel, "ram:ApplicableHeaderTradeAgreement")
	_Baum.neu(agr, "ram:BuyerReference", d["kaeufer_referenz"])
	_partei(agr, "ram:SellerTradeParty", d["verkaeufer"], kontakt=True)
	_partei(agr, "ram:BuyerTradeParty", d["kaeufer"])
	if d.get("bestellnr"):
		_Baum.neu(_Baum.neu(agr, "ram:BuyerOrderReferencedDocument"), "ram:IssuerAssignedID", d["bestellnr"])

	# --- Lieferung
	lief = _Baum.neu(handel, "ram:ApplicableHeaderTradeDelivery")
	_Baum.neu(_Baum.neu(_Baum.neu(lief, "ram:ActualDeliverySupplyChainEvent"), "ram:OccurrenceDateTime"), "udt:DateTimeString", _d102(d["leistung_bis"]), format="102")
	if d.get("lieferscheine"):
		_Baum.neu(_Baum.neu(lief, "ram:DespatchAdviceReferencedDocument"), "ram:IssuerAssignedID", ", ".join(d["lieferscheine"]))

	# --- Abrechnung
	abr = _Baum.neu(handel, "ram:ApplicableHeaderTradeSettlement")
	_Baum.neu(abr, "ram:InvoiceCurrencyCode", d.get("waehrung", "EUR"))
	v = d["verkaeufer"]
	if v.get("iban"):
		zm = _Baum.neu(abr, "ram:SpecifiedTradeSettlementPaymentMeans")
		_Baum.neu(zm, "ram:TypeCode", "58")
		_Baum.neu(_Baum.neu(zm, "ram:PayeePartyCreditorFinancialAccount"), "ram:IBANID", v["iban"])
		if v.get("bic"):
			_Baum.neu(_Baum.neu(zm, "ram:PayeeSpecifiedCreditorFinancialInstitution"), "ram:BICID", v["bic"])
	netto, steuer, brutto = pos(d["netto"]), pos(d["steuer"]), pos(d["brutto"])
	st = _Baum.neu(abr, "ram:ApplicableTradeTax")
	_Baum.neu(st, "ram:CalculatedAmount", betrag(steuer))
	_Baum.neu(st, "ram:TypeCode", "VAT")
	_Baum.neu(st, "ram:BasisAmount", betrag(netto))
	_Baum.neu(st, "ram:CategoryCode", kat)
	_Baum.neu(st, "ram:RateApplicablePercent", betrag(satz))
	if d.get("leistung_von") and _d102(d["leistung_von"]) != _d102(d["leistung_bis"]):
		zeitraum = _Baum.neu(abr, "ram:BillingSpecifiedPeriod")
		_Baum.neu(_Baum.neu(zeitraum, "ram:StartDateTime"), "udt:DateTimeString", _d102(d["leistung_von"]), format="102")
		_Baum.neu(_Baum.neu(zeitraum, "ram:EndDateTime"), "udt:DateTimeString", _d102(d["leistung_bis"]), format="102")
	if not storno:
		zt = _Baum.neu(abr, "ram:SpecifiedTradePaymentTerms")
		_Baum.neu(zt, "ram:Description", d.get("zahlungsbedingung") or "")
		_Baum.neu(_Baum.neu(zt, "ram:DueDateDateTime"), "udt:DateTimeString", _d102(d["faellig"]), format="102")
	summe = _Baum.neu(abr, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
	_Baum.neu(summe, "ram:LineTotalAmount", betrag(netto))
	_Baum.neu(summe, "ram:TaxBasisTotalAmount", betrag(netto))
	_Baum.neu(summe, "ram:TaxTotalAmount", betrag(steuer), currencyID=d.get("waehrung", "EUR"))
	_Baum.neu(summe, "ram:GrandTotalAmount", betrag(brutto))
	_Baum.neu(summe, "ram:DuePayableAmount", betrag(brutto))
	if storno and d.get("vorgaenger"):
		ref = _Baum.neu(abr, "ram:InvoiceReferencedDocument")
		_Baum.neu(ref, "ram:IssuerAssignedID", d["vorgaenger"]["nummer"])
		_Baum.neu(_Baum.neu(ref, "ram:FormattedIssueDateTime"), "qdt:DateTimeString", _d102(d["vorgaenger"]["datum"]), format="102")
	return etree.tostring(wurzel, xml_declaration=True, encoding="UTF-8", pretty_print=True)
