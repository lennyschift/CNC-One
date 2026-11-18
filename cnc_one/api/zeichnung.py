"""Zeichnungsvorlagen je Kunde: angelernte Regeln, wo auf den Zeichnungen eines Kunden welche Angabe steht.
Die Erkennung selbst läuft im Browser (frontend/src/lib/erkennung.js); hier werden die Regeln gespeichert.

Eine Vorlage: { "felder": { feld: [regel, …] }, "geaendert": iso }. Eine Regel ist entweder { "stichwort": text, "dx", "dy" }
(der Wert steht um dx/dy versetzt zu diesem Label; ohne Versatz rechts daneben oder darunter) oder { "bereich": { x, y, b, h } }
(Stelle auf der Seite). Alle Lagen als Anteil der Seite, 0 bis 1. Welche Regeln bleiben, entscheidet die Oberfläche beim Anlernen
(neue vorne, auf der Zeichnung widerlegte fallen weg); hier werden sie geprüft und gespeichert."""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from cnc_one.api.stamm import nur_cnc, schreibweisen

FELDER = ("teilenummer", "zeichnungsnr", "bezeichnung", "revision", "werkstoff", "oberflaeche", "toleranz", "kunde")
MAX_REGELN = 4  # je Feld; die erste passende Regel gilt


def _lesen(kunde):
	roh = frappe.db.get_value("Kunde", kunde, "zeichnungsvorlage")
	v = json.loads(roh) if isinstance(roh, str) and roh else (roh or {})
	v.setdefault("felder", {})
	return v


def _stichwort(text):
	return " ".join(str(text or "").lower().split()).rstrip(":").strip()[:80]


def _bereich(b):
	try:
		werte = {k: round(min(1.0, max(0.0, float(b[k]))), 4) for k in ("x", "y", "b", "h")}
	except (KeyError, TypeError, ValueError):
		frappe.throw(_("Der Bereich auf der Zeichnung ist ungültig."))
	if werte["b"] <= 0 or werte["h"] <= 0:
		frappe.throw(_("Der Bereich auf der Zeichnung ist ungültig."))
	return werte


def _kunde(kunde, schreiben=False):
	if not kunde or not frappe.db.exists("Kunde", kunde):
		frappe.throw(_("Den Kunden {0} gibt es nicht.").format(kunde or ""))
	if schreiben:
		frappe.get_doc("Kunde", kunde).check_permission("write")


def _speichern(kunde, v):
	v["geaendert"] = now_datetime().isoformat()
	frappe.db.set_value("Kunde", kunde, "zeichnungsvorlage", json.dumps(v, ensure_ascii=False))
	return v


@frappe.whitelist(methods=["POST"])
def vorlage(kunde):
	"""Die Zeichnungsvorlage eines Kunden (leer, wenn noch nichts angelernt wurde)."""
	nur_cnc()
	_kunde(kunde)
	return _lesen(kunde)


def _regel(r):
	if not isinstance(r, dict):
		frappe.throw(_("Die Regel ist ungültig."))
	if r.get("bereich"):
		return {"bereich": _bereich(r["bereich"])}
	stichwort = _stichwort(r.get("stichwort"))
	if not stichwort:
		frappe.throw(_("Die Regel ist ungültig."))
	regel = {"stichwort": stichwort}
	if r.get("dx") is not None or r.get("dy") is not None:
		try:
			regel.update(dx=round(max(-1.0, min(1.0, float(r.get("dx") or 0))), 4), dy=round(max(-1.0, min(1.0, float(r.get("dy") or 0))), 4))
		except (TypeError, ValueError):
			frappe.throw(_("Die Regel ist ungültig."))
	return regel


@frappe.whitelist(methods=["POST"])
def lernen(kunde, felder):
	"""Speichert, wo Angaben auf den Zeichnungen des Kunden stehen. `felder`: { feld: [regel, …] } ersetzt die Regeln je Feld
	(höchstens vier, doppelte fallen weg); andere Felder bleiben unverändert."""
	nur_cnc()
	_kunde(kunde, schreiben=True)
	if isinstance(felder, str):
		felder = frappe.parse_json(felder)
	v = _lesen(kunde)
	for feld, regeln in (felder or {}).items():
		if feld not in FELDER:
			frappe.throw(_("Die Angabe {0} gibt es nicht.").format(feld))
		liste = []
		for r in regeln or []:
			r = _regel(r)
			if r not in liste:
				liste.append(r)
		if liste:
			v["felder"][feld] = liste[:MAX_REGELN]
	return _speichern(kunde, v)


@frappe.whitelist(methods=["POST"])
def vergessen(kunde, feld=None):
	"""Löscht die angelernten Regeln eines Kunden, ganz oder für eine Angabe."""
	nur_cnc()
	_kunde(kunde, schreiben=True)
	v = _lesen(kunde)
	if feld:
		v["felder"].pop(feld, None)
	else:
		v["felder"] = {}
	return _speichern(kunde, v)


# ----------------------------------------------------------------- Rohmaterial zu Werkstoffangaben
MAX_SCHREIBWEISEN = 30


def _rohmaterial_ui(d):
	return {"name": d.name, "preisKg": d.preis_kg or 0, "dichte": d.dichte or 0, "schreibweisen": schreibweisen(d.schreibweisen)}


def _text(text):
	return " ".join(str(text or "").split())[:80]


@frappe.whitelist(methods=["POST"])
def schreibweise_merken(material, text):
	"""Merkt sich, wie ein Rohmaterial auf Zeichnungen geschrieben wird (z. B. "X5CrNi18-10" für "1.4301 Edelstahl").
	Danach ordnet die Erkennung diesen Werkstoff bei allen Kunden von selbst zu."""
	nur_cnc()
	doc = frappe.get_doc("Material", material)
	doc.check_permission("write")
	t = _text(text)
	liste = schreibweisen(doc.schreibweisen)
	if t and t.lower() != doc.name.lower() and t.lower() not in [x.lower() for x in liste]:
		liste.append(t)
		doc.schreibweisen = "\n".join(liste[-MAX_SCHREIBWEISEN:])
		doc.save()
	return _rohmaterial_ui(doc)


@frappe.whitelist(methods=["POST"])
def rohmaterial_anlegen(name, schreibweise=""):
	"""Legt ein Rohmaterial zu einem Werkstoff von der Zeichnung an (Preis je kg später in den Stammdaten). Gibt es den
	Namen schon, wird das vorhandene geliefert."""
	nur_cnc()
	name = _text(name)
	if not name:
		frappe.throw(_("Bitte einen Namen für das Rohmaterial angeben."))
	if frappe.db.exists("Material", name):
		return schreibweise_merken(name, schreibweise) if schreibweise else _rohmaterial_ui(frappe.get_doc("Material", name))
	if not frappe.has_permission("Material", "create"):
		frappe.throw(_("Rohmaterial anlegen dürfen nur die Rollen mit Schreibrecht auf die Stammdaten (z. B. CNC Admin)."), frappe.PermissionError)
	doc = frappe.new_doc("Material")
	doc.materialname = name
	doc.aktiv = 1
	t = _text(schreibweise)
	if t and t.lower() != name.lower():
		doc.schreibweisen = t
	doc.insert()
	return _rohmaterial_ui(doc)


# ----------------------------------------------------------------- Markierungen und Drehung einer Zeichnung
# Gespeichert je Datei (URL) als eigene Ebene: die PDF bleibt unverändert, alle sehen die Markierungen überall, wo die
# Zeichnung angezeigt wird (Workbench, Auftrag, Fertigung, Posteingang). Lagen als Anteil der Seite (0 bis 1), ohne die Drehung.

MARKIER_TYPEN = ("marker", "rahmen", "pfeil", "freihand", "notiz")
MARKIER_FARBEN = ("rot", "gelb", "gruen", "blau")
MAX_MARKIERUNGEN = 500
MAX_PUNKTE = 2000


def _datei_pruefen(datei):
	name = frappe.db.get_value("File", {"file_url": datei}, "name") if datei else None
	if not name or not frappe.has_permission("File", "read", doc=name):
		frappe.throw(_("Die Zeichnung wurde nicht gefunden."), frappe.PermissionError)


def _anteil(wert):
	try:
		return round(min(1.0, max(0.0, float(wert))), 5)
	except (TypeError, ValueError):
		frappe.throw(_("Eine Markierung ist ungültig."))


def _markierung(m):
	if not isinstance(m, dict) or m.get("typ") not in MARKIER_TYPEN:
		frappe.throw(_("Eine Markierung ist ungültig."))
	try:
		seite = max(1, int(m.get("seite") or 1))
	except (TypeError, ValueError):
		frappe.throw(_("Eine Markierung ist ungültig."))
	out = {"typ": m["typ"], "seite": seite, "farbe": m.get("farbe") if m.get("farbe") in MARKIER_FARBEN else "rot"}
	if m["typ"] in ("marker", "rahmen"):
		out.update({k: _anteil(m.get(k)) for k in ("x", "y", "b", "h")})
	elif m["typ"] == "pfeil":
		out.update({k: _anteil(m.get(k)) for k in ("x1", "y1", "x2", "y2")})
	elif m["typ"] == "freihand":
		punkte = m.get("punkte") or []
		if not isinstance(punkte, list) or len(punkte) > MAX_PUNKTE:
			frappe.throw(_("Eine Markierung ist ungültig."))
		out["punkte"] = [[_anteil(p[0]), _anteil(p[1])] for p in punkte if isinstance(p, (list, tuple)) and len(p) == 2]
	else:
		out.update({"x": _anteil(m.get("x")), "y": _anteil(m.get("y")), "text": str(m.get("text") or "")[:500]})
		if not out["text"].strip():
			return None
	return out


def _markierungen_ui(row):
	roh = row.markierungen if row else None
	liste = json.loads(roh) if isinstance(roh, str) and roh else (roh or [])
	return {"drehung": int(row.drehung or 0) if row else 0, "markierungen": liste}


@frappe.whitelist(methods=["POST"])
def markierungen(datei):
	"""Drehung und Markierungen einer Zeichnung: { drehung, markierungen: [...] }."""
	nur_cnc()
	_datei_pruefen(datei)
	return _markierungen_ui(frappe.db.get_value("Zeichnung Markierung", {"datei": datei}, ["drehung", "markierungen"], as_dict=True))


@frappe.whitelist(methods=["POST"])
def markierungen_speichern(datei, drehung=0, markierungen=None):
	"""Speichert Drehung (0, 90, 180, 270) und alle Markierungen einer Zeichnung (ersetzt die bisherigen)."""
	nur_cnc()
	_datei_pruefen(datei)
	try:
		drehung = int(drehung or 0) % 360
	except (TypeError, ValueError):
		drehung = 0
	if drehung not in (0, 90, 180, 270):
		frappe.throw(_("Die Drehung ist ungültig."))
	liste = json.loads(markierungen) if isinstance(markierungen, str) else (markierungen or [])
	if not isinstance(liste, list) or len(liste) > MAX_MARKIERUNGEN:
		frappe.throw(_("Zu viele Markierungen."))
	liste = [x for x in (_markierung(m) for m in liste) if x]
	name = frappe.db.get_value("Zeichnung Markierung", {"datei": datei}, "name")
	doc = frappe.get_doc("Zeichnung Markierung", name) if name else frappe.new_doc("Zeichnung Markierung")
	doc.datei = datei
	doc.drehung = drehung
	doc.markierungen = json.dumps(liste, ensure_ascii=False)
	doc.save() if name else doc.insert()
	return _markierungen_ui(doc)
