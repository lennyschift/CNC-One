"""Regeln der Fertigung. Muss dasselbe regeln wie frontend/src/lib/fertigung.js.

Alle Funktionen arbeiten auf Zeilen mit den Feldern der Doctypes Fertigungsarbeitsgang (ag_id, gebucht, status, typ)
und Fertigungssendung (ag_id, menge, datum_weg, datum_zurueck).
"""


def _n(wert):
	return int(wert or 0)


def produziert(ags):
	"""Stückzahl, die alle Arbeitsgänge durchlaufen hat (Minimum der gebuchten Mengen)."""
	return min(_n(a.gebucht) for a in ags) if ags else 0


def ueberproduktion(menge, prod):
	"""Mehr als bestellt produziert: der Rest geht später ins Lager."""
	return max(0, prod - _n(menge))


def fremd_gebucht(sendungen):
	"""Fremdvergabe: gebucht ist, was vom Lieferanten zurück ist."""
	return sum(_n(s.menge) for s in sendungen if s.datum_zurueck)


def gesendet(sendungen):
	return sum(_n(s.menge) for s in sendungen)


def noch_nicht_gesendet(menge, sendungen):
	return max(0, _n(menge) - gesendet(sendungen))


def nachzuholen(ags, ag_id, neue_gesamt):
	"""Wird in einem Arbeitsgang auf `neue_gesamt` gebucht, gelten alle früheren mindestens bis zu dieser Menge
	als erledigt. Liefert die dafür nötigen Nachbuchungen als Liste von (ag_id, delta)."""
	i = next((k for k, a in enumerate(ags) if a.ag_id == ag_id), -1)
	out = []
	for a in ags[: max(i, 0)]:
		delta = neue_gesamt - _n(a.gebucht)
		if delta > 0:
			out.append((a.ag_id, delta))
	return out


def auto_status(ags, menge):
	"""Status aus dem Stand der Arbeitsgänge. Ohne Arbeitsgänge bleibt das Bauteil offen."""
	if ags and all(_n(a.gebucht) >= _n(menge) for a in ags):
		return "Fertig"
	if any(_n(a.gebucht) > 0 or a.status == "Läuft" for a in ags):
		return "In Fertigung"
	return "Offen"


def arbeitsgang_status(ag, menge, sendungen):
	if _n(ag.gebucht) >= _n(menge):
		return "Fertig"
	unterwegs = any(s.datum_weg and not s.datum_zurueck for s in sendungen)
	if _n(ag.gebucht) > 0 or unterwegs:
		return "Läuft"
	return "Offen"
