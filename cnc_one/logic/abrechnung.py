"""Abrechnungsstand eines Auftrags aus den Rechnungen. Stornierte Rechnungen und Stornorechnungen zählen nicht,
Entwürfe zählen mit, damit dieselbe Menge nicht in zwei Entwürfen landet."""

import json

import frappe


def _rechnungspositionen(auftrag):
	return frappe.db.sql(
		"""select rp.art, rp.auftragsposition_key, rp.auftragskosten_name, rp.menge, rp.lieferungen,
			r.name, r.rechnungsnummer, r.status
		from `tabRechnungsposition` rp join `tabRechnung` r on r.name = rp.parent
		where r.auftrag = %s and r.art != 'Storno' and r.status != 'Storniert' order by r.creation, rp.idx""",
		(auftrag,), as_dict=True,
	)


def berechnet_je_position(auftrag):
	"""{ Auftragspositions-Schlüssel: { menge, rechnungen: [{ id, nummer, menge, status }] } }"""
	ergebnis = {}
	for z in _rechnungspositionen(auftrag):
		if z.art != "Bauteil" or not z.auftragsposition_key:
			continue
		e = ergebnis.setdefault(z.auftragsposition_key, {"menge": 0, "rechnungen": []})
		e["menge"] += int(z.menge or 0)
		e["rechnungen"].append({"id": z.name, "nummer": z.rechnungsnummer or "", "menge": int(z.menge or 0), "status": z.status})
	return ergebnis


def berechnet_je_lieferscheinposition(auftrag):
	"""{ (Lieferschein, Auftragspositions-Schlüssel): schon berechnete Menge }. Quelle sind die Verweise in den Rechnungspositionen."""
	ergebnis = {}
	for z in _rechnungspositionen(auftrag):
		if z.art != "Bauteil" or not z.lieferungen:
			continue
		for ref in json.loads(z.lieferungen) if isinstance(z.lieferungen, str) else z.lieferungen:
			k = (ref["lieferschein"], z.auftragsposition_key)
			ergebnis[k] = ergebnis.get(k, 0) + int(ref.get("menge") or 0)
	return ergebnis


def sonderkosten_in_rechnung(auftrag):
	"""Namen der Kostenzeilen des Auftrags, die schon in einer Rechnung (auch Entwurf) stehen."""
	return {z.auftragskosten_name for z in _rechnungspositionen(auftrag) if z.art == "Sonderkosten" and z.auftragskosten_name}


def rechnungen_zum_auftrag(auftrag):
	return [
		{"id": r.name, "nummer": r.rechnungsnummer or "", "art": r.art, "status": r.status}
		for r in frappe.get_all("Rechnung", filters={"auftrag": auftrag}, fields=["name", "rechnungsnummer", "art", "status"], order_by="creation asc")
	]


def abrechnungsstatus(bestellt, berechnet):
	if berechnet <= 0:
		return "Nicht berechnet"
	return "Berechnet" if berechnet >= bestellt else "Teilweise berechnet"


def rechnungen_je_lieferschein():
	"""{ Lieferschein: [Rechnungsname, ...] } über alle nicht stornierten Rechnungen."""
	zeilen = frappe.db.sql(
		"""select rp.lieferungen, r.name from `tabRechnungsposition` rp join `tabRechnung` r on r.name = rp.parent
		where r.art != 'Storno' and r.status != 'Storniert' and rp.lieferungen is not null and rp.lieferungen != ''""",
		as_dict=True,
	)
	ergebnis = {}
	for z in zeilen:
		for ref in json.loads(z.lieferungen) if isinstance(z.lieferungen, str) else z.lieferungen:
			liste = ergebnis.setdefault(ref["lieferschein"], [])
			if z.name not in liste:
				liste.append(z.name)
	return ergebnis
