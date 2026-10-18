"""Kalkulation eines Bauteils im Angebot. Muss dasselbe rechnen wie frontend/src/lib/calc.js.

Beide Seiten werden mit denselben Fällen aus shared/kalkulation_faelle.json geprüft. Wer eine Regel ändert,
ändert sie hier und in calc.js und erzeugt die Fälle neu.

Hat ein Bauteil einen Arbeitsplan (arbeitsgaenge), kommen Rüst- und Stückkosten aus den internen Arbeitsgängen
(Zeit mal Satz der Maschine). Fremdvergaben liefern Kosten je Stück und einmalig. Ohne Arbeitsplan gelten die
einfachen Felder (ruestMin, stueckMin, satzRuest, satzStueck).
"""

import math
import sys

EPSILON = sys.float_info.epsilon


def _summe(werte):
	"""Von links nach rechts addieren wie reduce() in JavaScript. Das eingebaute sum() rechnet ab Python 3.12 genauer und weicht ab."""
	gesamt = 0
	for w in werte:
		gesamt += w
	return gesamt


def num(v):
	"""Wie Number(v) in JavaScript, nur dass ungültige Werte 0 sind."""
	try:
		n = float(v)
	except (TypeError, ValueError):
		return 0.0
	return n if math.isfinite(n) else 0.0


def r2(v):
	"""Auf zwei Stellen runden wie Math.round((v + EPSILON) * 100) / 100 in JavaScript."""
	return math.floor((num(v) + EPSILON) * 100 + 0.5) / 100


def _alle(p):
	a = p.get("arbeitsgaenge")
	return a if isinstance(a, list) else []


def _intern(p):
	return [a for a in _alle(p) if a.get("typ") == "intern"]


def _fremd(p):
	return [a for a in _alle(p) if a.get("typ") == "fremd"]


def hat_plan(p):
	return len(_intern(p)) > 0


def ruest_kosten(p):
	if hat_plan(p):
		return r2(_summe(num(a.get("ruestMin")) / 60 * num(a.get("satz")) for a in _intern(p)))
	return r2(num(p.get("ruestMin")) / 60 * num(p.get("satzRuest")))


def stueck_kosten(p):
	if hat_plan(p):
		return r2(_summe(num(a.get("stueckMin")) / 60 * num(a.get("satz")) for a in _intern(p)))
	return r2(num(p.get("stueckMin")) / 60 * num(p.get("satzStueck")))


def fremd_pro_stueck(p):
	return r2(_summe(num(a.get("fremdProStk")) for a in _fremd(p)))


def material_pro_stueck(p):
	return r2(num(p.get("gewichtKg")) * num(p.get("materialPreisKg")))


def _basis(p):
	return {
		"setup": ruest_kosten(p),
		"unit": r2(stueck_kosten(p) + fremd_pro_stueck(p)),
		"mat": material_pro_stueck(p),
		"pauschal": r2(p.get("pauschalMaterial")),
		"mess": r2(p.get("messkosten")),
		"sonder": r2(p.get("sonderkosten")),
		"express": r2(p.get("expresskosten")),
	}


def _extras(p, b):
	f = p.get("inStueckpreis") or {}
	liste = [
		{"key": "mess", "label": "Messkosten", "betrag": b["mess"], "eingerechnet": bool(f.get("mess"))},
		{"key": "sonder", "label": "Sonderkosten", "betrag": b["sonder"], "eingerechnet": bool(f.get("sonder"))},
		{"key": "express", "label": "Expresskosten", "betrag": b["express"], "eingerechnet": bool(f.get("express"))},
	]
	for a in _fremd(p):
		if num(a.get("fremdEinmal")) > 0:
			name = a.get("name") or ""
			liste.append({
				"key": "fremd-" + str(a.get("id") if a.get("id") is not None else name),
				"label": f"Fremdvergabe {name}".strip(),
				"betrag": r2(a.get("fremdEinmal")),
				"eingerechnet": False,
			})
	return liste


def _fix(liste):
	return (
		_summe(x["betrag"] for x in liste if x["eingerechnet"]),
		_summe(x["betrag"] for x in liste if not x["eingerechnet"]),
	)


def gueltige_stufen(p):
	staffel = p.get("staffel") or {}
	stufen = [
		{"menge": math.floor(num(s.get("menge"))), "extra": num(s.get("extra"))}
		for s in (staffel.get("stufen") or [])
	]
	return sorted((s for s in stufen if s["menge"] > 0), key=lambda s: s["menge"])


def berechne(p):
	"""Liefert dasselbe Ergebnis wie berechne() in calc.js (Schlüssel und Reihenfolge der Zeilen)."""
	menge = max(1, math.floor(num(p.get("menge"))) or 1)
	b = _basis(p)
	liste = _extras(p, b)
	eingerechnet, einzeln = _fix(liste)
	f = p.get("inStueckpreis") or {}
	out = {"menge": menge, **b, "stufen": [], "zeilen": [], "gesamt": 0, "stueckpreis": 0}

	def kosten_zeilen():
		return [
			{"typ": "kosten", "label": x["label"], "menge": 1, "betrag": x["betrag"]}
			for x in liste
			if not x["eingerechnet"] and x["betrag"] > 0
		]

	if (p.get("staffel") or {}).get("aktiv"):
		for s in gueltige_stufen(p):
			stueck = r2((b["setup"] + b["pauschal"] + eingerechnet) / s["menge"] + b["unit"] + b["mat"] + s["extra"])
			out["stufen"].append({
				"menge": s["menge"], "extra": s["extra"], "stueckpreis": stueck, "gesamt": r2(stueck * s["menge"] + einzeln),
			})
		kleinste = out["stufen"][0] if out["stufen"] else None
		out["gesamt"] = kleinste["gesamt"] if kleinste else 0
		out["stueckpreis"] = kleinste["stueckpreis"] if kleinste else 0
		out["zeilen"].extend(kosten_zeilen())
		return out

	stueck_anteil = (
		b["unit"]
		+ b["mat"]
		+ (0 if p.get("pauschalAlsZeile") else b["pauschal"] / menge)
		+ (b["setup"] / menge if f.get("ruest") else 0)
		+ eingerechnet / menge
	)
	out["zeilen"].append({
		"typ": "teil", "label": p.get("name") or "Bauteil", "menge": menge,
		"einzel": r2(stueck_anteil), "betrag": r2(stueck_anteil * menge),
	})
	if not f.get("ruest") and b["setup"] > 0:
		out["zeilen"].append({"typ": "kosten", "label": "Rüstkosten", "menge": 1, "betrag": b["setup"]})
	if p.get("pauschalAlsZeile") and b["pauschal"] > 0:
		out["zeilen"].append({"typ": "kosten", "label": "Pauschal Material", "menge": 1, "betrag": b["pauschal"]})
	out["zeilen"].extend(kosten_zeilen())
	out["gesamt"] = r2(_summe(z["betrag"] for z in out["zeilen"]))
	out["stueckpreis"] = r2(out["gesamt"] / menge)
	return out


def summe(ergebnisse):
	return r2(_summe(e["gesamt"] for e in ergebnisse))
