"""Aufträge. Entstehen aus einem gesendeten Angebot, der Server rechnet Preise und Summen selbst."""

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import arbeitsgang_ui, kunde_ui, nur_cnc
from cnc_one.logic.beleg import position_fuer_auftrag
from cnc_one.logic.daten import als_json, datum, iso
from cnc_one.logic.kalkulation import berechne


def auftrag_ui(d):
	"""Der Auftrag in der Form, die die Oberfläche erwartet."""
	kunde = frappe.get_doc("Kunde", d.kunde) if d.kunde else None
	return {
		"id": d.name,
		"angebotId": d.angebot,
		"kundeName": d.kunde_name or "",
		"kunde": kunde_ui(kunde) if kunde else None,
		"kundenbestellnr": d.kundenbestellnr or "",
		"datum": iso(d.creation),
		"status": d.status,
		"netto": d.netto or 0,
		"positionen": [
			{
				"key": p.position_key,
				"angebotKey": p.angebot_position_key or "",
				"teil": {
					"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "",
					"material": p.material or "", "vorschaubild": "",
				},
				"menge": p.menge,
				"einzelpreis": p.einzelpreis or 0,
				"staffelMenge": p.staffel_menge or None,
				"termin": datum(p.liefertermin),
				"kosten": [{"label": k.bezeichnung, "betrag": k.betrag or 0} for k in d.kosten if k.position_key == p.position_key],
				"summe": p.summe or 0,
				"arbeitsgaenge": als_json(p.arbeitsplan) if p.arbeitsplan else [],
			}
			for p in d.positionen
		],
	}


def alle_ui():
	namen = frappe.get_list("Auftrag", pluck="name", order_by="creation desc", limit_page_length=0)
	return [auftrag_ui(frappe.get_doc("Auftrag", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


@frappe.whitelist(methods=["POST"])
def aus_angebot(angebot, kundenbestellnr="", positionen=None):
	"""Legt einen Auftrag aus einem gesendeten Angebot an.

	`positionen`: Liste mit { angebotKey, optionId, menge, termin, kostenAus: [Bezeichnung], arbeitsgaenge, planSpeichern }.
	Staffel, Menge und abgewählte Kostenzeilen wählt der Benutzer, Preise und Summen rechnet der Server.
	"""
	nur_cnc()
	if isinstance(positionen, str):
		positionen = frappe.parse_json(positionen)
	if not positionen:
		frappe.throw(_("Der Auftrag braucht mindestens eine Position."))
	ang = frappe.get_doc("Angebot", angebot)
	if ang.status != "Gesendet":
		frappe.throw(_("Nur aus einem gesendeten Angebot lässt sich ein Auftrag anlegen."))

	doc = frappe.new_doc("Auftrag")
	doc.kunde = ang.kunde
	doc.angebot = ang.name
	doc.status = "Offen"
	doc.kundenbestellnr = (kundenbestellnr or "").strip()
	zu_speichern = []
	for p in positionen:
		ap = next((z for z in ang.positionen if z.position_key == p.get("angebotKey")), None)
		if not ap:
			frappe.throw(_("Die Angebotsposition {0} gibt es nicht.").format(p.get("angebotKey")))
		teil = als_json(ap.kalkulation)
		r = position_fuer_auftrag(teil, berechne(teil), p.get("optionId"), p.get("menge"), p.get("kostenAus") or [])
		key = f"{ap.position_key}-{frappe.generate_hash(length=6)}"
		plan = p.get("arbeitsgaenge") or []
		doc.append("positionen", {
			"position_key": key,
			"angebot_position_key": ap.position_key,
			"bauteil": ap.bauteil or None,
			"teilenummer": ap.teilenummer,
			"bezeichnung": ap.bezeichnung,
			"zeichnungsnr": ap.zeichnungsnr,
			"material": ap.material,
			"menge": r["menge"],
			"einzelpreis": r["einzelpreis"],
			"staffel_menge": r["staffelMenge"],
			"liefertermin": p.get("termin") or None,
			"arbeitsplan": frappe.as_json(plan),
		})
		for k in r["kosten"]:
			doc.append("kosten", {"position_key": key, "bezeichnung": k["label"], "betrag": k["betrag"]})
		if p.get("planSpeichern") and plan and (ap.teilenummer or "").strip():
			zu_speichern.append((ap, plan))
	doc.insert()
	for ap, plan in zu_speichern:
		bauteil_api.plan_setzen(ang.kunde, ap.teilenummer, plan, ap.bezeichnung, ap.zeichnungsnr, ap.material)
	return auftrag_ui(doc)


def plan_fuer_position(auftrag, pos):
	"""Arbeitsplan einer Auftragsposition: im Auftrag gepflegt, sonst am Bauteil gespeichert, sonst aus dem Angebot, sonst leer."""
	eigener = als_json(pos.arbeitsplan) if pos.arbeitsplan else []
	if eigener:
		return eigener
	if pos.bauteil:
		am_bauteil = [arbeitsgang_ui(r) for r in frappe.get_doc("Bauteil", pos.bauteil).arbeitsplan]
		if am_bauteil:
			return am_bauteil
	ang = frappe.get_doc("Angebot", auftrag.angebot)
	ap = next((z for z in ang.positionen if z.position_key == pos.angebot_position_key), None)
	return (als_json(ap.kalkulation).get("arbeitsgaenge") or []) if ap else []
