"""Rechnungen, Zahlungen. Eine Rechnung entsteht nur aus einem Auftrag: als Gesamtrechnung oder als Teilrechnung
über ausgewählte Mengen aus Lieferscheinen. Sonderkosten kommen vollständig in die erste Rechnung."""

import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from cnc_one.api.firma import firma_ui
from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import abrechnung, erechnung, nummernkreis
from cnc_one.logic.daten import datum, iso
from cnc_one.logic.kalkulation import r2
from cnc_one.logic.lieferung import geliefert_je_position
from cnc_one.logic.rechnung import STEUERSATZ_STANDARD, faellig_am, iban_formatiert, inhalt_hash, summen, tage_ueberfaellig, zeilenbetrag, zuteilen
from cnc_one.logic.serien import STANDARD_STELLEN, formatiert

BUCHHALTUNG = ("CNC Admin", "CNC Buchhaltung", "System Manager")
FESTGESCHRIEBEN = ("Offen", "Teilbezahlt", "Bezahlt")


# ------------------------------------------------------------------ Umrechnung für die Oberfläche
def _zahlung_ui(z):
	return {"id": z.name, "betrag": z.betrag or 0, "datum": datum(z.datum), "referenz": z.referenz or "", "konto": z.konto or "", "storniert": bool(z.storniert), "stornoGrund": z.storno_grund or "", "benutzer": z.benutzer or ""}


def rechnung_ui(d):
	zahlungen = frappe.get_all("Zahlung", filters={"rechnung": d.name}, fields=["*"], order_by="datum asc, creation asc")
	mahnungen = frappe.get_all("Mahnung", filters={"rechnung": d.name}, fields=["name", "stufe", "status", "datum", "frist_bis"], order_by="creation asc")
	offen_status = d.status in ("Offen", "Teilbezahlt")
	return {
		"id": d.name,
		"nummer": d.rechnungsnummer or "",
		"art": d.art,
		"status": d.status,
		"kundeId": d.kunde,
		"kundeName": d.kunde_name or "",
		"auftragId": d.auftrag,
		"erstellt": iso(d.creation),
		"rechnungsdatum": datum(d.rechnungsdatum),
		"leistungVon": datum(d.leistung_von),
		"leistungBis": datum(d.leistung_bis),
		"zahlungszielTage": d.zahlungsziel_tage or 0,
		"faelligAm": datum(d.faellig_am),
		"tageUeberfaellig": tage_ueberfaellig(d.faellig_am) if offen_status and d.faellig_am and tage_ueberfaellig(d.faellig_am) > 0 else 0,
		"kundenbestellnr": d.kundenbestellnr or "",
		"adresse": [z for z in (d.rechnungsadresse or "").split("\n") if z],
		"kundeUstId": d.kunde_ust_id or "",
		"leitwegId": d.leitweg_id or "",
		"einleitung": d.einleitung or "",
		"bemerkung": d.bemerkung or "",
		"zahlungshinweis": d.zahlungshinweis or "",
		"fusstext": d.fusstext or "",
		"firma": json.loads(d.firma_snapshot) if d.firma_snapshot and isinstance(d.firma_snapshot, str) else (d.firma_snapshot or (firma_ui() if d.status == "Entwurf" else None)),
		"steuersatz": d.steuersatz or 0,
		"netto": d.netto or 0, "steuerbetrag": d.steuerbetrag or 0, "brutto": d.brutto or 0, "bezahlt": d.bezahlt or 0, "offen": d.offen or 0,
		"stornoZu": d.storno_zu or "", "storniertDurch": d.storniert_durch or "", "stornoGrund": d.storno_grund or "",
		"eRechnung": {
			"status": d.erechnung_status or "", "hinweis": d.erechnung_hinweis or "",
			"pdf": d.erechnung_status in ("ZUGFeRD und XRechnung", "ZUGFeRD", "Nur PDF"), "zugferd": d.erechnung_status in ("ZUGFeRD und XRechnung", "ZUGFeRD"),
			"xrechnung": d.erechnung_status == "ZUGFeRD und XRechnung",
		},
		"festgeschriebenAm": iso(d.festgeschrieben_am), "festgeschriebenVon": d.festgeschrieben_von or "", "inhaltHash": d.inhalt_hash or "",
		"positionen": [
			{
				"zeile": p.zeilen_id, "art": p.art, "bauteilId": p.bauteil or "",
				"teil": {"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "", "vorschaubild": ""},
				"bezeichnung": p.bezeichnung or "", "menge": p.menge, "einheit": p.einheit or "Stk", "einzelpreis": p.einzelpreis or 0, "netto": p.netto or 0,
				"auftragPosKey": p.auftragsposition_key or "", "auftragskosten": p.auftragskosten_name or "",
				"lieferungen": json.loads(p.lieferungen) if p.lieferungen and isinstance(p.lieferungen, str) else (p.lieferungen or []),
				"lieferungenText": p.lieferungen_text or "", "serienText": p.serien_text or "",
			}
			for p in d.positionen
		],
		"zahlungen": [_zahlung_ui(z) for z in zahlungen],
		"mahnungen": [{"id": m.name, "stufe": m.stufe, "status": m.status, "datum": datum(m.datum), "fristBis": datum(m.frist_bis)} for m in mahnungen],
	}


def alle_ui():
	namen = frappe.get_list("Rechnung", pluck="name", order_by="creation desc", limit_page_length=0)
	return [rechnung_ui(frappe.get_doc("Rechnung", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


# ------------------------------------------------------------------ Vorschlag aus dem Auftrag
def _lieferstand(auftrag):
	return frappe.db.sql(
		"""select l.name as lieferschein, l.status, l.lieferdatum, l.geliefert_am, l.creation, p.auftragsposition_key as pos_key, p.menge,
			p.serien_von, p.serien_bis, p.serien_stellen
		from `tabLieferscheinposition` p join `tabLieferschein` l on l.name = p.parent
		where p.auftrag = %s and l.status != 'Storniert' order by l.creation, p.idx""",
		(auftrag,), as_dict=True,
	)


def _ls_datum(r):
	return r.geliefert_am or r.lieferdatum or getdate(r.creation)


@frappe.whitelist(methods=["POST"])
def vorschlag(auftrag):
	"""Was lässt sich aus dem Auftrag berechnen? Je Position bestellt, geliefert, schon berechnet; dazu die Lieferscheine mit der
	noch nicht berechneten Menge und die Sonderkosten (schon in einer Rechnung oder noch frei)."""
	nur_cnc()
	auf = frappe.get_doc("Auftrag", auftrag)
	geliefert = geliefert_je_position(auf.name)
	berechnet = abrechnung.berechnet_je_position(auf.name)
	je_ls = abrechnung.berechnet_je_lieferscheinposition(auf.name)
	belegt = abrechnung.sonderkosten_in_rechnung(auf.name)
	positionen = []
	for p in auf.positionen:
		b = berechnet.get(p.position_key, {}).get("menge", 0)
		positionen.append({
			"key": p.position_key, "bauteilId": p.bauteil or "",
			"teil": {"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "", "vorschaubild": ""},
			"bestellt": p.menge, "geliefert": geliefert.get(p.position_key, {}).get("menge", 0), "berechnet": b, "offen": max(0, p.menge - b),
			"einzelpreis": p.einzelpreis or 0,
			"kosten": [{"name": k.name, "label": k.bezeichnung, "betrag": k.betrag or 0, "inRechnung": k.name in belegt} for k in auf.kosten if k.position_key == p.position_key],
		})
	lieferscheine = {}
	for r in _lieferstand(auf.name):
		e = lieferscheine.setdefault(r.lieferschein, {"id": r.lieferschein, "status": r.status, "datum": datum(_ls_datum(r)), "positionen": []})
		schon = je_ls.get((r.lieferschein, r.pos_key), 0)
		e["positionen"].append({"auftragPosKey": r.pos_key, "menge": r.menge, "berechnet": schon, "frei": max(0, r.menge - schon)})
	return {
		"auftragId": auf.name, "kundeId": auf.kunde, "kundeName": auf.kunde_name,
		"positionen": positionen, "lieferscheine": list(lieferscheine.values()),
	}


# ------------------------------------------------------------------ Entwurf anlegen
def _adresse_des_kunden(kunde):
	return next((x for x in kunde.adressen if x.typ in ("Rechnung", "Rechnung und Lieferung") and x.standard), None) \
		or next((x for x in kunde.adressen if x.typ in ("Rechnung", "Rechnung und Lieferung")), None) \
		or (kunde.adressen[0] if kunde.adressen else None)


def kaeufer_felder(kunde):
	"""Empfängerdaten für die E-Rechnung (als Snapshot an der Rechnung): Anschrift der Rechnungsadresse, E-Mail des Rechnungskontakts."""
	a = _adresse_des_kunden(kunde)
	kontakt = next((k for k in kunde.kontakte if k.ist_rechnungskontakt and k.email), None) or next((k for k in kunde.kontakte if k.email), None)
	return {
		"kunde_email": (kontakt.email if kontakt else "") or "",
		"kunde_strasse": (a.strasse if a else "") or "", "kunde_plz": (a.plz if a else "") or "", "kunde_ort": (a.ort if a else "") or "",
		"kunde_land": (erechnung.laendercode(a.land) or a.land) if a else "DE",
	}


def _rechnungsadresse(kunde):
	a = _adresse_des_kunden(kunde)
	zeilen = [kunde.kundenname]
	if a:
		land = a.land if (a.land or "").strip().upper() not in ("", "DE", "DEUTSCHLAND") else ""
		zeilen += [z for z in (a.strasse, " ".join(x for x in (a.plz, a.ort) if x), land) if z]
	return zeilen


def _steuer():
	"""Standard-Steuerschlüssel (erstmal Inland 19 %). Fehlt er, gilt 19 % ohne Schlüssel."""
	r = frappe.db.get_value("Steuerschluessel", {"standard": 1, "aktiv": 1}, ["name", "satz"], as_dict=True)
	return (r.name, r.satz) if r else (None, STEUERSATZ_STANDARD)


def _serien_text(von, bis, stellen, schon, menge):
	"""Seriennummern des berechneten Teils eines Lieferscheinpostens: die Nummern nach den schon berechneten."""
	if not von:
		return ""
	a = von + schon
	b = a + menge - 1
	return formatiert(a, stellen) if a == b else f"{formatiert(a, stellen)}–{formatiert(b, stellen)}"


@frappe.whitelist(methods=["POST"])
def anlegen(auftrag, art, mengen=None, rechnungsdatum=None, bemerkung=""):
	"""Legt einen Rechnungsentwurf aus einem Auftrag an.

	art "Gesamtrechnung": alles, was noch nicht berechnet ist (Bestellmenge minus schon berechnet).
	art "Teilrechnung": `mengen` = [{ lieferschein, auftragsposition, menge }], höchstens die noch nicht berechnete Menge je Lieferscheinposition.
	Sonderkosten kommen in die erste Rechnung zur Position, vollständig."""
	nur_cnc()
	if isinstance(mengen, str):
		mengen = frappe.parse_json(mengen)
	if art not in ("Gesamtrechnung", "Teilrechnung"):
		frappe.throw(_("Die Art der Rechnung ist Gesamtrechnung oder Teilrechnung."))
	auf = frappe.get_doc("Auftrag", auftrag)
	if auf.status == "Storniert":
		frappe.throw(_("Ein stornierter Auftrag lässt sich nicht berechnen."))
	kunde = frappe.get_doc("Kunde", auf.kunde)
	firma = firma_ui()

	berechnet = abrechnung.berechnet_je_position(auf.name)
	je_ls = abrechnung.berechnet_je_lieferscheinposition(auf.name)
	belegt = abrechnung.sonderkosten_in_rechnung(auf.name)
	ls_rows = _lieferstand(auf.name)
	frei = {}
	for r in ls_rows:
		k = (r.lieferschein, r.pos_key)
		f = frei.setdefault(k, {"frei": 0, "schon": je_ls.get(k, 0), "von": r.serien_von, "bis": r.serien_bis, "stellen": r.serien_stellen or STANDARD_STELLEN, "datum": _ls_datum(r)})
		f["frei"] += r.menge
	for k, f in frei.items():
		f["frei"] = max(0, f["frei"] - f["schon"])

	# Wie viel je Auftragsposition, aus welchen Lieferscheinen: [(lieferschein, menge)]
	wahl = {}
	rest_ungeliefert = {}
	if art == "Gesamtrechnung":
		for p in auf.positionen:
			offen = p.menge - berechnet.get(p.position_key, {}).get("menge", 0)
			if offen <= 0:
				continue
			freie = [((ls, key), f["frei"]) for (ls, key), f in frei.items() if key == p.position_key]
			zugeteilt, rest = zuteilen(offen, freie)
			wahl[p.position_key] = [(k[0], n) for k, n in zugeteilt]
			rest_ungeliefert[p.position_key] = rest
	else:
		if not mengen:
			frappe.throw(_("Bitte die Mengen aus den Lieferscheinen wählen."))
		for m in mengen:
			menge = int(m.get("menge") or 0)
			if menge <= 0:
				continue
			k = (m.get("lieferschein"), m.get("auftragsposition"))
			if k not in frei:
				frappe.throw(_("Die Position gibt es im Lieferschein {0} nicht.").format(m.get("lieferschein")))
			if menge > frei[k]["frei"]:
				frappe.throw(_("Aus {0} sind nur noch {1} Stück zu berechnen.").format(m.get("lieferschein"), frei[k]["frei"]))
			frei[k]["frei"] -= menge
			wahl.setdefault(k[1], []).append((k[0], menge))
		for key, refs in wahl.items():
			p = next(x for x in auf.positionen if x.position_key == key)
			if sum(n for _ls, n in refs) > p.menge - berechnet.get(key, {}).get("menge", 0):
				frappe.throw(_("Von {0} ist schon mehr berechnet, als bestellt wurde.").format(p.bezeichnung or p.teilenummer))
			rest_ungeliefert[key] = 0
	if not wahl:
		frappe.throw(_("Es gibt nichts zu berechnen."))

	doc = frappe.new_doc("Rechnung")
	doc.kunde = auf.kunde
	doc.auftrag = auf.name
	doc.art = art
	doc.status = "Entwurf"
	doc.rechnungsdatum = getdate(rechnungsdatum or today())
	doc.zahlungsziel_tage = kunde.zahlungsziel_tage or firma["zahlungszielTage"]
	doc.kundenbestellnr = auf.kundenbestellnr or ""
	doc.rechnungsadresse = "\n".join(_rechnungsadresse(kunde))
	doc.kunde_ust_id = kunde.ust_id or ""
	doc.leitweg_id = kunde.leitweg_id or ""
	doc.update(kaeufer_felder(kunde))
	doc.einleitung = firma["rechnungText"]
	doc.bemerkung = (bemerkung or "").strip()
	schluessel, satz = _steuer()
	doc.steuerschluessel = schluessel
	doc.steuersatz = satz

	nr = 0
	daten = []
	netto_zeilen = []
	for p in auf.positionen:
		if p.position_key not in wahl:
			continue
		nr += 1
		refs = wahl[p.position_key]
		menge = sum(n for _ls, n in refs) if art == "Teilrechnung" else (p.menge - berechnet.get(p.position_key, {}).get("menge", 0))
		lieferungen = [{"lieferschein": ls, "menge": n} for ls, n in refs]
		teile = [f"{ls} ({n} Stk)" for ls, n in refs]
		rest = rest_ungeliefert.get(p.position_key, 0)
		text = ("Geliefert mit " + ", ".join(teile)) if teile else "Noch nicht geliefert"
		if teile and rest:
			text += f" · noch nicht geliefert: {rest} Stk"
		serien = []
		for ls, n in refs:
			f = frei[(ls, p.position_key)]
			s = _serien_text(f["von"], f["bis"], f["stellen"], f["schon"], n)
			f["schon"] += n
			if s:
				serien.append(s)
			daten.append(f["datum"])
		netto = zeilenbetrag(menge, p.einzelpreis)
		netto_zeilen.append(netto)
		doc.append("positionen", {
			"zeilen_id": str(nr), "art": "Bauteil", "bauteil": p.bauteil or None, "teilenummer": p.teilenummer, "bezeichnung": p.bezeichnung,
			"zeichnungsnr": p.zeichnungsnr, "menge": menge, "einheit": "Stk", "einzelpreis": p.einzelpreis or 0, "netto": netto,
			"auftragsposition_key": p.position_key, "lieferungen": json.dumps(lieferungen), "lieferungen_text": text, "serien_text": ", ".join(serien),
		})
		# Sonderkosten: in der ersten Rechnung zur Position vollständig, danach nicht mehr
		k = 0
		for kz in auf.kosten:
			if kz.position_key != p.position_key or kz.name in belegt:
				continue
			k += 1
			netto_zeilen.append(r2(kz.betrag))
			doc.append("positionen", {
				"zeilen_id": f"{nr}.{k}", "art": "Sonderkosten", "bezeichnung": f"{kz.bezeichnung} ({p.bezeichnung})", "menge": 1, "einheit": "pauschal",
				"einzelpreis": kz.betrag or 0, "netto": r2(kz.betrag), "auftragsposition_key": p.position_key, "auftragskosten_name": kz.name,
			})
	doc.leistung_von = min(daten) if daten else doc.rechnungsdatum
	doc.leistung_bis = max(daten) if daten else doc.rechnungsdatum
	doc.netto, doc.steuerbetrag, doc.brutto = summen(netto_zeilen, satz)
	doc.bezahlt = 0
	doc.offen = doc.brutto
	doc.faellig_am = faellig_am(doc.rechnungsdatum, doc.zahlungsziel_tage)
	doc.insert()
	return rechnung_ui(doc)


def _geladen(id):
	doc = frappe.get_doc("Rechnung", id)
	doc.check_permission("write")
	return doc


@frappe.whitelist(methods=["POST"])
def speichern(id, felder):
	"""Ändert einen Entwurf: Rechnungsdatum, Zahlungsziel, Bestellnummer, Einleitung, Bemerkung. Die Positionen ändert man nicht, dafür neu anlegen."""
	nur_cnc()
	if isinstance(felder, str):
		felder = frappe.parse_json(felder)
	doc = _geladen(id)
	if doc.status != "Entwurf":
		frappe.throw(_("Nur ein Entwurf lässt sich ändern."))
	if felder.get("rechnungsdatum"):
		doc.rechnungsdatum = getdate(felder["rechnungsdatum"])
	if "zahlungszielTage" in felder:
		doc.zahlungsziel_tage = max(0, int(felder["zahlungszielTage"] or 0))
	for ui, feld in (("kundenbestellnr", "kundenbestellnr"), ("einleitung", "einleitung"), ("bemerkung", "bemerkung")):
		if ui in felder:
			doc.set(feld, (felder[ui] or "").strip())
	doc.faellig_am = faellig_am(doc.rechnungsdatum, doc.zahlungsziel_tage)
	doc.save()
	return rechnung_ui(doc)


@frappe.whitelist(methods=["POST"])
def verwerfen(id):
	"""Löscht einen Entwurf. Festgeschriebene Rechnungen lassen sich nur stornieren."""
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Entwurf":
		frappe.throw(_("Nur ein Entwurf lässt sich verwerfen."))
	frappe.delete_doc("Rechnung", id)
	return {"id": id}


# ------------------------------------------------------------------ Festschreiben und Storno
def _festgeschrieben_menge(auftrag, key, ausser):
	return int(frappe.db.sql(
		"""select coalesce(sum(rp.menge), 0) from `tabRechnungsposition` rp join `tabRechnung` r on r.name = rp.parent
		where r.auftrag = %s and rp.auftragsposition_key = %s and rp.art = 'Bauteil' and r.name != %s
		and r.art != 'Storno' and r.status in ('Offen', 'Teilbezahlt', 'Bezahlt')""",
		(auftrag, key, ausser),
	)[0][0])


def _hash_inhalt(d):
	return inhalt_hash({
		"nummer": d.rechnungsnummer, "art": d.art, "kunde": d.kunde, "auftrag": d.auftrag, "datum": str(d.rechnungsdatum), "adresse": d.rechnungsadresse,
		"faellig": str(d.faellig_am), "steuersatz": d.steuersatz, "netto": d.netto, "steuer": d.steuerbetrag, "brutto": d.brutto,
		"positionen": [[p.zeilen_id, p.art, p.bezeichnung, p.menge, p.einzelpreis, p.netto, p.lieferungen_text, p.serien_text] for p in d.positionen],
		"firma": d.firma_snapshot,
	})


def _zahlungshinweis(firma, nummer):
	zeilen = [f"Bitte überweisen Sie den Betrag bis zum Fälligkeitsdatum unter Angabe der Rechnungsnummer {nummer} auf eines unserer Konten:"]
	for b in firma["banken"]:
		zeilen.append(f"{b['bezeichnung']}: IBAN {b['iban']}" + (f", BIC {b['bic']}" if b["bic"] else ""))
	return "\n".join(zeilen)


def _erechnung(doc):
	"""E-Rechnung (PDF/A-3 mit ZUGFeRD, XRechnung) zur festgeschriebenen Rechnung ablegen; ein Fehler hält das Festschreiben nicht auf."""
	from cnc_one.api import erechnung as ablage

	ablage.erzeugen_sicher(doc)


@frappe.whitelist(methods=["POST"])
def festschreiben(id):
	"""Schreibt den Entwurf fest: lückenlose Rechnungsnummer, Rechnungsdatum heute, Firmendaten als Snapshot, Prüfsumme.
	Danach ist die Rechnung unveränderlich, Korrektur nur per Storno."""
	frappe.only_for(BUCHHALTUNG)
	doc = _geladen(id)
	if doc.status != "Entwurf":
		frappe.throw(_("Nur ein Entwurf lässt sich festschreiben."))
	if not doc.positionen:
		frappe.throw(_("Die Rechnung hat keine Positionen."))
	bestellt = {p.position_key: p.menge for p in frappe.get_doc("Auftrag", doc.auftrag).positionen}
	for z in doc.positionen:
		if z.art == "Bauteil":
			if _festgeschrieben_menge(doc.auftrag, z.auftragsposition_key, doc.name) + z.menge > bestellt.get(z.auftragsposition_key, 0):
				frappe.throw(_("Von {0} ist inzwischen mehr berechnet, als bestellt wurde. Bitte den Entwurf verwerfen und neu anlegen.").format(z.bezeichnung))
		elif z.auftragskosten_name:
			schon = frappe.db.get_value("Auftragskosten", z.auftragskosten_name, "abgerechnet_in")
			if schon and schon != doc.name:
				frappe.throw(_("Die Sonderkosten {0} sind schon in {1} abgerechnet.").format(z.bezeichnung, schon))
	firma = firma_ui()
	heute = getdate(today())
	doc.rechnungsdatum = heute
	doc.faellig_am = faellig_am(heute, doc.zahlungsziel_tage)
	doc.leistung_von = doc.leistung_von or heute
	doc.leistung_bis = doc.leistung_bis or heute
	doc.rechnungsnummer = nummernkreis.rechnungsnummer(heute.year)
	doc.firma_snapshot = json.dumps(firma, ensure_ascii=False)
	doc.zahlungshinweis = _zahlungshinweis(firma, doc.rechnungsnummer)
	doc.fusstext = firma["rechnungFusstext"]
	doc.status = "Offen"
	doc.festgeschrieben_am = now_datetime()
	doc.festgeschrieben_von = frappe.session.user
	doc.inhalt_hash = _hash_inhalt(doc)
	doc.flags.festschreiben = True
	doc.save()
	for z in doc.positionen:
		if z.art == "Sonderkosten" and z.auftragskosten_name:
			frappe.db.set_value("Auftragskosten", z.auftragskosten_name, "abgerechnet_in", doc.name, update_modified=False)
	_erechnung(doc)
	return rechnung_ui(frappe.get_doc("Rechnung", doc.name))


@frappe.whitelist(methods=["POST"])
def stornieren(id, grund):
	"""Storniert eine festgeschriebene Rechnung mit einer Stornorechnung (Gutschrift, eigene Nummer, negative Beträge).
	Die berechneten Mengen und Sonderkosten sind danach im Auftrag wieder frei, offene Mahnungen werden zurückgezogen."""
	frappe.only_for(BUCHHALTUNG)
	if not (grund or "").strip():
		frappe.throw(_("Bitte einen Grund für die Stornierung angeben."))
	orig = _geladen(id)
	if orig.status not in FESTGESCHRIEBEN:
		frappe.throw(_("Nur eine festgeschriebene Rechnung lässt sich stornieren."))
	heute = getdate(today())
	s = frappe.new_doc("Rechnung")
	for f in ("kunde", "auftrag", "kundenbestellnr", "rechnungsadresse", "kunde_ust_id", "leitweg_id", "kunde_email", "kunde_strasse", "kunde_plz", "kunde_ort", "kunde_land",
	"steuerschluessel", "steuersatz", "firma_snapshot", "fusstext"):
		s.set(f, orig.get(f))
	s.art = "Storno"
	s.status = "Gutschrift"
	s.storno_zu = orig.name
	s.storno_grund = grund.strip()
	s.rechnungsdatum = heute
	s.leistung_von = s.leistung_bis = heute
	s.zahlungsziel_tage = 0
	s.faellig_am = heute
	s.einleitung = f"Stornorechnung zur Rechnung {orig.rechnungsnummer} vom {orig.rechnungsdatum.strftime('%d.%m.%Y')}. Grund: {grund.strip()}"
	for z in orig.positionen:
		s.append("positionen", {
			"zeilen_id": z.zeilen_id, "art": z.art, "bauteil": z.bauteil, "teilenummer": z.teilenummer, "bezeichnung": z.bezeichnung, "zeichnungsnr": z.zeichnungsnr,
			"menge": -(z.menge or 0), "einheit": z.einheit, "einzelpreis": z.einzelpreis, "netto": -(z.netto or 0),
			"lieferungen_text": z.lieferungen_text, "serien_text": z.serien_text,
		})
	s.netto, s.steuerbetrag, s.brutto = -orig.netto, -orig.steuerbetrag, -orig.brutto
	s.bezahlt = 0
	s.offen = 0
	s.rechnungsnummer = nummernkreis.rechnungsnummer(heute.year)
	s.festgeschrieben_am = now_datetime()
	s.festgeschrieben_von = frappe.session.user
	s.zahlungshinweis = ""
	s.inhalt_hash = _hash_inhalt(s)
	s.flags.festschreiben = True
	s.insert()
	frappe.db.set_value("Rechnung", orig.name, {"status": "Storniert", "storniert_durch": s.name, "offen": 0}, update_modified=True)
	for z in orig.positionen:
		if z.art == "Sonderkosten" and z.auftragskosten_name:
			frappe.db.set_value("Auftragskosten", z.auftragskosten_name, "abgerechnet_in", None, update_modified=False)
	for m in frappe.get_all("Mahnung", filters={"rechnung": orig.name, "status": ["in", ["Angelegt", "Versendet"]]}, pluck="name"):
		frappe.db.set_value("Mahnung", m, "status", "Zurückgezogen", update_modified=False)
	_erechnung(s)
	return {"storno": rechnung_ui(frappe.get_doc("Rechnung", s.name)), "original": rechnung_ui(frappe.get_doc("Rechnung", orig.name))}


# ------------------------------------------------------------------ Zahlungen
def zahlungsstand(name):
	"""Bezahlt, offen und Status der Rechnung aus den (nicht stornierten) Zahlungen neu berechnen."""
	d = frappe.get_doc("Rechnung", name)
	if d.status not in FESTGESCHRIEBEN:
		return d
	bezahlt = r2(frappe.db.sql("select coalesce(sum(betrag), 0) from `tabZahlung` where rechnung = %s and storniert = 0", (name,))[0][0])
	offen = r2((d.brutto or 0) - bezahlt)
	status = "Bezahlt" if offen <= 0 else "Teilbezahlt" if bezahlt > 0 else "Offen"
	frappe.db.set_value("Rechnung", name, {"bezahlt": bezahlt, "offen": max(0, offen), "status": status}, update_modified=False)
	if status == "Bezahlt":
		for m in frappe.get_all("Mahnung", filters={"rechnung": name, "status": ["in", ["Angelegt", "Versendet"]]}, pluck="name"):
			frappe.db.set_value("Mahnung", m, "status", "Erledigt", update_modified=False)
	return frappe.get_doc("Rechnung", name)


@frappe.whitelist(methods=["POST"])
def zahlung_erfassen(rechnung, betrag, zahlungsdatum=None, referenz="", konto=""):
	"""Erfasst einen Zahlungseingang (auch Teilzahlung)."""
	frappe.only_for(BUCHHALTUNG)
	d = frappe.get_doc("Rechnung", rechnung)
	if d.status not in ("Offen", "Teilbezahlt"):
		frappe.throw(_("Für diese Rechnung lässt sich keine Zahlung erfassen."))
	betrag = r2(betrag)
	if betrag <= 0:
		frappe.throw(_("Der Betrag muss größer als null sein."))
	if betrag > r2(d.offen) + 0.004:
		frappe.throw(_("Der Betrag {0} ist höher als der offene Betrag {1}.").format(betrag, d.offen))
	z = frappe.new_doc("Zahlung")
	z.rechnung = d.name
	z.betrag = betrag
	z.datum = getdate(zahlungsdatum or today())
	z.referenz = (referenz or "").strip()
	z.konto = (konto or "").strip()
	z.benutzer = frappe.session.user
	z.insert()
	return rechnung_ui(zahlungsstand(d.name))


@frappe.whitelist(methods=["POST"])
def zahlung_stornieren(id, grund):
	"""Storniert eine erfasste Zahlung (z. B. falsch zugeordnet). Sie bleibt mit Grund sichtbar."""
	frappe.only_for(BUCHHALTUNG)
	if not (grund or "").strip():
		frappe.throw(_("Bitte einen Grund angeben."))
	z = frappe.get_doc("Zahlung", id)
	if z.storniert:
		frappe.throw(_("Die Zahlung ist schon storniert."))
	frappe.db.set_value("Zahlung", z.name, {"storniert": 1, "storno_grund": grund.strip()}, update_modified=True)
	return rechnung_ui(zahlungsstand(z.rechnung))
