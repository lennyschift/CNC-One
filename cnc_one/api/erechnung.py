"""E-Rechnung zu festgeschriebenen Rechnungen: ZUGFeRD-PDF (PDF/A-3 mit eingebettetem XML), abgelegt als private Datei an der Rechnung.
Eine eigenständige XRechnung gibt es nicht (nur B2B). Die Daten stammen aus der Rechnung und ihrem Firmen-Snapshot; was dort fehlt
(Ansprechpartner, Telefon, E-Mail), wird aus den aktuellen Firmendaten ergänzt, damit sich auch ältere Rechnungen nachträglich ausstellen lassen."""

import json
import re
from datetime import date, datetime

import frappe
from frappe import _

from cnc_one.api.firma import firma_ui
from cnc_one.api.rechnung import BUCHHALTUNG, FESTGESCHRIEBEN, kaeufer_felder, rechnung_ui
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import briefbogen, erechnung, pdf
from cnc_one.logic.kalkulation import r2

STATUS_ZUGFERD = "ZUGFeRD"
STATUS_PDF = "Nur PDF"
STATUS_FEHLER = "Fehler"
EINHEITEN = {"Stk": "C62", "pauschal": "C62"}
TEMPLATE = "templates/rechnung_pdf.html"


# ------------------------------------------------------------------ Daten
def _de(wert):
	if not wert:
		return ""
	if isinstance(wert, (date, datetime)):
		return wert.strftime("%d.%m.%Y")
	t = str(wert)[:10].split("-")
	return f"{t[2]}.{t[1]}.{t[0]}" if len(t) == 3 else str(wert)


def _eur(wert):
	s = f"{abs(wert or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
	return ("-" if (wert or 0) < 0 else "") + s + " €"


def _firma(doc):
	"""Firmendaten der Rechnung (Snapshot); leere Angaben werden aus den aktuellen Firmendaten ergänzt."""
	snap = json.loads(doc.firma_snapshot) if isinstance(doc.firma_snapshot, str) and doc.firma_snapshot else dict(doc.firma_snapshot or {})
	jetzt = firma_ui()
	for k, v in jetzt.items():
		if not snap.get(k):
			snap[k] = v
	return snap


def _kaeufer(doc):
	felder = {
		"email": doc.get("kunde_email"), "strasse": doc.get("kunde_strasse"), "plz": doc.get("kunde_plz"), "ort": doc.get("kunde_ort"),
		"land": doc.get("kunde_land"),
	}
	if not (felder["plz"] or felder["ort"]) and doc.kunde and frappe.db.exists("Kunde", doc.kunde):
		# ältere Rechnung ohne Empfänger-Snapshot: aktuelle Stammdaten des Kunden
		neu = kaeufer_felder(frappe.get_doc("Kunde", doc.kunde))
		felder = {k.removeprefix("kunde_"): v for k, v in neu.items()}
	return {
		"name": doc.kunde_name or (doc.rechnungsadresse or "").split("\n")[0], "ust_id": doc.kunde_ust_id or "",
		**{k: (v or "").strip() for k, v in felder.items()},
	}


def _voller_name(firma):
	"""Firmenname samt Rechtsform (z. B. „Muster GmbH“), wie er auf der Rechnung stehen muss."""
	name, form = (firma.get("firmenname") or "").strip(), (firma.get("rechtsform") or "").strip()
	return f"{name} {form}" if form and form.lower() not in name.lower() else name


def _hinweis(p):
	teile = [p.lieferungen_text] if p.lieferungen_text else []
	if p.serien_text:
		teile.append(f"Seriennummern {p.serien_text}")
	return " · ".join(teile)


def _zeilen(doc):
	"""Die Positionen der E-Rechnung. Sonderkosten (Zeile 1.1, 1.2 …) hängen als Zuschläge an ihrer Bauteilposition (BG-28), die Zeilensumme
	enthält sie. Eine Sonderkosten-Zeile ohne Bauteilposition bleibt eine eigene Zeile."""
	zeilen, eltern = [], {}
	for p in doc.positionen:
		nr = (p.zeilen_id or "").split(".")[0]
		if p.art == "Sonderkosten" and nr in eltern:
			z = eltern[nr]
			z["zuschlaege"].append({"text": f"{p.bezeichnung} – Sonderkosten zu Position {nr}", "betrag": p.netto or 0})
			z["netto"] = r2(z["netto"] + (p.netto or 0))
			continue
		z = {
			"id": p.zeilen_id, "name": p.bezeichnung or p.teilenummer or "Position", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "",
			"menge": p.menge, "einheit": EINHEITEN.get(p.einheit or "Stk", erechnung.EINHEIT_STUECK), "einzelpreis": p.einzelpreis or 0,
			"netto": p.netto or 0, "hinweis": _hinweis(p), "zuschlaege": [],
		}
		zeilen.append(z)
		if p.art == "Bauteil":
			eltern[p.zeilen_id] = z
	return zeilen


def daten_aus_rechnung(doc, firma=None):
	"""Das Eingabe-Dictionary für `logic.erechnung` aus einer (festgeschriebenen) Rechnung."""
	firma = firma or _firma(doc)
	storno = doc.art == "Storno"
	bank = firma["banken"][0] if firma.get("banken") else {}
	vorgaenger = None
	if storno and doc.storno_zu:
		v = frappe.db.get_value("Rechnung", doc.storno_zu, ["rechnungsnummer", "rechnungsdatum"], as_dict=True)
		if v:
			vorgaenger = {"nummer": v.rechnungsnummer, "datum": v.rechnungsdatum}
	lieferscheine = []
	for p in doc.positionen:
		for x in (json.loads(p.lieferungen) if p.lieferungen and isinstance(p.lieferungen, str) else (p.lieferungen or [])):
			if x["lieferschein"] not in lieferscheine:
				lieferscheine.append(x["lieferschein"])
	bestellnr = (doc.kundenbestellnr or "").strip()
	tage = doc.zahlungsziel_tage or 0
	return {
		"nummer": doc.rechnungsnummer, "art": doc.art, "datum": doc.rechnungsdatum, "faellig": doc.faellig_am or doc.rechnungsdatum,
		"leistung_von": doc.leistung_von or doc.rechnungsdatum, "leistung_bis": doc.leistung_bis or doc.rechnungsdatum,
		"waehrung": "EUR", "bestellnr": bestellnr, "kaeufer_referenz": (doc.leitweg_id or bestellnr or doc.auftrag),
		"lieferscheine": lieferscheine, "vorgaenger": vorgaenger,
		"bemerkung": (doc.einleitung or "") if storno else "",
		"zahlungsbedingung": f"Zahlbar innerhalb von {tage} Tagen ohne Abzug bis {_de(doc.faellig_am)}" if tage else f"Sofort zahlbar ohne Abzug, fällig am {_de(doc.faellig_am)}",
		"verkaeufer": {
			"name": _voller_name(firma), "strasse": firma.get("strasse", ""), "plz": firma.get("plz", ""), "ort": firma.get("ort", ""),
			"land": firma.get("land", ""), "ust_id": firma.get("ustId", ""), "steuernummer": firma.get("steuernummer", ""),
			"ansprechpartner": firma.get("ansprechpartner", ""), "telefon": firma.get("telefon", ""), "email": firma.get("email", ""),
			"iban": "".join((bank.get("iban") or "").split()), "bic": bank.get("bic", ""),
		},
		"kaeufer": _kaeufer(doc),
		"steuersatz": doc.steuersatz or 19, "steuerkategorie": "S",
		"zeilen": _zeilen(doc),
		"netto": doc.netto or 0, "steuer": doc.steuerbetrag or 0, "brutto": doc.brutto or 0,
	}


# ------------------------------------------------------------------ PDF
def _zuschlaege_markieren(positionen):
	"""Sonderkosten erscheinen im PDF wie im XML als Zuschläge unter ihrer Bauteilposition; die letzte Zuschlagszeile trägt die Positionssumme."""
	eltern = None
	for p in positionen:
		if p["art"] == "Bauteil":
			eltern = {"pos": p, "summe": 0.0, "letzte": None}
		elif p["art"] == "Sonderkosten" and eltern:
			eltern["summe"] = r2(eltern["summe"] + p["netto"])
			eltern["letzte"] = p
			p["zuschlagZu"] = eltern["pos"]["zeile"]
			p["positionssumme"] = r2(eltern["pos"]["netto"] + eltern["summe"])
			for frueher in positionen:  # nur die letzte Zeile trägt die Summe
				if frueher is not p and frueher.get("zuschlagZu") == p["zuschlagZu"]:
					frueher.pop("positionssumme", None)


def _html(doc, firma):
	from cnc_one.api.angebot import _bild
	from cnc_one.api.bauteil import vorschau

	r = rechnung_ui(doc)
	r["firma"] = firma
	_zuschlaege_markieren(r["positionen"])
	for p in r["positionen"]:
		p["bild"] = _bild(vorschau(p["bauteilId"])) if p.get("art") == "Bauteil" and p.get("bauteilId") else ""
	storno = doc.art == "Storno"
	von, bis = _de(doc.leistung_von), _de(doc.leistung_bis)
	kontext = {
		"r": r, "f": firma, "storno": storno, "de": _de, "eur": _eur, "rahmen": briefbogen.rahmen(firma),
		"leistung": von if von == bis else f"{von} – {bis}" if von and bis else "",
		"vorgaenger_nummer": frappe.db.get_value("Rechnung", doc.storno_zu, "rechnungsnummer") if doc.storno_zu else "",
	}
	with open(frappe.get_app_path("cnc_one", TEMPLATE), encoding="utf-8") as f:
		return frappe.render_template(f.read(), kontext)


# ------------------------------------------------------------------ Ablage
def _dateiname(doc):
	return f"{doc.rechnungsnummer}.pdf"


def _fassungen(doc):
	"""Alle abgelegten Fassungen (neueste zuerst): `<Nr>.pdf`, dann `<Nr>_v2.pdf` … Eine abgelegte Datei wird nie überschrieben (GoBD)."""
	stamm = _dateiname(doc).rsplit(".", 1)[0]
	liste = frappe.get_all("File", filters={"attached_to_doctype": "Rechnung", "attached_to_name": doc.name, "file_name": ["like", f"{stamm}%.pdf"]}, fields=["name", "file_name"], order_by="creation desc, name desc")
	return [x for x in liste if re.fullmatch(re.escape(stamm) + r"(_v\d+)?\.pdf", x.file_name)]


def _datei_suchen(doc):
	f = _fassungen(doc)
	return f[0].name if f else None


def _ablegen(doc, inhalt):
	stamm = _dateiname(doc).rsplit(".", 1)[0]
	n = len(_fassungen(doc))
	frappe.get_doc({
		"doctype": "File", "file_name": f"{stamm}.pdf" if not n else f"{stamm}_v{n + 1}.pdf", "attached_to_doctype": "Rechnung",
		"attached_to_name": doc.name, "is_private": 1, "content": inhalt,
	}).insert(ignore_permissions=True)


def _status_setzen(doc, status, hinweis=""):
	frappe.db.set_value("Rechnung", doc.name, {"erechnung_status": status, "erechnung_hinweis": hinweis}, update_modified=False)


def erzeugen(doc):
	"""Erzeugt das PDF (immer als PDF/A-3) und bettet das ZUGFeRD-XML ein, wenn die Pflichtangaben vorhanden sind. Gibt den Status zurück."""
	if doc.status not in FESTGESCHRIEBEN + ("Gutschrift", "Storniert") or not doc.rechnungsnummer:
		frappe.throw(_("Eine E-Rechnung gibt es nur zu festgeschriebenen Rechnungen."))
	firma = _firma(doc)
	d = daten_aus_rechnung(doc, firma)
	fehlt = erechnung.fehlende_angaben(d)
	xml = erechnung.baue_cii(d) if not fehlt else None
	titel = f"{'Stornorechnung' if doc.art == 'Storno' else 'Rechnung'} {doc.rechnungsnummer}"
	_ablegen(doc, pdf.pdf_a3(_html(doc, firma), xml, titel=titel, autor=firma.get("firmenname", "")))
	if fehlt:
		status, hinweis = STATUS_PDF, "Für ZUGFeRD fehlt noch: " + ", ".join(fehlt) + "."
	else:
		status, hinweis = STATUS_ZUGFERD, ""
	_status_setzen(doc, status, hinweis)
	return status


def erzeugen_sicher(doc):
	"""Wie `erzeugen`, aber ein Fehler hält das Festschreiben nicht auf: Er wird protokolliert und als Status vermerkt."""
	if frappe.flags.in_test and not frappe.flags.erechnung_testen:
		return None  # die übrigen Tests sollen keine Dateien auf der Platte hinterlassen
	try:
		return erzeugen(frappe.get_doc("Rechnung", doc.name))
	except Exception:
		frappe.log_error(title=f"E-Rechnung {doc.name}")
		_status_setzen(doc, STATUS_FEHLER, "Die E-Rechnung ließ sich nicht erzeugen. Bitte über „E-Rechnung neu erzeugen“ erneut versuchen.")
		return STATUS_FEHLER


# ------------------------------------------------------------------ API
@frappe.whitelist(methods=["POST"])
def neu_erzeugen(id):
	"""Erzeugt die E-Rechnung einer festgeschriebenen Rechnung neu (z. B. nachdem Firmen- oder Kundendaten ergänzt wurden)."""
	frappe.only_for(BUCHHALTUNG)
	doc = frappe.get_doc("Rechnung", id)
	doc.check_permission("write")
	erzeugen(doc)
	return rechnung_ui(frappe.get_doc("Rechnung", id))


@frappe.whitelist()
def herunterladen(id):
	"""Lädt das PDF (mit ZUGFeRD-Daten, soweit möglich) einer festgeschriebenen Rechnung. Fehlt die Datei, wird sie erzeugt."""
	nur_cnc()
	doc = frappe.get_doc("Rechnung", id)
	doc.check_permission("read")
	name = _datei_suchen(doc)
	if not name and doc.status != "Entwurf":
		erzeugen(doc)
		name = _datei_suchen(doc)
	if not name:
		frappe.throw(_("Zu dieser Rechnung gibt es noch kein PDF."))
	datei = frappe.get_doc("File", name)
	inhalt = datei.get_content()
	frappe.local.response.filename = datei.file_name
	frappe.local.response.filecontent = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
	frappe.local.response.type = "pdf"
