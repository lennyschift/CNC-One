"""E-Rechnung zu festgeschriebenen Rechnungen: ZUGFeRD-PDF (PDF/A-3 mit eingebettetem XML) und XRechnung-XML, abgelegt als private Dateien
an der Rechnung. Die Daten stammen aus der Rechnung und ihrem Firmen-Snapshot; was dort fehlt (Ansprechpartner, Telefon, E-Mail), wird
aus den aktuellen Firmendaten ergänzt, damit sich auch ältere Rechnungen nachträglich ausstellen lassen."""

import json
import re
from datetime import date, datetime

import frappe
from frappe import _

from cnc_one.api.firma import firma_ui
from cnc_one.api.rechnung import BUCHHALTUNG, FESTGESCHRIEBEN, kaeufer_felder, rechnung_ui
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import erechnung, pdf

STATUS_ALLES = "ZUGFeRD und XRechnung"
STATUS_ZUGFERD = "ZUGFeRD"
STATUS_PDF = "Nur PDF"
STATUS_FEHLER = "Fehler"
ZUGFERD_STATUS = (STATUS_ALLES, STATUS_ZUGFERD)
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
		"zeilen": [
			{
				"id": p.zeilen_id, "name": p.bezeichnung or p.teilenummer or "Position", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "",
				"menge": p.menge, "einheit": EINHEITEN.get(p.einheit or "Stk", erechnung.EINHEIT_STUECK), "einzelpreis": p.einzelpreis or 0,
				"netto": p.netto or 0, "hinweis": _hinweis(p),
			}
			for p in doc.positionen
		],
		"netto": doc.netto or 0, "steuer": doc.steuerbetrag or 0, "brutto": doc.brutto or 0,
	}


# ------------------------------------------------------------------ PDF
def _html(doc, firma):
	r = rechnung_ui(doc)
	r["firma"] = firma
	storno = doc.art == "Storno"
	von, bis = _de(doc.leistung_von), _de(doc.leistung_bis)
	kontext = {
		"r": r, "f": firma, "storno": storno, "de": _de, "eur": _eur,
		"leistung": von if von == bis else f"{von} – {bis}" if von and bis else "",
		"vorgaenger_nummer": frappe.db.get_value("Rechnung", doc.storno_zu, "rechnungsnummer") if doc.storno_zu else "",
	}
	with open(frappe.get_app_path("cnc_one", TEMPLATE), encoding="utf-8") as f:
		return frappe.render_template(f.read(), kontext)


# ------------------------------------------------------------------ Ablage
def _dateiname(doc, art):
	return f"{doc.rechnungsnummer}.pdf" if art == "pdf" else f"{doc.rechnungsnummer}_xrechnung.xml"


def _fassungen(doc, art):
	"""Alle abgelegten Fassungen (neueste zuerst): `<Nr>.pdf`, dann `<Nr>_v2.pdf` … Eine abgelegte Datei wird nie überschrieben (GoBD)."""
	stamm, endung = _dateiname(doc, art).rsplit(".", 1)
	liste = frappe.get_all("File", filters={"attached_to_doctype": "Rechnung", "attached_to_name": doc.name, "file_name": ["like", f"{stamm}%.{endung}"]}, fields=["name", "file_name"], order_by="creation desc, name desc")
	return [x for x in liste if re.fullmatch(re.escape(stamm) + r"(_v\d+)?\." + endung, x.file_name)]


def _datei_suchen(doc, art):
	f = _fassungen(doc, art)
	return f[0].name if f else None


def _ablegen(doc, art, inhalt):
	stamm, endung = _dateiname(doc, art).rsplit(".", 1)
	n = len(_fassungen(doc, art))
	frappe.get_doc({
		"doctype": "File", "file_name": f"{stamm}.{endung}" if not n else f"{stamm}_v{n + 1}.{endung}", "attached_to_doctype": "Rechnung",
		"attached_to_name": doc.name, "is_private": 1, "content": inhalt,
	}).insert(ignore_permissions=True)


def _status_setzen(doc, status, hinweis=""):
	frappe.db.set_value("Rechnung", doc.name, {"erechnung_status": status, "erechnung_hinweis": hinweis}, update_modified=False)


def erzeugen(doc):
	"""Erzeugt PDF (immer, als PDF/A-3) und, soweit die Angaben reichen, ZUGFeRD-Anhang und XRechnung-XML. Gibt den Status zurück."""
	if doc.status not in FESTGESCHRIEBEN + ("Gutschrift", "Storniert") or not doc.rechnungsnummer:
		frappe.throw(_("Eine E-Rechnung gibt es nur zu festgeschriebenen Rechnungen."))
	firma = _firma(doc)
	d = daten_aus_rechnung(doc, firma)
	fehlt = erechnung.fehlende_angaben(d)
	xml_zugferd = erechnung.baue_cii(d, "zugferd") if not fehlt["zugferd"] else None
	titel = f"{'Stornorechnung' if doc.art == 'Storno' else 'Rechnung'} {doc.rechnungsnummer}"
	_ablegen(doc, "pdf", pdf.pdf_a3(_html(doc, firma), xml_zugferd, titel=titel, autor=firma.get("firmenname", "")))
	if not fehlt["xrechnung"]:
		_ablegen(doc, "xml", erechnung.baue_cii(d, "xrechnung"))
	if not fehlt["xrechnung"]:
		status, hinweis = STATUS_ALLES, ""
	elif not fehlt["zugferd"]:
		status, hinweis = STATUS_ZUGFERD, "Für die XRechnung fehlt noch: " + ", ".join(fehlt["xrechnung"]) + "."
	else:
		status, hinweis = STATUS_PDF, "Für ZUGFeRD und XRechnung fehlt noch: " + ", ".join(fehlt["xrechnung"]) + "."
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
def herunterladen(id, art):
	"""Lädt das PDF (art=pdf) oder die XRechnung-XML (art=xml) einer Rechnung. Fehlt die Datei, wird sie erzeugt, wenn möglich."""
	nur_cnc()
	if art not in ("pdf", "xml"):
		frappe.throw(_("Die Art der Datei ist pdf oder xml."))
	doc = frappe.get_doc("Rechnung", id)
	doc.check_permission("read")
	if art == "xml" and doc.erechnung_status != STATUS_ALLES:
		frappe.throw(_("Für diese Rechnung gibt es keine XRechnung. Prüfen Sie den Hinweis zur E-Rechnung."))
	name = _datei_suchen(doc, art)
	if not name and doc.status != "Entwurf":
		erzeugen(doc)
		name = _datei_suchen(doc, art)
	if not name:
		frappe.throw(_("Diese Datei gibt es nicht. Prüfen Sie den Hinweis zur E-Rechnung."))
	datei = frappe.get_doc("File", name)
	frappe.local.response.filename = datei.file_name
	inhalt = datei.get_content()
	frappe.local.response.filecontent = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
	frappe.local.response.type = "pdf" if art == "pdf" else "download"
