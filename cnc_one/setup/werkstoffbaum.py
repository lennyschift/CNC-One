"""Grundbestand des Rohmaterial-Baums: Zustände, Ausführungen je Form, Abmessungsreihen, Materialanforderungen und
gängige Werkstoffe mit Zuständen und Formen. Legt nur an, was fehlt (idempotent); Preise je kg sind Richtwerte zum
Überschreiben. Bestehende Einträge des Benutzers bleiben unverändert.
"""

import frappe

ZUSTAENDE = [
	("+N", "normalgeglüht"), ("+QT", "vergütet"), ("+C", "kaltgezogen"), ("+A", "weichgeglüht"), ("+AR", "walzhart, unbehandelt"),
	("+AT", "lösungsgeglüht"), ("+SH", "geschält"),
	("T3", "lösungsgeglüht, kaltverfestigt, kaltausgelagert"), ("T351", "T3, durch Recken entspannt"), ("T4", "lösungsgeglüht, kaltausgelagert"),
	("T6", "lösungsgeglüht, warmausgelagert"), ("T651", "T6, durch Recken entspannt (verzugsarm)"),
	("T7351", "überaltert, entspannt (spannungsrisskorrosionsbeständig)"),
	("H111", "geglüht, leicht kaltverfestigt"), ("H112", "leicht kaltverfestigt (gepresst)"), ("H116", "kaltverfestigt, seewasserbeständig"),
	("O", "weichgeglüht (Aluminium)"), ("R430", "Zugfestigkeit min. 430 MPa"), ("R500", "Zugfestigkeit min. 500 MPa"),
	("geglüht", "geglüht"), ("lösungsgeglüht", "lösungsgeglüht"), ("ausgehärtet", "lösungsgeglüht und ausgehärtet"),
	("gehärtet", "gehärtet"), ("Strangguss", "stranggegossen"), ("gegossen", "gegossen, entspannt"),
]

AUSFUEHRUNGEN = [
	("Rund", "gezogen h9", ""), ("Rund", "gezogen h11", ""), ("Rund", "geschält h9", "P M S H"), ("Rund", "gewalzt", "P M S H"),
	("Rund", "gepresst", "N"), ("Rund", "stranggegossen", "K"),
	("Vierkant", "gezogen h11", ""), ("Vierkant", "gepresst", "N"), ("Vierkant", "gewalzt", "P M"),
	("Flach", "gezogen h11", ""), ("Flach", "gewalzt", "P M H"), ("Flach", "gepresst", "N"), ("Flach", "aus Platte gesägt", ""), ("Flach", "stranggegossen", "K"),
	("Sechskant", "gezogen h11", ""), ("Sechskant", "gepresst", "N"),
	("Rohr", "nahtlos", ""), ("Rohr", "geschweißt", "P M"),
	("Platte", "gewalzt", ""), ("Platte", "gewalzt, feingefräst", "N"), ("Platte", "gegossen, feingefräst", "N"), ("Platte", "brenngeschnitten", "P"),
]

ABMESSUNGEN = {
	"Rund": [(d, 0) for d in (5, 6, 8, 10, 12, 14, 15, 16, 18, 20, 22, 25, 28, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200, 250)],
	"Vierkant": [(a, 0) for a in (10, 12, 15, 16, 20, 25, 30, 35, 40, 50, 60, 70, 80, 100)],
	"Flach": [(b, h) for b, h in (
		(20, 5), (20, 10), (25, 5), (25, 10), (30, 5), (30, 10), (30, 15), (30, 20), (40, 10), (40, 15), (40, 20), (40, 30), (50, 10), (50, 15), (50, 20),
		(50, 30), (50, 40), (60, 10), (60, 20), (60, 30), (60, 40), (70, 20), (80, 10), (80, 20), (80, 30), (80, 40), (80, 50), (100, 10), (100, 20),
		(100, 30), (100, 40), (100, 50), (120, 20), (120, 40), (150, 20), (150, 40), (150, 50), (200, 20), (200, 50))],
	"Sechskant": [(sw, 0) for sw in (8, 10, 11, 13, 14, 17, 19, 22, 24, 27, 30, 32, 36, 41, 46, 50, 55, 60)],
	"Rohr": [(d, s) for d, s in ((20, 2), (25, 2), (25, 3), (30, 3), (35, 3), (40, 4), (40, 5), (50, 5), (60, 5), (60, 10), (70, 10), (80, 10), (100, 10), (100, 15), (120, 20))],
	"Platte": [(t, 0) for t in (3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 120, 150)],
}

ANFORDERUNGEN = ["Ultraschallgeprüft", "RoHS/REACH", "Ursprung EU", "Luftfahrt (EN 9100)", "Konfliktmineral-frei", "Werkstoffprüfung extern"]

ALLE = ["Rund", "Vierkant", "Flach", "Sechskant", "Rohr", "Platte"]
# (Name, ISO, Kurzname, Schreibweisen, Dichte, Preis €/kg, Zustände, Formen)
WERKSTOFFE = [
	("1.0037", "P", "S235JR", ["S235", "St37-2", "Baustahl"], 7.85, 1.5, ["+AR", "+C"], ALLE),
	("1.0503", "P", "C45", ["C45E", "Ck45", "AISI 1045"], 7.85, 1.9, ["+N", "+QT", "+C"], ["Rund", "Vierkant", "Flach", "Sechskant", "Platte"]),
	("1.0718", "P", "11SMnPb30", ["9SMnPb28", "Automatenstahl"], 7.85, 1.7, ["+C"], ["Rund", "Sechskant", "Vierkant"]),
	("1.7225", "P", "42CrMo4", ["AISI 4140"], 7.85, 2.6, ["+QT", "+A"], ["Rund", "Vierkant", "Flach", "Platte"]),
	("1.8519", "P", "31CrMoV9", ["Nitrierstahl"], 7.85, 3.4, ["+QT"], ["Rund", "Flach"]),
	("1.2312", "P", "40CrMnMoS8-6", ["P20+S"], 7.85, 4.8, ["+QT"], ["Flach", "Platte", "Rund"]),
	("1.4301", "M", "X5CrNi18-10", ["V2A", "AISI 304"], 7.9, 4.9, ["+AT", "+C"], ALLE),
	("1.4305", "M", "X8CrNiS18-9", ["AISI 303", "V2A Automat"], 7.9, 5.2, ["+AT", "+C"], ["Rund", "Sechskant", "Vierkant", "Flach"]),
	("1.4404", "M", "X2CrNiMo17-12-2", ["V4A", "AISI 316L"], 8.0, 6.4, ["+AT"], ["Rund", "Flach", "Rohr", "Platte"]),
	("1.4571", "M", "X6CrNiMoTi17-12-2", ["V4A Ti", "AISI 316Ti"], 8.0, 6.9, ["+AT"], ["Rund", "Flach", "Rohr", "Platte"]),
	("1.4057", "M", "X17CrNi16-2", ["AISI 431"], 7.7, 5.9, ["+QT"], ["Rund"]),
	("EN-GJL-250", "K", "GG25", ["0.6025", "Grauguss"], 7.2, 2.9, ["Strangguss"], ["Rund", "Flach"]),
	("EN-GJS-400-15", "K", "GGG40", ["0.7040", "Sphäroguss"], 7.1, 3.2, ["Strangguss"], ["Rund", "Flach"]),
	("EN AW-6082", "N", "AlSi1MgMn", ["3.2315", "AlMgSi1"], 2.7, 5.8, ["T6", "T651"], ALLE),
	("EN AW-6060", "N", "AlMgSi", ["3.3206", "AlMgSi0,5"], 2.7, 5.4, ["T6", "T66"], ["Rund", "Vierkant", "Flach", "Rohr"]),
	("EN AW-7075", "N", "AlZn5,5MgCu", ["3.4365", "AlZnMgCu1,5", "Ergal"], 2.81, 9.5, ["T6", "T651", "T7351"], ["Rund", "Flach", "Platte"]),
	("EN AW-5083", "N", "AlMg4,5Mn0,7", ["3.3547", "AlMg4,5Mn"], 2.66, 6.1, ["H111", "H116", "gegossen"], ["Platte", "Flach"]),
	("EN AW-5754", "N", "AlMg3", ["3.3535"], 2.67, 5.2, ["H111", "O"], ["Platte", "Flach", "Rund"]),
	("EN AW-2007", "N", "AlCuMgPb", ["3.1645", "Automatenalu"], 2.85, 6.3, ["T3", "T4", "T351"], ["Rund", "Sechskant", "Vierkant", "Flach"]),
	("CW614N", "N", "CuZn39Pb3", ["2.0401", "Ms58", "Messing"], 8.47, 8.9, ["R430", "R500"], ["Rund", "Sechskant", "Vierkant", "Flach"]),
	("3.7165", "S", "Ti6Al4V", ["Grade 5", "TiAl6V4"], 4.43, 38.0, ["geglüht"], ["Rund", "Platte"]),
	("2.4668", "S", "NiCr19Fe19Nb5Mo3", ["Inconel 718", "Alloy 718"], 8.19, 62.0, ["lösungsgeglüht", "ausgehärtet"], ["Rund"]),
	("1.2379", "H", "X153CrMoV12", ["D2", "K110"], 7.7, 7.4, ["+A", "gehärtet"], ["Rund", "Flach"]),
]


def abmessung_text(form, m1, m2=0):
	z = lambda v: f"{float(v):g}".replace(".", ",")  # noqa: E731
	if form == "Rund":
		return f"Ø{z(m1)}"
	if form == "Vierkant":
		return f"□{z(m1)}"
	if form == "Flach":
		return f"{z(m1)} × {z(m2)}"
	if form == "Sechskant":
		return f"SW{z(m1)}"
	if form == "Rohr":
		return f"Ø{z(m1)} × {z(m2)}"
	if form == "Platte":
		return f"{z(m1)} mm"
	return z(m1)


def grundbestand(werkstoffe=True):
	for code, text in ZUSTAENDE:
		if not frappe.db.exists("Werkstoffzustand", code):
			frappe.get_doc({"doctype": "Werkstoffzustand", "code": code, "beschreibung": text, "aktiv": 1}).insert(ignore_permissions=True)
	if not frappe.db.exists("Werkstoffzustand", "T66"):
		frappe.get_doc({"doctype": "Werkstoffzustand", "code": "T66", "beschreibung": "T6, erhöhte Festigkeit (6060)", "aktiv": 1}).insert(ignore_permissions=True)
	for form, name, iso in AUSFUEHRUNGEN:
		if not frappe.db.exists("Rohmaterial Ausfuehrung", {"form": form, "bezeichnung": name}):
			frappe.get_doc({"doctype": "Rohmaterial Ausfuehrung", "form": form, "bezeichnung": name, "iso_gruppen": iso, "aktiv": 1}).insert(ignore_permissions=True)
	for form, reihe in ABMESSUNGEN.items():
		for m1, m2 in reihe:
			text = abmessung_text(form, m1, m2)
			if not frappe.db.exists("Rohmaterial Abmessung", {"form": form, "bezeichnung": text}):
				frappe.get_doc({"doctype": "Rohmaterial Abmessung", "form": form, "mass1": m1, "mass2": m2, "bezeichnung": text, "aktiv": 1}).insert(ignore_permissions=True)
	for a in ANFORDERUNGEN:
		a = a.replace("­", "")
		if not frappe.db.exists("Materialanforderung", a):
			frappe.get_doc({"doctype": "Materialanforderung", "bezeichnung": a, "aktiv": 1}).insert(ignore_permissions=True)
	if werkstoffe:
		for name, iso, kurz, alias, dichte, preis, zust, formen in WERKSTOFFE:
			if frappe.db.exists("Material", name):
				continue
			frappe.get_doc({
				"doctype": "Material", "materialname": name, "iso_gruppe": iso, "kurzname": kurz, "schreibweisen": "\n".join([kurz, *alias]),
				"dichte": dichte, "preis_kg": preis, "zustaende": "\n".join(zust), "formen": "\n".join(formen), "aktiv": 1,
			}).insert(ignore_permissions=True)
