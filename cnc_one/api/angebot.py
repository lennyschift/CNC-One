"""Angebote. Die Workbench arbeitet auf einem gespeicherten Angebot im Status Entwurf."""

import json

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import kunde_ui, nur_cnc


def _iso(wert):
	return get_datetime(wert).isoformat() if wert else None


def _json(wert):
	if wert in (None, ""):
		return {}
	return json.loads(wert) if isinstance(wert, str) else wert


def angebot_ui(d):
	"""Das Angebot in der Form, die die Oberfläche erwartet."""
	kunde = frappe.get_doc("Kunde", d.kunde) if d.kunde else None
	return {
		"id": d.name,
		"status": d.status,
		"erstellt": _iso(d.creation),
		"versandt": _iso(d.versandt_am),
		"geaendert": _iso(d.modified),
		"kopf": {
			"kundeId": d.kunde or "",
			"anfrageNr": d.anfrage_nr or "",
			"gueltigWochen": d.gueltig_wochen or 4,
			"lieferzeit": d.lieferzeit or "",
			"kundeName": d.kunde_name or "",
			"kunde": kunde_ui(kunde) if kunde else None,
		},
		"positionen": [
			{
				"key": z.position_key, "teil": _json(z.kalkulation), "ergebnis": _json(z.ergebnis),
				"bauteilId": z.bauteil or "", "herkunft": ("neu" if z.bauteil_neu else "bestand") if z.bauteil else "",
				"seriennummern": bool(z.bauteil and frappe.db.get_value("Bauteil", z.bauteil, "seriennummern")),
			}
			for z in d.positionen
		],
		"netto": d.netto or 0,
		"entwurfId": "",
	}


def alle_ui():
	namen = frappe.get_list("Angebot", pluck="name", order_by="creation desc", limit_page_length=0)
	return [angebot_ui(frappe.get_doc("Angebot", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


@frappe.whitelist(methods=["POST"])
def entwurf_speichern(angebot):
	"""Legt einen Entwurf an oder aktualisiert ihn. `angebot`: { id, kopf, teile } wie in der Workbench."""
	nur_cnc()
	if isinstance(angebot, str):
		angebot = frappe.parse_json(angebot)
	kopf = angebot.get("kopf") or {}
	teile = angebot.get("teile") or []

	if angebot.get("id") and frappe.db.exists("Angebot", angebot["id"]):
		doc = frappe.get_doc("Angebot", angebot["id"])
	else:
		doc = frappe.new_doc("Angebot")

	kunde = kopf.get("kundeId") or None
	if kunde and not frappe.db.exists("Kunde", kunde):
		frappe.throw(_("Der Kunde {0} gibt es nicht.").format(kunde))
	doc.kunde = kunde
	doc.anfrage_nr = kopf.get("anfrageNr") or ""
	doc.gueltig_wochen = int(kopf.get("gueltigWochen") or 4)
	doc.lieferzeit = kopf.get("lieferzeit") or ""

	# Was dieses Angebot an Bauteilen schon verknüpft hat: Position -> (Bauteil, mit diesem Angebot neu angelegt)
	alt = {z.position_key: (z.bauteil, bool(z.bauteil_neu)) for z in doc.positionen if z.bauteil}
	doc.set("positionen", [])
	behalten = set()
	for t in teile:
		zeile = doc.append("positionen", {"kalkulation": json.dumps(t, ensure_ascii=False)})
		# Bauteil des Kunden wiederfinden oder neu anlegen, sobald Kunde und Teilenummer da sind. Nie doppelt.
		b, neu = bauteil_api.fuer_position(kunde, t, alt.get(str(t.get("id"))))
		zeile.bauteil = b.name if b else None
		zeile.bauteil_neu = 1 if neu else 0
		if b:
			behalten.add(b.name)

	doc.save() if not doc.is_new() else doc.insert()
	# Bauteile, die dieses Angebot neu angelegt hatte und die nicht mehr vorkommen, wieder entfernen
	for name, neu in alt.values():
		if neu and name not in behalten:
			bauteil_api.aufraeumen(name)
	return angebot_ui(doc)


def _geladen(name):
	doc = frappe.get_doc("Angebot", name)
	doc.check_permission("write")
	return doc


@frappe.whitelist(methods=["POST"])
def senden(id):
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Entwurf":
		frappe.throw(_("Nur ein Entwurf lässt sich senden."))
	if not doc.kunde:
		frappe.throw(_("Bitte zuerst einen Kunden wählen."))
	if not doc.positionen:
		frappe.throw(_("Das Angebot enthält noch kein Bauteil."))
	doc.flags.status_wechsel = True
	doc.status = "Gesendet"
	doc.versandt_am = now_datetime()
	doc.save()
	return angebot_ui(doc)


@frappe.whitelist(methods=["POST"])
def ablehnen(id):
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Gesendet":
		frappe.throw(_("Nur ein gesendetes Angebot lässt sich als abgelehnt markieren."))
	doc.flags.status_wechsel = True
	doc.status = "Abgelehnt"
	doc.save()
	return angebot_ui(doc)


@frappe.whitelist(methods=["POST"])
def loeschen(id):
	nur_cnc()
	frappe.delete_doc("Angebot", id)
	return {"id": id}
