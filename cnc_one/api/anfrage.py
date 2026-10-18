"""Lieferantenanfragen für Fremdvergabe. Eine Anfrage geht an einen Lieferanten und enthält mehrere Positionen."""

import json

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic.daten import als_json, datum, iso


def anfrage_ui(d):
	"""Die Anfrage in der Form, die die Oberfläche erwartet."""
	antwort = None
	if d.preise or d.lieferantenangebot_nr:
		antwort = {
			"angebotsnr": d.lieferantenangebot_nr or "",
			"gueltigBis": datum(d.gueltig_bis),
			"preise": [{"posKey": z.position_key, "menge": z.menge, "proStk": z.pro_stk or 0, "einmalig": z.einmalig or 0} for z in d.preise],
		}
	return {
		"id": d.name,
		"lieferantId": d.lieferant,
		"lieferantName": d.lieferant,
		"erstellt": iso(d.creation),
		"status": d.status,
		"notiz": d.notiz or "",
		"angebotId": d.angebot,
		"kundeName": d.kunde_name or "",
		"positionen": [
			{
				"key": p.position_key,
				"teilId": p.teil_id or "",
				"teil": {
					"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "",
					"material": p.material or "", "vorschaubild": "",
				},
				"agId": p.ag_id or "",
				"agName": p.ag_name or "",
				"mengen": als_json(p.mengen) if p.mengen else [],
			}
			for p in d.positionen
		],
		"antwort": antwort,
	}


def alle_ui():
	namen = frappe.get_list("Lieferantenanfrage", pluck="name", order_by="creation desc", limit_page_length=0)
	return [anfrage_ui(frappe.get_doc("Lieferantenanfrage", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


def _mengen(werte):
	return sorted({int(m) for m in (werte or []) if int(m or 0) > 0})


@frappe.whitelist(methods=["POST"])
def anlegen(angebot, lieferanten, positionen, notiz=""):
	"""Legt je Lieferant eine Anfrage mit allen Positionen an und liefert die neuen Anfragen.

	`positionen`: [{ teilId, teil: {name, teilenummer, zeichnungsnr, material}, agId, agName, mengen }]
	"""
	nur_cnc()
	if isinstance(lieferanten, str):
		lieferanten = frappe.parse_json(lieferanten)
	if isinstance(positionen, str):
		positionen = frappe.parse_json(positionen)
	if not lieferanten:
		frappe.throw(_("Bitte mindestens einen Lieferanten wählen."))
	if not positionen:
		frappe.throw(_("Bitte mindestens eine Position wählen."))
	ang = frappe.get_doc("Angebot", angebot)
	for l in lieferanten:
		if not frappe.db.exists("Lieferant", l):
			frappe.throw(_("Den Lieferanten {0} gibt es nicht.").format(l))

	zeilen = []
	for p in positionen:
		teil = p.get("teil") or {}
		mengen = _mengen(p.get("mengen"))
		if not mengen:
			frappe.throw(_("Jede Position braucht mindestens eine Menge."))
		zeilen.append({
			"position_key": f"{p.get('teilId') or ''}:{p.get('agId') or ''}",
			"teil_id": p.get("teilId") or "",
			"bauteil": bauteil_api.finden(ang.kunde, teil.get("teilenummer")),
			"teilenummer": teil.get("teilenummer") or "",
			"bezeichnung": teil.get("name") or "",
			"zeichnungsnr": teil.get("zeichnungsnr") or "",
			"material": teil.get("material") or "",
			"ag_id": p.get("agId") or "",
			"ag_name": p.get("agName") or "",
			"mengen": json.dumps(mengen),
		})

	neu = []
	for l in lieferanten:
		doc = frappe.new_doc("Lieferantenanfrage")
		doc.lieferant = l
		doc.angebot = ang.name
		doc.status = "Gesendet"
		doc.notiz = (notiz or "").strip()
		for z in zeilen:
			doc.append("positionen", dict(z))
		doc.insert()
		neu.append(anfrage_ui(doc))
	return neu


def _geladen(id):
	doc = frappe.get_doc("Lieferantenanfrage", id)
	doc.check_permission("write")
	return doc


@frappe.whitelist(methods=["POST"])
def antwort_erfassen(id, antwort):
	"""Erfasst das Angebot des Lieferanten: Nummer, Gültigkeit und Preise je Position und Menge."""
	nur_cnc()
	if isinstance(antwort, str):
		antwort = frappe.parse_json(antwort)
	preise = [z for z in (antwort.get("preise") or [])]
	if not any((z.get("proStk") or 0) > 0 or (z.get("einmalig") or 0) > 0 for z in preise):
		frappe.throw(_("Bitte mindestens einen Preis eintragen."))
	doc = _geladen(id)
	doc.lieferantenangebot_nr = (antwort.get("angebotsnr") or "").strip()
	doc.gueltig_bis = antwort.get("gueltigBis") or None
	doc.set("preise", [])
	for z in preise:
		doc.append("preise", {
			"position_key": z.get("posKey"), "menge": int(z.get("menge") or 0),
			"pro_stk": z.get("proStk") or 0, "einmalig": z.get("einmalig") or 0,
		})
	doc.status = "Angebot erhalten"
	doc.save()
	return anfrage_ui(doc)


@frappe.whitelist(methods=["POST"])
def absagen(id):
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Gesendet":
		frappe.throw(_("Nur eine gesendete Anfrage lässt sich als abgesagt markieren."))
	doc.status = "Abgesagt"
	doc.save()
	return anfrage_ui(doc)
