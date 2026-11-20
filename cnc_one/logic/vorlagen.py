"""Druckvorlagen der Belege (HTML mit Jinja, CSS).

Der Stand im Code (Ordner templates/) ist die Grundlage und kommt mit Git ins Produktivsystem. In der Oberfläche lässt
sich jede Vorlage ändern: der geänderte Stand liegt im Doctype „Druckvorlage“ und gilt dann statt der Datei. Ohne
Eintrag gilt die Datei. Auf dem Testsystem (developer_mode) schreibt „In den Code übernehmen“ den Stand in die Datei
zurück und entfernt den Eintrag; so wird die Änderung Teil des Codes und mit dem nächsten Commit ausgeliefert.

Für die Vorschau kann ein ungespeicherter Stand untergeschoben werden (`probe`), nur für diese Anfrage.
"""

import hashlib
from contextlib import contextmanager

import frappe
from frappe import _

# Datei: (Bezeichnung, Beleg für die Vorschau, Art)
VORLAGEN = {
	"angebot_pdf.html": ("Angebot", "Angebot", "html"),
	"auftragsbestaetigung_pdf.html": ("Auftragsbestätigung", "Auftrag", "html"),
	"lieferschein_pdf.html": ("Lieferschein", "Lieferschein", "html"),
	"rechnung_pdf.html": ("Rechnung", "Rechnung", "html"),
	"mahnung_pdf.html": ("Mahnung", "Mahnung", "html"),
	"beleg_posten.html": ("Positionstabelle (Angebot, Auftragsbestätigung)", "Angebot", "html"),
	"beleg_kopf.html": ("Kopf aller Belege", "Angebot", "html"),
	"beleg_fuss.html": ("Fuß aller Belege", "Angebot", "html"),
	"beleg_basis.css": ("Gestaltung Positionen und Summen (CSS)", "Angebot", "css"),
	"beleg_rahmen.css": ("Gestaltung Seite, Kopf und Fuß (CSS)", "Angebot", "css"),
	"briefbogen_muster.html": ("Briefbogen-Muster (Firma)", "Firma", "html"),
}


def pruefe_datei(datei):
	if datei not in VORLAGEN:
		frappe.throw(_("Die Vorlage {0} gibt es nicht.").format(datei))
	return datei


def pfad(datei):
	return frappe.get_app_path("cnc_one", "templates", pruefe_datei(datei))


def aus_code(datei):
	with open(pfad(datei), encoding="utf-8") as f:
		return f.read()


def pruefsumme(text):
	return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def geaendert(datei):
	"""Der in der Oberfläche geänderte Stand oder None."""
	if not frappe.db.exists("Druckvorlage", datei):
		return None
	return frappe.db.get_value("Druckvorlage", datei, "inhalt") or None


def lesen(datei):
	"""Der gültige Stand einer Vorlage: Probe (Vorschau) > geändert in der Oberfläche > Datei im Code."""
	probe = getattr(frappe.local, "cnc_vorlagen_probe", None) or {}
	if datei in probe:
		return probe[datei]
	return geaendert(datei) or aus_code(datei)


@contextmanager
def probe(datei, inhalt):
	"""Für die Vorschau: in diesem Block gilt `inhalt` als Stand der Vorlage."""
	alt = getattr(frappe.local, "cnc_vorlagen_probe", None)
	frappe.local.cnc_vorlagen_probe = {**(alt or {}), datei: inhalt}
	try:
		yield
	finally:
		frappe.local.cnc_vorlagen_probe = alt


def syntax_fehler(datei, inhalt):
	"""Text des Fehlers mit Zeile, wenn das Jinja-HTML nicht übersetzt werden kann; sonst ''."""
	if VORLAGEN[pruefe_datei(datei)][2] != "html":
		return ""
	from jinja2 import TemplateSyntaxError

	try:
		frappe.get_jenv().parse(inhalt or "")
	except TemplateSyntaxError as e:
		return _("Zeile {0}: {1}").format(e.lineno, e.message)
	return ""


def in_datei_schreiben(datei, inhalt):
	with open(pfad(datei), "w", encoding="utf-8", newline="\n") as f:
		f.write(inhalt)
