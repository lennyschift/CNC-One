"""Bestehende Lieferantenanfragen bekommen einen Vorgang: Anfragen zum selben Angebot mit denselben Positionen, die
innerhalb einer Minute angelegt wurden, gingen zusammen raus (gemeinsame Nummer = die kleinste)."""

import frappe


def execute():
	zeilen = frappe.get_all("Lieferantenanfrage", filters={"vorgang": ["in", ["", None]]}, fields=["name", "angebot", "creation"], order_by="creation asc")
	gruppen = []
	for z in zeilen:
		schluessel = tuple(sorted(frappe.get_all("Anfrageposition", filters={"parent": z.name, "parenttype": "Lieferantenanfrage"}, pluck="position_key")))
		g = next((g for g in gruppen if g["angebot"] == z.angebot and g["schluessel"] == schluessel and (z.creation - g["zeit"]).total_seconds() < 60), None)
		if g:
			g["namen"].append(z.name)
		else:
			gruppen.append({"angebot": z.angebot, "schluessel": schluessel, "zeit": z.creation, "namen": [z.name]})
	for g in gruppen:
		vorgang = min(g["namen"])
		for n in g["namen"]:
			frappe.db.set_value("Lieferantenanfrage", n, "vorgang", vorgang, update_modified=False)
