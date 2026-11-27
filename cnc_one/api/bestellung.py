"""Bestellungen des Kunden (PDF) einlesen, mit Angeboten und früheren Aufträgen abgleichen und daraus einen Auftrag anlegen
oder sie an einen vorhandenen Auftrag koppeln.

Den Text und die Tabelle liest die Oberfläche aus dem PDF (ui/src/lib/bestellung.js). Hier passiert der Abgleich:
Kunde erkennen, Bauteil finden (Teilenummer oder Zeichnungsnummer irgendwo im Text der Position), passende Angebote
suchen und Preise vergleichen (logic/bestellabgleich.py: auch mit Kosten, die der Kunde auf den Stückpreis umlegt).
"""

import json
import re

import frappe
from frappe import _

from cnc_one.api import auftrag as auftrag_api
from cnc_one.api import historie
from cnc_one.api.bauteil import sicherstellen
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import bestellabgleich
from cnc_one.logic.daten import als_json, iso
from cnc_one.logic.kalkulation import num, r2


def _norm(text):
	return re.sub(r"[\s\-_./]+", "", (text or "").lower())


def toleranz_prozent():
	wert = frappe.db.get_single_value("Firma", "bestellung_toleranz")
	return 0.5 if wert is None else num(wert)


# ----------------------------------------------------------------- Kunde und Bauteil erkennen
def kunde_erkennen(text):
	"""Kunde, dessen Name, Kürzel oder Mail-Domain im Text der Bestellung vorkommt (der längste Treffer gewinnt)."""
	t = (text or "").lower()
	if not t.strip():
		return ""
	beste = ("", 0)
	for k in frappe.get_all("Kunde", filters={"aktiv": 1}, fields=["name", "kundenname", "kuerzel"]):
		kandidaten = [k.kundenname or ""]
		kurz = re.sub(r"\b(gmbh|ag|kg|se|ohg|ug|co\.?|& co\.?|mbh|e\.k\.|ltd\.?|inc\.?)\b", "", (k.kundenname or "").lower()).strip(" ,&")
		if len(kurz) >= 4:
			kandidaten.append(kurz)
		if len(k.kuerzel or "") >= 3:
			kandidaten.append(k.kuerzel)
		for kontakt in frappe.get_all("Kunde Kontakt", filters={"parent": k.name, "parenttype": "Kunde"}, pluck="email"):
			if kontakt and "@" in kontakt:
				kandidaten.append("@" + kontakt.split("@", 1)[1])
		for c in kandidaten:
			c = c.lower().strip()
			if len(c) >= 3 and re.search(r"(?<![a-z0-9])" + re.escape(c) + r"(?![a-z0-9])", t) and len(c) > beste[1]:
				beste = (k.name, len(c))
	return beste[0]


def bauteil_finden(kunde, teilenummer="", text=""):
	"""Bauteil zu einer Bestellposition: zuerst die erkannte Teilenummer (ohne Leer- und Trennzeichen verglichen), sonst
	eine Teilenummer oder Zeichnungsnummer eines Bauteils des Kunden irgendwo im Text der Position (die längste)."""
	filters = {"kunde": kunde} if kunde else {}
	teile = frappe.get_all("Bauteil", filters=filters, fields=["name", "teilenummer", "zeichnungsnr"], limit_page_length=0)
	nr = _norm(teilenummer)
	if nr:
		for b in teile:
			if _norm(b.teilenummer) == nr:
				return b.name
		for b in teile:
			if b.zeichnungsnr and _norm(b.zeichnungsnr) == nr:
				return b.name
	t = _norm(text)
	if not t:
		return None
	treffer = []
	for b in teile:
		for wert in (b.teilenummer, b.zeichnungsnr):
			n = _norm(wert)
			if len(n) >= 4 and n in t:
				treffer.append((len(n), b.name))
	return max(treffer)[1] if treffer else None


# ----------------------------------------------------------------- Abgleich
def _angebotsquellen(kunde, bauteil, teilenummer, menge, preis, kosten_bestellt, prozent):
	"""Angebotspositionen zum Bauteil, gesendete zuerst, jede mit dem Preisabgleich für diese Bestellung."""
	bed = "p.bauteil = %(bauteil)s" if bauteil else "lower(p.teilenummer) = %(nr)s"
	if not bauteil and not (teilenummer or "").strip():
		return []
	zeilen = frappe.db.sql(
		f"""select p.parent, p.position_key, p.kalkulation, p.revision, a.status, a.creation, a.versandt_am
		from `tabAngebotsposition` p join `tabAngebot` a on a.name = p.parent
		where {bed} and a.kunde = %(kunde)s and a.status in ('Gesendet', 'Bestellt', 'Abgelehnt') and p.parenttype = 'Angebot'
		order by a.status in ('Gesendet', 'Bestellt') desc, coalesce(a.versandt_am, a.creation) desc limit 6""",
		{"bauteil": bauteil, "nr": (teilenummer or "").strip().lower(), "kunde": kunde},
		as_dict=True,
	)
	out = []
	for z in zeilen:
		teil = als_json(z.kalkulation)
		r = bestellabgleich.mit_angebot(teil, menge or teil.get("menge") or 1, preis, kosten_bestellt, prozent)
		out.append({
			"art": "angebot", "angebot": z.parent, "angebotKey": z.position_key, "status": z.status, "revision": z.revision or "",
			"datum": iso(z.versandt_am or z.creation), "staffel": bool((teil.get("staffel") or {}).get("aktiv")), **r,
		})
	return out


def _beste(quellen):
	"""Die vorgeschlagene Quelle: die erste, deren Preis passt, sonst die erste (neuestes gesendetes Angebot)."""
	for i, q in enumerate(quellen):
		if q["abgleich"]["status"] in (bestellabgleich.GLEICH, bestellabgleich.UMGELEGT):
			return i
	return 0 if quellen else -1


def _bauteil_kurz(name):
	if not name:
		return None
	b = frappe.db.get_value("Bauteil", name, ["name", "bezeichnung", "teilenummer", "zeichnungsnr", "revision", "material", "vorschaubild", "seriennummern", "serien_stellen", "letzte_seriennummer", "zeichnung", "step_datei", "frueher_gefertigt", "frueher_notiz"], as_dict=True)
	return {
		"id": b.name, "name": b.bezeichnung or "", "teilenummer": b.teilenummer or "", "zeichnungsnr": b.zeichnungsnr or "", "revision": b.revision or "",
		"material": b.material or "", "vorschaubild": b.vorschaubild or "", "seriennummern": bool(b.seriennummern), "serienStellen": b.serien_stellen or 4,
		"letzteSeriennummer": b.letzte_seriennummer or 0, "zeichnung": b.zeichnung or "", "stepDatei": b.step_datei or "",
		"frueherGefertigt": bool(b.frueher_gefertigt), "frueherNotiz": b.frueher_notiz or "",
	}


def _position(kunde, p, prozent, auftrag=None):
	menge = max(0, int(num(p.get("menge"))))
	preis = num(p.get("preis")) or None
	kosten_bestellt = num(p.get("kosten"))
	bauteil = p.get("bauteil") or bauteil_finden(kunde, p.get("teilenummer"), " ".join([p.get("teilenummer") or "", p.get("text") or ""]))
	teilenummer = p.get("teilenummer") or (frappe.db.get_value("Bauteil", bauteil, "teilenummer") if bauteil else "")
	out = {**p, "menge": menge, "preis": preis, "bauteil": _bauteil_kurz(bauteil), "teilenummer": teilenummer or ""}
	if auftrag:
		# Abgleich mit einem vorhandenen Auftrag: die Auftragsposition mit diesem Bauteil (oder dieser Teilenummer)
		z = next((x for x in auftrag.positionen if (bauteil and x.bauteil == bauteil) or (teilenummer and _norm(x.teilenummer) == _norm(teilenummer))), None)
		if z:
			kosten = [{"label": k.bezeichnung, "betrag": k.betrag or 0} for k in auftrag.kosten if k.position_key == z.position_key]
			erwartet = {"menge": z.menge, "einzelpreis": z.einzelpreis or 0, "kosten": kosten, "summe": z.summe or 0, "staffelMenge": z.staffel_menge or None}
			out["auftragKey"] = z.position_key
			out["erwartet"] = erwartet
			out["abgleich"] = bestellabgleich.vergleichen(erwartet, menge or z.menge, preis, kosten_bestellt, prozent)
			out["mengeAuftrag"] = z.menge
		else:
			out["auftragKey"] = ""
			out["abgleich"] = {"status": bestellabgleich.OHNE_VERGLEICH, "hinweis": _("Keine passende Position im Auftrag")}
		return out
	quellen = _angebotsquellen(kunde, bauteil, teilenummer, menge, preis, kosten_bestellt, prozent)
	out["quellen"] = quellen
	out["quelle"] = _beste(quellen)
	letzte = historie.auftraege(bauteil, kunde, teilenummer) if (bauteil or teilenummer) else []
	letzte = [a for a in letzte if a["status"] != "Storniert"]
	out["letzterAuftrag"] = letzte[0] if letzte else None
	if not quellen:
		# ohne Angebot: gegen den letzten Auftrag vergleichen (Stückpreis inklusive Kosten), sonst gibt es nichts zu vergleichen
		if letzte and preis:
			l = letzte[0]
			erwartet = {"menge": menge or l["menge"], "einzelpreis": l["jeStueck"], "kosten": [], "summe": r2(l["jeStueck"] * (menge or l["menge"]))}
			out["abgleich"] = {**bestellabgleich.vergleichen(erwartet, menge or l["menge"], preis, kosten_bestellt, prozent), "gegen": "letzter Auftrag"}
			if out["abgleich"]["status"] == bestellabgleich.ABWEICHEND:
				out["abgleich"]["hinweis"] = _("Im letzten Auftrag {0} kostete es {1} je Stück (inklusive Kosten bei {2} Stk)").format(l["auftrag"], bestellabgleich._eur(l["jeStueck"]), l["menge"])
		else:
			out["abgleich"] = {"status": bestellabgleich.OHNE_VERGLEICH if preis else bestellabgleich.OHNE_PREIS, "hinweis": _("Kein Angebot und kein früherer Auftrag zu diesem Bauteil") if preis else ""}
	return out


@frappe.whitelist(methods=["POST"])
def erkennen(text="", kunde=""):
	"""Kunde aus dem Text der Bestellung (wenn nicht schon bekannt) und dessen angelernte Bestellvorlage:
	{ kunde, kundeName, vorlage }."""
	nur_cnc()
	kunde = kunde or kunde_erkennen(text)
	return {"kunde": kunde, "kundeName": frappe.db.get_value("Kunde", kunde, "kundenname") if kunde else "", "vorlage": vorlage(kunde) if kunde else {}}


@frappe.whitelist(methods=["POST"])
def vorschlag(kunde, positionen, kundenbestellnr="", auftrag=""):
	"""Abgleich der Bestellpositionen. `positionen`: [{ bestellposition, teilenummer, text, menge, preis (je Stück),
	kosten (eigene Kostenzeilen), termin }]. Mit `auftrag`: gegen diesen Auftrag statt gegen Angebote."""
	nur_cnc()
	if isinstance(positionen, str):
		positionen = json.loads(positionen)
	prozent = toleranz_prozent()
	auf = frappe.get_doc("Auftrag", auftrag) if auftrag else None
	if auf:
		auf.check_permission("read")
		kunde = auf.kunde
	vorhanden = []
	if kunde and (kundenbestellnr or "").strip():
		vorhanden = frappe.get_all("Auftrag", filters={"kunde": kunde, "kundenbestellnr": kundenbestellnr.strip(), "status": ["!=", "Storniert"], "name": ["!=", auftrag or ""]}, pluck="name")
	return {
		"kunde": kunde or "",
		"kundeName": frappe.db.get_value("Kunde", kunde, "kundenname") if kunde else "",
		"toleranz": prozent,
		"vorhanden": vorhanden,
		"positionen": [_position(kunde, p, prozent, auf) for p in positionen or []],
	}


# ----------------------------------------------------------------- Auftrag anlegen oder koppeln
@frappe.whitelist(methods=["POST"])
def auftrag_anlegen(kunde, positionen, kundenbestellnr="", bestelldatum="", kontakt_name="", kontakt_email=""):
	"""Auftrag aus einer Bestellung. Je Position: { angebot, angebotKey, optionId } (aus einem Angebot, auch einem früheren)
	oder { bauteil } bzw. { teilenummer, bezeichnung } (ohne Angebot, Preis laut Bestellung); dazu menge, termin,
	bestellposition, bestellpreis, preisform ('Angebot' | 'Bestellung'), serienStart, kostenAus."""
	nur_cnc()
	if isinstance(positionen, str):
		positionen = json.loads(positionen)
	if not kunde:
		frappe.throw(_("Bitte den Kunden wählen."))
	if not positionen:
		frappe.throw(_("Der Auftrag braucht mindestens eine Position."))
	angebote = {}
	for p in positionen:
		if p.get("angebot") and p["angebot"] not in angebote:
			a = frappe.get_doc("Angebot", p["angebot"])
			if a.kunde != kunde:
				frappe.throw(_("Das Angebot {0} gehört zu einem anderen Kunden.").format(a.name))
			if a.status == "Entwurf":
				frappe.throw(_("Das Angebot {0} ist noch ein Entwurf.").format(a.name))
			angebote[a.name] = a
	nur_eines = next(iter(angebote.values())) if len(angebote) == 1 and all(p.get("angebot") for p in positionen) else None
	doc = auftrag_api.neuer_auftrag(kunde, kundenbestellnr, nur_eines)
	doc.bestelldatum = bestelldatum or None
	if kontakt_name or kontakt_email:
		doc.kontakt_name, doc.kontakt_email = kontakt_name or "", kontakt_email or ""
	merker = {"serien": [], "vergeben": [], "plaene": []}
	for p in positionen:
		if p.get("angebot"):
			ang = angebote[p["angebot"]]
			ap = next((z for z in ang.positionen if z.position_key == p.get("angebotKey")), None)
			if not ap:
				frappe.throw(_("Die Angebotsposition {0} gibt es nicht.").format(p.get("angebotKey")))
			auftrag_api.position_aus_angebot(doc, ang, ap, p, merker)
			continue
		b = frappe.get_doc("Bauteil", p["bauteil"]) if p.get("bauteil") else sicherstellen(kunde, p.get("teilenummer") or "", p.get("bezeichnung") or "")
		if not b:
			frappe.throw(_("Für die Position {0} fehlt das Bauteil (Teilenummer).").format(p.get("bestellposition") or ""))
		if b.kunde != kunde:
			frappe.throw(_("Das Bauteil {0} gehört zu einem anderen Kunden.").format(b.teilenummer))
		auftrag_api.position_aus_bauteil(doc, b, p, merker)
	doc.insert()
	auftrag_api.nachbereiten(doc, merker)
	return auftrag_api.auftrag_ui(doc)


@frappe.whitelist(methods=["POST"])
def koppeln(auftrag, positionen=None, kundenbestellnr="", bestelldatum=""):
	"""Bestellung an einen vorhandenen Auftrag koppeln: Bestellnummer und -datum, je Position die Positionsnummer des
	Kunden, sein Stückpreis und der Liefertermin. Preise des Auftrags bleiben, wie sie sind."""
	nur_cnc()
	if isinstance(positionen, str):
		positionen = json.loads(positionen)
	doc = frappe.get_doc("Auftrag", auftrag)
	doc.check_permission("write")
	if (kundenbestellnr or "").strip():
		doc.kundenbestellnr = kundenbestellnr.strip()
	if bestelldatum:
		doc.bestelldatum = bestelldatum
	for p in positionen or []:
		z = next((x for x in doc.positionen if x.position_key == p.get("auftragKey")), None)
		if not z:
			continue
		z.bestellposition = str(p.get("bestellposition") or z.bestellposition or "")[:40]
		if num(p.get("bestellpreis")) > 0:
			z.bestellpreis = r2(num(p["bestellpreis"]))
		if p.get("termin"):
			z.liefertermin = p["termin"]
		angaben = auftrag_api.bestellung_bereinigt(p.get("bestellung"))
		if angaben:
			z.bestellangaben = frappe.as_json(angaben)
	doc.save()
	return auftrag_api.auftrag_ui(doc)


@frappe.whitelist(methods=["POST"])
def datei_setzen(auftrag, datei):
	"""Das hochgeladene Bestell-PDF (am Auftrag abgelegt) als Bestellung des Kunden vermerken."""
	nur_cnc()
	doc = frappe.get_doc("Auftrag", auftrag)
	doc.check_permission("write")
	if not frappe.db.exists("File", {"file_url": datei, "attached_to_doctype": "Auftrag", "attached_to_name": auftrag}):
		frappe.throw(_("Die Datei gehört nicht zu diesem Auftrag."))
	doc.db_set("bestellung_datei", datei)
	return auftrag_api.auftrag_ui(doc)


# ----------------------------------------------------------------- Bestellvorlage je Kunde (angelernt)
def vorlage(kunde):
	"""Angelernte Spalten der Bestell-PDFs: { spalten: { kopftext: rolle }, kopf: { bestellnr: stichwort, datum: stichwort } }."""
	try:
		return json.loads(frappe.db.get_value("Kunde", kunde, "bestellvorlage") or "{}") or {}
	except (TypeError, ValueError):
		return {}


@frappe.whitelist(methods=["POST"])
def vorlage_lernen(kunde, vorlage):
	nur_cnc()
	if isinstance(vorlage, str):
		vorlage = json.loads(vorlage)
	sauber = {
		"spalten": {str(k)[:80]: str(v)[:30] for k, v in (vorlage.get("spalten") or {}).items() if k and v},
		"kopf": {str(k)[:30]: str(v)[:80] for k, v in (vorlage.get("kopf") or {}).items() if k and v},
	}
	frappe.db.set_value("Kunde", kunde, "bestellvorlage", json.dumps(sauber, ensure_ascii=False))
	return sauber


@frappe.whitelist(methods=["POST"])
def vorlage_vergessen(kunde):
	nur_cnc()
	frappe.db.set_value("Kunde", kunde, "bestellvorlage", None)
	return {}
