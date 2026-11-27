"""Rohmaterial in der Fertigung: passende Chargen im Lager, wie viele Zuschnitte sie hergeben, der Materialstand eines
Fertigungsbauteils und die Rechnung einer Entnahme (Stangen/Platten raus, Reststück zurück). Reine Logik ohne Datenbank;
die Rechnung entspricht ui/src/lib/werkstoffbaum.js (reichtFuer, chargePruefen)."""

ZEUGNISSE = ["", "2.2", "3.1", "3.2"]
EPS = 1e-6


def _n(v):
	try:
		return float(v or 0)
	except (TypeError, ValueError):
		return 0.0


def spez_vollstaendig(spez):
	return bool(spez and spez.get("werkstoff") and spez.get("abmessungId") and _n(spez.get("laenge")))


def passt(charge, spez):
	"""Charge passt zu Werkstoff, Abmessung und (wenn angegeben) Zustand und ist vorrätig."""
	return (
		charge.get("werkstoff") == spez.get("werkstoff")
		and charge.get("abmessung") == spez.get("abmessungId")
		and (not spez.get("zustand") or charge.get("zustand") == spez.get("zustand"))
		and (charge.get("status") or "Vorrätig") == "Vorrätig"
		and (charge.get("stueck") or 0) > 0
	)


def reicht_fuer(charge, spez):
	"""Wie viele Zuschnitte gibt die Charge her (Stangen: je Stange abgesägt, Platte: im Raster, auch gedreht)?
	Ist aus einer früheren Fertigung der tatsächliche Verbrauch je Stück bekannt (spez.verbrauchJeStueck, mm bzw. mm²)
	und größer als der Zuschnitt, zählt dieser."""
	s = _n(spez.get("saege"))
	ist = _n(spez.get("verbrauchJeStueck"))
	if charge.get("form") == "Platte":
		b, l = _n(spez.get("breite")) + s, _n(spez.get("laenge")) + s
		if not b or not l:
			return 0
		je = max(int(_n(charge.get("breite")) // b) * int(_n(charge.get("laenge")) // l), int(_n(charge.get("breite")) // l) * int(_n(charge.get("laenge")) // b))
		if ist > b * l:
			je = min(je, int(_n(charge.get("breite")) * _n(charge.get("laenge")) // ist))
		return je * max(1, int(charge.get("stueck") or 1))
	l = max(_n(spez.get("laenge")) + s, ist)
	return int(_n(charge.get("laenge")) // l) * max(1, int(charge.get("stueck") or 1)) if _n(spez.get("laenge")) else 0


def je_einheit(charge, spez):
	"""Zuschnitte je Stange bzw. je Platte."""
	return reicht_fuer({**charge, "stueck": 1}, spez)


def pruefen(charge, anforderungen):
	"""Erfüllt die Charge Werkszeugnis und Prüfungen? → (ok, fehlt)"""
	anf = anforderungen or {}
	fehlt = []
	z = anf.get("zeugnis") or ""
	if z and ZEUGNISSE.index(charge.get("zeugnis") or "") < ZEUGNISSE.index(z if z in ZEUGNISSE else ""):
		fehlt.append(f"Zeugnis {z}")
	for p in anf.get("pruefungen") or []:
		if p not in (charge.get("pruefungen") or []):
			fehlt.append(p)
	return not fehlt, fehlt


def anforderungen(spez):
	a = (spez or {}).get("anforderungen")
	return a if isinstance(a, dict) else {"zeugnis": (spez or {}).get("zeugnis") or "", "pruefungen": []}


def stand(spez, menge, chargen, gewaehlt="", entnahmen=None, angefragt=False):
	"""Materialstand eines Fertigungsbauteils für Karte, Liste und Kalender.
	status: ohne (kein Rohmaterial angegeben) | entnommen | reserviert (gewählte Charge reicht) | lager (passende Chargen
	reichen) | teilweise | fehlt. Dazu die passenden Chargen mit „reicht für“ und Prüfung der Anforderungen."""
	if not spez_vollstaendig(spez):
		if entnahmen:
			return {"status": "entnommen", "text": "Material entnommen", "passend": [], "teile": 0}
		return {"status": "ohne", "text": "Rohmaterial nicht angegeben", "passend": [], "teile": 0}
	anf = anforderungen(spez)
	passend = []
	for c in chargen or []:
		if not passt(c, spez):
			continue
		ok, fehlt = pruefen(c, anf)
		passend.append({**c, "reicht": reicht_fuer(c, spez), "jeEinheit": je_einheit(c, spez), "ok": ok, "fehlt": fehlt})
	# Fokus auf das, was im Lager liegt und passt: gewählte Charge zuerst, dann die mit erfüllten Anforderungen, die reichen
	passend.sort(key=lambda c: (c["id"] != gewaehlt, not c["ok"], c["reicht"] < menge, -c["reicht"]))
	teile = sum(c["reicht"] for c in passend if c["ok"])
	g = next((c for c in passend if c["id"] == gewaehlt), None)
	if entnahmen:
		st, text = "entnommen", "Material entnommen"
	elif g and g["ok"] and g["reicht"] >= menge:
		st, text = "reserviert", f"Charge {g.get('interneNr') or g['id']} reserviert"
	elif teile >= menge:
		st, text = "lager", "Material im Lager"
	elif teile > 0:
		st, text = "teilweise", f"Im Lager nur für {teile} von {menge} Stk"
	else:
		st, text = "fehlt", "Material angefragt, noch nicht im Lager" if angefragt else "Material nicht im Lager"
	return {"status": st, "text": text, "passend": passend, "teile": teile}


def verbrauch_fuer_bauteil(entnahmen):
	"""Tatsächlicher Verbrauch je Stück aus den Entnahmen eines Fertigungsbauteils (für den nächsten Auftrag):
	Summe des Verbrauchs geteilt durch die gefertigte Menge. → { jeStueck, einheit } oder None."""
	if not entnahmen:
		return None
	einheit = entnahmen[-1].get("einheit") or "mm"
	gleich = [e for e in entnahmen if (e.get("einheit") or "mm") == einheit]
	menge = max(int(e.get("menge") or 0) for e in gleich)
	if menge < 1:
		return None
	return {"jeStueck": round(sum(_n(e.get("verbraucht")) for e in gleich) / menge, 1), "einheit": einheit}


def entnahme_rechnen(charge, stueck, rest_laenge=0, rest_breite=0, menge=0):
	"""Verbrauch einer Entnahme: `stueck` Stangen/Platten aus der Charge, ein Reststück (Länge, bei Platten auch Breite)
	geht zurück ins Lager. → { verbraucht (mm bzw. mm²), einheit, jeStueck } oder ValueError."""
	stueck = int(stueck or 0)
	if stueck < 1:
		raise ValueError("Bitte angeben, wie viele Stangen bzw. Platten entnommen wurden.")
	if stueck > int(charge.get("stueck") or 0):
		raise ValueError(f"In der Charge sind nur {int(charge.get('stueck') or 0)} Stück.")
	platte = charge.get("form") == "Platte"
	rl, rb = _n(rest_laenge), _n(rest_breite)
	if rl < 0 or rb < 0 or rl > _n(charge.get("laenge")) + EPS or (platte and rb > _n(charge.get("breite")) + EPS):
		raise ValueError("Das Reststück ist größer als das entnommene Material.")
	if platte:
		if rl and not rb:
			raise ValueError("Bitte beim Reststück einer Platte Länge und Breite angeben.")
		gesamt = stueck * _n(charge.get("laenge")) * _n(charge.get("breite"))
		verbraucht = gesamt - rl * rb
	else:
		verbraucht = stueck * _n(charge.get("laenge")) - rl
	return {
		"verbraucht": round(verbraucht, 1), "einheit": "mm²" if platte else "mm",
		"jeStueck": round(verbraucht / menge, 1) if menge else 0,
	}
