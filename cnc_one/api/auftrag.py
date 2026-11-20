"""Aufträge. Entstehen aus einem gesendeten Angebot oder aus einer Bestellung des Kunden (api/bestellung.py), der Server
rechnet Preise und Summen selbst."""

import frappe
from frappe import _

from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.stamm import arbeitsgang_ui, kunde_ui, nur_cnc
from cnc_one.logic.beleg import position_fuer_auftrag
from cnc_one.logic.daten import als_json, datum, iso
from cnc_one.logic.kalkulation import berechne, num, r2
from cnc_one.logic import abrechnung
from cnc_one.logic.lieferung import geliefert_je_position, lieferstatus
from cnc_one.logic.serien import STANDARD_STELLEN, bereich, hoechste, ueberschneidet


def auftrag_ui(d):
	"""Der Auftrag in der Form, die die Oberfläche erwartet."""
	kunde = frappe.get_doc("Kunde", d.kunde) if d.kunde else None
	geliefert = geliefert_je_position(d.name) if d.name else {}
	berechnet = abrechnung.berechnet_je_position(d.name) if d.name else {}
	berechnet_summe = sum(min(berechnet.get(p.position_key, {}).get("menge", 0), p.menge or 0) for p in d.positionen)
	gefertigt = {r.auftragsposition_key: int(r.produziert or 0) for r in frappe.get_all("Fertigungsbauteil", filters={"auftrag": d.name}, fields=["auftragsposition_key", "produziert"])} if d.name else {}
	bestellt_summe = sum(p.menge or 0 for p in d.positionen)
	geliefert_summe = sum(min(geliefert.get(p.position_key, {}).get("menge", 0), p.menge or 0) for p in d.positionen)
	return {
		"id": d.name,
		"lieferung": {"bestellt": bestellt_summe, "geliefert": geliefert_summe, "status": lieferstatus(bestellt_summe, geliefert_summe)},
		"abrechnung": {"berechnet": berechnet_summe, "status": abrechnung.abrechnungsstatus(bestellt_summe, berechnet_summe), "rechnungen": abrechnung.rechnungen_zum_auftrag(d.name) if d.name else []},
		"angebotId": d.angebot or "",
		"angebote": list(dict.fromkeys(x for x in [d.angebot] + [p.angebot for p in d.positionen] if x)),
		"bestelldatum": datum(d.bestelldatum),
		"bestellungDatei": d.bestellung_datei or "",
		"kundeName": d.kunde_name or "",
		"kunde": kunde_ui(kunde) if kunde else None,
		"kundenbestellnr": d.kundenbestellnr or "",
		"projekt": d.projekt or "",
		"kontaktName": d.kontakt_name or "",
		"kontaktEmail": d.kontakt_email or "",
		"datum": iso(d.creation),
		"status": d.status,
		"netto": d.netto or 0,
		"ab": {"gesendetAm": iso(d.ab_gesendet_am) if d.ab_gesendet_am else "", "gesendetAn": d.ab_gesendet_an or "", "aenderung": d.ab_aenderung or 0},
		"aenderungNr": d.aenderung_nr or 0,
		"aenderungen": [
			{"nr": z.nr, "datum": iso(z.datum), "benutzer": z.benutzer or "", "grund": z.grund or "", "details": [x for x in (z.details or "").splitlines() if x.strip()]}
			for z in d.aenderungen
		],
		"positionen": [
			{
				"key": p.position_key,
				"entfallen": bool(p.entfallen),
				"mengeUrspruenglich": p.menge_urspruenglich or None,
				"angebotKey": p.angebot_position_key or "",
				"angebotId": p.angebot or d.angebot or "",
				"bestellposition": p.bestellposition or "",
				"bestellpreis": p.bestellpreis or 0,
				"preisform": p.preisform or "Angebot",
				"teil": {
					"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "",
					"material": p.material or "", "bauteilId": p.bauteil or "", **bauteil_api.dateien_fuer(p.bauteil, p.revision),
					"vorschaubild": bauteil_api.bild(p.bauteil, p.revision, p.angebot or d.angebot, p.angebot_position_key),
				},
				"menge": p.menge,
				"einzelpreis": p.einzelpreis or 0,
				"staffelMenge": p.staffel_menge or None,
				"termin": datum(p.liefertermin),
				"kosten": [{"label": k.bezeichnung, "betrag": k.betrag or 0} for k in d.kosten if k.position_key == p.position_key],
				"summe": p.summe or 0,
				"arbeitsgaenge": als_json(p.arbeitsplan) if p.arbeitsplan else [],
				"serienVon": p.serien_von or None,
				"serienBis": p.serien_bis or None,
				"serienStellen": p.serien_stellen or STANDARD_STELLEN,
				"gefertigt": gefertigt.get(p.position_key, 0),
				"geliefert": geliefert.get(p.position_key, {}).get("menge", 0),
				"lieferscheine": geliefert.get(p.position_key, {}).get("lieferscheine", []),
				"berechnet": berechnet.get(p.position_key, {}).get("menge", 0),
				"rechnungen": berechnet.get(p.position_key, {}).get("rechnungen", []),
				"kostenAbgerechnet": {k.bezeichnung: (k.abgerechnet_in or "") for k in d.kosten if k.position_key == p.position_key},
			}
			for p in d.positionen
		],
	}


def alle_ui():
	namen = frappe.get_list("Auftrag", pluck="name", order_by="creation desc", limit_page_length=0)
	return [auftrag_ui(frappe.get_doc("Auftrag", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


@frappe.whitelist(methods=["POST"])
def aus_angebot(angebot, kundenbestellnr="", positionen=None):
	"""Legt einen Auftrag aus einem gesendeten Angebot an.

	`positionen`: Liste mit { angebotKey, optionId, menge, termin, kostenAus: [Bezeichnung], arbeitsgaenge, planSpeichern, serienStart }.
	Staffel, Menge und abgewählte Kostenzeilen wählt der Benutzer, Preise und Summen rechnet der Server.
	Bei Bauteilen mit Seriennummern ist `serienStart` Pflicht: die Nummern laufen ab dort fortlaufend, die höchste wird am Bauteil vermerkt.
	"""
	nur_cnc()
	if isinstance(positionen, str):
		positionen = frappe.parse_json(positionen)
	if not positionen:
		frappe.throw(_("Der Auftrag braucht mindestens eine Position."))
	ang = frappe.get_doc("Angebot", angebot)
	if ang.status != "Gesendet":
		frappe.throw(_("Nur aus einem gesendeten Angebot lässt sich ein Auftrag anlegen."))

	doc = neuer_auftrag(ang.kunde, kundenbestellnr, ang)
	merker = {"serien": [], "vergeben": [], "plaene": []}
	for p in positionen:
		ap = next((z for z in ang.positionen if z.position_key == p.get("angebotKey")), None)
		if not ap:
			frappe.throw(_("Die Angebotsposition {0} gibt es nicht.").format(p.get("angebotKey")))
		position_aus_angebot(doc, ang, ap, p, merker)
	doc.insert()
	nachbereiten(doc, merker)
	return auftrag_ui(doc)


def neuer_auftrag(kunde, kundenbestellnr="", ang=None):
	doc = frappe.new_doc("Auftrag")
	doc.kunde = kunde
	doc.angebot = ang.name if ang else None
	doc.status = "Offen"
	doc.kundenbestellnr = (kundenbestellnr or "").strip()
	if ang:
		doc.projekt, doc.kontakt_name, doc.kontakt_email = ang.projekt or "", ang.kontakt_name or "", ang.kontakt_email or ""
	return doc


def _bestellangaben(p):
	"""Angaben aus der Bestellung des Kunden an einer Position (leer, wenn der Auftrag nicht aus einer Bestellung kommt)."""
	return {
		"bestellposition": str(p.get("bestellposition") or "").strip()[:40],
		"bestellpreis": r2(num(p.get("bestellpreis"))) if num(p.get("bestellpreis")) > 0 else 0,
	}


def position_aus_angebot(doc, ang, ap, p, merker):
	"""Position aus einer Angebotsposition. Preisform „Bestellung“: Stückpreis laut Bestellung, keine eigenen Kostenzeilen
	(der Kunde hat die Kosten auf den Stückpreis umgelegt)."""
	teil = als_json(ap.kalkulation)
	r = position_fuer_auftrag(teil, berechne(teil), p.get("optionId"), p.get("menge"), p.get("kostenAus") or [])
	bestellung = _bestellangaben(p)
	preisform = "Bestellung" if p.get("preisform") == "Bestellung" and bestellung["bestellpreis"] else "Angebot"
	if preisform == "Bestellung":
		r = {**r, "einzelpreis": bestellung["bestellpreis"], "kosten": [], "summe": r2(bestellung["bestellpreis"] * r["menge"])}
	key = f"{ap.position_key}-{frappe.generate_hash(length=6)}"
	plan = p.get("arbeitsgaenge") or []
	von, bis, stellen = serienbereich(ap, teil, p, r["menge"], merker["vergeben"])
	doc.append("positionen", {
		"position_key": key,
		"angebot": ang.name,
		"angebot_position_key": ap.position_key,
		"bauteil": ap.bauteil or None,
		"teilenummer": ap.teilenummer,
		"bezeichnung": ap.bezeichnung,
		"zeichnungsnr": ap.zeichnungsnr,
		"revision": ap.revision or "",
		"material": ap.material,
		"menge": r["menge"],
		"einzelpreis": r["einzelpreis"],
		"staffel_menge": r["staffelMenge"],
		"liefertermin": p.get("termin") or None,
		"arbeitsplan": frappe.as_json(plan),
		"serien_von": von or None,
		"serien_bis": bis or None,
		"serien_stellen": stellen if von else None,
		"preisform": preisform,
		**bestellung,
	})
	if von and ap.bauteil:
		merker["serien"].append((ap.bauteil, bis))
	for k in r["kosten"]:
		doc.append("kosten", {"position_key": key, "bezeichnung": k["label"], "betrag": k["betrag"]})
	if p.get("planSpeichern") and plan and (ap.teilenummer or "").strip():
		merker["plaene"].append((ang.kunde, ap, plan))


def position_aus_bauteil(doc, b, p, merker):
	"""Position ohne Angebot (Wiederholbestellung ohne neues Angebot): Angaben und Arbeitsplan vom Bauteil, Preis laut
	Bestellung."""
	bestellung = _bestellangaben(p)
	if not bestellung["bestellpreis"]:
		frappe.throw(_("Für {0} gibt es kein Angebot, bitte den Stückpreis der Bestellung angeben.").format(b.teilenummer))
	menge = max(1, int(num(p.get("menge")) or 1))
	ap = frappe._dict(bauteil=b.name, bezeichnung=b.bezeichnung or b.teilenummer, teilenummer=b.teilenummer)
	von, bis, stellen = serienbereich(ap, {}, p, menge, merker["vergeben"])
	plan = p.get("arbeitsgaenge") or [arbeitsgang_ui(r) for r in b.arbeitsplan]
	doc.append("positionen", {
		"position_key": f"b-{frappe.generate_hash(length=8)}",
		"bauteil": b.name,
		"teilenummer": b.teilenummer,
		"bezeichnung": b.bezeichnung or "",
		"zeichnungsnr": b.zeichnungsnr or "",
		"revision": p.get("revision") or b.revision or "",
		"material": b.material or "",
		"menge": menge,
		"einzelpreis": bestellung["bestellpreis"],
		"liefertermin": p.get("termin") or None,
		"arbeitsplan": frappe.as_json(plan),
		"serien_von": von or None,
		"serien_bis": bis or None,
		"serien_stellen": stellen if von else None,
		"preisform": "Bestellung",
		**bestellung,
	})
	if von:
		merker["serien"].append((b.name, bis))


def nachbereiten(doc, merker):
	"""Nach dem Anlegen: höchste Seriennummer am Bauteil vermerken, gewünschte Arbeitspläne am Bauteil speichern."""
	for bauteil, bis in merker["serien"]:
		# die höchste vergebene Nummer am Bauteil festhalten, der nächste Auftrag macht dort weiter
		letzte = frappe.db.get_value("Bauteil", bauteil, "letzte_seriennummer") or 0
		if bis > letzte:
			frappe.db.set_value("Bauteil", bauteil, "letzte_seriennummer", bis)
	for kunde, ap, plan in merker["plaene"]:
		bauteil_api.plan_setzen(kunde, ap.teilenummer, plan, ap.bezeichnung, ap.zeichnungsnr, ap.material)


def mit_serien(ap, teil):
	"""Hat das Bauteil dieser Angebotsposition Seriennummern? Maßgeblich ist das Bauteil, sonst die Angabe in der Workbench."""
	if ap.bauteil:
		return bool(frappe.db.get_value("Bauteil", ap.bauteil, "seriennummern"))
	return bool(teil.get("seriennummern"))


def serienbereich(ap, teil, p, menge, vergeben):
	"""Bereich (von, bis, Stellen) der Position oder (0, 0, 0) ohne Seriennummern.

	Seriennummern bestehen nur aus Ziffern und haben immer die am Bauteil festgelegte Stellenzahl (Standard 4: 0001).
	Geprüft wird auch, dass sich nichts mit früheren Aufträgen überschneidet."""
	if not mit_serien(ap, teil):
		return 0, 0, 0
	stellen = (frappe.db.get_value("Bauteil", ap.bauteil, "serien_stellen") if ap.bauteil else 0) or STANDARD_STELLEN
	text = str(p.get("serienStart") or "").strip()
	if not text:
		frappe.throw(_("Für {0} bitte die erste Seriennummer eingeben.").format(ap.bezeichnung or ap.teilenummer))
	if not text.isdigit():
		frappe.throw(_("Seriennummern bestehen nur aus Ziffern, zum Beispiel {0}.").format("1".zfill(stellen)))
	start = int(text)
	if start <= 0:
		frappe.throw(_("Die erste Seriennummer muss größer als null sein."))
	neu = bereich(start, menge)
	if neu[1] > hoechste(stellen):
		frappe.throw(_("Die Seriennummern {0} bis {1} passen nicht in {2} Stellen.").format(str(neu[0]).zfill(stellen), neu[1], stellen))
	if ap.bauteil:
		bestehend = frappe.db.sql(
			"""select p.serien_von, p.serien_bis, p.parent from `tabAuftragsposition` p
			join `tabAuftrag` a on a.name = p.parent
			where p.bauteil = %s and p.serien_von > 0 and a.status != 'Storniert'""",
			(ap.bauteil,),
		)
		for von, bis, auftrag in bestehend:
			if ueberschneidet(neu, (von, bis)):
				frappe.throw(_("Die Seriennummern {0} bis {1} überschneiden sich mit {2} ({3} bis {4}).").format(neu[0], neu[1], auftrag, von, bis))
		for b, vb in vergeben:
			if b == ap.bauteil and ueberschneidet(neu, vb):
				frappe.throw(_("Die Seriennummern {0} bis {1} überschneiden sich mit einer anderen Position dieses Auftrags.").format(neu[0], neu[1]))
		vergeben.append((ap.bauteil, neu))
	return neu[0], neu[1], stellen


def plan_fuer_position(auftrag, pos):
	"""Arbeitsplan einer Auftragsposition: im Auftrag gepflegt, sonst am Bauteil gespeichert, sonst aus dem Angebot, sonst leer."""
	eigener = als_json(pos.arbeitsplan) if pos.arbeitsplan else []
	if eigener:
		return eigener
	if pos.bauteil:
		am_bauteil = [arbeitsgang_ui(r) for r in frappe.get_doc("Bauteil", pos.bauteil).arbeitsplan]
		if am_bauteil:
			return am_bauteil
	angebot = pos.angebot or auftrag.angebot
	if not angebot:
		return []
	ang = frappe.get_doc("Angebot", angebot)
	ap = next((z for z in ang.positionen if z.position_key == pos.angebot_position_key), None)
	return (als_json(ap.kalkulation).get("arbeitsgaenge") or []) if ap else []


# ----------------------------------------------------------------- Auftrag ändern
def _pos_name(p):
	return " ".join(x for x in (p.bezeichnung or "", f"({p.teilenummer})" if p.teilenummer else "") if x) or p.position_key


def _serien_ok(d, p, von, bis):
	"""Die verlängerten Seriennummern dürfen sich nicht mit anderen Aufträgen überschneiden."""
	if not p.bauteil:
		return
	for v, b, auftrag in frappe.db.sql(
		"""select p.serien_von, p.serien_bis, p.parent from `tabAuftragsposition` p join `tabAuftrag` a on a.name = p.parent
		where p.bauteil = %s and p.serien_von > 0 and a.status != 'Storniert' and not (p.parent = %s and p.position_key = %s)""",
		(p.bauteil, d.name, p.position_key),
	):
		if ueberschneidet((von, bis), (v, b)):
			frappe.throw(_("Die Seriennummern {0} bis {1} überschneiden sich mit {2} ({3} bis {4}).").format(von, bis, auftrag, v, b))


def _fertigung_anpassen(d, p, details):
	"""Fertigungsbauteil der Position an Menge und Termin anpassen. Eine entfallene Position ohne Buchungen verschwindet
	aus der Fertigung; mit Buchungen bleibt sie mit der neuen Menge und einem Hinweis stehen."""
	name = frappe.db.get_value("Fertigungsbauteil", {"auftrag": d.name, "auftragsposition_key": p.position_key}, "name")
	if not name:
		return
	fb = frappe.get_doc("Fertigungsbauteil", name)
	gebucht = (fb.produziert or 0) > 0 or any((a.gebucht or 0) > 0 for a in fb.arbeitsgaenge)
	if p.entfallen and not gebucht:
		frappe.delete_doc("Fertigungsbauteil", name, ignore_permissions=True)
		details.append(_("Fertigung: {0} herausgenommen ({1})").format(_pos_name(p), name))
		return
	if (fb.menge or 0) != (p.menge or 0) or p.entfallen:
		hinweis = _("Auftragsänderung {0}: Menge {1} → {2}").format(d.aenderung_nr, fb.menge, p.menge) + (_(" (Position entfällt)") if p.entfallen else "")
		fb.bemerkungen = ((fb.bemerkungen or "") + "\n" + hinweis).strip()
	fb.update({"menge": p.menge, "termin": p.liefertermin, "serien_von": p.serien_von or None, "serien_bis": p.serien_bis or None})
	fb.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def aendern(id, grund="", positionen=None, neu=None):
	"""Ändert einen laufenden Auftrag: Menge (0 = Position entfällt), Stückpreis, Liefertermin und Sonderkosten je
	Position, dazu neue Positionen aus einem Angebot. Die Nummer bleibt; jede Änderung wird mit Grund festgehalten und
	verlangt eine neue Auftragsbestätigung („Änderung 1“, „Änderung 2“ …). Fertigung wird mit angepasst.

	`positionen`: [{ key, menge, einzelpreis, termin, kosten: [{label, betrag}] }]
	`neu`: [{ angebotId, angebotKey, optionId, menge, termin, kostenAus, serienStart }] wie beim Anlegen aus dem Angebot

	Grenzen: nicht unter die gelieferte oder berechnete Menge; Preis und Sonderkosten nur, solange nichts berechnet ist."""
	from cnc_one.api.erechnung import _de, _eur

	nur_cnc()
	positionen = frappe.parse_json(positionen) if isinstance(positionen, str) else (positionen or [])
	neu = frappe.parse_json(neu) if isinstance(neu, str) else (neu or [])
	d = frappe.get_doc("Auftrag", id)
	d.check_permission("write")
	if d.status == "Storniert":
		frappe.throw(_("Ein stornierter Auftrag lässt sich nicht ändern."))
	grund = (grund or "").strip()
	if not grund:
		frappe.throw(_("Bitte den Grund der Änderung angeben (z. B. Nachverhandlung, Position entfällt)."))
	geliefert = geliefert_je_position(d.name)
	berechnet = abrechnung.berechnet_je_position(d.name)
	nr = (d.aenderung_nr or 0) + 1
	details, geaendert = [], []

	for w in positionen:
		p = next((x for x in d.positionen if x.position_key == w.get("key")), None)
		if not p:
			frappe.throw(_("Die Position {0} gibt es im Auftrag nicht.").format(w.get("key")))
		name = _pos_name(p)
		g = geliefert.get(p.position_key, {}).get("menge", 0)
		b = berechnet.get(p.position_key, {}).get("menge", 0)
		vorher = len(details)
		# Menge
		if "menge" in w and w["menge"] not in (None, ""):
			menge = int(num(w["menge"]))
			if menge < 0:
				frappe.throw(_("{0}: Die Menge darf nicht negativ sein.").format(name))
			if menge < max(g, b):
				frappe.throw(_("{0}: {1} Stück sind schon geliefert oder berechnet, weniger geht nicht.").format(name, max(g, b)))
			if menge != (p.menge or 0):
				if not p.menge_urspruenglich:
					p.menge_urspruenglich = p.menge
				details.append(_("{0}: entfällt (vorher {1} Stk)").format(name, p.menge) if menge == 0 else _("{0}: Menge {1} → {2} Stk").format(name, p.menge, menge))
				if p.entfallen and menge > 0:
					details.append(_("{0}: wieder aufgenommen").format(name))
				p.menge = menge
				p.entfallen = 1 if menge == 0 else 0
				if p.serien_von:
					if menge == 0:
						p.serien_von = p.serien_bis = None
					else:
						bis = p.serien_von + menge - 1
						if bis > (p.serien_bis or 0):
							_serien_ok(d, p, p.serien_von, bis)
						p.serien_bis = bis
		# Stückpreis
		if "einzelpreis" in w and w["einzelpreis"] not in (None, "") and r2(num(w["einzelpreis"])) != r2(p.einzelpreis or 0):
			if b:
				frappe.throw(_("{0}: Es ist schon etwas berechnet, der Stückpreis lässt sich nicht mehr ändern.").format(name))
			details.append(_("{0}: Stückpreis {1} → {2}").format(name, _eur(p.einzelpreis or 0), _eur(r2(num(w["einzelpreis"])))))
			p.einzelpreis = r2(num(w["einzelpreis"]))
		# Liefertermin
		if "termin" in w:
			termin = w.get("termin") or None
			if str(termin or "") != str(p.liefertermin or ""):
				details.append(_("{0}: Liefertermin {1} → {2}").format(name, _de(p.liefertermin) if p.liefertermin else "–", _de(termin) if termin else "–"))
				p.liefertermin = termin
		# Sonderkosten der Position (abgerechnete bleiben, wie sie sind)
		if w.get("kosten") is not None or p.entfallen:
			alt = [k for k in d.kosten if k.position_key == p.position_key]
			wunsch = [] if p.entfallen else [{"label": (k.get("label") or "").strip(), "betrag": r2(num(k.get("betrag")))} for k in (w.get("kosten") or []) if (k.get("label") or "").strip()]
			for k in alt:
				z = next((x for x in wunsch if x["label"] == k.bezeichnung), None)
				if k.abgerechnet_in:
					if not z or z["betrag"] != r2(k.betrag or 0):
						frappe.throw(_("{0}: {1} ist schon berechnet ({2}) und bleibt.").format(name, k.bezeichnung, k.abgerechnet_in))
					continue
				if not z:
					details.append(_("{0}: {1} entfällt ({2})").format(name, k.bezeichnung, _eur(k.betrag or 0)))
					d.remove(k)
				elif z["betrag"] != r2(k.betrag or 0):
					details.append(_("{0}: {1} {2} → {3}").format(name, k.bezeichnung, _eur(k.betrag or 0), _eur(z["betrag"])))
					k.betrag = z["betrag"]
			for z in wunsch:
				if not any(k.bezeichnung == z["label"] for k in alt):
					details.append(_("{0}: {1} neu ({2})").format(name, z["label"], _eur(z["betrag"])))
					d.append("kosten", {"position_key": p.position_key, "bezeichnung": z["label"], "betrag": z["betrag"]})
		if len(details) > vorher:
			geaendert.append(p)

	# neue Positionen aus einem Angebot
	merker = {"serien": [], "vergeben": [], "plaene": []}
	neue_keys = []
	for w in neu:
		ang = frappe.get_doc("Angebot", w.get("angebotId") or d.angebot)
		if ang.status != "Gesendet" or ang.kunde != d.kunde:
			frappe.throw(_("Neue Positionen kommen aus einem gesendeten Angebot desselben Kunden."))
		ap = next((z for z in ang.positionen if z.position_key == w.get("angebotKey")), None)
		if not ap:
			frappe.throw(_("Die Angebotsposition {0} gibt es nicht.").format(w.get("angebotKey")))
		position_aus_angebot(d, ang, ap, w, merker)
		p = d.positionen[-1]
		neue_keys.append(p.position_key)
		details.append(_("Neue Position {0}: {1} Stk zu {2}").format(_pos_name(p), p.menge, _eur(p.einzelpreis or 0)))

	if not details:
		frappe.throw(_("Es wurde nichts geändert."))
	d.aenderung_nr = nr
	d.append("aenderungen", {"nr": nr, "datum": frappe.utils.now_datetime(), "benutzer": frappe.session.user, "grund": grund, "details": "\n".join(details)})
	d.save()
	nachbereiten(d, merker)

	# Fertigung mitziehen, wenn sie schon läuft
	if frappe.db.exists("Fertigungsbauteil", {"auftrag": d.name}):
		from cnc_one.api.fertigung import fb_anlegen

		zusatz = []
		for p in geaendert:
			_fertigung_anpassen(d, p, zusatz)
		for key in neue_keys:
			fb_anlegen(d, next(x for x in d.positionen if x.position_key == key))
		if zusatz:
			zeile = d.aenderungen[-1]
			zeile.db_set("details", zeile.details + "\n" + "\n".join(zusatz), update_modified=False)
	return auftrag_ui(frappe.get_doc("Auftrag", d.name))


@frappe.whitelist(methods=["POST"])
def projekt_setzen(id, projekt=""):
	"""Projektname (intern) des Auftrags ändern; Fertigung, Lieferschein und Rechnung zeigen ihn über den Auftrag."""
	nur_cnc()
	doc = frappe.get_doc("Auftrag", id)
	doc.check_permission("write")
	doc.db_set("projekt", (projekt or "").strip())
	return auftrag_ui(doc)
