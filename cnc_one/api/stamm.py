"""Schnittstelle für Stammdaten. Liefert und speichert Daten in der Form, die die Oberfläche erwartet.

Alle Funktionen prüfen die Rechte über Frappe (Doctype-Berechtigungen), nicht über eigene Listen.
"""

import frappe
from frappe import _

CNC_ROLLEN = ("CNC Admin", "CNC Vertrieb", "CNC Fertigung", "CNC Buchhaltung", "System Manager")


def nur_cnc():
	frappe.only_for(CNC_ROLLEN)


# ----------------------------------------------------------------- Einstellungen je Benutzer
# Was die Oberfläche sich merkt (früher im Browser): Farbschema und welches Angebot die Workbench zuletzt offen hatte.
EINSTELLUNGEN = {
	"theme": ("dark", "light"),
	"workbenchAngebot": None,
	"workbenchAuswahl": None,
}


def _default_key(key):
	return f"cnc_one_{key.lower()}"


def einstellungen(user=None):
	user = user or frappe.session.user
	return {k: frappe.defaults.get_user_default(_default_key(k), user) or "" for k in EINSTELLUNGEN}


@frappe.whitelist(methods=["POST"])
def einstellung_setzen(key, wert=""):
	"""Merkt sich eine Einstellung des angemeldeten Benutzers."""
	nur_cnc()
	if key not in EINSTELLUNGEN:
		frappe.throw(_("Unbekannte Einstellung {0}.").format(key))
	wert = str(wert or "")
	erlaubt = EINSTELLUNGEN[key]
	if erlaubt and wert not in erlaubt:
		frappe.throw(_("Ungültiger Wert für {0}.").format(key))
	if len(wert) > 140:
		frappe.throw(_("Der Wert ist zu lang."))
	if wert:
		frappe.defaults.set_user_default(_default_key(key), wert)
	else:
		frappe.defaults.clear_user_default(_default_key(key))
	return {key: wert}


# ----------------------------------------------------------------- Umrechnung Frappe <-> Oberfläche
def typ_ui(t):
	return "fremd" if t == "Fremd" else "intern"


def typ_db(t):
	return "Fremd" if t == "fremd" else "Intern"


def arbeitsgang_ui(r):
	return {
		"id": r.ag_id or r.name,
		"name": r.bezeichnung or "",
		"typ": typ_ui(r.typ),
		"maschine": r.maschine or "",
		"satz": r.satz or 0,
		"ruestMin": r.ruest_min or 0,
		"stueckMin": r.stueck_min or 0,
		"lieferant": r.lieferant or "",
		"fremdProStk": r.fremd_pro_stk or 0,
		"fremdEinmal": r.fremd_einmal or 0,
		"anfrageId": r.anfrage or "",
		"serie": bool(r.serie),
	}


def serienart_namen():
	"""Namen der Arbeitsgangarten, die Seriennummern anbringen (kleingeschrieben)."""
	return {(n or "").strip().lower() for n in frappe.get_all("Arbeitsgangart", filters={"serie": 1}, pluck="bezeichnung")}


def ist_serienart(name, namen=None):
	return (name or "").strip().lower() in (namen if namen is not None else serienart_namen())


def arbeitsgang_zeile(a):
	"""Eine Arbeitsgang-Zeile aus der Oberfläche als Werte für eine Child-Tabelle."""
	return {
		"ag_id": a.get("id") or frappe.generate_hash(length=10),
		"bezeichnung": (a.get("name") or "").strip(),
		"typ": typ_db(a.get("typ")),
		"maschine": a.get("maschine") or None,
		"satz": a.get("satz") or 0,
		"ruest_min": a.get("ruestMin") or 0,
		"stueck_min": a.get("stueckMin") or 0,
		"lieferant": a.get("lieferant") or None,
		"fremd_pro_stk": a.get("fremdProStk") or 0,
		"fremd_einmal": a.get("fremdEinmal") or 0,
		"anfrage": a.get("anfrageId") or "",
		# ob der Arbeitsgang Seriennummern anbringt, ergibt sich allein aus der Arbeitsgangart (dem Namen)
		"serie": 1 if ist_serienart(a.get("name")) else 0,
	}


def kunde_ui(d):
	adresse = next((a for a in d.adressen if a.standard), None) or (d.adressen[0] if d.adressen else None)
	kontakt = next((k for k in d.kontakte if k.ist_rechnungskontakt), None) or (d.kontakte[0] if d.kontakte else None)
	return {
		"id": d.name,
		"name": d.kundenname,
		"kuerzel": d.kuerzel or "",
		"lieferantennr": d.lieferantennummer or "",
		"ustId": d.ust_id or "",
		"adresse": [z for z in (adresse.strasse, " ".join(x for x in (adresse.plz, adresse.ort) if x)) if z] if adresse else [],
		"kontakt": {
			"name": " ".join(x for x in (kontakt.anrede, kontakt.vorname, kontakt.nachname) if x),
			"email": kontakt.email or "",
		} if kontakt else None,
	}


def vorlage_ui(d):
	return {
		"id": d.name,
		"name": d.vorlagenname,
		"kundeId": d.kunde or "",
		"arbeitsgaenge": [arbeitsgang_ui(r) for r in d.arbeitsgaenge],
	}


def art_ui(d):
	return {"id": d.name, "name": d.bezeichnung, "typ": typ_ui(d.typ), "serie": bool(d.serie)}


# ----------------------------------------------------------------- Lesen
def _namen(doctype, filters=None, order_by="creation asc"):
	return frappe.get_list(doctype, filters=filters, pluck="name", order_by=order_by, limit_page_length=0)


@frappe.whitelist()
def bootstrap():
	"""Alles, was die Oberfläche beim Start braucht: Benutzer und Stammdaten."""
	nur_cnc()
	from cnc_one.api import anfrage, angebot, auftrag, bauteil, fertigung, firma, lager, lieferschein, mahnung, rechnung

	user = frappe.session.user
	return {
		"benutzer": {"id": user, "name": frappe.utils.get_fullname(user), "rollen": frappe.get_roles(user), "einstellungen": einstellungen(user)},
		**stammdaten(),
		"bauteile": bauteil.alle_ui(),
		"angebote": angebot.alle_ui(),
		"auftraege": auftrag.alle_ui(),
		"fertigung": fertigung.alle_ui(),
		"anfragen": anfrage.alle_ui(),
		"lieferscheine": lieferschein.alle_ui(),
		"rechnungen": rechnung.alle_ui(),
		"mahnungen": mahnung.alle_ui(),
		"firma": firma.firma_ui(),
		"lager": lager.bestand_ui(),
	}


def stammdaten():
	return {
		"kunden": [kunde_ui(frappe.get_doc("Kunde", n)) for n in _namen("Kunde", {"aktiv": 1})],
		"lieferanten": [
			{"id": r.name, "name": r.name, "leistung": r.leistung or ""}
			for r in frappe.get_list("Lieferant", filters={"aktiv": 1}, fields=["name", "leistung"], order_by="name asc", limit_page_length=0)
		],
		"maschinen": [
			{"name": r.name, "satz": r.satz or 0}
			for r in frappe.get_list("Maschine", filters={"aktiv": 1}, fields=["name", "satz"], order_by="name asc", limit_page_length=0)
		],
		"materialien": [
			{"name": r.name, "preisKg": r.preis_kg or 0}
			for r in frappe.get_list("Material", filters={"aktiv": 1}, fields=["name", "preis_kg"], order_by="name asc", limit_page_length=0)
		],
		"arten": [art_ui(frappe.get_doc("Arbeitsgangart", n)) for n in _namen("Arbeitsgangart", {"aktiv": 1})],
		"vorlagen": [vorlage_ui(frappe.get_doc("Arbeitsplan Vorlage", n)) for n in _namen("Arbeitsplan Vorlage")],
	}


# ----------------------------------------------------------------- Arbeitsgangarten
@frappe.whitelist(methods=["POST"])
def art_speichern(name, typ="intern", id=None):
	nur_cnc()
	if id:
		doc = frappe.get_doc("Arbeitsgangart", id)
	else:
		doc = frappe.new_doc("Arbeitsgangart")
	doc.bezeichnung = name
	doc.typ = typ_db(typ)
	doc.save() if id else doc.insert()
	return art_ui(doc)


@frappe.whitelist(methods=["POST"])
def art_loeschen(id):
	nur_cnc()
	frappe.delete_doc("Arbeitsgangart", id)
	return {"id": id}


# ----------------------------------------------------------------- Vorlagen
@frappe.whitelist(methods=["POST"])
def vorlage_speichern(vorlage):
	"""Legt eine Vorlage an oder aktualisiert sie. `vorlage` hat die Form der Oberfläche."""
	nur_cnc()
	if isinstance(vorlage, str):
		vorlage = frappe.parse_json(vorlage)
	if vorlage.get("id") and frappe.db.exists("Arbeitsplan Vorlage", vorlage["id"]):
		doc = frappe.get_doc("Arbeitsplan Vorlage", vorlage["id"])
	else:
		doc = frappe.new_doc("Arbeitsplan Vorlage")
	doc.vorlagenname = (vorlage.get("name") or "").strip() or _("Neue Vorlage")
	doc.kunde = vorlage.get("kundeId") or None
	doc.set("arbeitsgaenge", [])
	for a in vorlage.get("arbeitsgaenge") or []:
		doc.append("arbeitsgaenge", arbeitsgang_zeile(a))
	doc.save() if doc.get("name") and not doc.is_new() else doc.insert()
	return vorlage_ui(doc)


@frappe.whitelist(methods=["POST"])
def vorlage_loeschen(id):
	nur_cnc()
	frappe.delete_doc("Arbeitsplan Vorlage", id)
	return {"id": id}
