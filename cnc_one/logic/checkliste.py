"""Checkliste vor dem Fertigungsstart: feste Punkte aus den Einstellungen (Material, Werkzeug, Messmittel …), je
Fertigungsbauteil abgehakt und um eigene Punkte ergänzt. Reine Logik ohne Datenbank, damit sie testbar bleibt."""

STANDARD = [
	{"id": "material", "text": "Material", "hinweis": "Rohmaterial bereitgestellt, Charge und Zeugnis geprüft", "pflicht": True},
	{"id": "werkzeug", "text": "Werkzeug", "hinweis": "Werkzeuge vorhanden und vermessen", "pflicht": True},
	{"id": "messmittel", "text": "Messmittel", "hinweis": "Messmittel vorhanden und geprüft", "pflicht": True},
	{"id": "spannmittel", "text": "Spannmittel / Vorrichtung", "hinweis": "", "pflicht": True},
	{"id": "zeichnung", "text": "Zeichnung", "hinweis": "Aktuelle Revision liegt an der Maschine", "pflicht": True},
	{"id": "programm", "text": "NC-Programm", "hinweis": "Programm vorhanden und freigegeben", "pflicht": False},
]


def _text(v, laenge):
	return str(v or "").strip()[:laenge]


def vorlage_bereinigt(punkte):
	"""Punkte der Vorlage: { id, text, hinweis, pflicht, aktiv }; ohne Text fällt ein Punkt weg, die id bleibt stabil."""
	out, ids = [], set()
	for i, p in enumerate(punkte or []):
		if not isinstance(p, dict) or not _text(p.get("text"), 80):
			continue
		pid = _text(p.get("id"), 40) or f"p{i}"
		while pid in ids:
			pid += "x"
		ids.add(pid)
		out.append({
			"id": pid, "text": _text(p.get("text"), 80), "hinweis": _text(p.get("hinweis"), 200),
			"pflicht": bool(p.get("pflicht")), "aktiv": p.get("aktiv") is not False,
		})
	return out


def zusammenfuehren(vorlage, stand):
	"""Checkliste eines Fertigungsbauteils: die aktiven Punkte der Vorlage (in deren Reihenfolge) mit dem gespeicherten
	Stand, dazu die eigenen Punkte dieses Bauteils. Ein inzwischen abgeschalteter Punkt bleibt, wenn er schon abgehakt war."""
	stand = {s.get("id"): s for s in (stand or []) if isinstance(s, dict)}
	out = []
	for p in vorlage:
		s = stand.get(p["id"], {})
		if not p.get("aktiv", True) and not s.get("erledigt"):
			continue
		out.append({
			"id": p["id"], "text": p["text"], "hinweis": p.get("hinweis", ""), "pflicht": bool(p.get("pflicht")), "eigen": False,
			"erledigt": bool(s.get("erledigt")), "von": s.get("von", ""), "am": s.get("am", ""), "notiz": s.get("notiz", ""),
		})
	vorlage_ids = {p["id"] for p in vorlage}
	for s in stand.values():
		if s.get("eigen") and s.get("id") not in vorlage_ids:
			out.append({
				"id": s["id"], "text": s.get("text", ""), "hinweis": "", "pflicht": bool(s.get("pflicht")), "eigen": True,
				"erledigt": bool(s.get("erledigt")), "von": s.get("von", ""), "am": s.get("am", ""), "notiz": s.get("notiz", ""),
			})
	return out


def offen(liste):
	"""Pflichtpunkte, die vor dem Start noch nicht abgehakt sind."""
	return [p for p in liste if p["pflicht"] and not p["erledigt"]]


def gespeichert(liste):
	"""Was am Fertigungsbauteil gespeichert wird: nur der Stand (Text und Pflicht nur bei eigenen Punkten)."""
	out = []
	for p in liste:
		z = {"id": p["id"], "erledigt": bool(p["erledigt"]), "von": p.get("von", ""), "am": p.get("am", ""), "notiz": p.get("notiz", "")}
		if p.get("eigen"):
			z.update({"eigen": True, "text": p["text"], "pflicht": bool(p.get("pflicht"))})
		if z["erledigt"] or z["notiz"] or p.get("eigen"):
			out.append(z)
	return out
