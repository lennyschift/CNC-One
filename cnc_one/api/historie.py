"""Historie eines Bauteils: frühere Angebote, Aufträge und Fertigungen.

Die Historie wird nicht am Bauteil gespeichert, sondern bei jedem Abruf aus den Belegen gelesen (Angebotsposition,
Auftragsposition, Fertigungsbauteil mit dem Bauteil). So gibt es nur einen Datenstand: ändert sich ein Beleg, zeigt die
Historie das sofort.
"""

import frappe

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic.beleg import optionen
from cnc_one.logic.daten import als_json, datum, iso
from cnc_one.logic.kalkulation import num, r2


def _bauteil(bauteil="", kunde="", teilenummer=""):
	if bauteil and frappe.db.exists("Bauteil", bauteil):
		return bauteil
	from cnc_one.api.bauteil import finden

	return finden(kunde, teilenummer)


def _bedingung(bauteil, kunde, teilenummer, alias):
	"""SQL-Bedingung für die Positionen des Bauteils; ohne Bauteil über Kunde und Teilenummer."""
	if bauteil:
		return f"{alias}.bauteil = %(bauteil)s"
	if kunde and (teilenummer or "").strip():
		return f"lower({alias}.teilenummer) = %(teilenummer)s and k.kunde = %(kunde)s"
	return None


def angebote(bauteil, kunde="", teilenummer="", ohne_angebot=""):
	bed = _bedingung(bauteil, kunde, teilenummer, "p")
	if not bed:
		return []
	zeilen = frappe.db.sql(
		f"""select p.parent as angebot, p.position_key, p.menge, p.netto, p.kalkulation, p.ergebnis, p.revision,
			k.status, k.creation, k.versandt_am, k.kunde_name
		from `tabAngebotsposition` p join `tabAngebot` k on k.name = p.parent
		where {bed} and p.parenttype = 'Angebot' and k.name != %(ohne)s
		order by coalesce(k.versandt_am, k.creation) desc limit 50""",
		{"bauteil": bauteil, "kunde": kunde, "teilenummer": (teilenummer or "").strip().lower(), "ohne": ohne_angebot or ""},
		as_dict=True,
	)
	beauftragt = set()
	if zeilen:
		for r in frappe.db.sql(
			"""select coalesce(nullif(p.angebot, ''), a.angebot), p.angebot_position_key from `tabAuftragsposition` p join `tabAuftrag` a on a.name = p.parent
			where a.status != 'Storniert' and coalesce(nullif(p.angebot, ''), a.angebot) in %(angebote)s""",
			{"angebote": tuple({z.angebot for z in zeilen})},
		):
			beauftragt.add(tuple(r))
	out = []
	for z in zeilen:
		teil, ergebnis = als_json(z.kalkulation), als_json(z.ergebnis)
		preise = [{"menge": o["menge"], "einzel": r2(num(o["einzel"]))} for o in optionen(teil, ergebnis)] if ergebnis.get("zeilen") is not None else []
		out.append({
			"angebot": z.angebot, "positionKey": z.position_key, "status": z.status, "datum": iso(z.versandt_am or z.creation),
			"kundeName": z.kunde_name or "", "revision": z.revision or "", "menge": z.menge or 0, "netto": z.netto or 0,
			"preise": preise, "kosten": [{"label": k["label"], "betrag": k["betrag"]} for k in ergebnis.get("zeilen") or [] if k.get("typ") == "kosten"],
			"preisart": teil.get("preisart") or "kalkuliert", "staffel": bool((teil.get("staffel") or {}).get("aktiv")),
			"beauftragt": (z.angebot, z.position_key) in beauftragt,
		})
	return out


def auftraege(bauteil, kunde="", teilenummer=""):
	bed = _bedingung(bauteil, kunde, teilenummer, "p")
	if not bed:
		return []
	zeilen = frappe.db.sql(
		f"""select p.parent as auftrag, p.position_key, p.menge, p.einzelpreis, p.summe, p.liefertermin, p.revision, p.staffel_menge,
			p.preisform, p.bestellpreis, coalesce(nullif(p.angebot, ''), k.angebot) as angebot, p.angebot_position_key,
			k.status, k.creation, k.kundenbestellnr, k.kunde_name
		from `tabAuftragsposition` p join `tabAuftrag` k on k.name = p.parent
		where {bed} and p.parenttype = 'Auftrag'
		order by k.creation desc limit 50""",
		{"bauteil": bauteil, "kunde": kunde, "teilenummer": (teilenummer or "").strip().lower()},
		as_dict=True,
	)
	kosten = {}
	if zeilen:
		for k in frappe.get_all("Auftragskosten", filters={"parent": ["in", list({z.auftrag for z in zeilen})], "parenttype": "Auftrag"}, fields=["parent", "position_key", "bezeichnung", "betrag"]):
			kosten.setdefault((k.parent, k.position_key), []).append({"label": k.bezeichnung, "betrag": k.betrag or 0})
	return [{
		"auftrag": z.auftrag, "positionKey": z.position_key, "status": z.status, "datum": iso(z.creation), "kundeName": z.kunde_name or "",
		"kundenbestellnr": z.kundenbestellnr or "", "menge": z.menge or 0, "einzelpreis": z.einzelpreis or 0, "summe": z.summe or 0,
		"jeStueck": r2((z.summe or 0) / z.menge) if z.menge else 0, "kosten": kosten.get((z.auftrag, z.position_key), []),
		"termin": datum(z.liefertermin), "revision": z.revision or "", "staffelMenge": z.staffel_menge or None,
		"preisform": z.preisform or "Angebot", "bestellpreis": z.bestellpreis or 0,
		"angebot": z.angebot or "", "angebotKey": z.angebot_position_key or "",
	} for z in zeilen]


def fertigungen(bauteil, kunde="", teilenummer=""):
	if bauteil:
		filters = {"bauteil": bauteil}
	elif kunde and (teilenummer or "").strip():
		filters = {"kunde": kunde, "teilenummer": teilenummer.strip()}
	else:
		return []
	out = []
	for n in frappe.get_all("Fertigungsbauteil", filters=filters, pluck="name", order_by="creation desc", limit=30):
		d = frappe.get_doc("Fertigungsbauteil", n)
		zeiten = sorted(b.zeit for b in d.buchungen if b.zeit)
		out.append({
			"id": d.name, "auftrag": d.auftrag, "status": d.status, "menge": d.menge or 0, "produziert": d.produziert or 0,
			"ueberproduktion": d.ueberproduktion or 0, "termin": datum(d.termin), "revision": d.revision or "",
			"von": iso(zeiten[0]) if zeiten else "", "bis": iso(zeiten[-1]) if zeiten else "",
			"arbeitsgaenge": [{"name": a.bezeichnung or "", "maschine": a.maschine or "", "lieferant": a.lieferant or "", "ruestMin": a.ruest_min or 0, "stueckMin": a.stueck_min or 0} for a in d.arbeitsgaenge],
			"rohmaterial": " · ".join(x for x in (d.roh_werkstoff, d.roh_info, d.roh_charge and f"Charge {d.roh_charge}") if x),
			"bemerkungen": d.bemerkungen or "", "pruefmasse": d.pruefmasse or "",
		})
	return out


def historie_daten(bauteil="", kunde="", teilenummer="", ohne_angebot=""):
	b = _bauteil(bauteil, kunde, teilenummer)
	if b:
		kunde = frappe.db.get_value("Bauteil", b, "kunde") or kunde
	ang = angebote(b, kunde, teilenummer, ohne_angebot)
	auf = auftraege(b, kunde, teilenummer)
	fert = fertigungen(b, kunde, teilenummer)
	aktive = [a for a in auf if a["status"] != "Storniert"]
	return {
		"bauteilId": b or "",
		"angebote": ang,
		"auftraege": auf,
		"fertigungen": fert,
		"kennzahlen": {
			"angebote": len(ang), "auftraege": len(aktive), "stueck": sum(a["menge"] for a in aktive),
			"letzterAuftrag": aktive[0] if aktive else None,
			"letztesAngebot": ang[0] if ang else None,
		},
	}


@frappe.whitelist(methods=["POST"])
def historie(bauteil="", kunde="", teilenummer="", ohne_angebot=""):
	"""Historie zu einem Bauteil (oder, ohne Bauteil, zu Kunde und Teilenummer). `ohne_angebot`: das gerade offene
	Angebot der Workbench nicht mitzählen."""
	nur_cnc()
	return historie_daten(bauteil, kunde, teilenummer, ohne_angebot)


@frappe.whitelist(methods=["POST"])
def kalkulation(angebot, position_key):
	"""Die Kalkulation (Eingaben der Workbench) einer früheren Angebotsposition, zum Übernehmen der Preise."""
	nur_cnc()
	doc = frappe.get_doc("Angebot", angebot)
	doc.check_permission("read")
	z = next((p for p in doc.positionen if p.position_key == position_key), None)
	return als_json(z.kalkulation) if z else {}
