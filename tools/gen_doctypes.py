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
        Link("lieferant", "Lieferant", "Lieferant"),
        Money("fremd_pro_stk", "Fremdvergabe je Stück"),
        Money("fremd_einmal", "Fremdvergabe einmalig"),
        Data("anfrage", "Anfrage, aus der der Preis stammt"),
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
        Data("telefon", "Telefon"),
        Check("ist_rechnungskontakt", "Rechnungskontakt"),
    ]),
    # ---- Stammdaten
    dict(name="Maschine", autoname="field:maschinenname", title="maschinenname", rechte=stamm_rechte(), icon="cog", fields=[
        Data("maschinenname", "Maschine", reqd=1, unique=1, in_list_view=1),
        Money("satz", "Stundensatz (€/h)", reqd=1, in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Text("bemerkung", "Bemerkung"),
    ]),
    dict(name="Material", autoname="field:materialname", title="materialname", rechte=stamm_rechte(), icon="layers", fields=[
        Data("materialname", "Werkstoff", reqd=1, unique=1, in_list_view=1),
        Money("preis_kg", "Preis (€/kg)", in_list_view=1),
        Num("dichte", "Dichte (kg/dm³)"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Lieferant", autoname="field:lieferantenname", title="lieferantenname", rechte=stamm_rechte(("CNC Vertrieb",)), icon="truck", fields=[
        Data("lieferantenname", "Lieferant", reqd=1, unique=1, in_list_view=1),
        Data("leistung", "Leistung", in_list_view=1, description="z. B. Eloxieren, Härten"),
        Data("email", "E-Mail", options="Email"),
        Data("telefon", "Telefon"),
        Text("adresse", "Adresse"),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Arbeitsgangart", autoname="AA-.####", title="bezeichnung", rechte=stamm_rechte(), icon="list-tree", fields=[
        Data("bezeichnung", "Bezeichnung", reqd=1, in_list_view=1),
        Select("typ", ["Intern", "Fremd"], "Art", default="Intern", reqd=1, in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
    ]),
    dict(name="Kunde", autoname="K-.####", title="kundenname", rechte=stamm_rechte(("CNC Vertrieb",)), icon="users", fields=[
        Data("kundenname", "Kunde", reqd=1, in_list_view=1),
        Data("kuerzel", "Kürzel", in_list_view=1),
        Check("aktiv", "Aktiv", default="1", in_list_view=1),
        Section("sb_steuer", "Steuer und Rechnung"),
        Data("ust_id", "USt-IdNr."),
        Data("steuernummer", "Steuernummer"),
        Data("zahlungsbedingung", "Zahlungsbedingung"),
        Data("leitweg_id", "Leitweg-ID / Käuferreferenz"),
        Data("lieferantennummer", "Lieferantennummer beim Kunden"),
        Section("sb_adressen", "Adressen und Kontakte"),
        Table("adressen", "Kunde Adresse", "Adressen"),
        Table("kontakte", "Kunde Kontakt", "Kontakte"),
    ]),
    dict(name="Arbeitsplan Vorlage", autoname="VL-.####", title="vorlagenname", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="workflow", fields=[
        Data("vorlagenname", "Name der Vorlage", reqd=1, in_list_view=1),
        Link("kunde", "Kunde", "Nur für Kunde", in_list_view=1, description="leer = für alle Kunden"),
        Table("arbeitsgaenge", "Arbeitsgang Plan", "Arbeitsgänge"),
    ]),
]

DOCTYPES += [
    dict(name="Bauteil", autoname="BT-.#####", title="bezeichnung", rechte=stamm_rechte(("CNC Vertrieb", "CNC Fertigung")), icon="package", fields=[
        Link("kunde", "Kunde", "Kunde", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("teilenummer", "Teilenummer", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer"),
        Data("revision", "Revision"),
        Link("material", "Material", "Werkstoff"),
        Select("status", ["Aktiv", "Gesperrt"], "Status", default="Aktiv", in_list_view=1),
        Section("sb_dateien", "Dateien"),
        F("vorschaubild", "Attach Image", "Vorschaubild", description="entsteht später aus dem STEP-Modell"),
        F("step_datei", "Attach", "STEP-Modell"),
        Section("sb_plan", "Arbeitsplan"),
        Table("arbeitsplan", "Arbeitsgang Plan", "Arbeitsgänge"),
    ]),
    dict(name="Angebotsposition", istable=1, fields=[
        Data("position_key", "Schlüssel", read_only=1, description="Kennung der Position aus der Workbench"),
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1),
        Data("teilenummer", "Teilenummer", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", read_only=1, in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer", read_only=1),
        Data("material", "Werkstoff", read_only=1),
        Int("menge", "Menge", read_only=1, in_list_view=1),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Json("kalkulation", "Kalkulation (Eingaben)"),
        Json("ergebnis", "Ergebnis (vom Server berechnet)", read_only=1),
    ]),
    dict(name="Angebot", autoname="ANG-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="file-text", extra={"search_fields": "kunde_name,anfrage_nr"}, fields=[
        Link("kunde", "Kunde", "Kunde", in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1, in_list_view=1),
        Select("status", ["Entwurf", "Gesendet", "Abgelehnt"], "Status", default="Entwurf", read_only=1, in_list_view=1, in_standard_filter=1),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Section("sb_kopf", "Angaben"),
        Data("anfrage_nr", "Anfrage-Nr. des Kunden"),
        Int("gueltig_wochen", "Gültig (Wochen)", default="4"),
        Data("lieferzeit", "Lieferzeit", default="Nach Absprache"),
        F("versandt_am", "Datetime", "Gesendet am", read_only=1),
        Section("sb_pos", "Positionen"),
        Table("positionen", "Angebotsposition", "Positionen"),
    ]),
]


# ---- Aufträge und Fertigung
DOCTYPES += [
    dict(name="Auftragsposition", istable=1, fields=[
        Data("position_key", "Schlüssel", read_only=1),
        Data("angebot_position_key", "Position im Angebot", read_only=1),
        Link("bauteil", "Bauteil", "Bauteil", in_list_view=1),
        Data("teilenummer", "Teilenummer", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", read_only=1, in_list_view=1),
        Data("zeichnungsnr", "Zeichnungsnummer", read_only=1),
        Data("material", "Werkstoff", read_only=1),
        Int("menge", "Bestellte Menge", in_list_view=1),
        Money("einzelpreis", "Stückpreis", in_list_view=1),
        Int("staffel_menge", "Gewählte Staffel"),
        Date("liefertermin", "Liefertermin", in_list_view=1),
        Money("summe", "Summe Position", read_only=1),
        Json("arbeitsplan", "Arbeitsplan zum Zeitpunkt der Bestellung"),
    ]),
    dict(name="Auftragskosten", istable=1, fields=[
        Data("position_key", "Position", read_only=1, in_list_view=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Money("betrag", "Betrag", in_list_view=1),
    ]),
    dict(name="Auftrag", autoname="AUF-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="clipboard-list", extra={"search_fields": "kunde_name,kundenbestellnr"}, fields=[
        Link("kunde", "Kunde", "Kunde", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1, in_list_view=1),
        Link("angebot", "Angebot", "Angebot", reqd=1, in_list_view=1, in_standard_filter=1),
        Select("status", ["Offen", "In Fertigung", "Fertig", "Storniert"], "Status", default="Offen", read_only=1, in_list_view=1, in_standard_filter=1),
        Money("netto", "Netto", read_only=1, in_list_view=1),
        Section("sb_kopf", "Angaben"),
        Data("kundenbestellnr", "Bestellnummer des Kunden"),
        Section("sb_pos", "Positionen"),
        Table("positionen", "Auftragsposition", "Positionen"),
        Table("kosten", "Auftragskosten", "Kosten (Sonderkosten je Position)"),
    ]),
    dict(name="Fertigungsarbeitsgang", istable=1, fields=[
        Data("ag_id", "Id", read_only=1),
        Data("bezeichnung", "Bezeichnung", in_list_view=1),
        Select("typ", ["Intern", "Fremd"], "Art", default="Intern", in_list_view=1),
        Link("maschine", "Maschine", "Maschine", in_list_view=1),
        Money("satz", "Satz (€/h)"),
        Num("ruest_min", "Rüstzeit (min)"),
        Num("stueck_min", "Stückzeit (min)"),
        Select("status", ["Offen", "Läuft", "Fertig"], "Status", default="Offen", in_list_view=1),
        Int("gebucht", "Gebucht", in_list_view=1),
        Link("lieferant", "Lieferant", "Lieferant"),
        Money("fremd_pro_stk", "Fremdvergabe je Stück"),
        Money("fremd_einmal", "Fremdvergabe einmalig"),
        Data("anfrage", "Anfrage"),
        Data("bestellung", "Bestellung"),
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
        Data("material", "Werkstoff"),
        Section("sb_plan", "Plan"),
        Int("menge", "Sollmenge", in_list_view=1),
        Date("termin", "Liefertermin", in_list_view=1),
        Select("prioritaet", ["Normal", "Hoch", "Eilig"], "Priorität", default="Normal", in_list_view=1, in_standard_filter=1),
        Select("status", ["Offen", "In Fertigung", "Fertig"], "Status", default="Offen", in_list_view=1, in_standard_filter=1),
        Int("produziert", "Fertig durch alle Arbeitsgänge", read_only=1),
        Int("ueberproduktion", "Überproduktion", read_only=1),
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
        Json("mengen", "Angefragte Mengen"),
    ]),
    dict(name="Anfragepreis", istable=1, fields=[
        Data("position_key", "Position", read_only=1, in_list_view=1),
        Int("menge", "Menge", in_list_view=1),
        Money("pro_stk", "Preis je Stück", in_list_view=1),
        Money("einmalig", "Einmalig", in_list_view=1),
    ]),
    dict(name="Lieferantenanfrage", autoname="LA-.YYYY.-.####", rechte=stamm_rechte(("CNC Vertrieb",)), icon="send", extra={"search_fields": "lieferant,angebot,kunde_name"}, fields=[
        Link("lieferant", "Lieferant", "Lieferant", reqd=1, in_list_view=1, in_standard_filter=1),
        Link("angebot", "Angebot", "Angebot", reqd=1, in_list_view=1, in_standard_filter=1),
        Data("kunde_name", "Kundenname", read_only=1),
        Select("status", ["Gesendet", "Angebot erhalten", "Abgesagt"], "Status", default="Gesendet", read_only=1, in_list_view=1, in_standard_filter=1),
        Section("sb_notiz", "Anfrage"),
        Text("notiz", "Hinweis an den Lieferanten"),
        Section("sb_antwort", "Angebot des Lieferanten"),
        Data("lieferantenangebot_nr", "Angebotsnummer des Lieferanten"),
        Date("gueltig_bis", "Gültig bis"),
        Section("sb_pos", "Positionen und Preise"),
        Table("positionen", "Anfrageposition", "Positionen"),
        Table("preise", "Anfragepreis", "Preise des Lieferanten"),
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
