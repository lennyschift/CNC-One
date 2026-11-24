"""Ähnliche Bauteile (Teilenummer, Bezeichnung, Zeichnung, Werkstoff, Rohteil, Geometrie) und der Geometrie-Fingerabdruck
aus dem STEP-Modell. Die Bewertung steht in logic/aehnlichkeit.py."""

import json

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import aehnlichkeit
from cnc_one.logic.daten import als_json

FELDER = ["name", "kunde", "teilenummer", "bezeichnung", "zeichnungsnr", "material", "fingerabdruck", "teilefamilie", "variante", "vorschaubild", "status"]


def _letzte_kalkulation():
	"""{Bauteil: Rohteil und Fingerabdruck aus der jüngsten Angebotsposition} (das Rohteil steht nur in der Kalkulation)."""
	out = {}
	for b, k in frappe.db.sql(
		"""select bauteil, kalkulation from `tabAngebotsposition` where parenttype = 'Angebot' and ifnull(bauteil, '') != ''
		order by modified desc"""
	):
		if b in out:
			continue
		t = als_json(k) or {}
		out[b] = {"roh": t.get("roh") if isinstance(t.get("roh"), dict) else None, "geo": t.get("geo") if isinstance(t.get("geo"), dict) else None}
	return out


def kandidaten():
	"""Alle Bauteile mit dem, was die Bewertung braucht."""
	kalk = _letzte_kalkulation()
	out = []
	for b in frappe.get_all("Bauteil", fields=FELDER, limit_page_length=0):
		k = kalk.get(b.name) or {}
		b["geo"] = (als_json(b.fingerabdruck) if b.fingerabdruck else None) or k.get("geo")
		b["roh"] = k.get("roh")
		out.append(b)
	return out


def _preise(bauteil):
	from cnc_one.api.historie import historie_daten

	k = historie_daten(bauteil)["kennzahlen"]
	a, g = k.get("letzterAuftrag"), k.get("letztesAngebot")
	return {
		"auftraege": k.get("auftraege") or 0,
		"letzterAuftrag": {"auftrag": a["auftrag"], "jeStueck": a["jeStueck"], "menge": a["menge"], "datum": a["datum"]} if a else None,
		"letztesAngebot": {"angebot": g["angebot"], "positionKey": g["positionKey"], "status": g["status"], "datum": g["datum"], "preise": g["preise"]} if g else None,
	}


@frappe.whitelist(methods=["POST"])
def aehnliche(bauteil="", kunde="", teilenummer="", bezeichnung="", zeichnungsnr="", material="", roh=None, geo=None, grenze=8):
	"""Die ähnlichsten Bauteile zu einem Bauteil (oder zu den Angaben eines Workbench-Bauteils ohne Bauteil), mit Gründen
	und den letzten Preisen. Das Bauteil selbst (gleicher Kunde, gleiche Teilenummer) zählt nicht."""
	nur_cnc()
	roh, geo = frappe.parse_json(roh) if isinstance(roh, str) else roh, frappe.parse_json(geo) if isinstance(geo, str) else geo
	alle = kandidaten()
	selbst = next((b for b in alle if b.name == bauteil), None) if bauteil else None
	a = {
		"teilenummer": teilenummer or (selbst or {}).get("teilenummer"), "bezeichnung": bezeichnung or (selbst or {}).get("bezeichnung"),
		"zeichnungsnr": zeichnungsnr or (selbst or {}).get("zeichnungsnr"), "material": material or (selbst or {}).get("material"),
		"roh": roh or (selbst or {}).get("roh"), "geo": geo or (selbst or {}).get("geo"),
	}
	kunde = kunde or (selbst or {}).get("kunde") or ""
	nr = aehnlichkeit.norm(a["teilenummer"])
	andere = [b for b in alle if b.name != bauteil and not (b.kunde == kunde and nr and aehnlichkeit.norm(b.teilenummer) == nr)]
	treffer = aehnlichkeit.finden(a, andere, grenze=min(int(grenze or 8), 20))
	kunden = {k.name: k.kundenname for k in frappe.get_all("Kunde", fields=["name", "kundenname"], limit_page_length=0)}
	familien = {f.name: f.bezeichnung for f in frappe.get_all("Teilefamilie", fields=["name", "bezeichnung"], limit_page_length=0)}
	out = []
	for p, gruende, b in treffer:
		out.append({
			"id": b.name, "teilenummer": b.teilenummer, "name": b.bezeichnung or "", "kundeId": b.kunde, "kundeName": kunden.get(b.kunde, ""),
			"zeichnungsnr": b.zeichnungsnr or "", "material": b.material or "", "vorschaubild": b.vorschaubild or "", "status": b.status,
			"familie": b.teilefamilie or "", "familieName": familien.get(b.teilefamilie, ""), "variante": b.variante or "",
			"punkte": p, "gruende": gruende, "mitGeometrie": bool(b.geo), **_preise(b.name),
		})
	return {"treffer": out, "mitGeometrie": bool(a["geo"]), "verglichen": len(andere)}


# ----------------------------------------------------------------- Fingerabdruck
def fingerabdruck_pruefen(d):
	"""Nur die bekannten Felder, als Zahlen; sonst None."""
	if not isinstance(d, dict):
		return None
	try:
		f = {
			"v": int(d.get("v") or 0),
			"masse": [round(float(x), 2) for x in (d.get("masse") or [])][:3],
			"volumen": round(float(d.get("volumen") or 0), 1),
			"flaeche": round(float(d.get("flaeche") or 0), 1),
			"fuell": round(float(d.get("fuell") or 0), 4),
			"d2": [round(float(x), 5) for x in (d.get("d2") or [])][:64],
		}
	except (TypeError, ValueError):
		return None
	if f["v"] < 1 or len(f["masse"]) != 3 or not f["d2"] or f["volumen"] <= 0:
		return None
	return f


def geo_uebernehmen(bauteil, geo):
	"""Fingerabdruck aus der Workbench am Bauteil ablegen (beim Speichern des Angebots), wenn er neu ist."""
	f = fingerabdruck_pruefen(geo)
	if not f or not bauteil:
		return
	neu = json.dumps(f, sort_keys=True)
	alt = frappe.db.get_value("Bauteil", bauteil, "fingerabdruck")
	if (json.dumps(als_json(alt), sort_keys=True) if alt else "") != neu:
		frappe.db.set_value("Bauteil", bauteil, "fingerabdruck", neu, update_modified=False)


@frappe.whitelist(methods=["POST"])
def fingerabdruck_speichern(bauteil, daten):
	"""Fingerabdruck eines Bauteils speichern (aus den Stammdaten: „Geometrie einlesen“)."""
	nur_cnc()
	daten = frappe.parse_json(daten) if isinstance(daten, str) else daten
	doc = frappe.get_doc("Bauteil", bauteil)
	doc.check_permission("write")
	f = fingerabdruck_pruefen(daten)
	if not f:
		frappe.throw(_("Der Fingerabdruck ist unvollständig."))
	doc.db_set("fingerabdruck", json.dumps(f, sort_keys=True), update_modified=False)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def ohne_fingerabdruck():
	"""Bauteile mit STEP-Modell, aber noch ohne Fingerabdruck: [{id, teilenummer, stepDatei}]."""
	nur_cnc()
	return [
		{"id": b.name, "teilenummer": b.teilenummer, "stepDatei": b.step_datei}
		for b in frappe.get_all("Bauteil", filters={"step_datei": ["is", "set"]}, fields=["name", "teilenummer", "step_datei", "fingerabdruck"], limit_page_length=0)
		if not b.fingerabdruck
	]
