"""Kopf und Fuß aller Beleg-PDFs (Angebot, Rechnung, Lieferschein, Mahnung) an einer Stelle.

Kopf: das Bild „Kopfzeile der Belege“ aus den Firmendaten, nur auf Seite 1; ohne Bild der Firmenname mit Anschrift.
Fuß: auf jeder Seite ganz unten in drei Spalten (Anschrift mit Register und USt-ID; Telefon, Mail, Web, Geschäftsführer
mit Symbol; die Banken untereinander mit IBAN), darunter die Seitenzahl.
Gestaltet wird in templates/beleg_kopf.html, beleg_fuss.html, beleg_rahmen.css und (Positionen, Summen) beleg_basis.css;
der Rahmen bringt das Basis-CSS mit, die Vorlagen ergänzen nur ihre Besonderheiten.
"""

import base64
import re

import frappe

# Symbole vor den Kontaktangaben im Fuß (Lucide, ISC-Lizenz), grau wie der Text
_SVG = {
	"telefon": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
	"mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
	"web": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
	"person": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
}


def _symbol(pfade):
	svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{pfade}</svg>'
	return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


SYMBOLE = {k: _symbol(v) for k, v in _SVG.items()}


def _datei(name):
	with open(frappe.get_app_path("cnc_one", "templates", name), encoding="utf-8") as f:
		return f.read()


def _web(url):
	"""Webseite ohne https:// und Schrägstrich am Ende, wie man sie liest: www.beispiel.de"""
	return re.sub(r"^https?://", "", (url or "").strip()).rstrip("/")


def rahmen(f):
	"""{css, kopf, fuss} für die Vorlage. `f` sind die Firmendaten des Belegs (bei der Rechnung die festgeschriebenen);
	die Kopfzeile kommt immer aus den aktuellen Firmendaten. Der Fuß muss im HTML vor dem Inhalt stehen."""
	from cnc_one.api.angebot import _bild

	bild = _bild(frappe.db.get_single_value("Firma", "briefkopf"))
	return {
		"css": _datei("beleg_basis.css") + _datei("beleg_rahmen.css"),
		"kopf": frappe.render_template(_datei("beleg_kopf.html"), {"f": f, "bild": bild}),
		"fuss": frappe.render_template(_datei("beleg_fuss.html"), {"f": {**f, "web": _web(f.get("web"))}, "symbol": SYMBOLE}),
	}


def muster_html(f):
	"""Zwei Seiten Blindtext im Rahmen der Belege: Kopf nur auf Seite 1, Fuß auf beiden."""
	return frappe.render_template(_datei("briefbogen_muster.html"), {"f": f, "rahmen": rahmen(f), "datum": frappe.utils.formatdate(frappe.utils.nowdate(), "dd.MM.yyyy")})
