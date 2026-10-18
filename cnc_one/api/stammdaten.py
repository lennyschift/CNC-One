"""Pflege der Stammdaten (Kunden, Bauteile, Lieferanten, Maschinen, Materialien) für die Oberfläche.

Eine Schnittstelle für alle Arten: `liste(art)`, `speichern(art, daten)`, `loeschen(art, id)`. Rechte prüft Frappe über die
Doctype-Berechtigungen. Was schon in Belegen verwendet wird, lässt sich nicht löschen, nur deaktivieren.
"""

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import arbeitsgang_ui, arbeitsgang_zeile, nur_cnc, stammdaten


def _text(v):
	return (v or "").strip() if isinstance(v, str) or v is None else str(v).strip()


# ----------------------------------------------------------------- Kunde
def kunde_voll_ui(d):
	return {
		"id": d.name,
		"name": d.kundenname,
		"kuerzel": d.kuerzel or "",
		"aktiv": bool(d.aktiv),
		"ustId": d.ust_id or "",
		"steuernummer": d.steuernummer or "",
		"zahlungsbedingung": d.zahlungsbedingung or "",
		"leitwegId": d.leitweg_id or "",
		"lieferantennr": d.lieferantennummer or "",
		"adressen": [
			{"typ": a.typ or "Rechnung und Lieferung", "strasse": a.strasse or "", "plz": a.plz or "", "ort": a.ort or "", "land": a.land or "", "standard": bool(a.standard)}
			for a in d.adressen
		],
		"kontakte": [
			{
				"anrede": k.anrede or "", "vorname": k.vorname or "", "nachname": k.nachname or "", "email": k.email or "",
				"telefon": k.telefon or "", "rechnungskontakt": bool(k.ist_rechnungskontakt),
			}
			for k in d.kontakte
		],
	}


def kunde_setzen(doc, d):
	doc.kundenname = _text(d.get("name"))
	doc.kuerzel = _text(d.get("kuerzel"))
	doc.aktiv = 1 if d.get("aktiv", True) else 0
	doc.ust_id = _text(d.get("ustId"))
	doc.steuernummer = _text(d.get("steuernummer"))
	doc.zahlungsbedingung = _text(d.get("zahlungsbedingung"))
	doc.leitweg_id = _text(d.get("leitwegId"))
	doc.lieferantennummer = _text(d.get("lieferantennr"))
	doc.set("adressen", [])
	adressen = [a for a in d.get("adressen") or [] if any(_text(a.get(k)) for k in ("strasse", "plz", "ort"))]
	for i, a in enumerate(adressen):
		doc.append("adressen", {
			"typ": a.get("typ") or "Rechnung und Lieferung", "strasse": _text(a.get("strasse")), "plz": _text(a.get("plz")),
			"ort": _text(a.get("ort")), "land": _text(a.get("land")), "standard": 1 if a.get("standard") or (i == 0 and not any(x.get("standard") for x in adressen)) else 0,
		})
	doc.set("kontakte", [])
	kontakte = [k for k in d.get("kontakte") or [] if _text(k.get("nachname")) or _text(k.get("vorname")) or _text(k.get("email"))]
	for k in kontakte:
		doc.append("kontakte", {
			"anrede": k.get("anrede") or "", "vorname": _text(k.get("vorname")), "nachname": _text(k.get("nachname")) or _text(k.get("vorname")) or _text(k.get("email")),
			"email": _text(k.get("email")), "telefon": _text(k.get("telefon")), "ist_rechnungskontakt": 1 if k.get("rechnungskontakt") else 0,
		})


# ----------------------------------------------------------------- Lieferant, Maschine, Material
def lieferant_ui(d):
	return {"id": d.name, "name": d.lieferantenname, "leistung": d.leistung or "", "email": d.email or "", "telefon": d.telefon or "", "adresse": d.adresse or "", "aktiv": bool(d.aktiv)}


def lieferant_setzen(doc, d):
	if doc.is_new():
		doc.lieferantenname = _text(d.get("name"))
	doc.leistung = _text(d.get("leistung"))
	doc.email = _text(d.get("email"))
	doc.telefon = _text(d.get("telefon"))
	doc.adresse = _text(d.get("adresse"))
	doc.aktiv = 1 if d.get("aktiv", True) else 0


def maschine_ui(d):
	return {"id": d.name, "name": d.maschinenname, "satz": d.satz or 0, "bemerkung": d.bemerkung or "", "aktiv": bool(d.aktiv)}


def maschine_setzen(doc, d):
	if doc.is_new():
		doc.maschinenname = _text(d.get("name"))
	doc.satz = d.get("satz") or 0
	doc.bemerkung = _text(d.get("bemerkung"))
	doc.aktiv = 1 if d.get("aktiv", True) else 0


def material_ui(d):
	return {"id": d.name, "name": d.materialname, "preisKg": d.preis_kg or 0, "dichte": d.dichte or 0, "aktiv": bool(d.aktiv)}


def material_setzen(doc, d):
	if doc.is_new():
		doc.materialname = _text(d.get("name"))
	doc.preis_kg = d.get("preisKg") or 0
	doc.dichte = d.get("dichte") or 0
	doc.aktiv = 1 if d.get("aktiv", True) else 0


# ----------------------------------------------------------------- Bauteil
def bauteil_voll_ui(d):
	return {**bauteil_api.bauteil_ui(d), "revision": d.revision or "", "status": d.status or "Aktiv"}


def bauteil_setzen(doc, d):
	if not _text(d.get("kundeId")) or not frappe.db.exists("Kunde", d.get("kundeId")):
		frappe.throw(_("Bitte einen Kunden wählen."))
	doc.kunde = d.get("kundeId")
	doc.teilenummer = _text(d.get("teilenummer"))
	doc.bezeichnung = _text(d.get("name"))
	doc.zeichnungsnr = _text(d.get("zeichnungsnr"))
	doc.revision = _text(d.get("revision"))
	material = _text(d.get("material"))
	doc.material = material if material and frappe.db.exists("Material", material) else None
	doc.status = d.get("status") if d.get("status") in ("Aktiv", "Gesperrt") else "Aktiv"
	doc.set("arbeitsplan", [])
	for a in d.get("arbeitsgaenge") or []:
		doc.append("arbeitsplan", arbeitsgang_zeile(a))


ARTEN = {
	"kunde": ("Kunde", kunde_voll_ui, kunde_setzen),
	"lieferant": ("Lieferant", lieferant_ui, lieferant_setzen),
	"maschine": ("Maschine", maschine_ui, maschine_setzen),
	"material": ("Material", material_ui, material_setzen),
	"bauteil": ("Bauteil", bauteil_voll_ui, bauteil_setzen),
}


def _art(art):
	if art not in ARTEN:
		frappe.throw(_("Unbekannte Stammdatenart {0}.").format(art))
	return ARTEN[art]


@frappe.whitelist(methods=["POST"])
def liste(art):
	"""Alle Einträge einer Art, auch die deaktivierten."""
	nur_cnc()
	doctype, ui, _setzen = _art(art)
	namen = frappe.get_list(doctype, pluck="name", order_by="creation asc", limit_page_length=0)
	return [ui(frappe.get_doc(doctype, n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def speichern(art, daten):
	"""Legt einen Eintrag an (ohne `id`) oder ändert ihn."""
	nur_cnc()
	if isinstance(daten, str):
		daten = frappe.parse_json(daten)
	doctype, ui, setzen = _art(art)
	if daten.get("id") and frappe.db.exists(doctype, daten["id"]):
		doc = frappe.get_doc(doctype, daten["id"])
	else:
		doc = frappe.new_doc(doctype)
	if not _text(daten.get("name")) and art != "bauteil":
		frappe.throw(_("Bitte einen Namen eingeben."))
	setzen(doc, daten)
	doc.save() if not doc.is_new() else doc.insert()
	return ui(doc)


@frappe.whitelist(methods=["POST"])
def loeschen(art, id):
	"""Löscht einen Eintrag. Wird er schon verwendet, bleibt er erhalten und lässt sich nur deaktivieren."""
	nur_cnc()
	doctype, _ui, _setzen = _art(art)
	try:
		frappe.delete_doc(doctype, id)
	except frappe.LinkExistsError:
		frappe.clear_messages()
		frappe.throw(_("{0} wird schon verwendet (z. B. in Angeboten, Aufträgen oder Bauteilen) und lässt sich nicht löschen. Bitte stattdessen deaktivieren.").format(id))
	return {"id": id}


@frappe.whitelist(methods=["POST"])
def aktuell():
	"""Die Stammdaten für Auswahllisten und Bauteile, damit die Oberfläche nach Änderungen frisch ist."""
	nur_cnc()
	return {**stammdaten(), "bauteile": bauteil_api.alle_ui()}
