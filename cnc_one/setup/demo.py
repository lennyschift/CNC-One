"""Beispieldaten für Entwicklung und Test. Erfundene Firmen, Preise und Sätze, nicht für den Produktivbetrieb.

Aufruf:  bench --site <site> execute cnc_one.setup.demo.stammdaten
Mehrfaches Ausführen legt nichts doppelt an.
"""

import frappe

MASCHINEN = [("Hermle C42", 105), ("Mori NTX2000", 125), ("CTX400", 88), ("Hermle UWF", 98)]

MATERIALIEN = [
	("1.4301 Edelstahl", 6.4), ("1.4404 Edelstahl", 8.1), ("1.4571 Edelstahl", 9.3), ("AlMg3 / EN AW-5754", 5.2),
	("EN AW-7075 Aluminium", 9.8), ("1.0037 Baustahl S235", 1.7), ("1.4305 Automatenstahl", 6.9),
	("CuZn39Pb3 Messing", 9.1), ("POM-C Kunststoff", 7.5),
]

LIEFERANTEN = [
	("Eloxal Beispiel GmbH", "Eloxieren"), ("Härterei Demo Süd", "Härten"),
	("Beschichtung Test KG", "Beschichten"), ("Schleiferei Muster", "Schleifen"),
]

KUNDEN = [
	("Muster Maschinenbau GmbH", "MUM", "40711", ("Industriestraße 12", "72461", "Albstadt"), ("Frau", "Anja", "Beispiel", "a.beispiel@muster-maschinenbau.example")),
	("Beispiel Antriebstechnik AG", "BAT", "88213", ("Am Werk 3", "78727", "Oberndorf"), ("Herr", "Tom", "Probe", "t.probe@beispiel-antriebe.example")),
	("Demo Hydraulik GmbH & Co. KG", "DHY", "1204", ("Kolbenweg 7", "88400", "Biberach"), ("Herr", "Max", "Demo", "m.demo@demo-hydraulik.example")),
	("Test Präzisionsteile GmbH", "TPT", "", ("Feinmechanikerallee 1", "78532", "Tuttlingen"), ("Frau", "Lisa", "Test", "l.test@test-praezision.example")),
]

ARTEN = [
	("Drehen", "Intern"), ("Fräsen", "Intern"), ("Entgraten", "Intern"), ("Messen / Prüfen", "Intern"), ("Verpacken", "Intern"),
	("Oberflächenbehandlung", "Fremd"), ("Härten", "Fremd"), ("Schleifen", "Fremd"), ("Beschichten", "Fremd"), ("Eloxieren", "Fremd"),
]


def _neu(doctype, **werte):
	doc = frappe.get_doc({"doctype": doctype, **werte})
	doc.insert(ignore_permissions=True)
	return doc


def stammdaten():
	for name, satz in MASCHINEN:
		if not frappe.db.exists("Maschine", name):
			_neu("Maschine", maschinenname=name, satz=satz)
	for name, preis in MATERIALIEN:
		if not frappe.db.exists("Material", name):
			_neu("Material", materialname=name, preis_kg=preis)
	for name, leistung in LIEFERANTEN:
		if not frappe.db.exists("Lieferant", name):
			_neu("Lieferant", lieferantenname=name, leistung=leistung)
	for name, typ in ARTEN:
		if not frappe.db.exists("Arbeitsgangart", {"bezeichnung": name}):
			_neu("Arbeitsgangart", bezeichnung=name, typ=typ)
	kunde_ids = {}
	for name, kuerzel, lnr, (strasse, plz, ort), (anrede, vor, nach, mail) in KUNDEN:
		vorhanden = frappe.db.get_value("Kunde", {"kundenname": name}, "name")
		if vorhanden:
			kunde_ids[name] = vorhanden
			continue
		d = _neu(
			"Kunde", kundenname=name, kuerzel=kuerzel, lieferantennummer=lnr,
			adressen=[{"typ": "Rechnung und Lieferung", "strasse": strasse, "plz": plz, "ort": ort, "land": "DE", "standard": 1}],
			kontakte=[{"anrede": anrede, "vorname": vor, "nachname": nach, "email": mail, "ist_rechnungskontakt": 1}],
		)
		kunde_ids[name] = d.name

	def ag(name, typ, **extra):
		return {"ag_id": frappe.generate_hash(length=10), "bezeichnung": name, "typ": typ, **extra}

	vorlagen = [
		("Drehen und Fräsen Standard", None, [
			ag("Drehen", "Intern", maschine="CTX400", satz=88, ruest_min=45, stueck_min=3),
			ag("Fräsen", "Intern", maschine="Hermle C42", satz=105, ruest_min=60, stueck_min=4),
			ag("Entgraten", "Intern", satz=60, stueck_min=1),
			ag("Messen / Prüfen", "Intern", satz=70, stueck_min=0.5),
		]),
		("Oberflächenbehandlung extern", None, [ag("Oberflächenbehandlung", "Fremd", lieferant="Eloxal Beispiel GmbH")]),
		("Muster Maschinenbau: Fräsen und Eloxieren", kunde_ids.get("Muster Maschinenbau GmbH"), [
			ag("Fräsen", "Intern", maschine="Hermle C42", satz=105, ruest_min=60, stueck_min=6),
			ag("Eloxieren", "Fremd", lieferant="Eloxal Beispiel GmbH"),
			ag("Messen / Prüfen", "Intern", satz=70, stueck_min=1),
		]),
	]
	for name, kunde, zeilen in vorlagen:
		if not frappe.db.exists("Arbeitsplan Vorlage", {"vorlagenname": name}):
			_neu("Arbeitsplan Vorlage", vorlagenname=name, kunde=kunde, arbeitsgaenge=zeilen)
	frappe.db.commit()
	return {"kunden": len(kunde_ids)}
