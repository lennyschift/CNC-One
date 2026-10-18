"""Lager, bewusst einfach: Bestand je Bauteil in zwei Lagergruppen, geführt über unveränderliche Buchungen.

Das Fertigbauteil Lager bekommt die gefertigte Menge aus der Fertigung (Zugang) und gibt sie mit dem Lieferschein wieder ab.
Der Bestand darf negativ werden: ein Lieferschein, der vor der Fertigung angelegt wird, bucht ab, und sobald die Fertigung
einbucht, ist es ausgeglichen.
"""

import frappe
from frappe.utils import now_datetime

FERTIG = "Fertigbauteil Lager"
ROHMATERIAL = "Rohmaterial Lager"


def buchen(bauteil, menge, art, lager=FERTIG, **bezug):
	"""Legt eine Lagerbuchung an (plus = Zugang, minus = Abgang). Ohne Bauteil oder Menge passiert nichts."""
	menge = int(menge or 0)
	if not bauteil or not menge:
		return None
	doc = frappe.get_doc({
		"doctype": "Lagerbuchung", "zeit": now_datetime(), "lager": lager, "bauteil": bauteil, "menge": menge,
		"art": art, "benutzer": frappe.session.user, **bezug,
	})
	doc.insert(ignore_permissions=True)
	return doc


def bestand(bauteil, lager=FERTIG):
	return int(frappe.db.sql("select coalesce(sum(menge), 0) from `tabLagerbuchung` where bauteil = %s and lager = %s", (bauteil, lager))[0][0])


def fertigung_abgleichen(fb):
	"""Bringt das Lager auf den Stand der Fertigung: gebucht wird die Differenz zur bisher eingebuchten Menge.

	Fertig ist, was alle Arbeitsgänge durchlaufen hat. Wird in der Fertigung eine Buchung storniert, gibt es eine Gegenbuchung."""
	if not fb.bauteil:
		return None
	ist = int(frappe.db.sql(
		"select coalesce(sum(menge), 0) from `tabLagerbuchung` where fertigungsbauteil = %s and art = 'Fertigung'", (fb.name,)
	)[0][0])
	diff = int(fb.produziert or 0) - ist
	if diff:
		return buchen(fb.bauteil, diff, "Fertigung", fertigungsbauteil=fb.name, auftrag=fb.auftrag)
	return None
