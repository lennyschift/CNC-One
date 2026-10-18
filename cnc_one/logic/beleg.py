"""Regeln für den Übergang Angebot -> Auftrag. Muss dasselbe rechnen wie frontend/src/lib/beleg.js.

Beide Seiten werden mit denselben Fällen aus shared/auftrag_faelle.json geprüft
(erzeugt mit scripts/gen_auftrag_faelle.mjs, Server-Test tests/test_beleg.py).
"""

import math

from cnc_one.logic.kalkulation import _summe, berechne, num, r2


def optionen(teil, ergebnis):
	"""Auswahlmöglichkeiten einer Angebotsposition: jede Staffel, oder die eine Angebotsmenge."""
	if (teil.get("staffel") or {}).get("aktiv") and ergebnis["stufen"]:
		return [
			{"id": str(s["menge"]), "label": f"{s['menge']} Stk", "menge": s["menge"], "einzel": s["stueckpreis"]}
			for s in ergebnis["stufen"]
		]
	z = next((x for x in ergebnis["zeilen"] if x["typ"] == "teil"), None)
	return [{"id": "einzel", "label": f"{ergebnis['menge']} Stk", "menge": ergebnis["menge"], "einzel": z["einzel"] if z else 0}]


def auftragsposition(teil, ergebnis, option, menge):
	"""Auftragsposition aus einer Angebotsposition: gewählte Option und tatsächlich bestellte Menge."""
	q = max(1, math.floor(num(menge)) or 1)
	staffel = bool((teil.get("staffel") or {}).get("aktiv"))
	if staffel:
		einzel = option["einzel"]
		kosten = [z for z in ergebnis["zeilen"] if z["typ"] == "kosten"]
	else:
		r = berechne({**teil, "menge": q})
		z = next((x for x in r["zeilen"] if x["typ"] == "teil"), None)
		einzel = z["einzel"] if z else 0
		kosten = [x for x in r["zeilen"] if x["typ"] == "kosten"]
	zeilen = [{"label": k["label"], "betrag": k["betrag"]} for k in kosten]
	return {
		"menge": q,
		"einzelpreis": r2(einzel),
		"staffelMenge": option["menge"] if staffel else None,
		"kosten": zeilen,
		"summe": r2(einzel * q + _summe(k["betrag"] for k in zeilen)),
		"unterStaffel": staffel and q < option["menge"],
	}


def position_fuer_auftrag(teil, ergebnis, option_id, menge, kosten_aus=()):
	"""Position mit allem, was der Dialog auswählt: Staffel (option_id), Menge und abgewählte Kostenzeilen."""
	opts = optionen(teil, ergebnis)
	opt = next((o for o in opts if o["id"] == str(option_id)), None) if option_id is not None else None
	pos = auftragsposition(teil, ergebnis, opt or opts[0], menge)
	kosten = [k for k in pos["kosten"] if k["label"] not in kosten_aus]
	return {**pos, "kosten": kosten, "summe": r2(pos["einzelpreis"] * pos["menge"] + _summe(k["betrag"] for k in kosten))}
