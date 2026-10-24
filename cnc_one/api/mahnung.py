"""Mahnwesen: überfällige Rechnungen, Mahnungen in drei Stufen (Zahlungserinnerung, 1. Mahnung, 2. Mahnung)."""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from cnc_one.api.firma import firma_ui
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic.daten import datum, iso
from cnc_one.logic.rechnung import MAHNSTUFEN, mahntext, naechste_mahnstufe, tage_ueberfaellig

BUCHHALTUNG = ("CNC Admin", "CNC Buchhaltung", "System Manager")
AKTIV = ("Angelegt", "Versendet", "Erledigt")


def mahnung_ui(m):
	r = frappe.db.get_value("Rechnung", m.rechnung, ["rechnungsnummer", "rechnungsdatum", "brutto", "rechnungsadresse", "auftrag"], as_dict=True) or {}
	return {
		"id": m.name,
		"rechnungId": m.rechnung,
		"rechnungNummer": r.get("rechnungsnummer") or "",
		"rechnungsdatum": datum(r.get("rechnungsdatum")),
		"rechnungBrutto": r.get("brutto") or 0,
		"auftragId": r.get("auftrag") or "",
		"kundeId": m.kunde or "",
		"kundeName": m.kunde_name or "",
		"adresse": [z for z in (r.get("rechnungsadresse") or "").split("\n") if z],
		"stufe": m.stufe,
		"status": m.status,
		"datum": datum(m.datum),
		"fristBis": datum(m.frist_bis),
		"offenerBetrag": m.offener_betrag or 0,
		"gebuehr": m.gebuehr or 0,
		"text": m.text or "",
		"versandtAm": datum(m.versandt_am),
		"erstellt": iso(m.creation),
		"firma": firma_ui(),
	}


def alle_ui():
	namen = frappe.get_list("Mahnung", pluck="name", order_by="creation desc", limit_page_length=0)
	return [mahnung_ui(frappe.get_doc("Mahnung", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


@frappe.whitelist(methods=["POST"])
def vorschlag():
	"""Überfällige Rechnungen mit der nächsten Mahnstufe. `bereit`: noch keine Mahnung, oder deren Frist ist abgelaufen."""
	nur_cnc()
	heute = getdate(today())
	out = []
	for r in frappe.get_all(
		"Rechnung", filters={"status": ["in", ["Offen", "Teilbezahlt"]], "art": ["!=", "Storno"], "faellig_am": ["<", heute]},
		fields=["name", "rechnungsnummer", "kunde_name", "faellig_am", "offen", "brutto"], order_by="faellig_am asc",
	):
		mahnungen = frappe.get_all("Mahnung", filters={"rechnung": r.name, "status": ["in", list(AKTIV)]}, fields=["name", "stufe", "status", "datum", "frist_bis"], order_by="creation asc")
		stufen = [m.stufe for m in mahnungen]
		letzte = mahnungen[-1] if mahnungen else None
		out.append({
			"rechnungId": r.name, "nummer": r.rechnungsnummer or "", "kundeName": r.kunde_name or "", "faelligAm": datum(r.faellig_am),
			"tageUeberfaellig": tage_ueberfaellig(r.faellig_am), "offen": r.offen or 0, "brutto": r.brutto or 0,
			"mahnungen": [{"id": m.name, "stufe": m.stufe, "status": m.status, "datum": datum(m.datum), "fristBis": datum(m.frist_bis)} for m in mahnungen],
			"naechsteStufe": naechste_mahnstufe(stufen),
			"bereit": bool(naechste_mahnstufe(stufen)) and (not letzte or getdate(letzte.frist_bis) < heute),
		})
	return out


@frappe.whitelist(methods=["POST"])
def anlegen(rechnung, stufe=None):
	"""Legt eine Mahnung an. Ohne Stufe die nächste. Die Gebühr kommt aus den Firmendaten (Zahlungserinnerung ohne Gebühr)."""
	frappe.only_for(BUCHHALTUNG)
	r = frappe.get_doc("Rechnung", rechnung)
	heute = getdate(today())
	if r.status not in ("Offen", "Teilbezahlt") or r.art == "Storno":
		frappe.throw(_("Für diese Rechnung lässt sich keine Mahnung anlegen."))
	if not r.faellig_am or getdate(r.faellig_am) >= heute:
		frappe.throw(_("Die Rechnung ist noch nicht überfällig."))
	vorhanden = frappe.get_all("Mahnung", filters={"rechnung": r.name, "status": ["in", list(AKTIV)]}, pluck="stufe")
	stufe = stufe or naechste_mahnstufe(vorhanden)
	if stufe not in MAHNSTUFEN:
		frappe.throw(_("Es gibt keine weitere Mahnstufe."))
	if stufe in vorhanden:
		frappe.throw(_("Die Stufe {0} gibt es für diese Rechnung schon.").format(stufe))
	firma = firma_ui()
	gebuehr = 0 if stufe == "Zahlungserinnerung" else (firma["mahngebuehr"] or 0)
	frist = add_days(heute, firma["mahnfristTage"])
	m = frappe.new_doc("Mahnung")
	m.rechnung = r.name
	m.kunde = r.kunde
	m.stufe = stufe
	m.status = "Angelegt"
	m.datum = heute
	m.frist_bis = frist
	m.offener_betrag = r.offen
	m.gebuehr = gebuehr
	m.text = mahntext(stufe, r.rechnungsnummer, r.rechnungsdatum, r.brutto, r.offen, frist, gebuehr)
	m.insert()
	return mahnung_ui(m)


def _geladen(id):
	m = frappe.get_doc("Mahnung", id)
	m.check_permission("write")
	return m


@frappe.whitelist(methods=["POST"])
def versendet_setzen(id):
	frappe.only_for(BUCHHALTUNG)
	m = _geladen(id)
	if m.status != "Angelegt":
		frappe.throw(_("Nur eine angelegte Mahnung lässt sich als versendet markieren."))
	frappe.db.set_value("Mahnung", m.name, {"status": "Versendet", "versandt_am": getdate(today())})
	return mahnung_ui(frappe.get_doc("Mahnung", m.name))


@frappe.whitelist(methods=["POST"])
def zurueckziehen(id):
	"""Zieht eine Mahnung zurück (z. B. irrtümlich angelegt). Die nächste Stufe fängt dann wieder dort an."""
	frappe.only_for(BUCHHALTUNG)
	m = _geladen(id)
	if m.status not in ("Angelegt", "Versendet"):
		frappe.throw(_("Diese Mahnung lässt sich nicht zurückziehen."))
	frappe.db.set_value("Mahnung", m.name, "status", "Zurückgezogen")
	return mahnung_ui(frappe.get_doc("Mahnung", m.name))
