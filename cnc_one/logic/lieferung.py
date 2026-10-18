"""Lieferstand der Auftragspositionen aus den Lieferscheinen (stornierte zählen nicht)."""

import frappe


def geliefert_je_position(auftrag):
	"""{ Auftragspositions-Schlüssel: { menge, lieferscheine: [{ id, menge, status }] } } über alle Lieferscheine zum Auftrag."""
	zeilen = frappe.db.sql(
		"""select p.auftragsposition_key, p.menge, l.name, l.status from `tabLieferscheinposition` p
		join `tabLieferschein` l on l.name = p.parent
		where p.auftrag = %s and l.status != 'Storniert' order by l.creation, p.idx""",
		(auftrag,),
	)
	ergebnis = {}
	for key, menge, ls, status in zeilen:
		e = ergebnis.setdefault(key, {"menge": 0, "lieferscheine": []})
		e["menge"] += int(menge or 0)
		e["lieferscheine"].append({"id": ls, "menge": int(menge or 0), "status": status})
	return ergebnis


def lieferstatus(bestellt, geliefert):
	if geliefert <= 0:
		return "Nicht geliefert"
	return "Geliefert" if geliefert >= bestellt else "Teilweise geliefert"
