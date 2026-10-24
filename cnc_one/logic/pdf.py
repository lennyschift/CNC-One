"""PDF/A-3 aus HTML, optional mit eingebettetem ZUGFeRD/Factur-X-XML (WeasyPrint).

Für ZUGFeRD braucht das PDF drei Dinge: das XML als Anhang (Beziehung "Alternative"), den Dateinamen `factur-x.xml` und in den
XMP-Metadaten die Factur-X-Erweiterung (Dateiname, Dokumenttyp, Version, Profil), samt Beschreibung dieser Erweiterung für PDF/A.
"""

import io

from lxml import etree

NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
NS_FX = "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"
NS_PDFA_EXT = "http://www.aiim.org/pdfa/ns/extension/"
NS_PDFA_SCHEMA = "http://www.aiim.org/pdfa/ns/schema#"
NS_PDFA_PROP = "http://www.aiim.org/pdfa/ns/property#"
PRAEFIXE = {"fx": NS_FX, "pdfaExtension": NS_PDFA_EXT, "pdfaSchema": NS_PDFA_SCHEMA, "pdfaProperty": NS_PDFA_PROP}
FX_DATEINAME ="factur-x.xml"
FX_PROFIL = "EN 16931"

_FX_EIGENSCHAFTEN = (
	("DocumentFileName", "Name der eingebetteten XML-Rechnung"),
	("DocumentType", "Art des Dokuments (INVOICE)"),
	("Version", "Version der Factur-X-Spezifikation"),
	("ConformanceLevel", "Profil der eingebetteten Rechnung"),
)


def _fx_metadaten(rdf):
	"""Hängt die Factur-X-Angaben und ihre PDF/A-Erweiterungsbeschreibung an das rdf:RDF der XMP-Metadaten."""
	def sub(eltern, name, text=None, ns=NS_RDF, **attr):
		# PDF/A verlangt feste Namensraum-Präfixe (fx, pdfaExtension, pdfaSchema, pdfaProperty), lxml würde sonst ns0, ns1 … vergeben
		e = etree.SubElement(eltern, f"{{{ns}}}{name}", nsmap=PRAEFIXE)
		if text is not None:
			e.text = text
		for k, v in attr.items():
			e.set(k, v)
		return e

	beschr = sub(rdf, "Description", **{f"{{{NS_RDF}}}about": ""})
	for name, text in (("DocumentType", "INVOICE"), ("DocumentFileName", FX_DATEINAME), ("Version", "1.0"), ("ConformanceLevel", FX_PROFIL)):
		sub(beschr, name, text, ns=NS_FX)

	ext = sub(rdf, "Description", **{f"{{{NS_RDF}}}about": ""})
	schemas = sub(sub(ext, "schemas", ns=NS_PDFA_EXT), "Bag")
	li = sub(schemas, "li", **{f"{{{NS_RDF}}}parseType": "Resource"})
	sub(li, "schema", "Factur-X PDFA Extension Schema", ns=NS_PDFA_SCHEMA)
	sub(li, "namespaceURI", NS_FX, ns=NS_PDFA_SCHEMA)
	sub(li, "prefix", "fx", ns=NS_PDFA_SCHEMA)
	seq = sub(sub(li, "property", ns=NS_PDFA_SCHEMA), "Seq")
	for name, beschreibung in _FX_EIGENSCHAFTEN:
		p = sub(seq, "li", **{f"{{{NS_RDF}}}parseType": "Resource"})
		sub(p, "name", name, ns=NS_PDFA_PROP)
		sub(p, "valueType", "Text", ns=NS_PDFA_PROP)
		sub(p, "category", "external", ns=NS_PDFA_PROP)
		sub(p, "description", beschreibung, ns=NS_PDFA_PROP)


def _finisher(document, pdf):
	"""Ergänzt die XMP-Metadaten, die WeasyPrint für PDF/A schreibt, um die Factur-X-Erweiterung."""
	ref = pdf.catalog["Metadata"]  # b"14 0 R"
	obj = pdf.objects[int(ref.split()[0])]
	roh = b"".join(obj.stream) if isinstance(obj.stream, list) else obj.stream
	kopf, rest = roh.split(b"<x:xmpmeta", 1)
	xml, fuss = rest.split(b"</x:xmpmeta>", 1)
	baum = etree.fromstring(b"<x:xmpmeta" + xml + b"</x:xmpmeta>")
	rdf = baum.find(f"{{{NS_RDF}}}RDF")
	_fx_metadaten(rdf)
	neu = etree.tostring(baum, encoding="UTF-8")
	obj.stream = [kopf + neu + fuss]


def pdf_a3(html, xml=None, titel="", autor=""):
	"""Rendert `html` als PDF/A-3b (bytes). Mit `xml` (bytes) wird es ein ZUGFeRD-/Factur-X-PDF mit eingebetteter `factur-x.xml`."""
	from weasyprint import HTML, Attachment

	anhaenge = []
	if xml:
		anhaenge.append(Attachment(file_obj=io.BytesIO(xml), name=FX_DATEINAME, description="Factur-X Rechnungsdaten (EN 16931)", relationship="Alternative"))
	dokument = HTML(string=html)
	optionen = {"pdf_variant": "pdf/a-3b", "attachments": anhaenge}
	if xml:
		optionen["finisher"] = _finisher
	return dokument.write_pdf(**optionen)
