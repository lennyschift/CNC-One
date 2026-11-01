"""Bauteile (Stammdaten) und ihr Arbeitsplan."""

import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from cnc_one.api.stamm import arbeitsgang_ui, arbeitsgang_zeile, nur_cnc


def bauteil_ui(d):
	return {
		"id": d.name,
		"kundeId": d.kunde,
		"teilenummer": d.teilenummer,
		"name": d.bezeichnung or "",
		"zeichnungsnr": d.zeichnungsnr or "",
		"revision": d.revision or "",
		"material": d.material or "",
		"arbeitsgaenge": [arbeitsgang_ui(r) for r in d.arbeitsplan],
		"seriennummern": bool(d.seriennummern),
		"serienStellen": d.serien_stellen or 4,
		"letzteSeriennummer": d.letzte_seriennummer or 0,
		"vorschaubild": d.vorschaubild or "",
		"stepDatei": d.step_datei or "",
		"zeichnung": d.zeichnung or "",
		"revisionen": revisionen_ui(d),
	}


def revisionen_ui(d):
	"""Revisionen mit ihren Dateien, neueste zuerst. Ältere Fassungen derselben Revision sind gekennzeichnet."""
	gesehen = set()
	out = []
	for z in reversed(d.get("revisionen") or []):
		schluessel = _rev(z.revision)
		out.append({
			"revision": z.revision or "", "zeichnung": z.zeichnung or "", "stepDatei": z.step_datei or "",
			"vorschaubild": z.vorschaubild or "", "angebot": z.angebot or "", "datum": str(z.datum or ""),
			"aktuell": schluessel == _rev(d.revision) and schluessel not in gesehen, "aeltereFassung": schluessel in gesehen,
		})
		gesehen.add(schluessel)
	return out


def vorschau(name):
	"""Vorschaubild eines Bauteils (url) oder leer."""
	return (frappe.db.get_value("Bauteil", name, "vorschaubild") or "") if name else ""


def dateien_fuer(name, revision=""):
	"""Zeichnung, Modell und Bild eines Bauteils in einer bestimmten Revision (z. B. der bestellten), sonst der aktuellen.
	Liefert { revision, zeichnung, stepDatei, vorschaubild, aktuelleRevision }."""
	if not name:
		return {"revision": revision or "", "zeichnung": "", "stepDatei": "", "vorschaubild": "", "aktuelleRevision": ""}
	b = frappe.db.get_value("Bauteil", name, ["revision", "zeichnung", "step_datei", "vorschaubild"], as_dict=True) or frappe._dict()
	quelle = b
	if revision and _rev(revision) != _rev(b.revision):
		zeilen = frappe.get_all("Bauteil Revision", filters={"parent": name, "parenttype": "Bauteil"}, fields=["revision", "zeichnung", "step_datei", "vorschaubild"], order_by="idx desc")
		quelle = next((z for z in zeilen if _rev(z.revision) == _rev(revision)), b)
	return {
		"revision": revision or b.revision or "", "zeichnung": quelle.zeichnung or "", "stepDatei": quelle.step_datei or "",
		"vorschaubild": quelle.vorschaubild or b.vorschaubild or "", "aktuelleRevision": b.revision or "",
	}


def alle_ui():
	namen = frappe.get_list("Bauteil", pluck="name", order_by="creation asc", limit_page_length=0)
	return [bauteil_ui(frappe.get_doc("Bauteil", n)) for n in namen]


def finden(kunde, teilenummer):
	"""Name des Bauteils eines Kunden zu einer Teilenummer, ohne Rücksicht auf Groß- und Kleinschreibung."""
	t = (teilenummer or "").strip().lower()
	if not kunde or not t:
		return None
	r = frappe.db.sql("select name from `tabBauteil` where kunde = %s and lower(teilenummer) = %s", (kunde, t))
	return r[0][0] if r else None


def sicherstellen(kunde, teilenummer, name="", zeichnungsnr="", material=""):
	"""Legt das Bauteil an, wenn es fehlt, und füllt leere Angaben auf. Liefert das Dokument oder None."""
	n = finden(kunde, teilenummer)
	if not kunde or not (teilenummer or "").strip():
		return None
	if n:
		doc = frappe.get_doc("Bauteil", n)
		geaendert = False
		for feld, wert in (("bezeichnung", name), ("zeichnungsnr", zeichnungsnr)):
			if wert and not doc.get(feld):
				doc.set(feld, wert)
				geaendert = True
		if material and not doc.material and frappe.db.exists("Material", material):
			doc.material = material
			geaendert = True
		if geaendert:
			doc.save()
		return doc
	doc = frappe.new_doc("Bauteil")
	doc.kunde = kunde
	doc.teilenummer = teilenummer.strip()
	doc.bezeichnung = name or ""
	doc.zeichnungsnr = zeichnungsnr or ""
	doc.material = material if material and frappe.db.exists("Material", material) else None
	doc.insert()
	return doc


def _material(name):
	return name if name and frappe.db.exists("Material", name) else None


def _angaben_setzen(doc, teil):
	"""Bezeichnung, Zeichnung, Werkstoff und Seriennummern-Kennzeichen aus der Workbench ins Bauteil übernehmen.
	Revision und Dateien kommen über `revision_uebernehmen`, nachdem das Angebot gespeichert ist."""
	doc.bezeichnung = (teil.get("name") or "").strip()
	doc.zeichnungsnr = (teil.get("zeichnungsnr") or "").strip()
	doc.material = _material(teil.get("material"))
	doc.seriennummern = 1 if teil.get("seriennummern") else 0


DATEIFELDER = ("zeichnung", "step_datei", "vorschaubild")


def dateien_aus_teil(teil):
	"""STEP-Modell, Zeichnung und Vorschaubild eines Workbench-Bauteils (hochgeladene Dateien): { feld: url }.
	Liegen mehrere Zeichnungen oder Modelle vor, gilt die zuletzt hinzugefügte."""
	neueste = {}
	for d in teil.get("dateien") or []:
		url = d.get("url") or ""
		if url and d.get("art") in ("STEP", "Zeichnung"):
			neueste["step_datei" if d["art"] == "STEP" else "zeichnung"] = url
	if teil.get("vorschaubild"):
		neueste["vorschaubild"] = teil["vorschaubild"]
	return neueste


def _rev(wert):
	return (wert or "").strip().lower()


def _an_bauteil_haengen(url, bauteil, feld):
	"""Die Datei gehört ab jetzt zum Bauteil (statt zum Angebot oder zu niemandem). So bleibt sie erhalten, wenn das Angebot
	gelöscht wird, alle mit Leserecht am Bauteil sehen sie, und Frappe legt beim Speichern keine Kopie an."""
	name = frappe.db.get_value("File", {"file_url": url, "attached_to_doctype": "Angebot"}, "name") or frappe.db.get_value(
		"File", {"file_url": url, "attached_to_doctype": ["is", "not set"]}, "name"
	)
	if name:
		frappe.db.set_value("File", name, {"attached_to_doctype": "Bauteil", "attached_to_name": bauteil, "attached_to_field": feld}, update_modified=False)


def revision_verwendet(bauteil, revision, ausser_angebot=None):
	"""Wird diese Revision des Bauteils in Aufträgen, der Fertigung oder (anderen) Angeboten gebraucht?"""
	r = _rev(revision)
	for dt in ("Auftragsposition", "Fertigungsbauteil"):
		if any(_rev(x) == r for x in frappe.get_all(dt, filters={"bauteil": bauteil}, pluck="revision")):
			return True
	return any(p.parent != ausser_angebot and _rev(p.revision) == r for p in frappe.get_all("Angebotsposition", filters={"bauteil": bauteil}, fields=["parent", "revision"]))


def revision_uebernehmen(bauteil, teil, angebot):
	"""Legt Revision und Dateien eines Workbench-Bauteils am Bauteil ab und liefert die Revision der Position.

	- Neue Revision: neue Zeile, sie ist ab jetzt die aktuelle. Ältere Revisionen bleiben mit ihren Dateien erhalten.
	- Bekannte Revision mit anderer Datei: neue Zeile darunter (die neuere Datei gilt, die ältere bleibt sichtbar).
	- Hat dieses Angebot die Zeile selbst angelegt und braucht sie sonst niemand, wird sie angepasst statt eine weitere
	  anzulegen (Tippen in der Workbench, Datei getauscht). Zeilen dieses Angebots, die niemand mehr braucht, fallen weg.
	"""
	doc = frappe.get_doc("Bauteil", bauteil)
	rev = (teil.get("revision") or "").strip() or (doc.revision or "")
	dateien = dateien_aus_teil(teil)
	vorher = [(z.revision, *(z.get(f) for f in DATEIFELDER), z.angebot) for z in doc.revisionen] + [doc.revision, *(doc.get(f) for f in DATEIFELDER)]

	# Zeilen dieses Angebots aus früherem Speichern, die keine Position mehr braucht (z. B. vertippte Revision)
	weg = [z for z in doc.revisionen if z.angebot == angebot and _rev(z.revision) != _rev(rev) and not revision_verwendet(bauteil, z.revision)]
	for z in weg:
		doc.remove(z)

	z = next((x for x in reversed(doc.revisionen) if _rev(x.revision) == _rev(rev)), None)
	gewuenscht = {f: (z.get(f) if z else "") or "" for f in DATEIFELDER}
	gewuenscht.update(dateien)
	if z is None:
		if rev or dateien:
			doc.append("revisionen", {"revision": rev, **gewuenscht, "angebot": angebot, "datum": now_datetime()})
			doc.revision = rev
	elif any((z.get(f) or "") != gewuenscht[f] for f in DATEIFELDER):
		if z.angebot == angebot and not revision_verwendet(bauteil, rev, ausser_angebot=angebot):
			z.update(gewuenscht)
		else:
			doc.append("revisionen", {"revision": rev, **gewuenscht, "angebot": angebot, "datum": now_datetime()})
	if weg and not any(_rev(x.revision) == _rev(doc.revision) for x in doc.revisionen):
		doc.revision = doc.revisionen[-1].revision if doc.revisionen else ""

	# Die Felder am Bauteil zeigen immer die neueste Fassung der aktuellen Revision
	aktuell = next((x for x in reversed(doc.revisionen) if _rev(x.revision) == _rev(doc.revision)), None)
	if aktuell:
		for f in DATEIFELDER:
			doc.set(f, aktuell.get(f) or "")
	nachher = [(x.revision, *(x.get(f) for f in DATEIFELDER), x.angebot) for x in doc.revisionen] + [doc.revision, *(doc.get(f) for f in DATEIFELDER)]
	if nachher != vorher:
		for x in doc.revisionen:
			for f in DATEIFELDER:
				if x.get(f):
					_an_bauteil_haengen(x.get(f), bauteil, f)
		doc.save()
	return rev


def revision_setzen(doc, revision):
	"""Revision in den Stammdaten von Hand ändern: eine vorhandene Revision wird wieder die aktuelle, eine neue bekommt eine
	eigene Zeile (ohne Dateien, die kommen mit der nächsten Zeichnung)."""
	rev = (revision or "").strip()
	if _rev(rev) == _rev(doc.revision) or not rev:
		doc.revision = rev
		return
	z = next((x for x in reversed(doc.get("revisionen") or []) if _rev(x.revision) == _rev(rev)), None)
	if z is None and rev:
		z = doc.append("revisionen", {"revision": rev, "datum": now_datetime()})
	doc.revision = rev
	for f in DATEIFELDER:
		doc.set(f, (z.get(f) if z else "") or "")


def fuer_position(kunde, teil, alt=None):
	"""Das Bauteil zu einem Workbench-Bauteil: wiederfinden oder neu anlegen, nie doppelt.

	`alt` ist (Bauteil, neu) dieser Position aus dem letzten Speichern. Ein Bauteil, das dieses Angebot neu angelegt hat,
	folgt den Änderungen in der Workbench (auch einer geänderten Teilenummer). Bei einem Bestandsbauteil bleiben die Angaben
	unverändert, nur Revision und Dateien kommen hinzu (`revision_uebernehmen`). Liefert (Dokument oder None, neu).
	"""
	nr = (teil.get("teilenummer") or "").strip()
	if not kunde or not nr:
		return None, False
	alt_name, alt_neu = alt or (None, False)
	vorhanden = finden(kunde, nr)
	if vorhanden:
		doc = frappe.get_doc("Bauteil", vorhanden)
		neu = bool(alt_neu and vorhanden == alt_name)
		if neu:
			_angaben_setzen(doc, teil)
			doc.save()
		return doc, neu
	if alt_neu and alt_name and frappe.db.get_value("Bauteil", alt_name, "kunde") == kunde and not _anderweitig_verwendet(alt_name):
		doc = frappe.get_doc("Bauteil", alt_name)
		doc.teilenummer = nr
		_angaben_setzen(doc, teil)
		doc.save()
		return doc, True
	doc = frappe.new_doc("Bauteil")
	doc.kunde = kunde
	doc.teilenummer = nr
	_angaben_setzen(doc, teil)
	doc.insert()
	return doc, True


def _anderweitig_verwendet(name):
	"""Wird das Bauteil außerhalb des eben bearbeiteten Angebots schon gebraucht (Aufträge, Fertigung, Anfragen, andere Angebote)?"""
	for dt in ("Auftragsposition", "Fertigungsbauteil", "Anfrageposition"):
		if frappe.db.exists(dt, {"bauteil": name}):
			return True
	return frappe.db.count("Angebotsposition", {"bauteil": name}) > 1


def aufraeumen(name):
	"""Löscht ein von einem Angebot neu angelegtes Bauteil wieder, wenn es nirgends gebraucht wird."""
	try:
		frappe.delete_doc("Bauteil", name)
	except frappe.LinkExistsError:
		frappe.clear_messages()


def plan_setzen(kunde, teilenummer, arbeitsgaenge, name="", zeichnungsnr="", material=""):
	"""Setzt den Arbeitsplan am Bauteil des Kunden. Fehlt das Bauteil, wird es angelegt. Ohne Kunde oder Teilenummer: None."""
	doc = sicherstellen(kunde, teilenummer, name, zeichnungsnr, material)
	if not doc:
		return None
	doc.set("arbeitsplan", [])
	for a in arbeitsgaenge or []:
		doc.append("arbeitsplan", arbeitsgang_zeile(a))
	doc.save()
	return doc


@frappe.whitelist(methods=["POST"])
def plan_speichern(kunde, teilenummer, arbeitsgaenge, name="", zeichnungsnr="", material=""):
	"""Speichert den Arbeitsplan am Bauteil. Fehlt das Bauteil, wird es angelegt."""
	nur_cnc()
	if isinstance(arbeitsgaenge, str):
		arbeitsgaenge = frappe.parse_json(arbeitsgaenge)
	doc = plan_setzen(kunde, teilenummer, arbeitsgaenge, name, zeichnungsnr, material)
	if not doc:
		frappe.throw(_("Für den Arbeitsplan braucht das Bauteil einen Kunden und eine Teilenummer."))
	return bauteil_ui(doc)


def _vergleich(wert):
	"""Nummern ohne Leer- und Trennzeichen vergleichen: "ZN 3003-01" = "zn3003.01"."""
	return re.sub(r"[\s\-_./]+", "", (wert or "").lower())


@frappe.whitelist(methods=["POST"])
def passende(teilenummer="", zeichnungsnr="", kunde=""):
	"""Vorhandene Bauteile zu einer aus der Zeichnung erkannten Teilenummer oder Zeichnungsnummer (höchstens 5).
	Treffer über die Teilenummer und Bauteile des gewählten Kunden kommen zuerst."""
	nur_cnc()
	t, z = _vergleich(teilenummer), _vergleich(zeichnungsnr)
	if not t and not z:
		return []
	treffer = []
	for b in frappe.get_all("Bauteil", fields=["name", "kunde", "teilenummer", "zeichnungsnr"], limit_page_length=0):
		grund = "teilenummer" if t and _vergleich(b.teilenummer) == t else "zeichnungsnr" if z and _vergleich(b.zeichnungsnr) == z else None
		if grund:
			treffer.append((grund != "teilenummer", b.kunde != kunde, b.name, grund))
	out = []
	for _a, _b, name, grund in sorted(treffer)[:5]:
		d = frappe.get_doc("Bauteil", name)
		out.append({**bauteil_ui(d), "grund": grund, "kundeName": frappe.db.get_value("Kunde", d.kunde, "kundenname") or "", "status": d.status})
	return out
