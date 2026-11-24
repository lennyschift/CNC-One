"""Lieferantenanfragen. Eine Anfrage geht an einen Lieferanten und enthält mehrere Positionen.

Aus der Workbench für Fremdvergaben eines Angebots, oder frei (ohne Angebot) z. B. für Material: dann trägt man
Bezeichnung, Werkstoff, Abmessung, Einheit und Mengen selbst ein."""

ARTEN = ("Fremdvergabe", "Material", "Sonstiges")
EINHEITEN = ("Stk", "m", "kg", "Stangen", "Platten", "Zuschnitte")

import json
import mimetypes

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.einstellung import absender_fuer
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic.daten import als_json, datum, iso


def anfrage_ui(d):
	"""Die Anfrage in der Form, die die Oberfläche erwartet."""
	antwort = None
	if d.preise or d.lieferantenangebot_nr:
		antwort = {
			"angebotsnr": d.lieferantenangebot_nr or "",
			"gueltigBis": datum(d.gueltig_bis),
			"lieferzeit": d.lieferzeit or "",
			"preise": [{"posKey": z.position_key, "menge": z.menge, "proStk": z.pro_stk or 0, "einmalig": z.einmalig or 0} for z in d.preise],
			"nebenkosten": d.nebenkosten or 0,
			"nebenkostenText": d.nebenkosten_text or "",
			"pdf": d.angebot_pdf or "",
			"daten": als_json(d.angebot_daten) if d.angebot_daten else None,
		}
	return {
		"id": d.name,
		"vorgang": d.vorgang or d.name,
		"lieferantId": d.lieferant,
		"lieferantName": d.lieferant,
		"lieferantEmail": frappe.db.get_value("Lieferant", d.lieferant, "email") or "",
		"versendetAm": iso(d.versendet_am) if d.versendet_am else "",
		"neueAntwort": bool(d.neue_antwort),
		"zuschlag": bool(d.zuschlag),
		**_zuschlag_fuer(d),
		"nachrichten": [
			{
				"richtung": n.richtung, "datum": iso(n.datum) if n.datum else "", "vonEmail": n.von_email or "", "vonName": n.von_name or "",
				"an": n.an or "", "betreff": n.betreff or "", "text": n.text or "", "html": n.html or "",
				"anhaenge": als_json(n.anhaenge) if n.anhaenge else [],
			}
			for n in d.nachrichten
		],
		"erstellt": iso(d.creation),
		"status": d.status,
		"notiz": d.notiz or "",
		"angebotId": d.angebot or "",
		"art": d.art or "Fremdvergabe",
		"kundeName": d.kunde_name or "",
		"positionen": [
			{
				"key": p.position_key,
				"teilId": p.teil_id or "",
				"teil": {
					"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "",
					"material": p.material or "", "vorschaubild": bauteil_api.vorschau(p.bauteil) or bauteil_api.bild_aus_angebot(d.angebot, p.teil_id),
				},
				"agId": p.ag_id or "",
				"agName": p.ag_name or "",
				"abmessung": p.abmessung or "",
				"anforderungen": p.anforderungen or "",
				"einheit": p.einheit or "Stk",
				"mengen": als_json(p.mengen) if p.mengen else [],
			}
			for p in d.positionen
		],
		"antwort": antwort,
	}


def alle_ui():
	namen = frappe.get_list("Lieferantenanfrage", pluck="name", order_by="creation desc", limit_page_length=0)
	return [anfrage_ui(frappe.get_doc("Lieferantenanfrage", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


def _mengen(werte):
	return sorted({int(m) for m in (werte or []) if int(m or 0) > 0})


@frappe.whitelist(methods=["POST"])
def anlegen(angebot="", lieferanten=None, positionen=None, notiz="", art=""):
	"""Legt je Lieferant eine Anfrage mit allen Positionen an und liefert die neuen Anfragen.

	Mit `angebot` (aus der Workbench): `positionen` = [{ teilId, teil: {name, teilenummer, zeichnungsnr, material}, agId, agName, mengen }].
	Ohne `angebot` (freie Anfrage, z. B. Material): [{ teil: {name, material}, agName, abmessung, anforderungen, einheit, mengen }].
	Material zu einem Angebot (art = Material, aus der Workbench): wie die freie Anfrage, aber mit Bezug zum Angebot.
	"""
	nur_cnc()
	if isinstance(lieferanten, str):
		lieferanten = frappe.parse_json(lieferanten)
	if isinstance(positionen, str):
		positionen = frappe.parse_json(positionen)
	if not lieferanten:
		frappe.throw(_("Bitte mindestens einen Lieferanten wählen."))
	if not positionen:
		frappe.throw(_("Bitte mindestens eine Position wählen."))
	ang = frappe.get_doc("Angebot", angebot) if angebot else None
	art = art if art in ARTEN else ("Fremdvergabe" if ang else "Material")
	for l in lieferanten:
		if not frappe.db.exists("Lieferant", l):
			frappe.throw(_("Den Lieferanten {0} gibt es nicht.").format(l))

	zeilen = []
	for i, p in enumerate(positionen, 1):
		teil = p.get("teil") or {}
		mengen = _mengen(p.get("mengen"))
		if not mengen:
			frappe.throw(_("Jede Position braucht mindestens eine Menge."))
		material = art == "Material"
		if (not ang or material) and not (teil.get("name") or "").strip():
			frappe.throw(_("Position {0} braucht eine Bezeichnung.").format(i))
		einheit = (p.get("einheit") or "Stk").strip()[:20] or "Stk"
		zeilen.append({
			"position_key": f"mat:{i}" if ang and material else f"{p.get('teilId') or ''}:{p.get('agId') or ''}" if ang else f"frei:{i}",
			"teil_id": p.get("teilId") or "",
			"bauteil": bauteil_api.finden(ang.kunde, teil.get("teilenummer")) if ang and not material else None,
			"teilenummer": (teil.get("teilenummer") or "").strip(),
			"bezeichnung": (teil.get("name") or "").strip(),
			"zeichnungsnr": (teil.get("zeichnungsnr") or "").strip(),
			"material": (teil.get("material") or "").strip(),
			"ag_id": p.get("agId") or "",
			"ag_name": (p.get("agName") or "").strip(),
			"abmessung": (p.get("abmessung") or "").strip(),
			"anforderungen": (p.get("anforderungen") or "").strip()[:140],
			"einheit": einheit,
			"mengen": json.dumps(mengen),
		})

	neu = []
	vorgang = None  # alle Anfragen dieses Aufrufs gehören zusammen: Nummer der ersten
	for l in lieferanten:
		doc = frappe.new_doc("Lieferantenanfrage")
		doc.lieferant = l
		doc.angebot = ang.name if ang else None
		doc.art = art
		doc.status = "Gesendet"
		doc.notiz = (notiz or "").strip()
		for z in zeilen:
			doc.append("positionen", dict(z))
		doc.vorgang = vorgang
		doc.insert()
		if not vorgang:
			vorgang = doc.name
			doc.db_set("vorgang", vorgang, update_modified=False)
		neu.append(anfrage_ui(doc))
	return neu


def _geladen(id):
	doc = frappe.get_doc("Lieferantenanfrage", id)
	doc.check_permission("write")
	return doc


@frappe.whitelist(methods=["POST"])
def antwort_erfassen(id, antwort):
	"""Erfasst das Angebot des Lieferanten: Nummer, Gültigkeit und Preise je Position und Menge."""
	nur_cnc()
	if isinstance(antwort, str):
		antwort = frappe.parse_json(antwort)
	preise = [z for z in (antwort.get("preise") or [])]
	if not any((z.get("proStk") or 0) > 0 or (z.get("einmalig") or 0) > 0 for z in preise):
		frappe.throw(_("Bitte mindestens einen Preis eintragen."))
	doc = _geladen(id)
	doc.lieferantenangebot_nr = (antwort.get("angebotsnr") or "").strip()
	doc.gueltig_bis = antwort.get("gueltigBis") or None
	doc.lieferzeit = (antwort.get("lieferzeit") or "").strip()[:140]
	doc.nebenkosten = max(float(antwort.get("nebenkosten") or 0), 0)
	doc.nebenkosten_text = (antwort.get("nebenkostenText") or "").strip()[:1000]
	# eingelesen aus einem PDF: Datei und erkannte Positionen (mit Zuordnung) bleiben zum Nachvollziehen
	if "pdf" in antwort:
		doc.angebot_pdf = (antwort.get("pdf") or "").strip()[:500]
	if "daten" in antwort:
		doc.angebot_daten = json.dumps(antwort["daten"], ensure_ascii=False) if antwort.get("daten") else None
	doc.neue_antwort = 0
	doc.set("preise", [])
	for z in preise:
		doc.append("preise", {
			"position_key": z.get("posKey"), "menge": int(z.get("menge") or 0),
			"pro_stk": z.get("proStk") or 0, "einmalig": z.get("einmalig") or 0,
		})
	doc.status = "Angebot erhalten"
	doc.save()
	return anfrage_ui(doc)


@frappe.whitelist(methods=["POST"])
def angebotsvorlage(lieferant):
	"""Angelernte Vorlage des Lieferanten für seine Angebots-PDFs: { spalten: { kopftext: rolle }, preisJe }."""
	nur_cnc()
	return als_json(frappe.db.get_value("Lieferant", lieferant, "angebot_vorlage")) or {}


@frappe.whitelist(methods=["POST"])
def angebotsvorlage_lernen(lieferant, vorlage):
	"""Merkt sich Spalten und Preiseinheit für die nächsten Angebote dieses Lieferanten (leer = vergessen)."""
	nur_cnc()
	if isinstance(vorlage, str):
		vorlage = frappe.parse_json(vorlage)
	doc = frappe.get_doc("Lieferant", lieferant)
	doc.check_permission("write")
	v = {"spalten": {str(k)[:80]: str(r or "")[:20] for k, r in ((vorlage or {}).get("spalten") or {}).items()}, "preisJe": str((vorlage or {}).get("preisJe") or "")[:5]}
	doc.db_set("angebot_vorlage", json.dumps(v, ensure_ascii=False) if v["spalten"] or v["preisJe"] else None, update_modified=False)
	return v


@frappe.whitelist(methods=["POST"])
def mail_uebernehmen(mail, id):
	"""Eine Mail aus dem Posteingang (Antwort des Lieferanten ohne Anfragenummer) gehört zu dieser Lieferantenanfrage:
	Nachrichten und Anhänge wandern dorthin, die Mail verschwindet aus dem Posteingang."""
	nur_cnc()
	doc = _geladen(id)
	m = frappe.get_doc("Mail Anfrage", mail)
	m.check_permission("write")
	if m.angebot or frappe.get_all("Eingangsrechnung", filters={"mail": m.name}, limit=1):
		frappe.throw(_("Diese Mail ist schon weiterverarbeitet."))
	for n in sorted(m.nachrichten, key=lambda x: x.idx):
		zeile = {f: n.get(f) for f in ("richtung", "datum", "von_email", "von_name", "an", "cc", "betreff", "message_id", "in_reply_to", "referenzen", "text", "html", "anhaenge", "hinweis")}
		n.message_id = None  # die Kennung gehört jetzt zur Lieferantenanfrage (Mail wird nicht erneut geholt)
		n.db_update()
		doc.append("nachrichten", zeile)
	for f in frappe.get_all("File", filters={"attached_to_doctype": "Mail Anfrage", "attached_to_name": m.name}, pluck="name"):
		frappe.db.set_value("File", f, {"attached_to_doctype": "Lieferantenanfrage", "attached_to_name": doc.name}, update_modified=False)
	doc.neue_antwort = 1
	doc.save()
	frappe.delete_doc("Mail Anfrage", m.name, ignore_permissions=True)
	return anfrage_ui(doc)


@frappe.whitelist(methods=["POST"])
def absagen(id):
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Gesendet":
		frappe.throw(_("Nur eine gesendete Anfrage lässt sich als abgesagt markieren."))
	doc.status = "Abgesagt"
	doc.save()
	return anfrage_ui(doc)


@frappe.whitelist(methods=["POST"])
def gelesen(id):
	"""Neue Antwort gesehen."""
	nur_cnc()
	doc = _geladen(id)
	if doc.neue_antwort:
		doc.db_set("neue_antwort", 0, update_modified=False)
	return anfrage_ui(doc)


def _mit_preis(d):
	"""Positionen, für die der Lieferant einen Preis genannt hat."""
	return [k for k in dict.fromkeys(z.position_key for z in d.preise if (z.pro_stk or 0) > 0 or (z.einmalig or 0) > 0)]


def _zuschlag_fuer(d):
	"""Wofür der Zuschlag gilt: Positionen (posKey) und gewählte Alternativen (Index im eingelesenen Angebot).
	Ohne Auswahl (ältere Zuschläge) gelten alle Positionen mit Preis."""
	if not d.zuschlag:
		return {"zuschlagPositionen": [], "zuschlagAlternativen": []}
	w = als_json(d.zuschlag_positionen) if d.zuschlag_positionen else None
	if not isinstance(w, dict):
		return {"zuschlagPositionen": _mit_preis(d), "zuschlagAlternativen": []}
	return {"zuschlagPositionen": list(w.get("positionen") or []), "zuschlagAlternativen": list(w.get("alternativen") or [])}


@frappe.whitelist(methods=["POST"])
def zuschlag(id, an=1, positionen=None, alternativen=None):
	"""Zuschlag erteilen (für alle oder ausgewählte Positionen, auch Alternativen) oder zurücknehmen; Grundlage für die
	Bestellung. Eine Position geht nur an einen Lieferanten: bei den anderen Anfragen des Vorgangs fällt sie heraus,
	bleibt dort nichts übrig, ist deren Zuschlag weg. Liefert die Anfrage, unter „geaenderte“ die anderen geänderten."""
	nur_cnc()
	doc = _geladen(id)
	geaenderte = []
	if not frappe.utils.cint(an):
		doc.zuschlag = 0
		doc.zuschlag_positionen = None
		doc.save()
	else:
		pos = als_json(positionen) if isinstance(positionen, str) else positionen
		alt = als_json(alternativen) if isinstance(alternativen, str) else alternativen
		pos = list(dict.fromkeys(pos)) if pos is not None else _mit_preis(doc)
		alt = [int(i) for i in (alt or [])]
		if not pos and not alt:
			frappe.throw(_("Bitte mindestens eine Position für den Zuschlag wählen."))
		gueltig = {p.position_key for p in doc.positionen}
		if any(k not in gueltig for k in pos):
			frappe.throw(_("Die Position gibt es in dieser Anfrage nicht."))
		doc.zuschlag = 1
		doc.zuschlag_positionen = frappe.as_json({"positionen": pos, "alternativen": alt})
		doc.save()
		for andere in vorgang_docs(doc.vorgang or doc.name):
			if andere.name == doc.name or not andere.zuschlag:
				continue
			bisher = _zuschlag_fuer(andere)
			rest = [k for k in bisher["zuschlagPositionen"] if k not in pos]
			if rest == bisher["zuschlagPositionen"]:
				continue
			if rest or bisher["zuschlagAlternativen"]:
				andere.zuschlag_positionen = frappe.as_json({"positionen": rest, "alternativen": bisher["zuschlagAlternativen"]})
			else:
				andere.zuschlag = 0
				andere.zuschlag_positionen = None
			andere.save()
			geaenderte.append(anfrage_ui(andere))
	return {**anfrage_ui(doc), "geaenderte": geaenderte}


# ----------------------------------------------------------------- per Mail: eine Mail je Vorgang, Lieferanten in BCC
def vorgang_docs(vorgang):
	namen = frappe.get_all("Lieferantenanfrage", filters={"vorgang": vorgang}, pluck="name", order_by="name asc")
	if not namen and frappe.db.exists("Lieferantenanfrage", vorgang):
		namen = [vorgang]
	if not namen:
		frappe.throw(_("Die Anfrage {0} gibt es nicht.").format(vorgang))
	return [frappe.get_doc("Lieferantenanfrage", n) for n in namen]


def _mengen_text(p):
	einheit = p.einheit or "Stk"
	return " / ".join(f"{m} {einheit}" for m in (als_json(p.mengen) if p.mengen else []))


def tabelle(doc):
	"""Die Positionen der Anfrage als Zeilen: [(Pos, Was, Werkstoff, Abmessung/Zeichnung, Menge)]."""
	zeilen = []
	for i, p in enumerate(doc.positionen, 1):
		was = p.bezeichnung or ""
		if p.ag_name:
			was = f"{p.ag_name}: {was}" if was else p.ag_name
		if p.teilenummer:
			was += f" (Teilenummer {p.teilenummer})"
		masse = p.abmessung or (f"Zeichnung {p.zeichnungsnr}" + (f" Rev. {p.revision}" if getattr(p, "revision", "") else "") if p.zeichnungsnr else "")
		zeilen.append((str(i), was, p.material or "", masse, _mengen_text(p)))
	return zeilen


TABELLE_KOPF = ("Pos", "Bezeichnung", "Werkstoff", "Abmessung / Zeichnung", "Menge")


def tabelle_text(zeilen):
	breiten = [max(len(TABELLE_KOPF[i]), *(len(z[i]) for z in zeilen)) for i in range(5)]
	fmt = lambda z: "  ".join(str(w).ljust(breiten[i]) for i, w in enumerate(z)).rstrip()
	return "\n".join([fmt(TABELLE_KOPF), "  ".join("-" * b for b in breiten), *(fmt(z) for z in zeilen)])


def tabelle_html(zeilen):
	from frappe.utils import escape_html

	th = "".join(f'<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;font-size:13px">{escape_html(k)}</th>' for k in TABELLE_KOPF)
	tr = "".join(
		"<tr>" + "".join(f'<td style="padding:6px 10px;border-bottom:1px solid #ddd;font-size:13px;vertical-align:top">{escape_html(w)}</td>' for w in z) + "</tr>"
		for z in zeilen
	)
	return f'<table style="border-collapse:collapse;margin:4px 0 14px;font-family:Arial,Helvetica,sans-serif;color:#1c1c1c"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


ANFRAGE_VORLAGE = (
	"Sehr geehrte Damen und Herren,\n\nbitte senden Sie uns ein Angebot für {was}:\n\n{{tabelle}}\n\n{hinweis}"
	"Bitte nennen Sie in Ihrem Angebot unsere Anfragenummer {nummer} und Ihre Lieferzeit.{anhang}\n\nMit freundlichen Grüßen\n{absender}"
)


def _anhaenge(docs, zeichnungen=True, modelle=False):
	"""Zeichnungen und Modelle der Bauteile in den Positionen: [(Dateiname, Inhalt)], ohne doppelte."""
	from cnc_one.api.bauteil import dateien_fuer

	urls = []
	for p in docs[0].positionen:
		if not p.bauteil:
			continue
		d = dateien_fuer(p.bauteil)
		if zeichnungen and d["zeichnung"]:
			urls.append(d["zeichnung"])
		if modelle and d["stepDatei"]:
			urls.append(d["stepDatei"])
	out = []
	for url in dict.fromkeys(urls):
		name = frappe.db.get_value("File", {"file_url": url}, "name")
		if name:
			f = frappe.get_doc("File", name)
			out.append((f.file_name, f.get_content()))
	return out


@frappe.whitelist(methods=["POST"])
def mail_vorschlag(vorgang):
	"""Vorschlag für die Anfrage-Mail eines Vorgangs: an uns selbst, die Lieferanten in BCC (sie sehen sich nicht
	gegenseitig). Der Text ist frei änderbar; {tabelle} steht für die Tabelle der Positionen."""
	nur_cnc()
	from cnc_one.api.firma import firma_ui
	from cnc_one.logic import mail

	docs = vorgang_docs(vorgang)
	s = mail.einstellungen()
	firma = firma_ui().get("firmenname", "")
	erste = docs[0]
	mit_bauteil = any(p.bauteil for p in erste.positionen)
	was = "folgendes Material" if erste.art == "Material" else "folgende Leistungen" if erste.art == "Fremdvergabe" else "folgende Positionen"
	text = ANFRAGE_VORLAGE.format(
		was=was, nummer=vorgang, absender=absender_fuer(firma, s.absender_name)[0],
		hinweis=f"Hinweis: {erste.notiz}\n\n" if erste.notiz else "",
		anhang=" Zeichnungen finden Sie im Anhang." if mit_bauteil else "",
	)
	titel = erste.positionen[0].bezeichnung if len(erste.positionen) == 1 else f"{len(erste.positionen)} Positionen"
	adressen = [(d.lieferant, frappe.db.get_value("Lieferant", d.lieferant, "email") or "") for d in docs]
	bereit = bool(s.smtp_server and s.benutzer and s.get_password("passwort", raise_exception=False))
	return {
		"an": s.benutzer or "", "cc": "", "bcc": ", ".join(a for _l, a in adressen if a),
		"ohneAdresse": [l for l, a in adressen if not a],
		"betreff": f"Anfrage {vorgang}: {titel}", "text": text,
		"tabelle": {"kopf": list(TABELLE_KOPF), "zeilen": [list(z) for z in tabelle(erste)]},
		"zeichnungen": mit_bauteil, "bereit": bereit, "absender": s.benutzer or "",
		"versendetAm": iso(erste.versendet_am) if erste.versendet_am else "",
	}


def _absaetze(text):
	from frappe.utils import escape_html
	import re

	return "".join(
		'<p style="margin:0 0 12px">' + escape_html(a.strip("\n")).replace("\n", "<br>") + "</p>"
		for a in re.split(r"\n\s*\n", (text or "").strip()) if a.strip()
	)


def mail_html(text, zeilen):
	"""Unser Text als HTML; an der Stelle {tabelle} steht die Tabelle der Positionen."""
	teile = (text or "").split("{tabelle}")
	inhalt = tabelle_html(zeilen).join(_absaetze(t) for t in teile)
	return f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.45;color:#1c1c1c">{inhalt}</div></body></html>'


@frappe.whitelist(methods=["POST"])
def mail_senden(vorgang, an="", cc="", bcc="", betreff="", text="", zeichnungen=1, modelle=0):
	"""Schickt die Anfrage als eine Mail: An/CC wie eingetragen, die Lieferanten in BCC. Text und HTML (mit Tabelle),
	auf Wunsch mit Zeichnungen und 3D-Modellen. Danach: Kopie in „Gesendet“ und die Mail im Verlauf jeder Anfrage."""
	nur_cnc()
	from email.message import EmailMessage
	from email.utils import formataddr, formatdate, getaddresses, make_msgid

	from frappe.utils import now_datetime, validate_email_address

	from cnc_one.api.firma import firma_ui
	from cnc_one.logic import mail

	docs = vorgang_docs(vorgang)
	for d in docs:
		d.check_permission("write")
	liste = lambda w: [a.lower() for _n, a in getaddresses([w or ""]) if "@" in a]
	an_l, cc_l, bcc_l = liste(an), liste(cc), liste(bcc)
	if not (an_l or cc_l or bcc_l):
		frappe.throw(_("Bitte mindestens einen Empfänger eintragen."))
	for x in an_l + cc_l + bcc_l:
		validate_email_address(x, throw=True)
	if not (betreff or "").strip():
		frappe.throw(_("Bitte einen Betreff eintragen."))

	s = mail.einstellungen()
	zeilen = tabelle(docs[0])
	msg = EmailMessage()
	msg["From"] = formataddr((absender_fuer(firma_ui().get("firmenname", ""), s.absender_name)[1], s.benutzer or ""))
	if an_l:
		msg["To"] = ", ".join(an_l)
	if cc_l:
		msg["Cc"] = ", ".join(cc_l)
	msg["Subject"] = betreff.strip()
	msg["Date"] = formatdate(localtime=True)
	msg["Message-ID"] = make_msgid(domain=(s.benutzer or "cnc-one.local").rsplit("@", 1)[-1])
	klartext = (text or "").replace("{tabelle}", tabelle_text(zeilen))
	msg.set_content(klartext)
	msg.add_alternative(mail_html(text, zeilen), subtype="html")
	anhaenge = _anhaenge(docs, frappe.utils.cint(zeichnungen), frappe.utils.cint(modelle))
	for name, inhalt in anhaenge:
		haupt, _s, unter = (mimetypes.guess_type(name)[0] or "application/octet-stream").partition("/")
		msg.add_attachment(inhalt, maintype=haupt, subtype=unter, filename=name)

	# BCC steht nicht in den Kopfzeilen, nur in der Empfängerliste des Servers
	mail.smtp_senden(s, msg, list(dict.fromkeys(an_l + cc_l + bcc_l)))
	hinweis = mail.gesendet_ablegen(s, msg)
	jetzt = now_datetime()
	for d in docs:
		d.append("nachrichten", {
			"richtung": "Ausgang", "datum": jetzt, "von_email": (s.benutzer or "").lower(), "von_name": absender_fuer(firma_ui().get("firmenname", ""), s.absender_name)[1],
			"an": msg["To"] or "", "cc": ", ".join(x for x in [msg["Cc"] or "", ("BCC: " + ", ".join(bcc_l)) if bcc_l else ""] if x),
			"betreff": msg["Subject"], "message_id": msg["Message-ID"], "text": klartext, "html": mail_html(text, zeilen),
			"anhaenge": json.dumps([{"name": n, "groesse": len(x)} for n, x in anhaenge], ensure_ascii=False),
		})
		d.versendet_am = jetzt
		d.save()
	return {"anfragen": [anfrage_ui(d) for d in docs], "hinweis": hinweis}


# ----------------------------------------------------------------- Vorlagen: Lieferanten je Werkstoff/Leistung
def vorlage_ui(d):
	return {
		"id": d.name, "name": d.bezeichnung, "stichwoerter": d.stichwoerter or "", "isoGruppe": d.iso_gruppe or "", "art": d.art or "",
		"lieferanten": als_json(d.lieferanten) if d.lieferanten else [], "hinweis": d.hinweis or "", "aktiv": bool(d.aktiv),
	}


def vorlage_setzen(doc, d):
	if doc.is_new():
		doc.bezeichnung = (d.get("name") or "").strip()
	doc.stichwoerter = ", ".join(w.strip() for w in (d.get("stichwoerter") or "").replace("\n", ",").split(",") if w.strip())
	doc.iso_gruppe = d.get("isoGruppe") if d.get("isoGruppe") in ("P", "M", "K", "N", "S", "H") else ""
	doc.art = d.get("art") if d.get("art") in ARTEN else ""
	lieferanten = [l for l in (d.get("lieferanten") or []) if frappe.db.exists("Lieferant", l)]
	doc.lieferanten = json.dumps(lieferanten, ensure_ascii=False)
	doc.hinweis = (d.get("hinweis") or "").strip()
	doc.aktiv = 1 if d.get("aktiv", True) else 0

