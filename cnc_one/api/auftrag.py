"""Aufträge. Entstehen aus einem gesendeten Angebot, der Server rechnet Preise und Summen selbst."""

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import arbeitsgang_ui, kunde_ui, nur_cnc
from cnc_one.logic.beleg import position_fuer_auftrag
from cnc_one.logic.daten import als_json, datum, iso
from cnc_one.logic.kalkulation import berechne
from cnc_one.logic.serien import STANDARD_STELLEN, bereich, hoechste, ueberschneidet


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
				"serienVon": p.serien_von or None,
				"serienBis": p.serien_bis or None,
				"serienStellen": p.serien_stellen or STANDARD_STELLEN,
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

	`positionen`: Liste mit { angebotKey, optionId, menge, termin, kostenAus: [Bezeichnung], arbeitsgaenge, planSpeichern, serienStart }.
	Staffel, Menge und abgewählte Kostenzeilen wählt der Benutzer, Preise und Summen rechnet der Server.
	Bei Bauteilen mit Seriennummern ist `serienStart` Pflicht: die Nummern laufen ab dort fortlaufend, die höchste wird am Bauteil vermerkt.
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
	serien = []
	vergeben = []
	for p in positionen:
		ap = next((z for z in ang.positionen if z.position_key == p.get("angebotKey")), None)
		if not ap:
			frappe.throw(_("Die Angebotsposition {0} gibt es nicht.").format(p.get("angebotKey")))
		teil = als_json(ap.kalkulation)
		r = position_fuer_auftrag(teil, berechne(teil), p.get("optionId"), p.get("menge"), p.get("kostenAus") or [])
		key = f"{ap.position_key}-{frappe.generate_hash(length=6)}"
		plan = p.get("arbeitsgaenge") or []
		von, bis, stellen = serienbereich(ap, teil, p, r["menge"], vergeben)
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
			"serien_von": von or None,
			"serien_bis": bis or None,
			"serien_stellen": stellen if von else None,
		})
		if von and ap.bauteil:
			serien.append((ap.bauteil, bis))
		for k in r["kosten"]:
			doc.append("kosten", {"position_key": key, "bezeichnung": k["label"], "betrag": k["betrag"]})
		if p.get("planSpeichern") and plan and (ap.teilenummer or "").strip():
			zu_speichern.append((ap, plan))
	doc.insert()
	for bauteil, bis in serien:
		# die höchste vergebene Nummer am Bauteil festhalten, der nächste Auftrag macht dort weiter
		letzte = frappe.db.get_value("Bauteil", bauteil, "letzte_seriennummer") or 0
		if bis > letzte:
			frappe.db.set_value("Bauteil", bauteil, "letzte_seriennummer", bis)
	for ap, plan in zu_speichern:
		bauteil_api.plan_setzen(ang.kunde, ap.teilenummer, plan, ap.bezeichnung, ap.zeichnungsnr, ap.material)
	return auftrag_ui(doc)


def mit_serien(ap, teil):
	"""Hat das Bauteil dieser Angebotsposition Seriennummern? Maßgeblich ist das Bauteil, sonst die Angabe in der Workbench."""
	if ap.bauteil:
		return bool(frappe.db.get_value("Bauteil", ap.bauteil, "seriennummern"))
	return bool(teil.get("seriennummern"))


def serienbereich(ap, teil, p, menge, vergeben):
	"""Bereich (von, bis, Stellen) der Position oder (0, 0, 0) ohne Seriennummern.

	Seriennummern bestehen nur aus Ziffern und haben immer die am Bauteil festgelegte Stellenzahl (Standard 4: 0001).
	Geprüft wird auch, dass sich nichts mit früheren Aufträgen überschneidet."""
	if not mit_serien(ap, teil):
		return 0, 0, 0
	stellen = (frappe.db.get_value("Bauteil", ap.bauteil, "serien_stellen") if ap.bauteil else 0) or STANDARD_STELLEN
	text = str(p.get("serienStart") or "").strip()
	if not text:
		frappe.throw(_("Für {0} bitte die erste Seriennummer eingeben.").format(ap.bezeichnung or ap.teilenummer))
	if not text.isdigit():
		frappe.throw(_("Seriennummern bestehen nur aus Ziffern, zum Beispiel {0}.").format("1".zfill(stellen)))
	start = int(text)
	if start <= 0:
		frappe.throw(_("Die erste Seriennummer muss größer als null sein."))
	neu = bereich(start, menge)
	if neu[1] > hoechste(stellen):
		frappe.throw(_("Die Seriennummern {0} bis {1} passen nicht in {2} Stellen.").format(str(neu[0]).zfill(stellen), neu[1], stellen))
	if ap.bauteil:
		bestehend = frappe.db.sql(
			"""select p.serien_von, p.serien_bis, p.parent from `tabAuftragsposition` p
			join `tabAuftrag` a on a.name = p.parent
			where p.bauteil = %s and p.serien_von > 0 and a.status != 'Storniert'""",
			(ap.bauteil,),
		)
		for von, bis, auftrag in bestehend:
			if ueberschneidet(neu, (von, bis)):
				frappe.throw(_("Die Seriennummern {0} bis {1} überschneiden sich mit {2} ({3} bis {4}).").format(neu[0], neu[1], auftrag, von, bis))
		for b, vb in vergeben:
			if b == ap.bauteil and ueberschneidet(neu, vb):
				frappe.throw(_("Die Seriennummern {0} bis {1} überschneiden sich mit einer anderen Position dieses Auftrags.").format(neu[0], neu[1]))
		vergeben.append((ap.bauteil, neu))
	return neu[0], neu[1], stellen


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
