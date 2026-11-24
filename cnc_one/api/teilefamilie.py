"""Teilefamilien: Varianten eines Teils (z. B. zehn Teile auf einer Zeichnung, nur die Gewindelänge verschieden). Jede
Variante bleibt ein eigenes Bauteil und einzeln bestellbar; die Familie verknüpft sie und sagt, worin sie sich
unterscheiden. Ein Bauteil gehört zu höchstens einer Familie (Feld teilefamilie am Bauteil)."""

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import aehnlichkeit


def _bauteil_kurz(b, kunden):
	return {
		"id": b.name, "teilenummer": b.teilenummer, "name": b.bezeichnung or "", "kundeId": b.kunde, "kundeName": kunden.get(b.kunde, ""),
		"zeichnungsnr": b.zeichnungsnr or "", "material": b.material or "", "vorschaubild": b.vorschaubild or "", "variante": b.variante or "",
	}


def _kunden():
	return {k.name: k.kundenname for k in frappe.get_all("Kunde", fields=["name", "kundenname"], limit_page_length=0)}


def familie_ui(d, kunden=None):
	kunden = kunden if kunden is not None else _kunden()
	varianten = frappe.get_all(
		"Bauteil", filters={"teilefamilie": d.name}, fields=["name", "teilenummer", "bezeichnung", "kunde", "zeichnungsnr", "material", "vorschaubild", "variante"],
		order_by="teilenummer asc", limit_page_length=0,
	)
	return {
		"id": d.name, "bezeichnung": d.bezeichnung or "", "merkmal": d.merkmal or "", "zeichnungsnr": d.zeichnungsnr or "",
		"kundeId": d.kunde or "", "kundeName": kunden.get(d.kunde, ""), "notiz": d.notiz or "",
		"varianten": [_bauteil_kurz(b, kunden) for b in varianten],
	}


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	kunden = _kunden()
	return [familie_ui(frappe.get_doc("Teilefamilie", n), kunden) for n in frappe.get_all("Teilefamilie", pluck="name", order_by="bezeichnung asc", limit_page_length=0)]


@frappe.whitelist(methods=["POST"])
def fuer_bauteil(bauteil):
	"""Die Familie eines Bauteils oder None."""
	nur_cnc()
	f = frappe.db.get_value("Bauteil", bauteil, "teilefamilie") if bauteil else None
	return familie_ui(frappe.get_doc("Teilefamilie", f)) if f else None


def _mitglieder_setzen(fam, bauteile):
	"""Genau diese Bauteile (mit Variante) gehören zur Familie; andere Familien, die dabei leer werden, verschwinden."""
	ids = []
	for v in bauteile or []:
		bid = v.get("id") if isinstance(v, dict) else v
		if not bid or not frappe.db.exists("Bauteil", bid):
			continue
		frappe.get_doc("Bauteil", bid).check_permission("write")
		ids.append((bid, ((v.get("variante") if isinstance(v, dict) else "") or "").strip()[:140]))
	if len(ids) < 2:
		frappe.throw(_("Eine Teilefamilie braucht mindestens zwei Bauteile."))
	bisher = set(frappe.get_all("Bauteil", filters={"teilefamilie": fam.name}, pluck="name"))
	andere = set()
	for bid, variante in ids:
		alt = frappe.db.get_value("Bauteil", bid, "teilefamilie")
		if alt and alt != fam.name:
			andere.add(alt)
		frappe.db.set_value("Bauteil", bid, {"teilefamilie": fam.name, "variante": variante}, update_modified=False)
	for bid in bisher - {i for i, _v in ids}:
		frappe.db.set_value("Bauteil", bid, {"teilefamilie": None, "variante": ""}, update_modified=False)
	for f in andere:
		if frappe.db.count("Bauteil", {"teilefamilie": f}) < 2:
			_aufloesen(f)
	# gemeinsamer Kunde, wenn alle Varianten vom selben Kunden sind
	kunden = {frappe.db.get_value("Bauteil", i, "kunde") for i, _v in ids}
	fam.db_set("kunde", kunden.pop() if len(kunden) == 1 else None, update_modified=False)


def _aufloesen(name):
	for b in frappe.get_all("Bauteil", filters={"teilefamilie": name}, pluck="name"):
		frappe.db.set_value("Bauteil", b, {"teilefamilie": None, "variante": ""}, update_modified=False)
	frappe.delete_doc("Teilefamilie", name, ignore_permissions=True)


def _felder(doc, daten):
	doc.bezeichnung = (daten.get("bezeichnung") or "").strip()[:140]
	doc.merkmal = (daten.get("merkmal") or "").strip()[:140]
	doc.zeichnungsnr = (daten.get("zeichnungsnr") or "").strip()[:140]
	doc.notiz = (daten.get("notiz") or "").strip()
	if not doc.bezeichnung:
		frappe.throw(_("Bitte eine Bezeichnung für die Teilefamilie eintragen."))


@frappe.whitelist(methods=["POST"])
def speichern(daten):
	"""Familie anlegen (ohne id) oder ändern: { id?, bezeichnung, merkmal, zeichnungsnr, notiz, bauteile: [{id, variante}] }."""
	nur_cnc()
	daten = frappe.parse_json(daten) if isinstance(daten, str) else daten
	if daten.get("id"):
		doc = frappe.get_doc("Teilefamilie", daten["id"])
		doc.check_permission("write")
		_felder(doc, daten)
		doc.save()
	else:
		doc = frappe.new_doc("Teilefamilie")
		_felder(doc, daten)
		doc.insert()
	_mitglieder_setzen(doc, daten.get("bauteile"))
	return familie_ui(frappe.get_doc("Teilefamilie", doc.name))


@frappe.whitelist(methods=["POST"])
def aufloesen(id):
	"""Die Familie auflösen; die Bauteile bleiben unverändert bestehen."""
	nur_cnc()
	frappe.get_doc("Teilefamilie", id).check_permission("delete")
	_aufloesen(id)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def vorschlaege():
	"""Mögliche Familien aus Bauteilen ohne Familie: gleiche Zeichnung, gleicher Nummernstamm mit anderem Index."""
	nur_cnc()
	kunden = _kunden()
	bauteile = frappe.get_all("Bauteil", fields=["name", "kunde", "teilenummer", "bezeichnung", "zeichnungsnr", "material", "vorschaubild", "variante", "teilefamilie"], limit_page_length=0)
	out = []
	for g in aehnlichkeit.familien_vorschlaege(bauteile):
		erste = g["bauteile"][0]
		out.append({
			"schluessel": g["schluessel"], "grund": g["grund"],
			"bezeichnung": erste.bezeichnung or (f"Zeichnung {erste.zeichnungsnr}" if g["schluessel"].startswith("z:") else erste.teilenummer),
			"zeichnungsnr": erste.zeichnungsnr if g["schluessel"].startswith("z:") else "",
			"bauteile": [{**_bauteil_kurz(b, kunden), "variante": v} for b, v in zip(g["bauteile"], g["varianten"])],
		})
	return out
