"""Pflege der Stammdaten (Kunden, Bauteile, Lieferanten, Maschinen, Materialien) für die Oberfläche.

Eine Schnittstelle für alle Arten: `liste(art)`, `speichern(art, daten)`, `loeschen(art, id)`. Rechte prüft Frappe über die
Doctype-Berechtigungen. Was schon in Belegen verwendet wird, lässt sich nicht löschen, nur deaktivieren.
"""

import json
import re

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import arbeitsgang_ui, arbeitsgang_zeile, nur_cnc, stammdaten
from cnc_one.logic.serien import hoechste


def _text(v):
	return (v or "").strip() if isinstance(v, str) or v is None else str(v).strip()


# ----------------------------------------------------------------- Kunde
TELEFON_ARTEN = ("Arbeit", "Mobil", "Zentrale", "Fax", "Privat", "Sonstige")


def _nummern_ui(wert, alt=""):
	"""Telefonnummern als Liste [{art, nummer}]; ältere Datensätze haben nur eine Nummer im Feld telefon."""
	try:
		liste = json.loads(wert) if isinstance(wert, str) and wert else (wert or [])
	except ValueError:
		liste = []
	out = [{"art": x.get("art") or "Arbeit", "nummer": x.get("nummer") or ""} for x in liste if isinstance(x, dict) and (x.get("nummer") or "").strip()]
	if not out and (alt or "").strip():
		out = [{"art": "Arbeit", "nummer": alt.strip()}]
	return out


def _nummern(liste):
	"""Leere Zeilen weg, unbekannte Arten werden „Sonstige“."""
	out = []
	for x in liste or []:
		nummer = _text((x or {}).get("nummer"))
		if nummer:
			art = (x or {}).get("art")
			out.append({"art": art if art in TELEFON_ARTEN else "Sonstige", "nummer": nummer})
	return out


def kunde_voll_ui(d):
	return {
		"id": d.name,
		"name": d.kundenname,
		"kuerzel": d.kuerzel or "",
		"aktiv": bool(d.aktiv),
		"telefonnummern": _nummern_ui(d.telefonnummern),
		"ustId": d.ust_id or "",
		"steuernummer": d.steuernummer or "",
		"zahlungsbedingung": d.zahlungsbedingung or "",
		"leitwegId": d.leitweg_id or "",
		"lieferantennr": d.lieferantennummer or "",
		"zahlungszielTage": d.zahlungsziel_tage or 0,
		"materialZeugnis": d.material_zeugnis or "",
		"materialPruefungen": [z.strip() for z in (d.material_pruefungen or "").splitlines() if z.strip()],
		"adressen": [
			{"typ": a.typ or "Rechnung und Lieferung", "strasse": a.strasse or "", "plz": a.plz or "", "ort": a.ort or "", "land": a.land or "", "standard": bool(a.standard)}
			for a in d.adressen
		],
		"kontakte": [
			{
				"anrede": k.anrede or "", "vorname": k.vorname or "", "nachname": k.nachname or "", "email": k.email or "",
				"telefon": k.telefon or "", "telefonnummern": _nummern_ui(k.telefonnummern, k.telefon), "rechnungskontakt": bool(k.ist_rechnungskontakt),
			}
			for k in d.kontakte
		],
	}


def kunde_setzen(doc, d):
	doc.kundenname = _text(d.get("name"))
	doc.kuerzel = _text(d.get("kuerzel"))
	doc.aktiv = 1 if d.get("aktiv", True) else 0
	doc.telefonnummern = json.dumps(_nummern(d.get("telefonnummern")), ensure_ascii=False)
	doc.ust_id = _text(d.get("ustId"))
	doc.steuernummer = _text(d.get("steuernummer"))
	doc.zahlungsbedingung = _text(d.get("zahlungsbedingung"))
	doc.leitweg_id = _text(d.get("leitwegId"))
	doc.lieferantennummer = _text(d.get("lieferantennr"))
	doc.zahlungsziel_tage = max(0, int(d.get("zahlungszielTage") or 0))
	if "materialZeugnis" in d:
		doc.material_zeugnis = d.get("materialZeugnis") if d.get("materialZeugnis") in ("2.2", "3.1", "3.2") else ""
	if "materialPruefungen" in d:
		doc.material_pruefungen = "\n".join(p for p in (d.get("materialPruefungen") or []) if frappe.db.exists("Materialanforderung", p))
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
		nummern = _nummern(k.get("telefonnummern")) if "telefonnummern" in k else _nummern([{"art": "Arbeit", "nummer": k.get("telefon")}])
		doc.append("kontakte", {
			"anrede": k.get("anrede") or "", "vorname": _text(k.get("vorname")), "nachname": _text(k.get("nachname")) or _text(k.get("vorname")) or _text(k.get("email")),
			"email": _text(k.get("email")), "telefon": nummern[0]["nummer"] if nummern else "",
			"telefonnummern": json.dumps(nummern, ensure_ascii=False), "ist_rechnungskontakt": 1 if k.get("rechnungskontakt") else 0,
		})


# ----------------------------------------------------------------- Lieferant, Maschine, Material
def lieferant_kontakt_ui(k):
	return {
		"anrede": k.anrede or "", "vorname": k.vorname or "", "nachname": k.nachname or "", "funktion": k.funktion or "",
		"email": k.email or "", "telefon": k.telefon or "", "mobil": k.mobil or "", "anfragen": bool(k.anfragen),
	}


def lieferant_ui(d):
	return {
		"id": d.name, "name": d.lieferantenname, "leistung": d.leistung or "", "email": d.email or "", "weitereEmails": d.weitere_emails or "",
		"telefon": d.telefon or "", "adresse": d.adresse or "", "ustId": d.ust_id or "", "aktiv": bool(d.aktiv),
		"kontakte": [lieferant_kontakt_ui(k) for k in d.get("kontakte") or []],
	}


def lieferant_setzen(doc, d):
	if doc.is_new():
		doc.lieferantenname = _text(d.get("name"))
	doc.leistung = _text(d.get("leistung"))
	doc.email = _text(d.get("email"))
	doc.telefon = _text(d.get("telefon"))
	doc.adresse = _text(d.get("adresse"))
	if "weitereEmails" in d:
		doc.weitere_emails = "\n".join(z.strip().lower() for z in re.split(r"[\s,;]+", d.get("weitereEmails") or "") if "@" in z)
	if "ustId" in d:
		doc.ust_id = _text(d.get("ustId"))
	if "kontakte" in d:
		doc.set("kontakte", [])
		for k in d.get("kontakte") or []:
			if not any(_text(k.get(f)) for f in ("nachname", "vorname", "email")):
				continue
			doc.append("kontakte", {
				"anrede": k.get("anrede") if k.get("anrede") in ("Herr", "Frau") else "", "vorname": _text(k.get("vorname")),
				"nachname": _text(k.get("nachname")) or _text(k.get("vorname")) or _text(k.get("email")), "funktion": _text(k.get("funktion")),
				"email": _text(k.get("email")).lower(), "telefon": _text(k.get("telefon")), "mobil": _text(k.get("mobil")),
				"anfragen": 1 if k.get("anfragen") else 0,
			})
	doc.aktiv = 1 if d.get("aktiv", True) else 0


def maschine_ui(d):
	return {
		"id": d.name, "name": d.maschinenname, "satz": d.satz or 0, "bemerkung": d.bemerkung or "", "aktiv": bool(d.aktiv),
		"arbeitsgaenge": [z.strip() for z in (d.arbeitsgaenge or "").splitlines() if z.strip()],
		"automation": "ja" if d.automation else "nein", "stundenTag": d.stunden_tag or 8,
	}


def maschine_setzen(doc, d):
	if doc.is_new():
		doc.maschinenname = _text(d.get("name"))
	doc.satz = d.get("satz") or 0
	doc.bemerkung = _text(d.get("bemerkung"))
	doc.aktiv = 1 if d.get("aktiv", True) else 0
	if "arbeitsgaenge" in d:
		doc.arbeitsgaenge = "\n".join(_text(x) for x in (d.get("arbeitsgaenge") or []) if _text(x))
	if "automation" in d:
		doc.automation = 1 if d.get("automation") in (True, 1, "ja") else 0
	if "stundenTag" in d:
		doc.stunden_tag = min(24, max(0, float(d.get("stundenTag") or 0))) or 8


ISO_GRUPPEN = ("P", "M", "K", "N", "S", "H")


def material_ui(d):
	return {
		"id": d.name, "name": d.materialname, "preisKg": d.preis_kg or 0, "dichte": d.dichte or 0, "aktiv": bool(d.aktiv), "schreibweisen": d.schreibweisen or "",
		"isoGruppe": d.iso_gruppe or "", "kurz": d.kurzname or "",
		"zustaende": [z.strip() for z in (d.zustaende or "").splitlines() if z.strip()], "formen": [z.strip() for z in (d.formen or "").splitlines() if z.strip()],
	}


def material_setzen(doc, d):
	if doc.is_new():
		doc.materialname = _text(d.get("name"))
	doc.preis_kg = d.get("preisKg") or 0
	doc.dichte = d.get("dichte") or 0
	doc.aktiv = 1 if d.get("aktiv", True) else 0
	if "isoGruppe" in d:
		doc.iso_gruppe = d.get("isoGruppe") if d.get("isoGruppe") in ISO_GRUPPEN else ""
	if "schreibweisen" in d:
		doc.schreibweisen = "\n".join(z.strip() for z in (d.get("schreibweisen") or "").splitlines() if z.strip())
	if "kurz" in d:
		doc.kurzname = _text(d.get("kurz"))
	if "zustaende" in d:
		doc.zustaende = "\n".join(z for z in (_text(x) for x in d.get("zustaende") or []) if z and frappe.db.exists("Werkstoffzustand", z))
	if "formen" in d:
		doc.formen = "\n".join(f for f in ("Rund", "Vierkant", "Flach", "Sechskant", "Rohr", "Platte") if f in (d.get("formen") or []))


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
	bauteil_api.revision_setzen(doc, _text(d.get("revision")))
	material = _text(d.get("material"))
	doc.material = material if material and frappe.db.exists("Material", material) else None
	doc.status = d.get("status") if d.get("status") in ("Aktiv", "Gesperrt") else "Aktiv"
	if "notizIntern" in d:
		doc.notiz_intern = (d.get("notizIntern") or "").strip()
	if "frueherGefertigt" in d:
		doc.frueher_gefertigt = 1 if d.get("frueherGefertigt") else 0
		doc.frueher_notiz = (d.get("frueherNotiz") or "").strip()[:140]
	doc.seriennummern = 1 if d.get("seriennummern") else 0
	stellen = min(9, max(1, int(d.get("serienStellen") or 4)))
	letzte = max(0, int(d.get("letzteSeriennummer") or 0))
	if letzte > hoechste(stellen):
		frappe.throw(_("Die letzte Seriennummer {0} passt nicht in {1} Stellen.").format(letzte, stellen))
	doc.serien_stellen = stellen
	doc.letzte_seriennummer = letzte
	doc.set("arbeitsplan", [])
	for a in d.get("arbeitsgaenge") or []:
		doc.append("arbeitsplan", arbeitsgang_zeile(a))


ARTEN = {
	"kunde": ("Kunde", kunde_voll_ui, kunde_setzen),
	"lieferant": ("Lieferant", lieferant_ui, lieferant_setzen),
	"maschine": ("Maschine", maschine_ui, maschine_setzen),
	"material": ("Material", material_ui, material_setzen),
	"bauteil": ("Bauteil", bauteil_voll_ui, bauteil_setzen),
	"anfragevorlage": ("Anfragevorlage", lambda d: _anfrage().vorlage_ui(d), lambda doc, d: _anfrage().vorlage_setzen(doc, d)),
}


def _anfrage():
	from cnc_one.api import anfrage

	return anfrage


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
