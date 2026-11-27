"""Erzeugt Frappe-Doctypes (JSON + Controller) aus einer kurzen Beschreibung.

Aufruf:  python gen_doctypes.py <Zielordner der App, z. B. .../cnc_one/cnc_one>
Die erzeugten Dateien werden ins Repo übernommen. Controller mit eigener Logik werden NICHT überschrieben.
"""
import json
import os
import re
import sys

MODUL = "CNC One"
APP = "cnc_one"
STAMP = "2026-10-18 09:00:00.000000"


def scrub(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("_")


def klasse(name):
    return "".join(w.capitalize() for w in re.split(r"[^A-Za-z0-9]+", name) if w)


# ---------------------------------------------------------------- Feldkürzel
def F(fieldname, fieldtype, label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label or fieldname.replace("_", " ").capitalize()}
    d.update(kw)
    return d


def Data(n, label=None, **kw): return F(n, "Data", label, **kw)
def Text(n, label=None, **kw): return F(n, "Small Text", label, **kw)
def Link(n, to, label=None, **kw): return F(n, "Link", label, options=to, **kw)
def Select(n, optionen, label=None, **kw): return F(n, "Select", label, options="\n".join(optionen), **kw)
def Check(n, label=None, **kw): return F(n, "Check", label, **kw)
def Money(n, label=None, **kw): return F(n, "Currency", label, precision="2", **kw)
def Num(n, label=None, **kw): return F(n, "Float", label, **kw)
def Int(n, label=None, **kw): return F(n, "Int", label, **kw)
def Date(n, label=None, **kw): return F(n, "Date", label, **kw)
def Table(n, to, label=None, **kw): return F(n, "Table", label, options=to, **kw)
def Section(n, label=None, **kw): return F(n, "Section Break", label, **kw)
def Json(n, label=None, **kw): return F(n, "JSON", label, **kw)
def LongText(n, label=None, **kw): return F(n, "Long Text", label, **kw)


# ---------------------------------------------------------------- Berechtigungen
ALLE = ("create", "delete", "read", "write", "export", "print", "report", "email", "share")


def recht(rolle, *rechte):
    return {"role": rolle, **{r: 1 for r in rechte}}


def stamm_rechte(schreiben=("CNC Admin",)):
    out = [recht("System Manager", *ALLE), recht("CNC Admin", *ALLE)]
    for r in schreiben:
        if r != "CNC Admin":
            out.append(recht(r, "create", "read", "write", "share"))
    for r in ("CNC Vertrieb", "CNC Fertigung", "CNC Buchhaltung"):
        if r not in schreiben:
            out.append(recht(r, "read"))
    return out


ROH_FORMEN = ["Rund", "Vierkant", "Flach", "Sechskant", "Rohr", "Platte"]


# ---------------------------------------------------------------- Beschreibung der Doctypes
DOCTYPES = [
    # ---- Child-Tabellen
    dict(name="Arbeitsgang Plan", istable=1, fields=[
        Data("ag_id", "Id", read_only=1, description="Stabile Kennung aus der Oberfläche"),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Select("typ", ["Intern", "Fremd"], "Art", default="Intern", in_list_view=1),
        Link("maschine", "Maschine", "Maschine", in_list_view=1),
        Money("satz", "Satz (€/h)"),
        Num("ruest_min", "Rüstzeit (min)"),
        Num("stueck_min", "Stückzeit (min)"),
        Check("ruest_direkt", "Rüstkosten direkt in €", description="statt Rüstzeit × Satz"),
        Money("ruest_euro", "Rüstkosten (€)"),
        Check("stueck_direkt", "Stückkosten direkt in €", description="statt Stückzeit × Satz"),
        Money("stueck_euro", "Stückkosten (€ je Stück)"),
        Link("lieferant", "Lieferant", "Lieferant"),
        Money("fremd_pro_stk", "Fremdvergabe je Stück"),
        Money("fremd_einmal", "Fremdvergabe einmalig"),
        Data("anfrage", "Anfrage, aus der der Preis stammt"),
        Check("serie", "Bringt die Seriennummer an", read_only=1, description="ergibt sich aus der Arbeitsgangart Seriennummern"),
    ]),
    dict(name="Kunde Adresse", istable=1, fields=[
        Select("typ", ["Rechnung und Lieferung", "Rechnung", "Lieferung"], "Art", default="Rechnung und Lieferung", in_list_view=1),
        Data("strasse", "Straße und Nummer", in_list_view=1),
        Data("plz", "PLZ", in_list_view=1),
        Data("ort", "Ort", in_list_view=1),
        Data("land", "Land (ISO-2)", default="DE"),
        Check("standard", "Standard"),
    ]),
    dict(name="Kunde Kontakt", istable=1, fields=[
        Select("anrede", ["", "Herr", "Frau"], "Anrede"),
        Data("vorname", "Vorname", in_list_view=1),
        Data("nachname", "Nachname", in_list_view=1, reqd=1),
        Data("email", "E-Mail", options="Email", in_list_view=1),
        Data("telefon", "Telefon", description="Erste Nummer der Liste, für Anzeigen und E-Rechnung"),
        Json("telefonnummern", "Telefonnummern", description="Liste [{art, nummer}], z. B. Arbeit, Mobil"),
        Check("ist_rechnungskontakt", "Rechnungskontakt"),
    ]),
    dict(name="Lieferant Kontakt", istable=1, fields=[
        Select("anrede", ["", "Herr", "Frau"], "Anrede"),
        Data("vorname", "Vorname", in_list_view=1),
        Data("nachname", "Nachname", in_list_view=1, reqd=1),
        Data("funktion", "Funktion", in_list_view=1, description="z. B. Verkauf Innendienst, Qualität"),
        Data("email", "E-Mail", options="Email", in_list_view=1),
        Data("telefon", "Telefon"),
        Data("mobil", "Mobil"),
        Check("anfragen", "Bekommt Anfragen", description="Lieferantenanfragen gehen an diese Adresse (sonst an die E-Mail des Lieferanten)"),
    ]),
    # ---- Stammdaten
    dict(name="Maschine", autoname="field:maschinenname", title="maschinenname", rechte=stamm_rechte(), icon="cog", fields=[
        Data("maschinenname", "Maschine", reqd=1, unique=1, in_list_view=1),
        Money("satz", "Stundensatz (€/h)", reqd=1, in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Text("arbeitsgaenge", "Arbeitsgänge", description="Arbeitsgangarten, die die Maschine kann, eine je Zeile; leer = alle internen"),
        Check("automation", "Mit Automation", description="z. B. Palettenwechsler oder Roboter"),
        Num("stunden_tag", "Verfügbare Stunden je Arbeitstag", default="8", description="Für die Auslastung; mit Automation auch mehr als eine Schicht"),
        Text("bemerkung", "Bemerkung"),
    ]),
    dict(name="Material", autoname="field:materialname", title="materialname", rechte=stamm_rechte(), icon="layers", fields=[
        Data("materialname", "Werkstoff", reqd=1, unique=1, in_list_view=1),
        Money("preis_kg", "Preis (€/kg)", in_list_view=1),
        Num("dichte", "Dichte (kg/dm³)"),
        Select("iso_gruppe", ["", "P", "M", "K", "N", "S", "H"], "ISO-Gruppe (Zerspanung)", description="P Stahl, M rostfreier Stahl, K Guss, N NE-Metalle, S Superlegierungen/Titan, H harte Werkstoffe; leer = aus dem Namen abgeleitet"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Text("schreibweisen", "Schreibweisen auf Zeichnungen", description="Eine je Zeile, z. B. X5CrNi18-10 für 1.4301; wird beim Anlernen in der Workbench ergänzt"),
        Data("kurzname", "Kurzname", description="z. B. AlZn5,5MgCu oder X5CrNi18-10"),
        Text("zustaende", "Zustände", description="Lieferzustände dieses Werkstoffs (Werkstoffzustand), einer je Zeile, z. B. T651"),
        Text("formen", "Formen", description="Lieferformen, eine je Zeile (Rund, Vierkant, Flach, Sechskant, Rohr, Platte); leer = alle"),
    ]),
    dict(name="Werkstoffzustand", autoname="field:code", title="code", rechte=stamm_rechte(("CNC Vertrieb",)), icon="flask-conical", fields=[
        Data("code", "Zustand", reqd=1, unique=1, in_list_view=1, description="z. B. T651, +QT, +AT"),
        Data("beschreibung", "Beschreibung", in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Rohmaterial Ausfuehrung", autoname="hash", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb",)), icon="layers", fields=[
        Data("bezeichnung", "Ausführung", reqd=1, in_list_view=1, description="z. B. gezogen h9, gepresst, gewalzt feingefräst"),
        Select("form", ROH_FORMEN, "Form", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("iso_gruppen", "Nur für ISO-Gruppen", in_list_view=1, description="z. B. N oder P M; leer = alle"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Rohmaterial Abmessung", autoname="hash", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb",)), icon="ruler", fields=[
        Select("form", ROH_FORMEN, "Form", reqd=1, in_list_view=1, in_standard_filter=1),
        Num("mass1", "Maß 1 (mm)", reqd=1, description="Rund/Rohr: Ø außen, Vierkant: Kante, Flach: Breite, Sechskant: SW, Platte: Dicke"),
        Num("mass2", "Maß 2 (mm)", description="Flach: Höhe, Rohr: Wandstärke"),
        Data("bezeichnung", "Abmessung", read_only=1, in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Materialanforderung", autoname="field:bezeichnung", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb",)), icon="shield-check", fields=[
        Data("bezeichnung", "Anforderung", reqd=1, unique=1, in_list_view=1, description="z. B. Ultraschallgeprüft, RoHS/REACH"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Rohmaterialcharge", autoname="RC-.YY.-.####", title="chargennr", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="warehouse", extra={"search_fields": "chargennr,material,lieferant"}, fields=[
        Data("chargennr", "Charge / Schmelze des Lieferanten", in_list_view=1),
        Link("material", "Material", "Werkstoff", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("zustand", "Zustand", in_list_view=1),
        Select("form", ROH_FORMEN, "Form", reqd=1, in_list_view=1),
        Link("abmessung", "Rohmaterial Abmessung", "Abmessung", reqd=1),
        Data("abmessung_text", "Abmessung (Text)", read_only=1, in_list_view=1),
        Data("ausfuehrung", "Ausführung"),
        Link("lieferant", "Lieferant", "Lieferant", in_standard_filter=1),
        Date("eingang", "Wareneingang", in_list_view=1),
        Num("laenge", "Länge (mm)", description="Stangen: Länge je Stange; Platte: Länge"),
        Num("breite", "Breite (mm)", description="nur Platte"),
        Int("stueck", "Stangen / Stück", default="1"),
        Select("zeugnis", ["", "2.2", "3.1", "3.2"], "Werkszeugnis (EN 10204)", in_list_view=1),
        Text("pruefungen", "Bestätigte Anforderungen", description="Materialanforderung, eine je Zeile"),
        F("zeugnis_datei", "Attach", "Zeugnis (PDF)"),
        Data("lagerplatz", "Lagerplatz"),
        Select("status", ["Vorrätig", "Aufgebraucht"], "Status", default="Vorrätig", in_list_view=1, in_standard_filter=1),
        Text("bemerkung", "Bemerkung"),
    ]),
    dict(name="Lieferant", autoname="field:lieferantenname", title="lieferantenname", rechte=stamm_rechte(("CNC Vertrieb",)), icon="truck", fields=[
        Data("lieferantenname", "Lieferant", reqd=1, unique=1, in_list_view=1),
        Data("leistung", "Leistung", in_list_view=1, description="z. B. Eloxieren, Härten"),
        Data("email", "E-Mail", options="Email"),
        Text("weitere_emails", "Weitere E-Mail-Adressen", description="Eine je Zeile, z. B. rechnung@… oder Ansprechpartner; Mails von dort kommen in den Posteingang"),
        Data("telefon", "Telefon"),
        Text("adresse", "Adresse"),
        Data("ust_id", "USt-IdNr.", description="Ordnet E-Rechnungen dem Lieferanten zu"),
        Json("angebot_vorlage", "Vorlage für Angebots-PDFs", description="Angelernt beim Einlesen: Spalten der Tabelle, Preiseinheit"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Table("kontakte", "Lieferant Kontakt", "Ansprechpartner"),
    ]),
    dict(name="Arbeitsgangart", autoname="AA-.####", title="bezeichnung", rechte=stamm_rechte(), icon="list-tree", fields=[
        Data("bezeichnung", "Bezeichnung", reqd=1, in_list_view=1),
        Select("typ", ["Intern", "Fremd"], "Standard", default="Intern", reqd=1, in_list_view=1, description="Intern oder extern (Fremdvergabe) als Vorgabe; im Arbeitsplan je Arbeitsgang änderbar"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Check("serie", "Seriennummern-Arbeitsgang", read_only=1, description="Systemart: bringt die Seriennummer an, lässt sich nicht löschen oder umbenennen"),
    ]),
    dict(name="Kunde", autoname="K-.####", title="kundenname", rechte=stamm_rechte(("CNC Vertrieb",)), icon="users", fields=[
        Data("kundenname", "Kunde", reqd=1, in_list_view=1),
        Data("kuerzel", "Kürzel", in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Json("telefonnummern", "Telefonnummern der Firma", description="Liste [{art, nummer}], z. B. Zentrale, Fax"),
        Section("sb_steuer", "Steuer und Rechnung"),
        Data("ust_id", "USt-IdNr."),
        Data("steuernummer", "Steuernummer"),
        Data("zahlungsbedingung", "Zahlungsbedingung"),
        Data("leitweg_id", "Leitweg-ID / Käuferreferenz"),
        Data("lieferantennummer", "Lieferantennummer beim Kunden"),
        Int("zahlungsziel_tage", "Zahlungsziel (Tage)", description="0 = Standard aus den Firmendaten"),
        Section("sb_material", "Material-Vorgaben"),
        Select("material_zeugnis", ["", "2.2", "3.1", "3.2"], "Fordert Werkszeugnis", description="Wird bei jedem Bauteil dieses Kunden als Mindestanforderung gesetzt"),
        Text("material_pruefungen", "Fordert immer", description="Materialanforderungen, eine je Zeile, z. B. Ultraschallgeprüft"),
        Section("sb_adressen", "Adressen und Kontakte"),
        Table("adressen", "Kunde Adresse", "Adressen"),
        Table("kontakte", "Kunde Kontakt", "Kontakte"),
        Section("sb_zeichnung", "Zeichnungen"),
        Json("zeichnungsvorlage", "Zeichnungsvorlage", read_only=1, description="Angelernte Regeln, wo auf den Zeichnungen dieses Kunden Teilenummer, Werkstoff usw. stehen"),
        Json("bestellvorlage", "Bestellvorlage (PDF)", read_only=1, description="Angelernte Spalten und Kopfangaben der Bestell-PDFs dieses Kunden"),
        Json("tabellenvorlage", "Tabellenvorlage (Mail)", read_only=1, description="Angelernte Spalten der Anfrage-Tabellen in Mails: je Kontakt und als Standard des Kunden"),
    ]),
    dict(name="Arbeitsplan Vorlage", autoname="VL-.####", title="vorlagenname", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="workflow", fields=[
        Data("vorlagenname", "Name der Vorlage", reqd=1, in_list_view=1),
        Link("kunde", "Kunde", "Nur für Kunde", in_list_view=1, description="leer = für alle Kunden"),
        Table("arbeitsgaenge", "Arbeitsgang Plan", "Arbeitsgänge"),
    ]),
]

DOCTYPES += [
    dict(name="Bauteil Revision", istable=1, fields=[
        Data("revision", "Revision", in_list_view=1),
        F("zeichnung", "Attach", "Zeichnung (PDF)", in_list_view=1),
        F("step_datei", "Attach", "STEP-Modell", in_list_view=1),
        F("vorschaubild", "Attach Image", "Vorschaubild"),
        Data("angebot", "Übernommen mit Angebot", read_only=1, in_list_view=1),
        F("datum", "Datetime", "Übernommen am", read_only=1),
    ]),
    dict(name="Bauteil", autoname="BT-.#####", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="package", fields=[
        Link("kunde", "Kunde", "Kunde", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("teilenummer", "Teilenummer", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer"),
        Data("revision", "Revision"),
        Link("material", "Material", "Werkstoff"),
        Select("status", ["Aktiv", "Gesperrt"], "Status", default="Aktiv", in_list_view=1),
        Text("notiz_intern", "Interne Notiz", description="Aus der Workbench; steht nicht auf Belegen"),
        Check("frueher_gefertigt", "Schon gefertigt (vor CNC One)", description="Von Hand: wurde schon einmal ohne CNC One gefertigt; Aufträge in CNC One zeigt die Historie"),
        Data("frueher_notiz", "Früher gefertigt: Hinweis", description="z. B. 2022, alter Auftrag 4711"),
        Section("sb_serie", "Seriennummern"),
        Check("seriennummern", "Seriennummern führen", description="Die Nummern nennt der Kunde je Auftrag, sie sind fortlaufend"),
        Int("serien_stellen", "Stellen der Seriennummer", default="4", description="Seriennummern sind immer so lang, mit führenden Nullen (0001)"),
        Int("letzte_seriennummer", "Letzte vergebene Seriennummer", description="Wird beim Anlegen eines Auftrags fortgeschrieben"),
        Section("sb_dateien", "Dateien"),
        F("vorschaubild", "Attach Image", "Vorschaubild", description="entsteht aus dem STEP-Modell"),
        F("step_datei", "Attach", "STEP-Modell"),
        F("zeichnung", "Attach", "Zeichnung (PDF)"),
        Table("revisionen", "Bauteil Revision", "Revisionen und Dateien", description="Jede Revision mit ihren Dateien. Eine neuere Datei derselben Revision steht darunter, die ältere bleibt sichtbar."),
        Section("sb_plan", "Arbeitsplan"),
        Table("arbeitsplan", "Arbeitsgang Plan", "Arbeitsgänge"),
        Section("sb_familie", "Teilefamilie und Ähnlichkeit"),
        Link("teilefamilie", "Teilefamilie", "Teilefamilie", in_standard_filter=1, description="Varianten eines Teils, z. B. mehrere Teile auf einer Zeichnung; jedes bleibt einzeln bestellbar"),
        Data("variante", "Variante", description="Was diese Variante von den anderen der Familie unterscheidet, z. B. Gewindelänge 16"),
        Json("fingerabdruck", "Geometrie-Fingerabdruck", read_only=1, description="Aus dem STEP-Modell: Maße, Volumen, Oberfläche, Formverteilung (für ähnliche Bauteile)"),
    ]),
    dict(name="Teilefamilie", autoname="TF-.####", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="network", extra={"search_fields": "bezeichnung,merkmal,zeichnungsnr"}, fields=[
        Data("bezeichnung", "Bezeichnung", reqd=1, in_list_view=1, description="z. B. Gewindebolzen M8 oder Zeichnung 4711"),
        Data("merkmal", "Unterschied der Varianten", in_list_view=1, description="z. B. Gewindelänge, Bohrungsbild"),
        Data("zeichnungsnr", "Gemeinsame Zeichnung"),
        Link("kunde", "Kunde", "Kunde", in_list_view=1, in_standard_filter=1),
        Text("notiz", "Notiz"),
    ]),
    # ---- Zeichnungen schwärzen (Kundendaten entfernen, bevor eine Zeichnung an Partner oder in die Fertigung geht)
    dict(name="Schwaerzregelsatz", autoname="field:bezeichnung", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb",)), icon="eraser", fields=[
        Data("bezeichnung", "Bezeichnung", reqd=1, unique=1, in_list_view=1),
        Link("kunde", "Kunde", "Kunde", in_list_view=1, unique=1, description="Leer = Standard für alle Kunden"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Json("regeln", "Regeln", description="Stichwörter, Kopfzeilen, Änderungstabelle, Beschriftungen, E-Mail/Telefon, Logos (Format lib/schwaerzen/rules.ts)"),
    ]),
    dict(name="Schwaerzung", autoname="SW-.#####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="eraser", extra={"search_fields": "bauteil,original_name"}, fields=[
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1, in_standard_filter=1),
        Data("revision", "Revision"),
        Link("kunde", "Kunde", "Kunde", in_standard_filter=1),
        Select("status", ["Ungeprüft", "Freigegeben", "Verworfen"], "Status", default="Ungeprüft", read_only=1, in_list_view=1, in_standard_filter=1),
        Check("automatisch", "Automatisch erstellt", read_only=1),
        Section("sb_original", "Original"),
        Data("original_url", "Original (Datei)", read_only=1),
        Data("original_name", "Dateiname des Originals", read_only=1),
        Data("original_sha", "SHA-256 des Originals", read_only=1),
        Section("sb_ergebnis", "Geschwärzte Fassung"),
        Data("ergebnis_url", "Geschwärzte Datei", read_only=1),
        Data("ergebnis_sha", "SHA-256 der geschwärzten Datei", read_only=1),
        Link("regelsatz", "Schwaerzregelsatz", "Regelsatz", read_only=1),
        Int("seiten", "Seiten", read_only=1),
        Int("bereiche_anzahl", "Bereiche", read_only=1),
        Check("pruefung_bestanden", "Prüfung bestanden", read_only=1, description="Automatische Prüfung im Browser und auf dem Server"),
        Json("bereiche", "Bereiche", read_only=1, description="Geschwärzte Bereiche (Seite, Lage 0…1, Art) zum erneuten Bearbeiten"),
        Json("protokoll", "Prüfprotokoll", read_only=1, description="Ohne Inhalte: nur Kennzahlen und Prüfergebnisse"),
        Section("sb_freigabe", "Gegenprüfung"),
        Link("geprueft_von", "User", "Geprüft von", read_only=1),
        F("geprueft_am", "Datetime", "Geprüft am", read_only=1),
    ]),
    dict(name="Angebotsposition", istable=1, fields=[
        Data("position_key", "Schlüssel", read_only=1, description="Kennung der Position aus der Workbench"),
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1),
        Check("bauteil_neu", "Bauteil mit diesem Angebot neu angelegt", read_only=1),
        Data("teilenummer", "Teilenummer", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", read_only=1, in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer", read_only=1),
        Data("revision", "Revision", read_only=1),
        Data("material", "Werkstoff", read_only=1),
        Int("menge", "Menge", read_only=1, in_list_view=1),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Json("kalkulation", "Kalkulation (Eingaben)"),
        Json("ergebnis", "Ergebnis (vom Server berechnet)", read_only=1),
    ]),
    dict(name="Angebot", autoname="ANG-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="file-text", extra={"search_fields": "kunde_name,anfrage_nr,projekt"}, fields=[
        Link("kunde", "Kunde", "Kunde", in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1, in_list_view=1),
        Select("status", ["Entwurf", "Gesendet", "Bestellt", "Abgelehnt", "Ersetzt"], "Status", default="Entwurf", read_only=1, in_list_view=1, in_standard_filter=1),
        Check("mit_bildern", "Bauteilbilder im PDF", default="1", description="Vorschaubild des Bauteils (aus dem 3D-Modell) neben jeder Position"),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Section("sb_fassung", "Fassung"),
        Link("ursprung", "Angebot", "Ursprüngliches Angebot", read_only=1, description="Erste Fassung; jede Überarbeitung bekommt dessen Nummer mit -1, -2 …"),
        Link("vorgaenger", "Angebot", "Ersetzt Fassung", read_only=1),
        Int("fassung", "Fassung", read_only=1, description="0 = ursprüngliches Angebot"),
        Link("ersetzt_durch", "Angebot", "Ersetzt durch", read_only=1),
        Text("aenderungsgrund", "Grund der Überarbeitung", description="intern, z. B. Position entfällt, Preis nachverhandelt"),
        Section("sb_kopf", "Angaben"),
        Data("anfrage_nr", "Anfrage-Nr. des Kunden"),
        Data("projekt", "Projekt", in_list_view=1, in_standard_filter=1, description="Interner Name zum Wiedererkennen, steht nicht auf den Belegen"),
        Data("kontakt_name", "Ansprechpartner", description="Einkäufer beim Kunden (z. Hd. im Angebot)"),
        Data("kontakt_email", "E-Mail des Ansprechpartners"),
        Int("gueltig_wochen", "Gültig (Wochen)", default="4"),
        Data("lieferzeit", "Lieferzeit", default="Nach Absprache"),
        Check("material_drucken", "Werkstoff auf dem Angebot", description="Werkstoff je Position im Angebots-PDF nennen"),
        Json("bestellung", "Aus Bestellung", description="Workbench aus einer Bestellung des Kunden: {nr, datum, datei}; Status „Bestellt“ = Auftrag daraus angelegt, nie an den Kunden gesendet"),
        F("versandt_am", "Datetime", "Gesendet am", read_only=1),
        Section("sb_pos", "Positionen"),
        Table("positionen", "Angebotsposition", "Positionen"),
    ]),
]


# ---- Aufträge und Fertigung
DOCTYPES += [
    dict(name="Auftragsposition", istable=1, fields=[
        Data("position_key", "Schlüssel", read_only=1),
        Link("angebot", "Angebot", "Angebot", read_only=1, description="Angebot, aus dem die Position stammt (auch ein früheres bei Wiederholbestellungen)"),
        Data("angebot_position_key", "Position im Angebot", read_only=1),
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1),
        Data("teilenummer", "Teilenummer", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", read_only=1, in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer", read_only=1),
        Data("revision", "Revision", read_only=1, description="Revision der Zeichnung, die bestellt wurde"),
        Data("material", "Werkstoff", read_only=1),
        Int("menge", "Bestellte Menge", in_list_view=1),
        Money("einzelpreis", "Stückpreis", in_list_view=1),
        Int("staffel_menge", "Gewählte Staffel"),
        Date("liefertermin", "Liefertermin", in_list_view=1),
        Money("summe", "Summe Position", read_only=1),
        Json("arbeitsplan", "Arbeitsplan zum Zeitpunkt der Bestellung"),
        Int("serien_von", "Seriennummer von"),
        Int("serien_bis", "Seriennummer bis"),
        Int("serien_stellen", "Stellen der Seriennummer"),
        Data("bestellposition", "Position in der Bestellung des Kunden"),
        Money("bestellpreis", "Stückpreis laut Bestellung"),
        Json("bestellangaben", "Angaben laut Bestellung", description="Alles, was in der Bestellung des Kunden zur Position steht (aus dem PDF gelesen)"),
        Select("preisform", ["Angebot", "Bestellung"], "Preisform", default="Angebot", description="Angebot: Stückpreis und Kosten wie angeboten; Bestellung: alles im Stückpreis der Bestellung"),
        Check("entfallen", "Entfallen", read_only=1, description="Durch eine Auftragsänderung gestrichen (Menge 0)"),
        Int("menge_urspruenglich", "Ursprünglich bestellte Menge", read_only=1),
    ]),
    dict(name="Auftragsaenderung", istable=1, fields=[
        Int("nr", "Änderung", in_list_view=1),
        F("datum", "Datetime", "Datum", in_list_view=1),
        Data("benutzer", "Von", in_list_view=1),
        Text("grund", "Grund", in_list_view=1),
        LongText("details", "Was geändert wurde", description="Eine Änderung je Zeile"),
    ]),
    dict(name="Auftragskosten", istable=1, fields=[
        Data("position_key", "Position", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Money("betrag", "Betrag", in_list_view=1),
        Data("abgerechnet_in", "Abgerechnet in Rechnung", read_only=1, description="Sonderkosten werden in der ersten Rechnung vollständig abgerechnet"),
    ]),
    dict(name="Auftrag", autoname="AUF-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="clipboard-list", extra={"search_fields": "kunde_name,kundenbestellnr,projekt"}, fields=[
        Link("kunde", "Kunde", "Kunde", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1, in_list_view=1),
        Link("angebot", "Angebot", "Angebot", in_list_view=1, in_standard_filter=1, description="Leer bei Aufträgen direkt aus einer Bestellung"),
        Check("mit_bildern", "Bauteilbilder im PDF", default="1", description="Vorschaubild des Bauteils (aus dem 3D-Modell) neben jeder Position"),
        Select("status", ["Offen", "In Fertigung", "Fertig", "Storniert"], "Status", default="Offen", read_only=1, in_list_view=1, in_standard_filter=1),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Section("sb_kopf", "Angaben"),
        Data("kundenbestellnr", "Bestellnummer des Kunden"),
        Date("bestelldatum", "Bestelldatum"),
        Data("bestellung_datei", "Bestellung des Kunden (PDF)", read_only=1),
        Data("projekt", "Projekt", in_list_view=1, in_standard_filter=1, description="Interner Name zum Wiedererkennen, steht nicht auf den Belegen"),
        Data("kontakt_name", "Ansprechpartner", description="Einkäufer beim Kunden (z. Hd. im Angebot)"),
        Data("kontakt_email", "E-Mail des Ansprechpartners"),
        Section("sb_pos", "Positionen"),
        Table("positionen", "Auftragsposition", "Positionen"),
        Table("kosten", "Auftragskosten", "Kosten (Sonderkosten je Position)"),
        Section("sb_ab", "Auftragsbestätigung"),
        F("ab_gesendet_am", "Datetime", "Auftragsbestätigung gesendet am", read_only=1),
        Data("ab_gesendet_an", "Auftragsbestätigung gesendet an", read_only=1),
        Int("ab_aenderung", "AB gesendet zu Änderung", read_only=1, description="Stand der zuletzt gesendeten Auftragsbestätigung (0 = ursprünglicher Auftrag)"),
        Section("sb_aenderungen", "Änderungen"),
        Int("aenderung_nr", "Letzte Änderung", read_only=1),
        Table("aenderungen", "Auftragsaenderung", "Änderungen"),
    ]),
    dict(name="Fertigungsarbeitsgang", istable=1, fields=[
        Data("ag_id", "Id", read_only=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Select("typ", ["Intern", "Fremd"], "Art", default="Intern", in_list_view=1),
        Link("maschine", "Maschine", "Maschine", in_list_view=1),
        Money("satz", "Satz (€/h)"),
        Num("ruest_min", "Rüstzeit (min)"),
        Num("stueck_min", "Stückzeit (min)"),
        Check("ruest_direkt", "Rüstkosten direkt in €", description="statt Rüstzeit × Satz"),
        Money("ruest_euro", "Rüstkosten (€)"),
        Check("stueck_direkt", "Stückkosten direkt in €", description="statt Stückzeit × Satz"),
        Money("stueck_euro", "Stückkosten (€ je Stück)"),
        Select("status", ["Offen", "Läuft", "Fertig"], "Status", default="Offen", in_list_view=1),
        Int("gebucht", "Gebucht", in_list_view=1),
        Link("lieferant", "Lieferant", "Lieferant"),
        Money("fremd_pro_stk", "Fremdvergabe je Stück"),
        Money("fremd_einmal", "Fremdvergabe einmalig"),
        Data("anfrage", "Anfrage"),
        Data("bestellung", "Bestellung"),
        Check("serie", "Bringt die Seriennummer an", read_only=1),
        Date("geplant_am", "Geplant am", description="Tag, an dem der Arbeitsgang laufen soll (Planung)"),
        Num("ist_ruest_min", "Ist-Rüstzeit (min)"),
        Num("ist_bearb_min", "Ist-Bearbeitungszeit (min)", description="Gesamte Bearbeitungszeit für die gebuchte Menge"),
        Data("ist_von", "Zeiten gemeldet von", read_only=1),
        F("ist_am", "Datetime", "Zeiten gemeldet am", read_only=1),
    ]),
    dict(name="Fertigungssendung", istable=1, fields=[
        Data("ag_id", "Arbeitsgang", read_only=1, in_list_view=1),
        Int("menge", "Menge", in_list_view=1),
        Date("datum_weg", "Ware weg am", in_list_view=1),
        Date("datum_zurueck", "Ware zurück am", in_list_view=1),
        Check("abgehakt", "Mit abgehakt"),
    ]),
    dict(name="Fertigungsbuchung", istable=1, fields=[
        F("zeit", "Datetime", "Zeitpunkt", in_list_view=1),
        Data("ag_id", "Arbeitsgang", read_only=1),
        Data("ag_name", "Arbeitsgang", in_list_view=1),
        Int("menge", "Menge", in_list_view=1),
        Data("benutzer", "Benutzer", in_list_view=1),
        Check("auto", "Automatisch abgehakt"),
    ]),
    dict(name="Fertigungsbauteil", autoname="FB-.YYYY.-.####", rechte=stamm_rechte(("CNC Fertigung",)), icon="factory", extra={"search_fields": "bezeichnung,teilenummer,kunde_name"}, fields=[
        Link("auftrag", "Auftrag", "Auftrag", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("auftragsposition_key", "Auftragsposition", read_only=1),
        Link("bauteil", "Bauteil", "Bauteil"),
        Link("kunde", "Kunde", "Kunde", in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Data("teilenummer", "Teilenummer", in_list_view=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer"),
        Data("revision", "Revision", read_only=1),
        Data("material", "Werkstoff"),
        Section("sb_plan", "Plan"),
        Int("menge", "Sollmenge", in_list_view=1),
        Date("termin", "Liefertermin", in_list_view=1),
        Select("prioritaet", ["Normal", "Hoch", "Eilig"], "Priorität", default="Normal", in_list_view=1, in_standard_filter=1),
        Select("status", ["Offen", "In Fertigung", "Fertig"], "Status", default="Offen", in_list_view=1, in_standard_filter=1),
        Int("produziert", "Fertig durch alle Arbeitsgänge", read_only=1),
        Int("ueberproduktion", "Überproduktion", read_only=1),
        Int("serien_von", "Seriennummer von", read_only=1),
        Int("serien_bis", "Seriennummer bis", read_only=1),
        Int("serien_stellen", "Stellen der Seriennummer", read_only=1),
        Section("sb_roh", "Rohmaterial"),
        Data("roh_werkstoff", "Werkstoff"),
        Data("roh_charge", "Charge"),
        Data("roh_lagerplatz", "Lagerplatz"),
        Data("roh_info", "Info (Maß, Länge)"),
        Num("roh_verbraucht_mm", "Verbrauchte Länge (mm)"),
        Section("sb_notizen", "Prüfung und Notizen"),
        Text("pruefmasse", "Prüfmaße und Qualität"),
        Text("bemerkungen", "Bemerkungen Fertigung"),
        Section("sb_ags", "Arbeitsgänge und Buchungen"),
        Table("arbeitsgaenge", "Fertigungsarbeitsgang", "Arbeitsgänge"),
        Table("sendungen", "Fertigungssendung", "Sendungen (Fremdvergabe)"),
        Table("buchungen", "Fertigungsbuchung", "Buchungen"),
    ]),
    dict(name="Anfrageposition", istable=1, fields=[
        Data("position_key", "Position", read_only=1, in_list_view=1),
        Data("teil_id", "Bauteil in der Workbench", read_only=1),
        Link("bauteil", "Bauteil", "Bauteil"),
        Data("teilenummer", "Teilenummer", in_list_view=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer"),
        Data("material", "Werkstoff"),
        Data("ag_id", "Arbeitsgang", read_only=1),
        Data("ag_name", "Arbeitsgang", in_list_view=1),
        Data("abmessung", "Abmessung", description="z. B. Ø 50 x 3000 mm (freie Anfrage)"),
        Json("roh", "Rohmaterial-Auswahl", description="Werkstoff, Zustand, Form, Ausführung, Abmessung, Länge/Breite: zum Ändern der Anfrage"),
        Data("anforderungen", "Anforderungen", description="z. B. Zeugnis 3.1, Ultraschallgeprüft"),
        Date("liefertermin", "Gewünschter Liefertermin"),
        Data("einheit", "Einheit", default="Stk"),
        Json("mengen", "Angefragte Mengen"),
    ]),
    dict(name="Anfragepreis", istable=1, fields=[
        Data("position_key", "Position", read_only=1, in_list_view=1),
        Int("menge", "Menge", in_list_view=1),
        F("pro_stk", "Currency", "Preis je Einheit", precision="4", in_list_view=1, description="4 Nachkommastellen (Preise je kg, aus Beträgen umgerechnet)"),
        Money("einmalig", "Einmalig", in_list_view=1),
    ]),
    dict(name="Lieferantenanfrage", autoname="LA-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="send", extra={"search_fields": "lieferant,angebot,kunde_name"}, fields=[
        Link("lieferant", "Lieferant", "Lieferant", reqd=1, in_list_view=1, in_standard_filter=1),
        Link("angebot", "Angebot", "Angebot", in_list_view=1, in_standard_filter=1, description="Leer bei einer freien Anfrage, z. B. für Material"),
        Select("art", ["Fremdvergabe", "Material", "Sonstiges"], "Art", default="Fremdvergabe", in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Select("status", ["Gesendet", "Angebot erhalten", "Abgesagt", "Ersetzt"], "Status", default="Gesendet", read_only=1, in_list_view=1, in_standard_filter=1),
        Section("sb_fassung", "Fassung"),
        Int("fassung", "Fassung", read_only=1, description="0 = ursprüngliche Anfrage, 1, 2 … = geänderte Fassung (Nummer mit -1, -2 …)"),
        Data("ursprung", "Ursprüngliche Anfrage", read_only=1),
        Data("vorgaenger", "Vorige Fassung", read_only=1),
        Data("ersetzt_durch", "Ersetzt durch", read_only=1),
        Data("aenderungsgrund", "Grund der Änderung"),
        Section("sb_notiz", "Anfrage"),
        Data("vorgang", "Vorgang", in_list_view=1, in_standard_filter=1, description="Gemeinsame Nummer aller Anfragen, die zusammen (eine Mail, Lieferanten in BCC) verschickt wurden; Grundlage für den Vergleich"),
        Text("notiz", "Hinweis an den Lieferanten"),
        F("versendet_am", "Datetime", "Per Mail versendet am", read_only=1),
        Check("neue_antwort", "Neue Antwort", read_only=1),
        Section("sb_antwort", "Angebot des Lieferanten"),
        Data("lieferantenangebot_nr", "Angebotsnummer des Lieferanten"),
        Date("gueltig_bis", "Gültig bis"),
        Data("lieferzeit", "Lieferzeit", description="z. B. 2 Wochen oder KW 50"),
        Check("zuschlag", "Zuschlag erteilt"),
        Json("zuschlag_positionen", "Zuschlag für", description="{positionen: [posKey], alternativen: [Index im eingelesenen Angebot]}; leer = alle Positionen mit Preis"),
        Money("nebenkosten", "Nebenkosten", description="Verpackung, Fracht, Zuschläge: einmal je Angebot, im Vergleich in der Summe"),
        Text("nebenkosten_text", "Nebenkosten (Aufstellung)"),
        Data("angebot_pdf", "Angebots-PDF", description="Datei, aus der das Angebot eingelesen wurde"),
        Json("angebot_daten", "Eingelesenes Angebot", description="Positionen des Lieferanten mit Zuordnung zu unseren Positionen"),
        Section("sb_pos", "Positionen und Preise"),
        Table("positionen", "Anfrageposition", "Positionen"),
        Table("preise", "Anfragepreis", "Preise des Lieferanten"),
        Section("sb_mail", "Mails"),
        Table("nachrichten", "Mail Nachricht", "Mails zur Anfrage"),
    ]),
    # Einstellungen je Benutzer für Mails (Signatur, Absendername); jeder pflegt nur seine eigene
    dict(name="Benutzereinstellung", autoname="field:benutzer", rechte=stamm_rechte(), icon="user-cog", fields=[
        Link("benutzer", "User", "Benutzer", reqd=1, unique=1, in_list_view=1),
        Data("anzeigename", "Name in Mails", in_list_view=1, description="z. B. Max Mustermann; leer = Name des Benutzers"),
        Data("funktion", "Funktion", description="z. B. Vertrieb, Arbeitsvorbereitung"),
        Data("telefon", "Telefon (Durchwahl)"),
        Data("mobil", "Mobil"),
        Data("email", "E-Mail in der Signatur", description="leer = Adresse des Benutzers"),
        Check("name_als_absender", "Eigenen Namen als Absender zeigen", default="1", description="Beim Kunden erscheint „Max Mustermann | Firma“"),
        Text("signatur", "Eigene Signatur", description="Freier Text statt der erzeugten Signatur; leer = aus den Angaben oben"),
    ]),
    dict(name="Listenfilter", autoname="hash", rechte=stamm_rechte(), icon="list-filter", fields=[
        Link("benutzer", "User", "Benutzer", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("modul", "Liste", reqd=1, in_list_view=1, description="z. B. auftraege, angebote, stamm-lieferant"),
        Json("daten", "Filter, angeheftete Felder und gespeicherte Ansichten"),
    ]),
    dict(name="Anfragevorlage", autoname="field:bezeichnung", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb",)), icon="list-checks", fields=[
        Data("bezeichnung", "Bezeichnung", reqd=1, unique=1, in_list_view=1, description="z. B. Aluminium"),
        Text("stichwoerter", "Stichwörter", description="Komma-getrennt; passt eines zum Werkstoff, zur Bezeichnung oder zum Arbeitsgang, wird die Vorlage vorgeschlagen (z. B. alu, en aw, almg)"),
        Select("iso_gruppe", ["", "P", "M", "K", "N", "S", "H"], "ISO-Gruppe des Werkstoffs", description="Passt auch, wenn der Werkstoff zu dieser Gruppe gehört (N = NE-Metalle wie Aluminium)"),
        Select("art", ["", "Material", "Fremdvergabe", "Sonstiges"], "Art der Anfrage", description="Leer = für alle Arten"),
        Json("lieferanten", "Lieferanten"),
        Text("hinweis", "Hinweis an die Lieferanten"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Lieferscheinposition", istable=1, fields=[
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1),
        Data("teilenummer", "Teilenummer", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", read_only=1, in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer", read_only=1),
        Int("menge", "Liefermenge", in_list_view=1),
        Link("auftrag", "Auftrag", "Auftrag", in_list_view=1),
        Data("auftragsposition_key", "Auftragsposition", read_only=1),
        Int("serien_von", "Seriennummer von"),
        Int("serien_bis", "Seriennummer bis"),
        Int("serien_stellen", "Stellen der Seriennummer"),
    ]),
    dict(name="Lieferschein", autoname="LS-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="truck", extra={"search_fields": "kunde_name,kundenbestellnr"}, fields=[
        Link("kunde", "Kunde", "Kunde", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1, in_list_view=1),
        Select("status", ["Bereit", "Geliefert", "Storniert"], "Status", default="Bereit", read_only=1, in_list_view=1, in_standard_filter=1),
        Check("mit_bildern", "Bauteilbilder im PDF", default="0", description="Vorschaubild des Bauteils (aus dem 3D-Modell) neben jeder Position"),
        Date("lieferdatum", "Lieferdatum", in_list_view=1),
        Date("geliefert_am", "Geliefert am", read_only=1),
        Section("sb_kopf", "Angaben"),
        Data("kundenbestellnr", "Bestellnummer des Kunden"),
        Text("lieferadresse", "Lieferadresse"),
        Text("bemerkung", "Bemerkung"),
        Section("sb_pos", "Positionen (ohne Preise)"),
        Table("positionen", "Lieferscheinposition", "Positionen"),
    ]),
    dict(name="Lagerbuchung", autoname="LB-.#####", rechte=stamm_rechte(), icon="warehouse", extra={"search_fields": "bauteil,lager"}, fields=[
        F("zeit", "Datetime", "Zeitpunkt", in_list_view=1, read_only=1),
        Select("lager", ["Fertigbauteil Lager", "Rohmaterial Lager"], "Lager", default="Fertigbauteil Lager", reqd=1, in_list_view=1, in_standard_filter=1),
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1, in_standard_filter=1),
        Int("menge", "Menge (plus Zugang, minus Abgang)", in_list_view=1),
        Select("art", ["Fertigung", "Lieferschein", "Storno Lieferschein", "Korrektur"], "Art", in_list_view=1, in_standard_filter=1),
        Link("lieferschein", "Lieferschein", "Lieferschein"),
        Link("fertigungsbauteil", "Fertigungsbauteil", "Fertigungsbauteil"),
        Link("auftrag", "Auftrag", "Auftrag"),
        Data("bemerkung", "Bemerkung"),
        Data("benutzer", "Benutzer", read_only=1),
    ]),
    dict(name="Firma Bank", istable=1, fields=[
        Data("bezeichnung", "Bank", reqd=1, in_list_view=1),
        Data("iban", "IBAN", reqd=1, in_list_view=1),
        Data("bic", "BIC", in_list_view=1),
    ]),
    dict(name="Firma", rechte=stamm_rechte(("CNC Buchhaltung",)), icon="building", extra={"issingle": 1}, fields=[
        Data("firmenname", "Firma", reqd=1),
        Data("rechtsform", "Rechtsform"),
        Data("strasse", "Straße und Nummer"),
        Data("plz", "PLZ"),
        Data("ort", "Ort"),
        Data("land", "Land", default="Deutschland"),
        Data("telefon", "Telefon"),
        Data("email", "E-Mail"),
        Data("web", "Webseite"),
        Section("sb_steuer", "Steuer und Register"),
        Data("steuernummer", "Steuernummer"),
        Data("ust_id", "USt-IdNr."),
        Data("handelsregister", "Handelsregister"),
        Data("geschaeftsfuehrer", "Geschäftsführer"),
        Data("ansprechpartner", "Ansprechpartner für Rechnungen", description="Steht als Kontakt in der E-Rechnung (ZUGFeRD)"),
        Section("sb_bank", "Bankverbindungen"),
        Table("banken", "Firma Bank", "Banken"),
        Section("sb_beleg", "Belege"),
        F("logo", "Attach Image", "Logo"),
        F("briefkopf", "Attach Image", "Kopfzeile der Belege (Bild)", description="PNG über die volle Textbreite (18 cm), steht oben auf Seite 1 von Angebot, Rechnung, Lieferschein und Mahnung"),
        Text("rechnung_text", "Einleitungstext der Rechnung"),
        Text("rechnung_fusstext", "Fußtext der Rechnung"),
        Int("zahlungsziel_tage", "Zahlungsziel (Tage)", default="14"),
        Section("sb_mahn", "Mahnwesen"),
        Int("mahnfrist_tage", "Frist je Mahnung (Tage)", default="7"),
        Money("mahngebuehr", "Mahngebühr je Mahnung", default="0"),
        F("bestellung_toleranz", "Float", "Toleranz beim Preisabgleich der Bestellung (%)", default="0.5", description="So weit darf der Betrag einer Bestellposition vom Angebot abweichen (Rundung beim Umlegen der Kosten auf den Stückpreis)"),
    ]),
    dict(name="Steuerschluessel", autoname="field:bezeichnung", title="bezeichnung", rechte=stamm_rechte(("CNC Buchhaltung",)), icon="percent", fields=[
        Data("bezeichnung", "Bezeichnung", reqd=1, unique=1, in_list_view=1),
        Num("satz", "Steuersatz (%)", reqd=1, in_list_view=1),
        Select("kategorie", ["S", "Z", "E", "AE", "K", "G", "O"], "Steuerkategorie (EN 16931)", default="S", description="S = normaler Satz"),
        Data("erloeskonto", "Erlöskonto", description="folgt mit der Abstimmung zu DATEV"),
        Text("hinweistext", "Hinweistext auf der Rechnung"),
        Check("standard", "Standard"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Nummernkreis", autoname="field:schluessel", rechte=stamm_rechte(), icon="hash", fields=[
        Data("schluessel", "Schlüssel", reqd=1, unique=1, in_list_view=1, description="z. B. Rechnung-2026"),
        Int("aktuell", "Zuletzt vergebene Nummer", read_only=1, in_list_view=1),
    ]),
    dict(name="Rechnungsposition", istable=1, fields=[
        Data("zeilen_id", "Zeile", read_only=1, in_list_view=1, description="1, 1.1 ... wie in der E-Rechnung"),
        Select("art", ["Bauteil", "Sonderkosten"], "Art", default="Bauteil", in_list_view=1),
        Link("bauteil", "Bauteil", "Bauteil"),
        Data("teilenummer", "Teilenummer", read_only=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer", read_only=1),
        Int("menge", "Menge", in_list_view=1),
        Data("einheit", "Einheit", default="Stk"),
        Money("einzelpreis", "Einzelpreis", in_list_view=1),
        Money("netto", "Zeilenbetrag netto", read_only=1, in_list_view=1),
        Data("auftragsposition_key", "Auftragsposition", read_only=1),
        Data("auftragskosten_name", "Kostenzeile im Auftrag", read_only=1),
        Json("lieferungen", "Lieferscheine mit Mengen"),
        Text("lieferungen_text", "Geliefert mit"),
        Data("serien_text", "Seriennummern"),
    ]),
    dict(name="Rechnung", autoname="ENT-RE-.#####", rechte=stamm_rechte(("CNC Vertrieb", "CNC Buchhaltung")), icon="receipt", extra={"search_fields": "rechnungsnummer,kunde_name,auftrag"}, fields=[
        Data("rechnungsnummer", "Rechnungsnummer", read_only=1, in_list_view=1, description="wird beim Festschreiben lückenlos vergeben"),
        Check("mit_bildern", "Bauteilbilder im PDF", default="0", description="Vorschaubild des Bauteils (aus dem 3D-Modell) neben jeder Position"),
        Link("kunde", "Kunde", "Kunde", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Link("auftrag", "Auftrag", "Auftrag", reqd=1, in_list_view=1, in_standard_filter=1),
        Select("art", ["Gesamtrechnung", "Teilrechnung", "Storno"], "Art", default="Gesamtrechnung", read_only=1, in_list_view=1, in_standard_filter=1),
        Select("status", ["Entwurf", "Offen", "Teilbezahlt", "Bezahlt", "Storniert", "Gutschrift"], "Status", default="Entwurf", read_only=1, in_list_view=1, in_standard_filter=1),
        Date("rechnungsdatum", "Rechnungsdatum", in_list_view=1),
        Date("leistung_von", "Leistungsdatum von"),
        Date("leistung_bis", "Leistungsdatum bis"),
        Int("zahlungsziel_tage", "Zahlungsziel (Tage)"),
        Date("faellig_am", "Fällig am", in_list_view=1),
        Section("sb_summen", "Summen"),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Num("steuersatz", "Steuersatz (%)", read_only=1),
        Money("steuerbetrag", "Umsatzsteuer", read_only=1),
        Money("brutto", "Brutto", read_only=1, in_list_view=1),
        Money("bezahlt", "Bezahlt", read_only=1),
        Money("offen", "Offen", read_only=1, in_list_view=1),
        Link("steuerschluessel", "Steuerschluessel", "Steuerschlüssel"),
        Section("sb_kopf", "Angaben"),
        Data("kundenbestellnr", "Bestellnummer des Kunden"),
        Text("rechnungsadresse", "Rechnungsadresse (zum Zeitpunkt der Rechnung)"),
        Data("kunde_ust_id", "USt-IdNr. des Kunden"),
        Data("leitweg_id", "Leitweg-ID"),
        Data("kunde_email", "E-Mail des Rechnungsempfängers"),
        Data("kunde_strasse", "Straße des Empfängers"),
        Data("kunde_plz", "PLZ des Empfängers"),
        Data("kunde_ort", "Ort des Empfängers"),
        Data("kunde_land", "Ländercode des Empfängers", default="DE"),
        Text("einleitung", "Einleitungstext"),
        Text("bemerkung", "Bemerkung"),
        Text("zahlungshinweis", "Zahlungshinweis mit Bankverbindungen"),
        Text("fusstext", "Fußtext"),
        Json("firma_snapshot", "Firmendaten zum Zeitpunkt der Rechnung", read_only=1),
        Section("sb_pos", "Positionen"),
        Table("positionen", "Rechnungsposition", "Positionen"),
        Section("sb_erechnung", "E-Rechnung"),
        Data("erechnung_status", "Stand der E-Rechnung", read_only=1),
        Text("erechnung_hinweis", "Hinweis zur E-Rechnung", read_only=1),
        Section("sb_gobd", "Festschreibung und Storno"),
        F("festgeschrieben_am", "Datetime", "Festgeschrieben am", read_only=1),
        Data("festgeschrieben_von", "Festgeschrieben von", read_only=1),
        Data("inhalt_hash", "Prüfsumme des Inhalts", read_only=1, description="SHA-256 über den festgeschriebenen Inhalt"),
        Link("storno_zu", "Rechnung", "Storno zu Rechnung", read_only=1),
        Link("storniert_durch", "Rechnung", "Storniert durch", read_only=1),
        Data("storno_grund", "Stornogrund", read_only=1),
    ]),
    dict(name="Zahlung", autoname="ZA-.YYYY.-.####", rechte=stamm_rechte(("CNC Buchhaltung",)), icon="banknote", extra={"search_fields": "rechnung,referenz"}, fields=[
        Link("rechnung", "Rechnung", "Rechnung", reqd=1, in_list_view=1, in_standard_filter=1),
        Money("betrag", "Betrag", reqd=1, in_list_view=1),
        Date("datum", "Zahlungsdatum", reqd=1, in_list_view=1),
        Data("referenz", "Verwendungszweck", in_list_view=1),
        Data("konto", "Eingegangen auf"),
        Data("benutzer", "Erfasst von", read_only=1),
        Check("storniert", "Storniert", read_only=1),
        Data("storno_grund", "Stornogrund", read_only=1),
    ]),
    dict(name="Mahnung", autoname="MA-.YYYY.-.####", rechte=stamm_rechte(("CNC Buchhaltung",)), icon="bell", extra={"search_fields": "rechnung,kunde_name"}, fields=[
        Link("rechnung", "Rechnung", "Rechnung", reqd=1, in_list_view=1, in_standard_filter=1),
        Link("kunde", "Kunde", "Kunde", in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Select("stufe", ["Zahlungserinnerung", "1. Mahnung", "2. Mahnung"], "Stufe", reqd=1, in_list_view=1, in_standard_filter=1),
        Select("status", ["Angelegt", "Versendet", "Erledigt", "Zurückgezogen"], "Status", default="Angelegt", read_only=1, in_list_view=1, in_standard_filter=1),
        Date("datum", "Datum", in_list_view=1),
        Date("frist_bis", "Zahlen bis", in_list_view=1),
        Money("offener_betrag", "Offener Betrag"),
        Money("gebuehr", "Mahngebühr"),
        Date("versandt_am", "Versendet am", read_only=1),
        Text("text", "Text der Mahnung"),
    ]),
]


# ---- Mail-Anbindung: Posteingang aus dem gemeinsamen Postfach (bekannte Absender und Mails mit Stichwort im Betreff)


DOCTYPES += [
    dict(name="Mail Einstellungen", rechte=[recht("System Manager", *ALLE), recht("CNC Admin", *ALLE)], icon="mail", extra={"issingle": 1}, fields=[
        Check("aktiv", "Mails automatisch abholen", description="Alle 5 Minuten; geholt werden Mails bekannter Absender und Mails mit einem Stichwort im Betreff"),
        Section("sb_server", "Postfach"),
        Data("benutzer", "Benutzer (E-Mail-Adresse)", description="z. B. info@cnc-hohenstein.de"),
        F("passwort", "Password", "Passwort"),
        Data("absender_name", "Absendername", description="erscheint beim Kunden als Absender der Antwort"),
        Select("verschluesselung", ["SSL/TLS", "STARTTLS", "Ohne (nur Test)"], "Verschlüsselung", default="SSL/TLS"),
        Data("imap_server", "IMAP-Server", default="imap.ionos.de"),
        Int("imap_port", "IMAP-Port", default="993"),
        Data("smtp_server", "SMTP-Server", default="smtp.ionos.de"),
        Int("smtp_port", "SMTP-Port", default="465"),
        Section("sb_abruf", "Abruf"),
        Text("stichwoerter", "Stichwörter im Betreff", default="Anfrage", description="Eines je Zeile, Groß-/Kleinschreibung egal; holt auch Mails unbekannter Absender (neue Kunden)"),
        Check("bekannte_absender", "Mails bekannter Absender abholen", default="1", description="Kontakte der Kunden, Lieferanten und deren Domains (ohne Freemail-Anbieter)"),
        Text("freemail_domains", "Freemail-Anbieter", description="Eine Domain je Zeile; dort zählt nur die genaue Adresse, nicht die Domain. Leer = Standardliste"),
        Text("ignorierte_absender", "Absender nie abholen", description="Eine Adresse oder Domain je Zeile; diese Mails werden nie geholt, auch nicht mit Stichwort im Betreff"),
        Section("sb_einordnen", "Einordnen"),
        Text("woerter_bestellung", "Stichwörter für Bestellungen", default="Bestellung\nOrder\nAbruf", description="im Betreff oder Dateinamen eines Anhangs"),
        Text("woerter_rechnung", "Stichwörter für Rechnungen", default="Rechnung\nInvoice\nGutschrift", description="im Betreff oder Dateinamen; E-Rechnungen (ZUGFeRD, XRechnung) werden immer erkannt"),
        Text("gesperrte_endungen", "Gesperrte Dateiendungen", description="Anhänge mit diesen Endungen werden nicht übernommen (Programme, Office mit Makros). Leer = Standardliste"),
        Date("abholen_ab", "Mails ab", description="Ältere Mails werden nicht geholt"),
        Data("postfach_ordner", "Ordner im Postfach", default="INBOX"),
        Data("gesendet_ordner", "Ordner für gesendete Mails", default="Gesendete Objekte"),
        Section("sb_antwort", "Antwort mit Angebot"),
        F("antwort_vorlage", "Text", "Text der Antwort", description="Platzhalter: {anrede}, {angebot}, {anfrage}, {absender}, {firma}. Leer = Standardtext"),
        Section("sb_stand", "Stand"),
        F("letzter_abruf", "Datetime", "Letzter Abruf", read_only=1),
        Text("letzter_fehler", "Letzter Fehler", read_only=1),
    ]),
    # Mailinhalte unverändert speichern (Adressen und Message-IDs stehen in <...>); angezeigt wird nur als Text
    dict(name="Mail Nachricht", istable=1, fields=[
        Select("richtung", ["Eingang", "Ausgang"], "Richtung", default="Eingang", in_list_view=1),
        F("datum", "Datetime", "Datum", in_list_view=1),
        Data("von_email", "Von (Adresse)", in_list_view=1),
        Data("von_name", "Von (Name)", ignore_xss_filter=1),
        Text("an", "An", ignore_xss_filter=1),
        Text("cc", "CC", ignore_xss_filter=1),
        Data("betreff", "Betreff", in_list_view=1, ignore_xss_filter=1),
        Data("message_id", "Message-ID", read_only=1, ignore_xss_filter=1),
        Data("in_reply_to", "Antwort auf (Message-ID)", read_only=1, ignore_xss_filter=1),
        Text("referenzen", "Verlauf (References)", read_only=1, ignore_xss_filter=1),
        LongText("text", "Text", ignore_xss_filter=1),
        LongText("html", "Text als HTML", read_only=1, ignore_xss_filter=1, description="Beim Abholen bereinigt (ohne Skripte, ohne Bilder fremder Server)"),
        Json("anhaenge", "Anhänge", description="[{ name, url, groesse }]"),
        Text("hinweis", "Hinweis", description="z. B. Anhang zu groß"),
    ]),
    dict(name="Mail Anfrage", autoname="MAIL-.YYYY.-.#####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="inbox", extra={"search_fields": "betreff,von_email,kunde_name"}, fields=[
        Select("status", ["Neu", "In Bearbeitung", "Beantwortet", "Erledigt", "Keine Anfrage"], "Status", default="Neu", in_list_view=1, in_standard_filter=1),
        Select("kategorie", ["Anfrage", "Bestellung", "Rechnung", "Lieferant", "Sonstiges"], "Art", default="Anfrage", in_list_view=1, in_standard_filter=1),
        Data("betreff", "Betreff", in_list_view=1, ignore_xss_filter=1),
        Data("von_email", "Von (Adresse)", in_list_view=1, in_standard_filter=1),
        Data("von_name", "Von (Name)", ignore_xss_filter=1),
        F("datum", "Datetime", "Eingegangen", in_list_view=1),
        F("letzte_nachricht", "Datetime", "Letzte Nachricht"),
        Check("neue_antwort", "Neue Nachricht des Kunden", description="Der Kunde hat im Verlauf geantwortet"),
        Check("wichtig", "Wichtig", in_standard_filter=1, description="Rotes Ausrufezeichen zur Priorisierung"),
        Link("kunde", "Kunde", "Kunde", in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Link("kunde_vorschlag", "Kunde", "Kundenvorschlag (gleiche Domain)", read_only=1),
        Link("lieferant", "Lieferant", "Lieferant", in_standard_filter=1),
        Link("angebot", "Angebot", "Angebot"),
        Link("auftrag", "Auftrag", "Auftrag", description="Auftrag aus einer Bestellung dieser Mail"),
        Check("absender_warnung", "Absender nicht bestätigt", read_only=1, description="SPF/DKIM/DMARC-Prüfung des Postfachs ist fehlgeschlagen: Absender könnte gefälscht sein"),
        Data("absender_pruefung", "Prüfung des Absenders", read_only=1),
        Section("sb_nachrichten", "Nachrichten"),
        Table("nachrichten", "Mail Nachricht", "Nachrichten"),
    ]),
]



# ---- Eingangsrechnungen (Rechnungen der Lieferanten), aus dem Posteingang oder hochgeladen
DOCTYPES += [
    dict(name="Eingangsrechnungsposition", istable=1, fields=[
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Num("menge", "Menge", in_list_view=1),
        Data("einheit", "Einheit"),
        Money("einzelpreis", "Einzelpreis", in_list_view=1),
        Money("betrag", "Betrag netto", in_list_view=1),
        Num("steuersatz", "Steuersatz (%)"),
    ]),
    dict(name="Eingangsrechnung", autoname="ER-.YYYY.-.#####", rechte=stamm_rechte(("CNC Buchhaltung",)), icon="receipt", extra={"search_fields": "lieferant_name,rechnungsnr"}, fields=[
        Select("status", ["Neu", "Geprüft", "Bezahlt", "Abgelehnt"], "Status", default="Neu", in_list_view=1, in_standard_filter=1),
        Link("lieferant", "Lieferant", "Lieferant", in_list_view=1, in_standard_filter=1),
        Data("lieferant_name", "Rechnungssteller", in_list_view=1, description="Name laut Rechnung"),
        Data("lieferant_ust_id", "USt-IdNr. laut Rechnung"),
        Data("rechnungsnr", "Rechnungsnummer", in_list_view=1),
        Date("rechnungsdatum", "Rechnungsdatum", in_list_view=1),
        Date("faellig_am", "Fällig am"),
        Select("art", ["Rechnung", "Gutschrift"], "Art", default="Rechnung"),
        Select("format", ["ZUGFeRD", "XRechnung", "PDF", "Papier"], "Format", read_only=1, in_list_view=1),
        Section("sb_betraege", "Beträge"),
        Money("netto", "Netto", in_list_view=1),
        Money("steuer", "Umsatzsteuer"),
        Money("brutto", "Brutto"),
        Data("waehrung", "Währung", default="EUR"),
        Data("iban", "IBAN des Lieferanten"),
        Data("bestellreferenz", "Unsere Bestellung laut Rechnung"),
        Section("sb_pos", "Positionen"),
        Table("positionen", "Eingangsrechnungsposition", "Positionen"),
        Section("sb_herkunft", "Herkunft"),
        Link("mail", "Mail Anfrage", "Aus der Mail"),
        Data("pdf_datei", "PDF", read_only=1),
        Data("xml_datei", "E-Rechnung (XML)", read_only=1),
        Text("pruefhinweise", "Hinweise beim Einlesen", read_only=1),
        Text("bemerkung", "Bemerkung"),
        Data("geprueft_von", "Geprüft von", read_only=1),
        F("geprueft_am", "Datetime", "Geprüft am", read_only=1),
    ]),
]


# ---- Dokumentenmanagement: ein Eintrag je Dokument (Inhalt), gleiche Datei an mehreren Belegen = ein Dokument
DOKUMENT_ARTEN = ["Zeichnung", "3D-Modell", "Angebot", "Rechnung", "E-Rechnung (XML)", "Lieferschein", "Mahnung", "Bestellung", "Werkszeugnis", "Mail-Anhang", "Sonstiges"]

DOCTYPES += [
    dict(name="Archiv Frist", istable=1, fields=[
        Select("art", DOKUMENT_ARTEN, "Dokumentart", reqd=1, in_list_view=1),
        Int("jahre", "Jahre", in_list_view=1, description="0 = keine Aufbewahrungspflicht"),
        Data("grundlage", "Grundlage", in_list_view=1),
    ]),
    dict(name="Archiv Einstellungen", rechte=[recht("System Manager", *ALLE), recht("CNC Admin", *ALLE), recht("CNC Buchhaltung", "read", "write"), recht("CNC Vertrieb", "read"), recht("CNC Fertigung", "read")], icon="archive", extra={"issingle": 1}, fields=[
        Table("fristen", "Archiv Frist", "Aufbewahrungsfristen", description="Die Frist beginnt mit dem Schluss des Kalenderjahres, in dem das Dokument entstanden ist (§ 147 Abs. 4 AO)"),
    ]),
    dict(name="Dokument Protokoll", autoname="DPR-.########", rechte=[recht("System Manager", "read", "report", "export"), recht("CNC Admin", "read", "report", "export"), recht("CNC Buchhaltung", "read", "report", "export"), recht("CNC Vertrieb", "read"), recht("CNC Fertigung", "read")], icon="history", extra={"search_fields": "titel,beleg"}, fields=[
        F("zeit", "Datetime", "Zeitpunkt", in_list_view=1),
        Link("benutzer", "User", "Benutzer", in_list_view=1, in_standard_filter=1),
        Select("aktion", ["Abgelegt", "Geändert", "Gelöscht", "Exportiert"], "Aktion", in_list_view=1, in_standard_filter=1),
        Data("titel", "Dokument", in_list_view=1, ignore_xss_filter=1),
        Data("art", "Art"),
        Data("beleg_typ", "Belegart"),
        Data("beleg", "Beleg", in_standard_filter=1),
        Data("content_hash", "Prüfwert"),
        Text("details", "Details", ignore_xss_filter=1),
    ]),
    dict(name="Dokument Bezug", istable=1, fields=[
        Data("beleg_typ", "Belegart", in_list_view=1),
        Data("beleg", "Beleg", in_list_view=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Data("datei", "Dateieintrag", read_only=1),
    ]),
    dict(name="Zeichnung Markierung", autoname="hash", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung", "CNC Buchhaltung")), icon="highlighter", extra={"search_fields": "datei"}, fields=[
        Data("datei", "Zeichnung (Datei-URL)", reqd=1, unique=1, in_list_view=1),
        Int("drehung", "Drehung (Grad)", in_list_view=1),
        Json("markierungen", "Markierungen", description="Textmarker, Rahmen, Pfeile, Freihand und Notizen als Anteil der Seite"),
    ]),
    dict(name="Dokument", autoname="DOK-.#####", title="titel", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung", "CNC Buchhaltung")), icon="folder-open", extra={"search_fields": "titel,teilenummer,kunde_name"}, fields=[
        Data("titel", "Titel", in_list_view=1, ignore_xss_filter=1),
        Select("art", DOKUMENT_ARTEN, "Art", in_list_view=1, in_standard_filter=1),
        Link("kunde", "Kunde", "Kunde", in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Data("teilenummer", "Teilenummer", in_standard_filter=1),
        Data("revision", "Revision"),
        Select("fassung", ["", "Aktuell", "Ältere Fassung"], "Fassung"),
        F("datum", "Datetime", "Datum", in_list_view=1),
        Data("herkunft", "Herkunft", read_only=1, ignore_xss_filter=1, description="z. B. aus einer ZIP-Datei der Mail-Anfrage"),
        Section("sb_archiv", "Aufbewahrung"),
        Check("abgeschlossen", "Abgeschlossen", read_only=1, description="Der Beleg ist festgeschrieben, gesendet, geliefert oder versendet"),
        Date("aufbewahren_bis", "Aufzubewahren bis", read_only=1),
        Check("gesperrt", "Löschsperre", read_only=1, description="Abgeschlossen und die Aufbewahrungsfrist läuft noch"),
        Section("sb_datei", "Datei"),
        Data("datei", "Datei (URL)", read_only=1),
        Data("content_hash", "Prüfwert", read_only=1, unique=1),
        Int("groesse", "Größe (Bytes)", read_only=1),
        Data("endung", "Dateityp", read_only=1),
        Section("sb_pflege", "Schlagworte und Notiz"),
        Text("schlagworte", "Schlagworte", description="mit Komma getrennt"),
        Text("notiz", "Notiz"),
        Section("sb_bezug", "Bezüge"),
        Table("bezuege", "Dokument Bezug", "Bezüge"),
        Section("sb_text", "Text für die Suche", collapsible=1),
        Check("text_gelesen", "Text gelesen", read_only=1),
        LongText("inhalt", "Text aus der Datei", read_only=1, ignore_xss_filter=1),
    ]),
]


# ---- Druckvorlagen: Belege (HTML/CSS) in der Oberfläche ändern. Ohne Eintrag gilt die Datei im Code (templates/);
# „In den Code übernehmen“ schreibt den Stand zurück in die Datei, damit er mit Git ins Produktivsystem kommt.
DOCTYPES += [
    dict(name="Druckvorlage", autoname="field:datei", title="bezeichnung", rechte=stamm_rechte(), icon="file-code", fields=[
        Data("datei", "Datei", reqd=1, unique=1, in_list_view=1, description="Name der Vorlage im Ordner templates, z. B. angebot_pdf.html"),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        F("inhalt", "Code", "Inhalt", options="HTML"),
        Data("code_hash", "Prüfsumme der Datei beim Ändern", read_only=1, description="Hat sich die Datei im Code seither geändert, wird darauf hingewiesen"),
    ]),
    dict(name="Druckvorlage Stand", autoname="hash", rechte=stamm_rechte(), icon="history", fields=[
        Data("vorlage", "Vorlage (Datei)", reqd=1, in_list_view=1, in_standard_filter=1),
        LongText("inhalt", "Inhalt"),
        Data("aktion", "Aktion", in_list_view=1, description="gespeichert, zurückgesetzt, in den Code übernommen"),
        Data("notiz", "Notiz"),
    ]),
]


def doctype_json(d):
    fields = d["fields"]
    j = {
        "actions": [],
        "creation": STAMP,
        "doctype": "DocType",
        "engine": "InnoDB",
        "field_order": [f["fieldname"] for f in fields],
        "fields": fields,
        "links": [],
        "modified": STAMP,
        "modified_by": "Administrator",
        "module": MODUL,
        "name": d["name"],
        "owner": "Administrator",
        "permissions": d.get("rechte", []),
        "sort_field": "creation",
        "sort_order": "DESC",
        "states": [],
    }
    if d.get("istable"):
        j["istable"] = 1
        j["editable_grid"] = 1
        j["autoname"] = "hash"
    else:
        j["autoname"] = d.get("autoname", "hash")
        if re.search(r"[#]", j["autoname"]):
            j["naming_rule"] = "Expression (old style)"
        elif j["autoname"].startswith("field:"):
            j["naming_rule"] = "By fieldname"
        if d.get("title"):
            j["title_field"] = d["title"]
            j["show_title_field_in_link"] = 1
            j["search_fields"] = d["title"]
        j["track_changes"] = 1
        j["allow_rename"] = 0
        if d.get("icon"):
            j["icon"] = d["icon"]
        if d.get("submittable"):
            j["is_submittable"] = 1
    for k, v in d.get("extra", {}).items():
        j[k] = v
    return j


CONTROLLER = '''import frappe
from frappe.model.document import Document


class {klasse}(Document):
	pass
'''


def main(ziel):
    for d in DOCTYPES:
        ordner = os.path.join(ziel, "doctype", scrub(d["name"]))
        os.makedirs(ordner, exist_ok=True)
        open(os.path.join(ordner, "__init__.py"), "a").close()
        pfad = os.path.join(ordner, scrub(d["name"]) + ".json")
        with open(pfad, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doctype_json(d), f, indent=1, ensure_ascii=False)
            f.write("\n")
        py = os.path.join(ordner, scrub(d["name"]) + ".py")
        if not os.path.exists(py):
            with open(py, "w", encoding="utf-8", newline="\n") as f:
                f.write(CONTROLLER.format(klasse=klasse(d["name"])))
    os.makedirs(os.path.join(ziel, "doctype"), exist_ok=True)
    open(os.path.join(ziel, "doctype", "__init__.py"), "a").close()
    print(f"{len(DOCTYPES)} Doctypes geschrieben nach {ziel}")


if __name__ == "__main__":
    main(sys.argv[1])
