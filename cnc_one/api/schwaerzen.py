"""Zeichnungen schwärzen: Kundendaten (Namen, Logos, Schriftfeld-Einträge …) aus Kundenzeichnungen entfernen, bevor
sie an Partner (Lieferantenanfragen) oder in die Fertigung gehen.

Geschwärzt wird im Browser (lib/schwaerzen: jede Seite wird zu einem Bild, die Bereiche werden übermalt, daraus entsteht
eine neue PDF nur aus Bildern, die danach geprüft wird). Hier liegen:
  - die Regelsätze (Standard + je Kunde) und die Begriffe aus den Stammdaten des Kunden,
  - das Protokoll je Schwärzung (ohne Inhalte) mit der geschwärzten Datei,
  - eine zweite, unabhängige Prüfung der fertigen Datei auf dem Server,
  - die Freigabe nach der Gegenprüfung durch einen Menschen. Nur freigegebene Fassungen gehen an Partner.
"""

import base64
import hashlib
import io
import json
import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic.daten import als_json, iso

STANDARD = "Standard"
MAX_PDF = 80 * 1024 * 1024
LISTEN = ("directKeywords", "headerKeywords", "changeTableKeywords", "labelRightKeywords", "columnAboveKeywords")
STANDARD_REGELN = {
	"version": 1, "name": STANDARD, "directKeywords": [], "headerKeywords": [], "changeTableKeywords": [],
	"labelRightKeywords": ["Gez.", "Gezeichnet", "Gepr.", "Geprüft", "Freigegeben", "Erstellt", "Bearb.", "Drawn by", "Checked by", "Approved by"],
	"columnAboveKeywords": [], "detectEmail": True, "detectPhone": False, "logoThreshold": 0.45, "logos": [], "logoOptions": {},
}


# ----------------------------------------------------------------- Regelsätze
def _liste(v, n=200):
	out, gesehen = [], set()
	for x in v if isinstance(v, list) else []:
		s = str(x or "").strip()[:80]
		if s and s.lower() not in gesehen:
			gesehen.add(s.lower())
			out.append(s)
	return out[:n]


def regeln_bereinigen(r):
	"""Nur bekannte Felder mit Grenzen (wie lib/schwaerzen/rules.ts regelnBereinigen)."""
	r = r if isinstance(r, dict) else {}
	out = {"version": 1, "name": str(r.get("name") or "")[:80]}
	for k in LISTEN:
		out[k] = _liste(r.get(k))
	out["detectEmail"] = bool(r.get("detectEmail", True))
	out["detectPhone"] = bool(r.get("detectPhone", False))
	try:
		out["logoThreshold"] = min(0.95, max(0.3, float(r.get("logoThreshold") or 0.45)))
	except (TypeError, ValueError):
		out["logoThreshold"] = 0.45
	logos = []
	for l in (r.get("logos") or [])[:12]:
		if not isinstance(l, dict):
			continue
		url = str(l.get("dataUrl") or "")
		if not re.match(r"^/private/files/[^/]+$", url):
			continue
		logos.append({
			"id": str(l.get("id") or url)[:64], "name": str(l.get("name") or "Logo")[:80], "dataUrl": url,
			"width": max(4, min(20000, int(l.get("width") or 100))), "height": max(4, min(20000, int(l.get("height") or 100))),
			"enabled": l.get("enabled") is not False,
		})
	out["logos"] = logos
	opt = {}
	for k, o in (r.get("logoOptions") or {}).items():
		if not isinstance(o, dict):
			continue
		e = {}
		if o.get("threshold") is not None:
			e["threshold"] = min(0.95, max(0.3, float(o["threshold"])))
		if o.get("maxHits") is not None:
			e["maxHits"] = max(1, min(10, int(o["maxHits"])))
		if o.get("zone") in ("all", "top", "bottom", "left", "right", "corners"):
			e["zone"] = o["zone"]
		opt[str(k)[:70]] = e
	out["logoOptions"] = opt
	return out


def _standard_doc():
	if not frappe.db.exists("Schwaerzregelsatz", STANDARD):
		frappe.get_doc({"doctype": "Schwaerzregelsatz", "bezeichnung": STANDARD, "aktiv": 1, "regeln": json.dumps(STANDARD_REGELN, ensure_ascii=False)}).insert(ignore_permissions=True)
	return frappe.get_doc("Schwaerzregelsatz", STANDARD)


def regelsatz_ui(d):
	return {
		"id": d.name, "bezeichnung": d.bezeichnung, "kundeId": d.kunde or "", "kundeName": frappe.db.get_value("Kunde", d.kunde, "kundenname") if d.kunde else "",
		"aktiv": bool(d.aktiv), "standard": d.name == STANDARD, "regeln": regeln_bereinigen(als_json(d.regeln) or {}),
	}


def kunden_begriffe(kunde):
	"""Begriffe aus den Stammdaten des Kunden, die auf einer weitergegebenen Zeichnung nicht stehen dürfen: Name (auch ohne
	Rechtsform), Kürzel, Ansprechpartner, E-Mail-Adressen und ihre Domain."""
	if not kunde or not frappe.db.exists("Kunde", kunde):
		return []
	k = frappe.get_doc("Kunde", kunde)
	out = []
	name = (k.kundenname or "").strip()
	if name:
		out.append(name)
		ohne = re.sub(r"\s*(gmbh\s*&\s*co\.?\s*kg|gmbh|ag|kg|ohg|gbr|e\.?\s*k\.?|ug|se|inc\.?|ltd\.?|co\.?\s*kg)\s*$", "", name, flags=re.I).strip(" ,.-")
		if ohne and ohne != name and len(ohne) >= 3:
			out.append(ohne)
	if len((k.kuerzel or "").strip()) >= 3:
		out.append(k.kuerzel.strip())
	for c in k.get("kontakte") or []:
		voll = " ".join(x for x in (c.vorname, c.nachname) if x).strip()
		if len(voll) >= 4:
			out.append(voll)
		if len((c.nachname or "").strip()) >= 4:
			out.append(c.nachname.strip())
		mail = (c.email or "").strip().lower()
		if "@" in mail:
			out.append(mail)
			domain = mail.split("@", 1)[1]
			if domain and domain.split(".")[0] not in ("gmail", "gmx", "web", "outlook", "hotmail", "t-online", "yahoo", "icloud", "freenet"):
				out.append(domain)
	gesehen, ergebnis = set(), []
	for b in out:
		if b.lower() not in gesehen:
			gesehen.add(b.lower())
			ergebnis.append(b)
	return ergebnis[:60]


@frappe.whitelist(methods=["POST"])
def regeln_fuer(kunde=""):
	"""Die Regeln für eine Zeichnung dieses Kunden: Standard plus Regelsatz des Kunden (Listen zusammen, Schalter und
	Logos des Kunden ergänzen), dazu die Begriffe aus den Stammdaten des Kunden."""
	nur_cnc()
	std = regeln_bereinigen(als_json(_standard_doc().regeln) or {})
	name = frappe.db.get_value("Schwaerzregelsatz", {"kunde": kunde, "aktiv": 1}, "name") if kunde else None
	regeln = dict(std)
	if name:
		eigen = regeln_bereinigen(als_json(frappe.db.get_value("Schwaerzregelsatz", name, "regeln")) or {})
		for k in LISTEN:
			regeln[k] = _liste(std[k] + eigen[k])
		regeln["detectEmail"] = std["detectEmail"] or eigen["detectEmail"]
		regeln["detectPhone"] = std["detectPhone"] or eigen["detectPhone"]
		regeln["logoThreshold"] = eigen["logoThreshold"]
		regeln["logos"] = std["logos"] + eigen["logos"]
		regeln["logoOptions"] = {**std["logoOptions"], **eigen["logoOptions"]}
	regeln["name"] = name or STANDARD
	return {"regeln": regeln, "regelsatz": name or STANDARD, "kundenBegriffe": kunden_begriffe(kunde)}


@frappe.whitelist(methods=["POST"])
def regelsaetze():
	nur_cnc()
	_standard_doc()
	return [regelsatz_ui(frappe.get_doc("Schwaerzregelsatz", n)) for n in frappe.get_all("Schwaerzregelsatz", pluck="name", order_by="kunde asc, bezeichnung asc")]


@frappe.whitelist(methods=["POST"])
def regelsatz_speichern(daten):
	"""Regelsatz anlegen oder ändern: { id?, bezeichnung, kundeId, aktiv, regeln }. Der Standard behält seinen Namen und hat keinen Kunden."""
	nur_cnc()
	daten = frappe.parse_json(daten) if isinstance(daten, str) else daten
	if daten.get("id"):
		doc = frappe.get_doc("Schwaerzregelsatz", daten["id"])
		doc.check_permission("write")
	else:
		bez = (daten.get("bezeichnung") or "").strip()[:140]
		if not bez:
			frappe.throw(_("Bitte eine Bezeichnung eintragen."))
		doc = frappe.new_doc("Schwaerzregelsatz")
		doc.bezeichnung = bez
	if doc.name != STANDARD:
		kunde = daten.get("kundeId") or None
		if kunde and frappe.db.get_value("Schwaerzregelsatz", {"kunde": kunde, "name": ["!=", doc.name or ""]}, "name"):
			frappe.throw(_("Für diesen Kunden gibt es schon einen Regelsatz."))
		doc.kunde = kunde
	doc.aktiv = 1 if daten.get("aktiv", True) else 0
	doc.regeln = json.dumps(regeln_bereinigen(daten.get("regeln") or {}), ensure_ascii=False)
	doc.save() if not doc.is_new() else doc.insert()
	return regelsatz_ui(doc)


@frappe.whitelist(methods=["POST"])
def regelsatz_loeschen(id):
	nur_cnc()
	if id == STANDARD:
		frappe.throw(_("Den Standard-Regelsatz kann man nur ändern, nicht löschen."))
	frappe.delete_doc("Schwaerzregelsatz", id)
	return {"ok": True}


# ----------------------------------------------------------------- Prüfung auf dem Server
def _ohne_stream_inhalte(daten):
	"""Kopie der Bytes, in der jeder Stream-Inhalt geleert ist (Bilddaten sind zufällige Bytes und „enthalten“ kurze
	Begriffe rein zufällig); Struktur, Wörterbücher und Zeichenketten bleiben."""
	out = bytearray(daten)
	pos = 0
	while True:
		s = out.find(b"stream", pos)
		while s >= 3 and out[s - 3:s] == b"end":
			s = out.find(b"stream", s + 1)
		if s < 0:
			break
		e = out.find(b"endstream", s + 6)
		if e < 0:
			break
		out[s + 6:e] = b"\0" * (e - s - 6)
		pos = e + 9
	return bytes(out)


INHALT_ERLAUBT = re.compile(rb"^\s*(q\s+(-?[\d.]+\s+){6}cm\s+/[^\s/\[\]()<>{}%]+\s+Do\s+Q\s*)+$")


def ergebnis_pruefen(inhalt, begriffe=()):
	"""Unabhängige Prüfung der geschwärzten Datei (pypdf, nicht pdf-lib/pdf.js wie im Browser). Liefert eine Liste von
	Fehlern (leer = bestanden). Erlaubt ist genau: Seiten mit je einem Bild, keine Schrift, kein Text, keine Anmerkungen,
	Anhänge, Formulare, Skripte, Lesezeichen oder Metadaten außer Erzeuger und Datum, keiner der Begriffe in den Bytes."""
	from pypdf import PdfReader

	fehler = []
	try:
		r = PdfReader(io.BytesIO(inhalt), strict=False)
	except Exception:
		return [_("Die Datei lässt sich nicht als PDF lesen.")]
	if r.is_encrypted:
		return [_("Die Datei ist verschlüsselt.")]
	root = r.trailer["/Root"].get_object()
	extra = sorted(set(root.keys()) - {"/Type", "/Pages"})
	if extra:
		fehler.append(_("Unerwartete Einträge im Katalog: {0}").format(", ".join(extra)))
	info = r.trailer.get("/Info")
	if info is not None:
		extra = sorted(set(info.get_object().keys()) - {"/Producer", "/Creator", "/CreationDate", "/ModDate"})
		if extra:
			fehler.append(_("Zusätzliche Metadaten: {0}").format(", ".join(extra)))
	for i, page in enumerate(r.pages, 1):
		extra = sorted(set(page.keys()) - {"/Type", "/Parent", "/MediaBox", "/Contents", "/Resources", "/Annots"})
		if extra:
			fehler.append(_("Seite {0}: unerwartete Einträge {1}").format(i, ", ".join(extra)))
		annots = page.get("/Annots")
		if annots is not None and len(annots.get_object()) > 0:
			fehler.append(_("Seite {0}: enthält Anmerkungen").format(i))
		res = page.get("/Resources")
		res = res.get_object() if res is not None else {}
		# pdf-lib legt leere /Font- und /ExtGState-Einträge an: leer sind sie erlaubt, mit Inhalt nicht
		extra = sorted(k for k in set(res.keys()) - {"/XObject", "/ProcSet"} if not (k in ("/Font", "/ExtGState") and len(res[k].get_object()) == 0))
		if extra:
			fehler.append(_("Seite {0}: unerwartete Ressourcen {1} (z. B. Schriften)").format(i, ", ".join(extra)))
		for _n, x in (res.get("/XObject") or {}).items():
			if x.get_object().get("/Subtype") != "/Image":
				fehler.append(_("Seite {0}: eingebettetes Objekt, das kein Bild ist").format(i))
		inhalt_seite = page.get_contents()
		daten = inhalt_seite.get_data() if inhalt_seite is not None else b""
		if not INHALT_ERLAUBT.match(daten or b""):
			fehler.append(_("Seite {0}: der Seiteninhalt zeichnet mehr als nur das Bild").format(i))
		try:
			if (page.extract_text() or "").strip():
				fehler.append(_("Seite {0}: enthält Text").format(i))
		except Exception:
			fehler.append(_("Seite {0}: Text ließ sich nicht prüfen").format(i))
	# Begriffe: in der Struktur (ohne Stream-Inhalte) und in allen entpackten Streams außer Bilddaten
	# PDF-Namen (/Width …) sind keine Zeichnungstexte: nicht mitsuchen (wie blankPdfSyntax im Browser)
	struktur = [re.sub(rb"/[^\s()<>\[\]{}/%]+", b" ", _ohne_stream_inhalte(inhalt)).lower()]
	nummern = {n for eintraege in r.xref.values() for n in eintraege} | set(r.xref_objStm)
	for nr in sorted(nummern)[:20000]:
		try:
			o = r.get_object(nr)
		except Exception:
			continue
		if o is not None and hasattr(o, "get_data") and o.get("/Subtype") != "/Image":
			try:
				struktur.append(o.get_data().lower())
			except Exception:
				pass
	treffer = 0
	for b in begriffe:
		b = (b or "").strip().lower()
		if len(b) < 3:
			continue
		if any(v in teil for teil in struktur for v in {b.encode("utf-8"), b.encode("latin-1", "ignore"), b.encode("utf-16-be")} if v):
			treffer += 1
	if treffer:
		fehler.append(_("{0} Begriff(e) des Kunden in den Dateibytes gefunden").format(treffer))
	return fehler


# ----------------------------------------------------------------- Schwärzungen
def _datei(url):
	name = frappe.db.get_value("File", {"file_url": url}, "name") if url else None
	if not name:
		frappe.throw(_("Die Zeichnung {0} gibt es nicht (mehr).").format(url))
	return frappe.get_doc("File", name)


def _sha(inhalt):
	return hashlib.sha256(inhalt).hexdigest()


def _bytes(f):
	"""Inhalt einer Datei als Bytes (File.get_content liefert bei textähnlichen Dateien einen String)."""
	with open(f.get_full_path(), "rb") as fh:
		return fh.read()


def schwaerzung_ui(d):
	p = als_json(d.protokoll) or {}
	return {
		"id": d.name, "bauteil": d.bauteil or "", "revision": d.revision or "", "kundeId": d.kunde or "", "status": d.status,
		"automatisch": bool(d.automatisch), "originalUrl": d.original_url or "", "originalName": d.original_name or "", "originalSha": d.original_sha or "",
		"ergebnisUrl": d.ergebnis_url or "", "ergebnisSha": d.ergebnis_sha or "", "regelsatz": d.regelsatz or "", "seiten": d.seiten or 0,
		"bereicheAnzahl": d.bereiche_anzahl or 0, "pruefungBestanden": bool(d.pruefung_bestanden), "bereiche": als_json(d.bereiche) or [],
		"protokoll": p, "erstellt": iso(d.creation), "erstelltVon": frappe.db.get_value("User", d.owner, "full_name") or d.owner,
		"geprueftVon": (frappe.db.get_value("User", d.geprueft_von, "full_name") or d.geprueft_von) if d.geprueft_von else "",
		"geprueftAm": iso(d.geprueft_am) if d.geprueft_am else "",
	}


def aktuelle(url):
	"""Die gültige Schwärzung einer Zeichnung: die freigegebene, sonst die neueste ungeprüfte (oder None)."""
	for status in ("Freigegeben", "Ungeprüft"):
		n = frappe.db.get_value("Schwaerzung", {"original_url": url, "status": status}, "name", order_by="creation desc")
		if n:
			return frappe.get_doc("Schwaerzung", n)
	return None


@frappe.whitelist(methods=["POST"])
def status(urls=None):
	"""Je Zeichnung (Adresse) die gültige Schwärzung: { url: schwaerzung_ui | null }."""
	nur_cnc()
	urls = frappe.parse_json(urls) if isinstance(urls, str) else (urls or [])
	out = {}
	for u in urls[:200]:
		d = aktuelle(u)
		out[u] = schwaerzung_ui(d) if d else None
	return out


@frappe.whitelist(methods=["POST"])
def speichern(daten, pdf):
	"""Neue geschwärzte Fassung ablegen (aus dem Browser): { bauteil, revision, kunde, originalUrl, originalSha, bereiche,
	protokoll, automatisch } und die PDF als Base64. Der Server prüft, dass die Fassung zum aktuellen Original gehört,
	dass die Prüfsumme stimmt, und prüft die Datei selbst noch einmal. Bisherige Fassungen (auch freigegebene) werden
	verworfen: an Partner geht erst wieder etwas, wenn die neue geprüft und freigegeben ist."""
	nur_cnc()
	daten = frappe.parse_json(daten) if isinstance(daten, str) else daten
	frappe.has_permission("Schwaerzung", "create", throw=True)
	original = _datei(daten.get("originalUrl"))
	if _sha(_bytes(original)) != daten.get("originalSha"):
		frappe.throw(_("Die Zeichnung hat sich inzwischen geändert. Bitte neu schwärzen."))
	inhalt = base64.b64decode(pdf or "", validate=True)
	if not inhalt or len(inhalt) > MAX_PDF:
		frappe.throw(_("Die geschwärzte Datei fehlt oder ist zu groß."))
	protokoll = daten.get("protokoll") or {}
	sha = _sha(inhalt)
	if protokoll.get("sha256") and protokoll["sha256"] != sha:
		frappe.throw(_("Die Prüfsumme der geschwärzten Datei stimmt nicht mit dem Prüfprotokoll überein."))
	kunde = daten.get("kunde") or (frappe.db.get_value("Bauteil", daten.get("bauteil"), "kunde") if daten.get("bauteil") else None)
	server = ergebnis_pruefen(inhalt, kunden_begriffe(kunde))
	protokoll["serverPruefung"] = {"bestanden": not server, "fehler": server}
	bereiche = [
		{k: b.get(k) for k in ("page", "x0", "y0", "x1", "y1", "kind", "source", "reason")}
		for b in (daten.get("bereiche") or [])[:5000] if isinstance(b, dict)
	]
	doc = frappe.get_doc({
		"doctype": "Schwaerzung", "bauteil": daten.get("bauteil") or None, "revision": (daten.get("revision") or "")[:40], "kunde": kunde or None,
		"status": "Ungeprüft", "automatisch": 1 if daten.get("automatisch") else 0, "original_url": original.file_url, "original_name": original.file_name,
		"original_sha": daten.get("originalSha"), "ergebnis_sha": sha, "regelsatz": daten.get("regelsatz") if frappe.db.exists("Schwaerzregelsatz", daten.get("regelsatz") or "") else None,
		"seiten": int(protokoll.get("pageCount") or 0), "bereiche_anzahl": len(bereiche), "bereiche": json.dumps(bereiche, ensure_ascii=False),
		"protokoll": json.dumps(protokoll, ensure_ascii=False), "pruefung_bestanden": 1 if protokoll.get("released") and not server else 0,
	}).insert()
	f = frappe.get_doc({
		"doctype": "File", "file_name": ausgabe_name(original.file_name), "is_private": 1, "content": inhalt,
		"attached_to_doctype": "Schwaerzung", "attached_to_name": doc.name,
	}).insert(ignore_permissions=True)
	doc.db_set("ergebnis_url", f.file_url)
	# eine neue Fassung ersetzt die bisherigen, auch eine schon freigegebene (sie wurde ja geändert, weil etwas fehlte)
	for alt in frappe.get_all("Schwaerzung", filters={"original_url": original.file_url, "status": ["in", ["Ungeprüft", "Freigegeben"]], "name": ["!=", doc.name]}, pluck="name"):
		frappe.db.set_value("Schwaerzung", alt, "status", "Verworfen")
	return schwaerzung_ui(frappe.get_doc("Schwaerzung", doc.name))


@frappe.whitelist(methods=["POST"])
def freigeben(id):
	"""Nach der Gegenprüfung durch einen Menschen: diese Fassung darf an Partner gehen. Nur mit bestandener Prüfung und
	solange das Original unverändert ist. Eine frühere Freigabe derselben Zeichnung wird verworfen."""
	nur_cnc()
	doc = frappe.get_doc("Schwaerzung", id)
	doc.check_permission("write")
	if doc.status != "Ungeprüft":
		frappe.throw(_("Nur eine ungeprüfte Fassung lässt sich freigeben."))
	if not doc.pruefung_bestanden:
		frappe.throw(_("Die automatische Prüfung ist nicht bestanden. Bitte die Bereiche korrigieren und neu erzeugen."))
	if _sha(_bytes(_datei(doc.original_url))) != doc.original_sha:
		frappe.throw(_("Die Zeichnung hat sich inzwischen geändert. Bitte neu schwärzen."))
	if _sha(_bytes(_datei(doc.ergebnis_url))) != doc.ergebnis_sha:
		frappe.throw(_("Die geschwärzte Datei wurde verändert."))
	for alt in frappe.get_all("Schwaerzung", filters={"original_url": doc.original_url, "status": "Freigegeben"}, pluck="name"):
		frappe.db.set_value("Schwaerzung", alt, "status", "Verworfen")
	doc.db_set({"status": "Freigegeben", "geprueft_von": frappe.session.user, "geprueft_am": now_datetime()})
	return schwaerzung_ui(doc)


@frappe.whitelist(methods=["POST"])
def verwerfen(id):
	nur_cnc()
	doc = frappe.get_doc("Schwaerzung", id)
	doc.check_permission("write")
	doc.db_set("status", "Verworfen")
	return schwaerzung_ui(doc)


def freigegebene_datei(url):
	"""(Dateiname, Inhalt) der freigegebenen geschwärzten Fassung einer Zeichnung, nur wenn das Original seitdem
	unverändert ist und die Datei ihre Prüfsumme hat; sonst None."""
	n = frappe.db.get_value("Schwaerzung", {"original_url": url, "status": "Freigegeben"}, "name", order_by="creation desc")
	if not n:
		return None
	d = frappe.get_doc("Schwaerzung", n)
	try:
		if _sha(_bytes(_datei(url))) != d.original_sha:
			return None
		f = _datei(d.ergebnis_url)
		inhalt = _bytes(f)
	except frappe.ValidationError:
		return None
	return (ausgabe_name(d.original_name), inhalt) if _sha(inhalt) == d.ergebnis_sha else None


def ausgabe_name(original_name):
	"""Dateiname der geschwärzten Fassung für Partner: <Name des Originals>_M01.pdf."""
	return re.sub(r"\.pdf$", "", original_name or "Zeichnung", flags=re.I) + "_M01.pdf"
