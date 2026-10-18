"""Fertigungsbauteile. Die Buchungsregeln stehen im Doctype-Controller und in logic/fertigung.py,
hier liegen nur die Schnittstellen und die Umrechnung in die Form der Oberfläche."""

import frappe
from frappe import _

from cnc_one.api import auftrag as auftrag_api
from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import arbeitsgang_ui, arbeitsgang_zeile, nur_cnc, typ_db, typ_ui
from cnc_one.logic.daten import datum, iso

FERTIGUNG_ROLLEN = ("CNC Admin", "CNC Vertrieb", "CNC Fertigung", "System Manager")


def _nur_fertigung():
	frappe.only_for(FERTIGUNG_ROLLEN)


def fb_ui(d):
	"""Das Fertigungsbauteil in der Form, die die Oberfläche erwartet (Sendungen verschachtelt im Arbeitsgang)."""
	ags = []
	for a in d.arbeitsgaenge:
		z = arbeitsgang_ui(a)
		z.update({
			"bestellung": a.bestellung or "",
			"status": a.status,
			"gebucht": a.gebucht or 0,
			"sendungen": [
				{
					"id": s.name, "menge": s.menge, "datumWeg": datum(s.datum_weg), "datumZurueck": datum(s.datum_zurueck),
					"abgehakt": bool(s.abgehakt),
				}
				for s in d.sendungen if s.ag_id == a.ag_id
			],
		})
		ags.append(z)
	return {
		"id": d.name,
		"auftragId": d.auftrag,
		"auftragPosKey": d.auftragsposition_key or "",
		"kundeId": d.kunde or "",
		"kundeName": d.kunde_name or "",
		"teil": {
			"name": d.bezeichnung or "", "teilenummer": d.teilenummer or "", "zeichnungsnr": d.zeichnungsnr or "",
			"material": d.material or "", "vorschaubild": "",
		},
		"menge": d.menge,
		"termin": datum(d.termin),
		"prioritaet": d.prioritaet,
		"status": d.status,
		"arbeitsgaenge": ags,
		"buchungen": [
			{"id": b.name, "zeit": iso(b.zeit), "agId": b.ag_id, "agName": b.ag_name or "", "menge": b.menge, "benutzer": b.benutzer or "", "auto": bool(b.auto)}
			for b in sorted(d.buchungen, key=lambda x: (x.zeit, x.idx), reverse=True)
		],
		"rohmaterial": {
			"werkstoff": d.roh_werkstoff or "", "charge": d.roh_charge or "", "lagerplatz": d.roh_lagerplatz or "",
			"info": d.roh_info or "", "verbrauchtMm": d.roh_verbraucht_mm or 0,
		},
		"notizen": {"pruefmasse": d.pruefmasse or "", "bemerkungen": d.bemerkungen or ""},
	}


def alle_ui():
	namen = frappe.get_list("Fertigungsbauteil", pluck="name", order_by="creation asc", limit_page_length=0)
	return [fb_ui(frappe.get_doc("Fertigungsbauteil", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


def _antwort(doc):
	"""Antwort jeder Änderung: das Fertigungsbauteil und der (evtl. geänderte) Status seines Auftrags."""
	return {"fb": fb_ui(doc), "auftragStatus": frappe.db.get_value("Auftrag", doc.auftrag, "status") if doc.auftrag else None}


def _laden(id):
	_nur_fertigung()
	doc = frappe.get_doc("Fertigungsbauteil", id)
	doc.check_permission("write")
	return doc


# ----------------------------------------------------------------- Starten
@frappe.whitelist(methods=["POST"])
def starten(auftrag):
	"""Legt je Auftragsposition ein Fertigungsbauteil an. Der Arbeitsplan darf fehlen und kommt dann später in der Fertigung."""
	_nur_fertigung()
	auf = frappe.get_doc("Auftrag", auftrag)
	if frappe.db.exists("Fertigungsbauteil", {"auftrag": auftrag}):
		frappe.throw(_("Für diesen Auftrag läuft die Fertigung schon."))
	ohne_plan = 0
	for pos in auf.positionen:
		plan = auftrag_api.plan_fuer_position(auf, pos)
		if not plan:
			ohne_plan += 1
		fb = frappe.new_doc("Fertigungsbauteil")
		fb.update({
			"auftrag": auf.name, "auftragsposition_key": pos.position_key, "bauteil": pos.bauteil or None,
			"kunde": auf.kunde, "kunde_name": auf.kunde_name, "teilenummer": pos.teilenummer,
			"bezeichnung": pos.bezeichnung, "zeichnungsnr": pos.zeichnungsnr, "material": pos.material,
			"menge": pos.menge, "termin": pos.liefertermin, "prioritaet": "Normal", "status": "Offen",
			"roh_werkstoff": pos.material or "",
		})
		for a in plan:
			zeile = arbeitsgang_zeile({**a, "id": None})
			fb.append("arbeitsgaenge", {**zeile, "status": "Offen", "gebucht": 0})
		fb.insert(ignore_permissions=True)
	return {
		"auftrag": auftrag_api.auftrag_ui(frappe.get_doc("Auftrag", auftrag)),
		"fertigung": [fb_ui(frappe.get_doc("Fertigungsbauteil", n)) for n in frappe.get_all("Fertigungsbauteil", filters={"auftrag": auftrag}, pluck="name", order_by="creation asc")],
		"ohnePlan": ohne_plan,
	}


# ----------------------------------------------------------------- Buchen
@frappe.whitelist(methods=["POST"])
def buchen(id, ag_id, menge):
	doc = _laden(id)
	nachgeholt = doc.buchen(ag_id, menge)
	doc.save()
	return {**_antwort(doc), "nachgeholt": nachgeholt, "ueberproduktion": doc.ueberproduktion}


@frappe.whitelist(methods=["POST"])
def buchung_loeschen(id, buchung):
	doc = _laden(id)
	doc.buchung_loeschen(buchung)
	doc.save()
	return _antwort(doc)


# ----------------------------------------------------------------- Arbeitsplan
@frappe.whitelist(methods=["POST"])
def arbeitsgang_hinzu(id, typ="intern"):
	doc = _laden(id)
	doc.arbeitsgaenge_hinzu([arbeitsgang_zeile({"typ": typ, "name": ""})])
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def vorlage_anwenden(id, vorlage):
	doc = _laden(id)
	v = frappe.get_doc("Arbeitsplan Vorlage", vorlage)
	zeilen = [arbeitsgang_zeile({**arbeitsgang_ui(r), "id": None}) for r in v.arbeitsgaenge]
	doc.arbeitsgaenge_hinzu(zeilen)
	doc.save()
	return {**_antwort(doc), "hinzugefuegt": len(zeilen)}


@frappe.whitelist(methods=["POST"])
def arbeitsgang_weg(id, ag_id):
	doc = _laden(id)
	doc.arbeitsgang_weg(ag_id)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def arbeitsgang_verschieben(id, ag_id, richtung):
	doc = _laden(id)
	doc.arbeitsgang_verschieben(ag_id, richtung)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def plan_am_bauteil_speichern(id):
	"""Speichert die Arbeitsgänge dieses Fertigungsbauteils als Arbeitsplan am Bauteil (gilt für künftige Angebote und Aufträge)."""
	doc = _laden(id)
	plan = [arbeitsgang_ui(a) for a in doc.arbeitsgaenge]
	b = bauteil_api.plan_setzen(doc.kunde, doc.teilenummer, plan, doc.bezeichnung, doc.zeichnungsnr, doc.material)
	if not b:
		frappe.throw(_("Dafür braucht das Bauteil einen Kunden und eine Teilenummer."))
	return {"bauteil": bauteil_api.bauteil_ui(b)}


# ----------------------------------------------------------------- Sendungen
@frappe.whitelist(methods=["POST"])
def sendung_anlegen(id, ag_id, menge=None):
	doc = _laden(id)
	doc.sendung_anlegen(ag_id, menge)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def sendung_weg(id, ag_id, sendung):
	doc = _laden(id)
	doc.sendung_weg(ag_id, sendung)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def sendung_zurueck(id, ag_id, sendung):
	doc = _laden(id)
	doc.sendung_zurueck(ag_id, sendung)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def sendung_loeschen(id, ag_id, sendung):
	doc = _laden(id)
	doc.sendung_loeschen(ag_id, sendung)
	doc.save()
	return _antwort(doc)


# ----------------------------------------------------------------- Status und Felder
@frappe.whitelist(methods=["POST"])
def status_setzen(id, status):
	doc = _laden(id)
	doc.status_setzen(status)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def felder_speichern(id, felder):
	"""Speichert die frei bearbeitbaren Felder. Buchungsstand, Status und Sendungen ändert das nicht.

	`felder`: { prioritaet, termin, rohmaterial: {...}, notizen: {...}, arbeitsgaenge: [{ id, name, maschine, satz, ruestMin, stueckMin, lieferant, fremdProStk, fremdEinmal, bestellung }] }
	"""
	doc = _laden(id)
	if isinstance(felder, str):
		felder = frappe.parse_json(felder)
	if "prioritaet" in felder:
		doc.prioritaet = felder["prioritaet"]
	if "termin" in felder:
		doc.termin = felder["termin"] or None
	roh = felder.get("rohmaterial")
	if roh:
		doc.roh_werkstoff = roh.get("werkstoff", doc.roh_werkstoff)
		doc.roh_charge = roh.get("charge", doc.roh_charge)
		doc.roh_lagerplatz = roh.get("lagerplatz", doc.roh_lagerplatz)
		doc.roh_info = roh.get("info", doc.roh_info)
		doc.roh_verbraucht_mm = roh.get("verbrauchtMm", doc.roh_verbraucht_mm) or 0
	notizen = felder.get("notizen")
	if notizen:
		doc.pruefmasse = notizen.get("pruefmasse", doc.pruefmasse)
		doc.bemerkungen = notizen.get("bemerkungen", doc.bemerkungen)
	for neu in felder.get("arbeitsgaenge") or []:
		ag = next((a for a in doc.arbeitsgaenge if a.ag_id == neu.get("id")), None)
		if not ag:
			continue
		ag.bezeichnung = (neu.get("name") or "").strip()
		ag.maschine = neu.get("maschine") or None
		ag.satz = neu.get("satz") or 0
		ag.ruest_min = neu.get("ruestMin") or 0
		ag.stueck_min = neu.get("stueckMin") or 0
		ag.lieferant = neu.get("lieferant") or None
		ag.fremd_pro_stk = neu.get("fremdProStk") or 0
		ag.fremd_einmal = neu.get("fremdEinmal") or 0
		ag.bestellung = neu.get("bestellung") or ""
	doc.save()
	return _antwort(doc)
