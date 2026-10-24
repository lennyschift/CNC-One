"""Firmendaten für Belege: Anschrift, Steuer, Bankverbindungen, Texte. Gibt es genau einmal."""

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic.rechnung import iban_formatiert, iban_gueltig

FIRMA_PFLEGE = ("CNC Admin", "CNC Buchhaltung", "System Manager")


def firma_ui(d=None):
	d = d or frappe.get_single("Firma")
	ort = " ".join(x for x in (d.plz, d.ort) if x)
	return {
		"firmenname": d.firmenname or "",
		"rechtsform": d.rechtsform or "",
		"strasse": d.strasse or "", "plz": d.plz or "", "ort": d.ort or "", "land": d.land or "",
		"adresse": [z for z in (d.strasse, ort) if z],
		"telefon": d.telefon or "", "email": d.email or "", "web": d.web or "",
		"steuernummer": d.steuernummer or "", "ustId": d.ust_id or "",
		"handelsregister": d.handelsregister or "", "geschaeftsfuehrer": d.geschaeftsfuehrer or "",
		"banken": [{"bezeichnung": b.bezeichnung or "", "iban": iban_formatiert(b.iban), "bic": b.bic or ""} for b in d.banken],
		"rechnungText": d.rechnung_text or "", "rechnungFusstext": d.rechnung_fusstext or "",
		"zahlungszielTage": d.zahlungsziel_tage or 14,
		"mahnfristTage": d.mahnfrist_tage or 7,
		"mahngebuehr": d.mahngebuehr or 0,
	}


@frappe.whitelist(methods=["POST"])
def holen():
	nur_cnc()
	return firma_ui()


@frappe.whitelist(methods=["POST"])
def speichern(daten):
	"""Speichert die Firmendaten. IBANs werden auf eine gültige Prüfziffer geprüft."""
	frappe.only_for(FIRMA_PFLEGE)
	if isinstance(daten, str):
		daten = frappe.parse_json(daten)
	d = frappe.get_single("Firma")
	if not (daten.get("firmenname") or "").strip():
		frappe.throw(_("Bitte den Namen der Firma eingeben."))
	zuordnung = {
		"firmenname": "firmenname", "rechtsform": "rechtsform", "strasse": "strasse", "plz": "plz", "ort": "ort", "land": "land",
		"telefon": "telefon", "email": "email", "web": "web", "steuernummer": "steuernummer", "ustId": "ust_id",
		"handelsregister": "handelsregister", "geschaeftsfuehrer": "geschaeftsfuehrer",
		"rechnungText": "rechnung_text", "rechnungFusstext": "rechnung_fusstext",
	}
	for ui, feld in zuordnung.items():
		if ui in daten:
			d.set(feld, (daten[ui] or "").strip())
	if "zahlungszielTage" in daten:
		d.zahlungsziel_tage = max(0, int(daten["zahlungszielTage"] or 0))
	if "mahnfristTage" in daten:
		d.mahnfrist_tage = max(0, int(daten["mahnfristTage"] or 0))
	if "mahngebuehr" in daten:
		d.mahngebuehr = max(0, float(daten["mahngebuehr"] or 0))
	if "banken" in daten:
		d.set("banken", [])
		for b in daten["banken"] or []:
			iban = "".join((b.get("iban") or "").split()).upper()
			if not iban and not (b.get("bezeichnung") or "").strip():
				continue
			if not iban_gueltig(iban):
				frappe.throw(_("Die IBAN {0} ist nicht gültig (Länge oder Prüfziffer). Bitte prüfen.").format(b.get("iban") or ""))
			d.append("banken", {"bezeichnung": (b.get("bezeichnung") or "").strip() or iban, "iban": iban, "bic": (b.get("bic") or "").strip().upper()})
	d.save()
	return firma_ui(d)
