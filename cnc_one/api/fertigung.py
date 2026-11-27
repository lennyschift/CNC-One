"""Fertigungsbauteile. Die Buchungsregeln stehen im Doctype-Controller und in logic/fertigung.py,
hier liegen nur die Schnittstellen und die Umrechnung in die Form der Oberfläche."""

import frappe
from frappe import _

from cnc_one.api import auftrag as auftrag_api
from cnc_one.api import bauteil as bauteil_api
from cnc_one.api.werkstoff import roh_angaben
from cnc_one.api.stamm import arbeitsgang_ui, arbeitsgang_zeile, ist_serienart, nur_cnc, serienart_namen, typ_db, typ_ui
from frappe.utils import now_datetime

from cnc_one.logic import checkliste as check
from cnc_one.logic import rohlager
from cnc_one.logic.daten import als_json, datum, iso

FERTIGUNG_ROLLEN = ("CNC Admin", "CNC Vertrieb", "CNC Fertigung", "System Manager")


def _nur_fertigung():
	frappe.only_for(FERTIGUNG_ROLLEN)


# In der Fertigung sind keine Preise zu sehen: Sätze und Kosten bleiben am Server.
PREISFELDER = ("satz", "ruestDirekt", "ruestEuro", "stueckDirekt", "stueckEuro", "fremdProStk", "fremdEinmal")


def fb_ui(d):
	"""Das Fertigungsbauteil in der Form, die die Oberfläche erwartet (Sendungen verschachtelt im Arbeitsgang), ohne Preise."""
	ags = []
	for a in d.arbeitsgaenge:
		z = {k: v for k, v in arbeitsgang_ui(a).items() if k not in PREISFELDER}
		z.update({
			"bestellung": a.bestellung or "",
			"status": a.status,
			"gebucht": a.gebucht or 0,
			"geplantAm": datum(a.geplant_am),
			"istRuestMin": a.ist_ruest_min or 0,
			"istBearbMin": a.ist_bearb_min or 0,
			"istVon": a.ist_von or "",
			"istAm": iso(a.ist_am) if a.ist_am else "",
			"sendungen": [
				{
					"id": s.name, "menge": s.menge, "datumWeg": datum(s.datum_weg), "datumZurueck": datum(s.datum_zurueck),
					"abgehakt": bool(s.abgehakt),
				}
				for s in d.sendungen if s.ag_id == a.ag_id
			],
		})
		ags.append(z)
	return {
		"id": d.name,
		"auftragId": d.auftrag,
		"auftragPosKey": d.auftragsposition_key or "",
		"serienVon": d.serien_von or None,
		"serienBis": d.serien_bis or None,
		"serienStellen": d.serien_stellen or 4,
		"serienBestellung": _serien_bestellung(d),
		"kundeId": d.kunde or "",
		"kundeName": d.kunde_name or "",
		"teil": {
			"name": d.bezeichnung or "", "teilenummer": d.teilenummer or "", "zeichnungsnr": d.zeichnungsnr or "",
			"material": d.material or "", "bauteilId": d.bauteil or "", **bauteil_api.dateien_fuer(d.bauteil, d.revision),
			"vorschaubild": bauteil_api.bild(d.bauteil, d.revision) or bauteil_api.bild_zur_auftragsposition(d.auftrag, d.auftragsposition_key),
		},
		"menge": d.menge,
		"termin": datum(d.termin),
		"prioritaet": d.prioritaet,
		"status": d.status,
		"arbeitsgaenge": ags,
		"buchungen": [
			{"id": b.name, "zeit": iso(b.zeit), "agId": b.ag_id, "agName": b.ag_name or "", "menge": b.menge, "benutzer": b.benutzer or "", "auto": bool(b.auto)}
			for b in sorted(d.buchungen, key=lambda x: (x.zeit, x.idx), reverse=True)
		],
		"rohmaterial": {
			"werkstoff": d.roh_werkstoff or "", "charge": d.roh_charge or "", "lagerplatz": d.roh_lagerplatz or "",
			"info": d.roh_info or "", "verbrauchtMm": d.roh_verbraucht_mm or 0,
		},
		"roh": _roh_ui(d),
		"hinweis": _bauteil(d).get("fertigungshinweis") or "",
		"notizen": {"pruefmasse": d.pruefmasse or "", "bemerkungen": d.bemerkungen or ""},
		"checkliste": _checkliste(d),
		"checklisteTrotzdem": d.checkliste_trotzdem or "",
	}


def _serien_bestellung(d):
	"""Seriennummern, die in der Bestellung des Kunden zu dieser Position stehen (aus dem Bestell-PDF), sonst None."""
	if not (d.auftrag and d.auftragsposition_key):
		return None
	angaben = frappe.db.get_value("Auftragsposition", {"parent": d.auftrag, "position_key": d.auftragsposition_key}, "bestellangaben")
	return (als_json(angaben) or {}).get("serien") if angaben else None


def _bauteil(d):
	"""Hinweise für die Fertigung und Rohmaterial der letzten Fertigung vom Bauteil (einmal je Fertigungsbauteil)."""
	if getattr(d, "_cnc_bauteil", None) is None:
		werte = frappe.db.get_value("Bauteil", d.bauteil, ["fertigungshinweis", "roh_verbrauch"], as_dict=True) if d.bauteil else None
		d._cnc_bauteil = dict(werte or {})
	return d._cnc_bauteil


@frappe.whitelist(methods=["POST"])
def hinweis_setzen(id, text=""):
	"""Hinweise, die bei diesem Bauteil grundsätzlich zu beachten sind (stehen am Bauteil, gelten für jeden Auftrag)."""
	doc = _laden(id)
	if not doc.bauteil:
		frappe.throw(_("Zu diesem Fertigungsbauteil gibt es kein Bauteil in den Stammdaten."))
	frappe.db.set_value("Bauteil", doc.bauteil, "fertigungshinweis", (text or "").strip()[:2000])
	doc._cnc_bauteil = None
	return _antwort(doc)


def _verbrauch_bekannt(d, spez):
	"""Verbrauch je Stück aus der letzten Fertigung dieses Bauteils, wenn es dasselbe Rohmaterial war, sonst None."""
	v = als_json(_bauteil(d).get("roh_verbrauch")) if _bauteil(d).get("roh_verbrauch") else None
	if not v or not v.get("jeStueck"):
		return None
	alt = v.get("spez") or {}
	if alt.get("werkstoff") != spez.get("werkstoff") or alt.get("abmessungId") != spez.get("abmessungId"):
		return None
	return v


def _verbrauch_merken(doc, entnahmen):
	"""Nach einer Entnahme: Rohteil und tatsächlichen Verbrauch je Stück am Bauteil merken (für Wiederholaufträge)."""
	v = rohlager.verbrauch_fuer_bauteil(entnahmen)
	if not v or not doc.bauteil:
		return
	spez = {k: w for k, w in _spez(doc).items() if k != "verbrauchJeStueck"}
	frappe.db.set_value("Bauteil", doc.bauteil, "roh_verbrauch", frappe.as_json({**v, "spez": spez, "fb": doc.name, "auftrag": doc.auftrag or "", "am": iso(now_datetime())}), update_modified=False)
	doc._cnc_bauteil = None


# ----------------------------------------------------------------- Rohmaterial aus dem Lager
def _chargen():
	"""Vorrätige Chargen (einmal je Anfrage)."""
	if not hasattr(frappe.local, "cnc_chargen"):
		from cnc_one.api.werkstoff import charge_ui

		namen = frappe.get_all("Rohmaterialcharge", filters={"status": "Vorrätig"}, pluck="name", order_by="eingang asc, creation asc")
		frappe.local.cnc_chargen = [charge_ui(frappe.get_doc("Rohmaterialcharge", n)) for n in namen]
	return frappe.local.cnc_chargen


def _chargen_vergessen():
	"""Zwischenstände dieser Anfrage (Chargen, Material-Anfragen, Checkliste) verwerfen."""
	for k in ("cnc_chargen", "cnc_material_angefragt", "cnc_checkliste_vorlage"):
		if hasattr(frappe.local, k):
			delattr(frappe.local, k)


def _angefragt(d):
	"""Gibt es eine Material-Anfrage an Lieferanten zum Angebot dieses Auftrags (noch offen oder beantwortet)?"""
	if not hasattr(frappe.local, "cnc_material_angefragt"):
		frappe.local.cnc_material_angefragt = set(frappe.get_all("Lieferantenanfrage", filters={"art": "Material", "status": ["in", ["Gesendet", "Angebot erhalten"]], "angebot": ["is", "set"]}, pluck="angebot"))
	angebot = frappe.db.get_value("Auftrag", d.auftrag, "angebot") if d.auftrag else None
	return bool(angebot and angebot in frappe.local.cnc_material_angefragt)


MASS_FELDER = ("durchmesser", "innen", "schluesselweite", "hoehe", "breite")


def mass_ergaenzen(spez):
	"""Fehlen im Rohteil die Maße der Abmessung (ältere Stände), kommen sie aus den Stammdaten (wie rohAusAbmessung)."""
	if not spez.get("abmessungId") or any(spez.get(k) for k in ("durchmesser", "schluesselweite", "hoehe")):
		return spez
	a = frappe.db.get_value("Rohmaterial Abmessung", spez["abmessungId"], ["form", "mass1", "mass2", "bezeichnung"], as_dict=True)
	if not a:
		return spez
	m1, m2 = a.mass1 or 0, a.mass2 or 0
	s = {**spez, "form": spez.get("form") or a.form, "abmessung": spez.get("abmessung") or a.bezeichnung or ""}
	if a.form == "Rund":
		s["durchmesser"] = m1
	elif a.form == "Rohr":
		s.update({"durchmesser": m1, "innen": max(m1 - 2 * m2, 0)})
	elif a.form == "Sechskant":
		s["schluesselweite"] = m1
	elif a.form == "Vierkant":
		s.update({"breite": m1, "hoehe": m1})
	elif a.form == "Flach":
		s.update({"breite": m1, "hoehe": m2})
	elif a.form == "Platte":
		s["hoehe"] = m1
	return s


def _spez(d):
	"""Rohteil des Fertigungsbauteils; ältere Bauteile holen es einmal aus der Workbench-Kalkulation des Angebots."""
	if d.roh_spez:
		return mass_ergaenzen(als_json(d.roh_spez) or {})
	spez = {}
	if d.auftrag and d.auftragsposition_key and frappe.db.exists("Auftrag", d.auftrag):
		auf = frappe.get_doc("Auftrag", d.auftrag)
		pos = next((p for p in auf.positionen if p.position_key == d.auftragsposition_key), None)
		if pos:
			spez = spez_aus_teil(auftrag_api.teil_fuer_position(auf, pos), pos.material)
	if d.name and not d.is_new():
		frappe.db.set_value("Fertigungsbauteil", d.name, "roh_spez", frappe.as_json(spez), update_modified=False)
	d.roh_spez = frappe.as_json(spez)
	return spez


def spez_aus_teil(teil, material=""):
	"""Rohteil aus der Workbench (teil.roh) ohne Preise und Gewichte, dazu der Werkstoff."""
	roh = (teil or {}).get("roh") or {}
	felder = ("form", "abmessungId", "abmessung", "zustand", "ausfuehrung", "durchmesser", "innen", "schluesselweite", "hoehe", "laenge", "breite", "saege", "anforderungen", "zeugnis")
	spez = {k: roh[k] for k in felder if roh.get(k) not in (None, "")}
	werkstoff = (teil or {}).get("material") or material or ""
	if werkstoff:
		spez["werkstoff"] = werkstoff
	return spez


def _roh_ui(d):
	spez = _spez(d)
	entnahmen = als_json(d.roh_entnahmen) if d.roh_entnahmen else []
	bekannt = _verbrauch_bekannt(d, spez) if spez else None
	rechnen = {**spez, "verbrauchJeStueck": bekannt["jeStueck"]} if bekannt and bekannt.get("einheit") == ("mm²" if spez.get("form") == "Platte" else "mm") else spez
	st = rohlager.stand(rechnen, d.menge or 0, _chargen(), d.roh_charge or "", entnahmen, _angefragt(d) if spez else False)
	return {
		"spez": spez, "gewaehlt": d.roh_charge or "", "entnahmen": entnahmen, "ohneLager": d.roh_ohne_lager or "",
		"verbrauch": {k: bekannt.get(k) for k in ("jeStueck", "einheit", "fb", "auftrag", "am")} if bekannt else None,
		"status": st["status"], "text": st["text"], "teile": st["teile"],
		"passend": [
			{k: c.get(k) for k in ("id", "interneNr", "chargennr", "lieferant", "lieferantKurz", "rest", "bemerkung", "werkstoff", "ausfuehrung", "zeugnisDatei", "form", "laenge", "breite", "stueck", "zeugnis", "pruefungen", "lagerplatz", "eingang", "zustand", "abmessungText", "reicht", "jeEinheit", "ok", "fehlt")}
			for c in st["passend"]
		],
	}


@frappe.whitelist(methods=["POST"])
def roh_setzen(id, spez=None, charge=None):
	"""Rohteil in der Fertigung ändern (Auswahl wie in der Workbench) und/oder die Charge wählen, die genommen wird."""
	doc = _laden(id)
	if spez is not None:
		spez = frappe.parse_json(spez) if isinstance(spez, str) else spez
		sauber = spez_aus_teil({"roh": spez, "material": spez.get("werkstoff")})
		doc.roh_spez = frappe.as_json(sauber)
		doc.roh_werkstoff = sauber.get("werkstoff", "")
		from cnc_one.api.werkstoff import roh_angaben

		doc.roh_info = roh_angaben({"roh": sauber})[0]
	if charge is not None:
		if charge and not frappe.db.exists("Rohmaterialcharge", charge):
			frappe.throw(_("Diese Charge gibt es nicht."))
		doc.roh_charge = charge or ""
		doc.roh_lagerplatz = frappe.db.get_value("Rohmaterialcharge", charge, "lagerplatz") or "" if charge else ""
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def material_entnehmen(id, charge, stueck, rest_laenge=0, rest_breite=0, menge=0, notiz=""):
	"""Material aus dem Lager nehmen: `stueck` Stangen/Platten der Charge, ein Reststück geht als eigener Lagerposten
	(gleiche Chargennummer, Zeugnis, Lagerplatz) zurück. Am Fertigungsbauteil steht danach, was genau verwendet wurde."""
	doc = _laden(id)
	c = frappe.get_doc("Rohmaterialcharge", charge)
	if c.status != "Vorrätig":
		frappe.throw(_("Die Charge {0} ist aufgebraucht.").format(c.name))
	menge = frappe.utils.cint(menge) or doc.menge or 0
	try:
		r = rohlager.entnahme_rechnen({"form": c.form, "laenge": c.laenge, "breite": c.breite, "stueck": c.stueck}, stueck, rest_laenge, rest_breite, menge)
	except ValueError as e:
		frappe.throw(str(e))
	stueck = frappe.utils.cint(stueck)
	rest_l, rest_b = frappe.utils.flt(rest_laenge), frappe.utils.flt(rest_breite)
	c.stueck = (c.stueck or 0) - stueck
	if c.stueck <= 0:
		c.stueck = 0
		c.status = "Aufgebraucht"
	c.save(ignore_permissions=True)
	rest_id = ""
	if rest_l > 0:
		rest = frappe.copy_doc(c)
		rest.update({"stueck": 1, "laenge": rest_l, "breite": rest_b if c.form == "Platte" else c.breite, "status": "Vorrätig",
			"bemerkung": _("Reststück aus {0} ({1})").format(c.name, doc.name)})
		rest.insert(ignore_permissions=True)
		rest_id = rest.name
	entnahmen = als_json(doc.roh_entnahmen) if doc.roh_entnahmen else []
	entnahmen.append({
		"id": frappe.generate_hash(length=8), "charge": c.name, "interneNr": c.interne_nr or "", "chargennr": c.chargennr or "", "lieferant": c.lieferant or "", "zeugnis": c.zeugnis or "",
		"form": c.form, "abmessung": c.abmessung_text or "", "stueck": stueck, "laenge": c.laenge or 0, "breite": c.breite or 0,
		"restLaenge": rest_l, "restBreite": rest_b, "restCharge": rest_id, "menge": menge, **r,
		"notiz": (notiz or "").strip()[:200], "von": frappe.utils.get_fullname(frappe.session.user), "am": iso(now_datetime()),
	})
	doc.roh_entnahmen = frappe.as_json(entnahmen)
	doc.roh_charge = c.name
	doc.roh_lagerplatz = c.lagerplatz or ""
	doc.roh_verbraucht_mm = sum(frappe.utils.flt(e.get("verbraucht")) for e in entnahmen if e.get("einheit") == "mm")
	doc.save()
	_verbrauch_merken(doc, entnahmen)
	_chargen_vergessen()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def entnahme_zurueck(id, entnahme):
	"""Entnahme rückgängig (falsche Charge gebucht): Stangen/Platten zurück in die Charge, ein unbenutztes Reststück weg."""
	doc = _laden(id)
	entnahmen = als_json(doc.roh_entnahmen) if doc.roh_entnahmen else []
	e = next((x for x in entnahmen if x.get("id") == entnahme), None)
	if not e:
		frappe.throw(_("Diese Entnahme gibt es nicht."))
	if e.get("restCharge") and frappe.db.exists("Rohmaterialcharge", e["restCharge"]):
		rest = frappe.get_doc("Rohmaterialcharge", e["restCharge"])
		if rest.status != "Vorrätig" or (rest.stueck or 0) < 1:
			frappe.throw(_("Das Reststück {0} wurde schon verwendet, die Entnahme lässt sich nicht zurücknehmen.").format(rest.name))
		frappe.delete_doc("Rohmaterialcharge", rest.name, ignore_permissions=True)
	c = frappe.get_doc("Rohmaterialcharge", e["charge"])
	c.stueck = (c.stueck or 0) + int(e.get("stueck") or 0)
	c.status = "Vorrätig"
	c.save(ignore_permissions=True)
	entnahmen = [x for x in entnahmen if x.get("id") != entnahme]
	doc.roh_entnahmen = frappe.as_json(entnahmen)
	doc.roh_verbraucht_mm = sum(frappe.utils.flt(x.get("verbraucht")) for x in entnahmen if x.get("einheit") == "mm")
	doc.save()
	_verbrauch_merken(doc, entnahmen)
	_chargen_vergessen()
	return _antwort(doc)


def _material_pruefen(doc, vorher_status, ohne_material):
	"""Fertig gemeldet (Status oder letzte Buchung): spätestens jetzt muss feststehen, welches Material verwendet wurde."""
	if doc.status != "Fertig" or vorher_status == "Fertig":
		return
	spez = _spez(doc)
	if not rohlager.spez_vollstaendig(spez) or (als_json(doc.roh_entnahmen) if doc.roh_entnahmen else []):
		return
	grund = (ohne_material or "").strip() if isinstance(ohne_material, str) else ""
	if not grund:
		frappe.throw(_("Bitte vor dem Fertigmelden angeben, welches Material verwendet wurde (Entnahme aus dem Lager)."), title=_("Material fehlt"))
	doc.roh_ohne_lager = _("{0} ({1}, {2})").format(grund, frappe.utils.get_fullname(frappe.session.user), now_datetime().strftime("%d.%m.%Y"))[:140]


# ----------------------------------------------------------------- Checkliste vor dem Start
def checkliste_vorlage():
	"""Die festen Punkte aus den Fertigung-Einstellungen, sonst der Standard (Material, Werkzeug, Messmittel …)."""
	if not frappe.db.exists("DocType", "Fertigung Einstellungen"):
		return check.vorlage_bereinigt(check.STANDARD)
	gespeichert = frappe.db.get_single_value("Fertigung Einstellungen", "checkliste")
	punkte = als_json(gespeichert) if gespeichert else None
	return check.vorlage_bereinigt(punkte if isinstance(punkte, list) else check.STANDARD)


def _checkliste(d):
	if not hasattr(frappe.local, "cnc_checkliste_vorlage"):
		frappe.local.cnc_checkliste_vorlage = checkliste_vorlage()
	return check.zusammenfuehren(frappe.local.cnc_checkliste_vorlage, als_json(d.checkliste) if d.checkliste else [])


def _checkliste_speichern(doc, liste):
	doc.checkliste = frappe.as_json(check.gespeichert(liste))


@frappe.whitelist(methods=["POST"])
def vorlage_checkliste():
	nur_cnc()
	darf = bool(set(frappe.get_roles()) & {"CNC Admin", "CNC Fertigung", "System Manager"})
	return {"punkte": checkliste_vorlage(), "standard": check.vorlage_bereinigt(check.STANDARD), "darf": darf}


@frappe.whitelist(methods=["POST"])
def vorlage_checkliste_speichern(punkte):
	"""Feste Punkte der Checkliste ändern (Text, Hinweis, Pflicht vor dem Start, aktiv, Reihenfolge)."""
	frappe.only_for(("CNC Admin", "CNC Fertigung", "System Manager"))
	if isinstance(punkte, str):
		punkte = frappe.parse_json(punkte)
	sauber = check.vorlage_bereinigt(punkte)
	frappe.db.set_single_value("Fertigung Einstellungen", "checkliste", frappe.as_json(sauber))
	if hasattr(frappe.local, "cnc_checkliste_vorlage"):
		del frappe.local.cnc_checkliste_vorlage
	return {"punkte": sauber}


@frappe.whitelist(methods=["POST"])
def check_setzen(id, punkt, erledigt=None, notiz=None):
	"""Einen Punkt der Checkliste abhaken (mit Name und Zeit) oder wieder öffnen, oder die Notiz dazu ändern."""
	doc = _laden(id)
	liste = _checkliste(doc)
	p = next((x for x in liste if x["id"] == punkt), None)
	if not p:
		frappe.throw(_("Diesen Punkt gibt es in der Checkliste nicht."))
	if erledigt is not None:
		p["erledigt"] = bool(frappe.utils.cint(erledigt))
		p["von"] = frappe.utils.get_fullname(frappe.session.user) if p["erledigt"] else ""
		p["am"] = iso(now_datetime()) if p["erledigt"] else ""
	if notiz is not None:
		p["notiz"] = str(notiz)[:300]
	_checkliste_speichern(doc, liste)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def check_eigen(id, text, pflicht=0):
	"""Eigener Punkt nur für dieses Bauteil (z. B. Sonderwerkzeug, Prüfvorrichtung vom Kunden)."""
	doc = _laden(id)
	text = (text or "").strip()[:80]
	if not text:
		frappe.throw(_("Bitte einen Text für den Punkt eingeben."))
	liste = _checkliste(doc)
	liste.append({"id": f"e-{frappe.generate_hash(length=6)}", "text": text, "pflicht": bool(frappe.utils.cint(pflicht)), "eigen": True, "erledigt": False, "von": "", "am": "", "notiz": ""})
	_checkliste_speichern(doc, liste)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def check_weg(id, punkt):
	"""Eigenen Punkt entfernen (feste Punkte bleiben, sie werden in den Einstellungen abgeschaltet)."""
	doc = _laden(id)
	liste = [p for p in _checkliste(doc) if not (p["id"] == punkt and p["eigen"])]
	_checkliste_speichern(doc, liste)
	doc.save()
	return _antwort(doc)


def _start_pruefen(doc, trotzdem):
	"""Vor dem Start (Offen → In Fertigung, auch durch die erste Buchung) müssen die Pflichtpunkte abgehakt sein. Mit
	`trotzdem` geht es dennoch, das wird am Bauteil vermerkt."""
	if doc.status != "Offen":
		return
	fehlt = check.offen(_checkliste(doc))
	if not fehlt:
		return
	if not frappe.utils.cint(trotzdem):
		frappe.throw(_("Checkliste vor dem Start: noch offen sind {0}.").format(", ".join(p["text"] for p in fehlt)), title=_("Checkliste unvollständig"))
	doc.checkliste_trotzdem = _("{0} am {1}, offen: {2}").format(
		frappe.utils.get_fullname(frappe.session.user), now_datetime().strftime("%d.%m.%Y %H:%M"), ", ".join(p["text"] for p in fehlt))[:140]


def alle_ui():
	_chargen_vergessen()
	namen = frappe.get_list("Fertigungsbauteil", pluck="name", order_by="creation asc", limit_page_length=0)
	return [fb_ui(frappe.get_doc("Fertigungsbauteil", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


def _antwort(doc):
	"""Antwort jeder Änderung: das Fertigungsbauteil und der (evtl. geänderte) Status seines Auftrags."""
	return {"fb": fb_ui(doc), "auftragStatus": frappe.db.get_value("Auftrag", doc.auftrag, "status") if doc.auftrag else None}


def _laden(id):
	_nur_fertigung()
	_chargen_vergessen()
	doc = frappe.get_doc("Fertigungsbauteil", id)
	doc.check_permission("write")
	return doc


# ----------------------------------------------------------------- Starten
def fb_anlegen(auf, pos):
	"""Fertigungsbauteil zu einer Auftragsposition (auch für eine Position, die eine Auftragsänderung später dazunimmt).
	Liefert, ob es einen Arbeitsplan gab."""
	plan = auftrag_api.plan_fuer_position(auf, pos)
	teil = auftrag_api.teil_fuer_position(auf, pos)
	roh_info, roh_charge, roh_platz = roh_angaben(teil)
	spez = spez_aus_teil(teil, pos.material)
	if not rohlager.spez_vollstaendig(spez) and pos.bauteil:
		# Wiederholauftrag ohne Kalkulation: Rohteil der letzten Fertigung dieses Bauteils
		alt = als_json(frappe.db.get_value("Bauteil", pos.bauteil, "roh_verbrauch") or "") or {}
		if rohlager.spez_vollstaendig(alt.get("spez")):
			spez = alt["spez"]
			roh_info = roh_angaben({"roh": spez})[0]
	fb = frappe.new_doc("Fertigungsbauteil")
	fb.update({
		"auftrag": auf.name, "auftragsposition_key": pos.position_key, "bauteil": pos.bauteil or None,
		"kunde": auf.kunde, "kunde_name": auf.kunde_name, "teilenummer": pos.teilenummer,
		"bezeichnung": pos.bezeichnung, "zeichnungsnr": pos.zeichnungsnr, "revision": pos.revision or "", "material": pos.material,
		"menge": pos.menge, "termin": pos.liefertermin, "prioritaet": "Normal", "status": "Offen",
		"roh_werkstoff": pos.material or "", "roh_info": roh_info, "roh_charge": roh_charge, "roh_lagerplatz": roh_platz,
		"roh_spez": frappe.as_json(spez),
		"serien_von": pos.serien_von or None, "serien_bis": pos.serien_bis or None, "serien_stellen": pos.serien_stellen or 4,
	})
	# Hinweise je Arbeitsgang gehören zum Bauteil: fehlen sie im Plan (z. B. aus einem älteren Angebot), vom Bauteil
	am_bauteil = {}
	if pos.bauteil:
		am_bauteil = {(r.bezeichnung or "").strip().lower(): r.hinweis for r in frappe.get_doc("Bauteil", pos.bauteil).arbeitsplan if r.get("hinweis")}
	for a in plan:
		if not a.get("hinweis"):
			a = {**a, "hinweis": am_bauteil.get((a.get("name") or "").strip().lower(), "")}
		zeile = arbeitsgang_zeile({**a, "id": None})
		fb.append("arbeitsgaenge", {**zeile, "status": "Offen", "gebucht": 0})
	fb.insert(ignore_permissions=True)
	return bool(plan)


@frappe.whitelist(methods=["POST"])
def starten(auftrag):
	"""Legt je Auftragsposition ein Fertigungsbauteil an. Der Arbeitsplan darf fehlen und kommt dann später in der Fertigung."""
	_nur_fertigung()
	_chargen_vergessen()
	auf = frappe.get_doc("Auftrag", auftrag)
	if frappe.db.exists("Fertigungsbauteil", {"auftrag": auftrag}):
		frappe.throw(_("Für diesen Auftrag läuft die Fertigung schon."))
	ohne_plan = 0
	for pos in auf.positionen:
		if pos.entfallen:
			continue
		if not fb_anlegen(auf, pos):
			ohne_plan += 1
	return {
		"auftrag": auftrag_api.auftrag_ui(frappe.get_doc("Auftrag", auftrag)),
		"fertigung": [fb_ui(frappe.get_doc("Fertigungsbauteil", n)) for n in frappe.get_all("Fertigungsbauteil", filters={"auftrag": auftrag}, pluck="name", order_by="creation asc")],
		"ohnePlan": ohne_plan,
	}


# ----------------------------------------------------------------- Ist-Zeiten
def _zeiten_setzen(doc, zeiten):
	"""Ist-Zeiten aus der Oberfläche: [{ agId, ruestMin, bearbMin, maschine }]. Wer und wann wird mitgeschrieben."""
	if isinstance(zeiten, str):
		zeiten = frappe.parse_json(zeiten)
	for z in zeiten or []:
		ag = doc.arbeitsgang(z.get("agId"))
		if ag.typ == "Fremd":
			continue
		ruest, bearb = float(z.get("ruestMin") or 0), float(z.get("bearbMin") or 0)
		if ruest < 0 or bearb < 0:
			frappe.throw(_("Zeiten können nicht negativ sein."))
		ag.ist_ruest_min = ruest
		ag.ist_bearb_min = bearb
		if z.get("maschine"):
			ag.maschine = z.get("maschine")
		ag.ist_von = frappe.session.user
		ag.ist_am = now_datetime()


def _zeiten_pruefen(doc, vorher_fertig):
	"""Interne Arbeitsgänge, die mit dieser Änderung fertig werden, brauchen gemeldete Zeiten."""
	fehlen = [a.bezeichnung or "Arbeitsgang" for a in doc.arbeitsgaenge if a.typ != "Fremd" and a.status == "Fertig" and a.ag_id not in vorher_fertig and not a.ist_am]
	if fehlen:
		frappe.throw(_("Bitte beim Abschließen die Zeiten eintragen: {0}").format(", ".join(fehlen)))


def _fertige(doc):
	return {a.ag_id for a in doc.arbeitsgaenge if a.status == "Fertig"}


@frappe.whitelist(methods=["POST"])
def zeiten_melden(id, zeiten):
	"""Ist-Zeiten (nach-)tragen oder korrigieren."""
	doc = _laden(id)
	_zeiten_setzen(doc, zeiten)
	doc.save()
	return _antwort(doc)


# ----------------------------------------------------------------- Buchen
@frappe.whitelist(methods=["POST"])
def buchen(id, ag_id, menge, zeiten=None, trotzdem=0, ohne_material=""):
	doc = _laden(id)
	_start_pruefen(doc, trotzdem)
	status_vorher = doc.status
	vorher = _fertige(doc)
	_zeiten_setzen(doc, zeiten)
	nachgeholt = doc.buchen(ag_id, menge)
	_zeiten_pruefen(doc, vorher)
	_material_pruefen(doc, status_vorher, ohne_material)
	doc.save()
	return {**_antwort(doc), "nachgeholt": nachgeholt, "ueberproduktion": doc.ueberproduktion}


@frappe.whitelist(methods=["POST"])
def buchung_loeschen(id, buchung):
	doc = _laden(id)
	doc.buchung_loeschen(buchung)
	doc.save()
	return _antwort(doc)


# ----------------------------------------------------------------- Arbeitsplan
@frappe.whitelist(methods=["POST"])
def arbeitsgang_hinzu(id, typ="intern", name=""):
	"""Neuer Arbeitsgang einer Arbeitsgangart; ohne Angabe von intern/extern gilt der Standard der Art."""
	doc = _laden(id)
	if name and not frappe.db.exists("Arbeitsgangart", {"bezeichnung": name}):
		frappe.throw(_("Die Arbeitsgangart {0} gibt es nicht.").format(name))
	if name and not typ:
		typ = typ_ui(frappe.db.get_value("Arbeitsgangart", {"bezeichnung": name}, "typ"))
	doc.arbeitsgaenge_hinzu([arbeitsgang_zeile({"typ": typ or "intern", "name": name})])
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def vorlage_anwenden(id, vorlage):
	doc = _laden(id)
	v = frappe.get_doc("Arbeitsplan Vorlage", vorlage)
	zeilen = [arbeitsgang_zeile({**arbeitsgang_ui(r), "id": None}) for r in v.arbeitsgaenge]
	doc.arbeitsgaenge_hinzu(zeilen)
	doc.save()
	return {**_antwort(doc), "hinzugefuegt": len(zeilen)}


@frappe.whitelist(methods=["POST"])
def arbeitsgang_weg(id, ag_id):
	doc = _laden(id)
	doc.arbeitsgang_weg(ag_id)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def arbeitsgang_verschieben(id, ag_id, richtung):
	doc = _laden(id)
	doc.arbeitsgang_verschieben(ag_id, richtung)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def plan_am_bauteil_speichern(id):
	"""Speichert die Arbeitsgänge dieses Fertigungsbauteils als Arbeitsplan am Bauteil (gilt für künftige Angebote und Aufträge)."""
	doc = _laden(id)
	plan = [arbeitsgang_ui(a) for a in doc.arbeitsgaenge]
	b = bauteil_api.plan_setzen(doc.kunde, doc.teilenummer, plan, doc.bezeichnung, doc.zeichnungsnr, doc.material)
	if not b:
		frappe.throw(_("Dafür braucht das Bauteil einen Kunden und eine Teilenummer."))
	return {"bauteil": bauteil_api.bauteil_ui(b)}


# ----------------------------------------------------------------- Sendungen
@frappe.whitelist(methods=["POST"])
def sendung_anlegen(id, ag_id, menge=None):
	doc = _laden(id)
	doc.sendung_anlegen(ag_id, menge)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def sendung_weg(id, ag_id, sendung):
	doc = _laden(id)
	doc.sendung_weg(ag_id, sendung)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def sendung_zurueck(id, ag_id, sendung):
	doc = _laden(id)
	doc.sendung_zurueck(ag_id, sendung)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def sendung_loeschen(id, ag_id, sendung):
	doc = _laden(id)
	doc.sendung_loeschen(ag_id, sendung)
	doc.save()
	return _antwort(doc)


# ----------------------------------------------------------------- Status und Felder
@frappe.whitelist(methods=["POST"])
def status_setzen(id, status, zeiten=None, trotzdem=0, ohne_material=""):
	doc = _laden(id)
	if status != "Offen":
		_start_pruefen(doc, trotzdem)
	status_vorher = doc.status
	vorher = _fertige(doc)
	_zeiten_setzen(doc, zeiten)
	doc.status_setzen(status)
	_zeiten_pruefen(doc, vorher)
	_material_pruefen(doc, status_vorher, ohne_material)
	doc.save()
	return _antwort(doc)


@frappe.whitelist(methods=["POST"])
def felder_speichern(id, felder):
	"""Speichert die frei bearbeitbaren Felder. Buchungsstand, Status und Sendungen ändert das nicht.

	`felder`: { prioritaet, termin, rohmaterial: {...}, notizen: {...}, arbeitsgaenge: [{ id, name, typ, geplantAm, maschine, ruestMin, stueckMin, lieferant, bestellung }] }
	Preise (satz, fremdProStk, fremdEinmal) werden nur übernommen, wenn sie mitkommen; die Oberfläche der Fertigung schickt keine.
	"""
	doc = _laden(id)
	if isinstance(felder, str):
		felder = frappe.parse_json(felder)
	if "prioritaet" in felder:
		doc.prioritaet = felder["prioritaet"]
	if "termin" in felder:
		doc.termin = felder["termin"] or None
	roh = felder.get("rohmaterial")
	if roh:
		doc.roh_werkstoff = roh.get("werkstoff", doc.roh_werkstoff)
		doc.roh_charge = roh.get("charge", doc.roh_charge)
		doc.roh_lagerplatz = roh.get("lagerplatz", doc.roh_lagerplatz)
		doc.roh_info = roh.get("info", doc.roh_info)
		doc.roh_verbraucht_mm = roh.get("verbrauchtMm", doc.roh_verbraucht_mm) or 0
	notizen = felder.get("notizen")
	if notizen:
		doc.pruefmasse = notizen.get("pruefmasse", doc.pruefmasse)
		doc.bemerkungen = notizen.get("bemerkungen", doc.bemerkungen)
	serienarten = serienart_namen()
	hinweise = {}
	for neu in felder.get("arbeitsgaenge") or []:
		ag = next((a for a in doc.arbeitsgaenge if a.ag_id == neu.get("id")), None)
		if not ag:
			continue
		ag.bezeichnung = (neu.get("name") or "").strip()
		if "typ" in neu and typ_db(neu.get("typ")) != ag.typ:
			if (ag.gebucht or 0) or doc.sendungen_von(ag.ag_id):
				frappe.throw(_("{0}: Intern/extern lässt sich nach Buchungen oder Sendungen nicht mehr ändern.").format(ag.bezeichnung or "Arbeitsgang"))
			ag.typ = typ_db(neu.get("typ"))
		if "geplantAm" in neu:
			ag.geplant_am = neu.get("geplantAm") or None
		ag.maschine = neu.get("maschine") or None
		# Preise kommen aus der Fertigung nicht mit; sie bleiben, wie sie aus dem Auftrag übernommen wurden
		if "satz" in neu:
			ag.satz = neu.get("satz") or 0
		ag.ruest_min = neu.get("ruestMin") or 0
		ag.stueck_min = neu.get("stueckMin") or 0
		for ui, feld in (("ruestDirekt", "ruest_direkt"), ("stueckDirekt", "stueck_direkt")):
			if ui in neu:
				ag.set(feld, 1 if neu.get(ui) else 0)
		for ui, feld in (("ruestEuro", "ruest_euro"), ("stueckEuro", "stueck_euro")):
			if ui in neu:
				ag.set(feld, neu.get(ui) or 0)
		ag.lieferant = neu.get("lieferant") or None
		if "fremdProStk" in neu:
			ag.fremd_pro_stk = neu.get("fremdProStk") or 0
		if "fremdEinmal" in neu:
			ag.fremd_einmal = neu.get("fremdEinmal") or 0
		ag.bestellung = neu.get("bestellung") or ""
		ag.serie = 1 if ist_serienart(ag.bezeichnung, serienarten) else 0
		if "hinweis" in neu:
			text = str(neu.get("hinweis") or "").strip()[:1000]
			if text != (ag.hinweis or ""):
				hinweise[(ag.bezeichnung or "").strip().lower()] = text
			ag.hinweis = text
	doc.save()
	_hinweise_ans_bauteil(doc, hinweise)
	return _antwort(doc)


def _hinweise_ans_bauteil(doc, hinweise):
	"""Geänderte Hinweise je Arbeitsgang gelten für das Bauteil: in dessen Arbeitsplan beim gleichnamigen Arbeitsgang
	übernehmen (künftige Aufträge). Steht der Arbeitsgang dort nicht, bleibt es bei „Am Bauteil speichern“."""
	if not hinweise or not doc.bauteil:
		return
	b = frappe.get_doc("Bauteil", doc.bauteil)
	geaendert = False
	for r in b.arbeitsplan:
		k = (r.bezeichnung or "").strip().lower()
		if k in hinweise and (r.hinweis or "") != hinweise[k]:
			r.hinweis = hinweise[k]
			geaendert = True
	if geaendert:
		b.save(ignore_permissions=True)
