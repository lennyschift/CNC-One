"""Lieferscheine: ohne Preise, auch vor der Fertigung anlegbar (Minusbuchung im Lager), Teillieferungen jederzeit."""

import frappe
from frappe import _
from frappe.utils import today

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import lager
from cnc_one.logic.daten import datum, iso
from cnc_one.logic.lieferung import geliefert_je_position
from cnc_one.logic.serien import STANDARD_STELLEN, bereich, hoechste


def adresse_zeilen(kunde):
	"""Lieferadresse des Kunden als Zeilen: Name, Straße, PLZ und Ort, Land."""
	a = next((x for x in kunde.adressen if x.typ in ("Lieferung", "Rechnung und Lieferung") and x.standard), None) \
		or next((x for x in kunde.adressen if x.typ in ("Lieferung", "Rechnung und Lieferung")), None) \
		or (kunde.adressen[0] if kunde.adressen else None)
	zeilen = [kunde.kundenname]
	if a:
		land = a.land if (a.land or "").strip().upper() not in ("", "DE", "DEUTSCHLAND") else ""
		zeilen += [z for z in (a.strasse, " ".join(x for x in (a.plz, a.ort) if x), land) if z]
	return zeilen


def lieferschein_ui(d):
	return {
		"id": d.name,
		"kundeId": d.kunde,
		"kundeName": d.kunde_name or "",
		"status": d.status,
		"erstellt": iso(d.creation),
		"lieferdatum": datum(d.lieferdatum),
		"gelieferAm": datum(d.geliefert_am),
		"kundenbestellnr": d.kundenbestellnr or "",
		"adresse": [z for z in (d.lieferadresse or "").split("\n") if z],
		"bemerkung": d.bemerkung or "",
		"positionen": [
			{
				"bauteilId": p.bauteil or "",
				"teil": {"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "", "vorschaubild": ""},
				"menge": p.menge,
				"auftragId": p.auftrag or "",
				"auftragPosKey": p.auftragsposition_key or "",
				"serienVon": p.serien_von or None,
				"serienBis": p.serien_bis or None,
				"serienStellen": p.serien_stellen or STANDARD_STELLEN,
			}
			for p in d.positionen
		],
	}


def alle_ui():
	namen = frappe.get_list("Lieferschein", pluck="name", order_by="creation desc", limit_page_length=0)
	return [lieferschein_ui(frappe.get_doc("Lieferschein", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return alle_ui()


@frappe.whitelist(methods=["POST"])
def vorschlag(auftrag):
	"""Wie viel lässt sich aus einem Auftrag liefern? Je Position: bestellt, gefertigt, schon geliefert und der Vorschlag
	(gefertigt und noch nicht geliefert, höchstens die offene Bestellmenge). Ist noch nichts gefertigt, ist der Vorschlag 0
	und die Menge wird von Hand eingegeben."""
	nur_cnc()
	auf = frappe.get_doc("Auftrag", auftrag)
	geliefert = geliefert_je_position(auf.name)
	gefertigt = {r.auftragsposition_key: int(r.produziert or 0) for r in frappe.get_all("Fertigungsbauteil", filters={"auftrag": auf.name}, fields=["auftragsposition_key", "produziert"])}
	positionen = []
	for p in auf.positionen:
		g = geliefert.get(p.position_key, {}).get("menge", 0)
		fertig = gefertigt.get(p.position_key, 0)
		offen = max(0, p.menge - g)
		positionen.append({
			"auftragPosKey": p.position_key,
			"bauteilId": p.bauteil or "",
			"teil": {"name": p.bezeichnung or "", "teilenummer": p.teilenummer or "", "zeichnungsnr": p.zeichnungsnr or "", "vorschaubild": ""},
			"bestellt": p.menge, "gefertigt": fertig, "geliefert": g, "offen": offen,
			"vorschlag": max(0, min(offen, fertig - g)),
			# nächste ungelieferte Nummer des bestellten Bereichs
			"serienVon": (p.serien_von + g) if p.serien_von else None,
			"serienBis": p.serien_bis or None,
			"serienStellen": p.serien_stellen or STANDARD_STELLEN,
		})
	return {"auftragId": auf.name, "kundeId": auf.kunde, "kundeName": auf.kunde_name, "kundenbestellnr": auf.kundenbestellnr or "", "positionen": positionen}


def _position(kunde, p, bereits):
	"""Prüft eine Position und liefert die Werte der Lieferscheinposition. `bereits`: in diesem Lieferschein schon geliefert je Auftragsposition."""
	menge = int(p.get("menge") or 0)
	if menge <= 0:
		frappe.throw(_("Die Liefermenge muss größer als null sein."))
	bauteil = p.get("bauteilId") or None
	werte = {"menge": menge}
	if p.get("auftrag"):
		auf = frappe.get_doc("Auftrag", p["auftrag"])
		if auf.kunde != kunde:
			frappe.throw(_("Der Auftrag {0} gehört zu einem anderen Kunden.").format(auf.name))
		pos = next((x for x in auf.positionen if x.position_key == p.get("auftragsposition")), None)
		if not pos:
			frappe.throw(_("Die Auftragsposition gibt es nicht."))
		schluessel = (auf.name, pos.position_key)
		schon = geliefert_je_position(auf.name).get(pos.position_key, {}).get("menge", 0) + bereits.get(schluessel, 0)
		offen = pos.menge - schon
		if menge > offen:
			frappe.throw(_("Von {0} sind nur noch {1} Stück zu liefern (bestellt {2}, geliefert {3}).").format(pos.bezeichnung or pos.teilenummer, max(0, offen), pos.menge, schon))
		bereits[schluessel] = bereits.get(schluessel, 0) + menge
		bauteil = bauteil or pos.bauteil or None
		werte.update({
			"auftrag": auf.name, "auftragsposition_key": pos.position_key, "teilenummer": pos.teilenummer,
			"bezeichnung": pos.bezeichnung, "zeichnungsnr": pos.zeichnungsnr,
		})
		if pos.serien_von:
			von = pos.serien_von + schon
			werte.update({"serien_von": von, "serien_bis": von + menge - 1, "serien_stellen": pos.serien_stellen or STANDARD_STELLEN})
	if bauteil:
		b = frappe.get_doc("Bauteil", bauteil)
		if b.kunde != kunde:
			frappe.throw(_("Das Bauteil {0} gehört zu einem anderen Kunden.").format(b.teilenummer))
		werte["bauteil"] = b.name
		for feld, wert in (("teilenummer", b.teilenummer), ("bezeichnung", b.bezeichnung), ("zeichnungsnr", b.zeichnungsnr)):
			werte.setdefault(feld, wert or "")
		# ohne Auftrag lassen sich die Nummern von Hand angeben (nur Ziffern, in der Stellenzahl des Bauteils)
		if b.seriennummern and not werte.get("serien_von") and str(p.get("serienStart") or "").strip():
			text = str(p["serienStart"]).strip()
			stellen = b.serien_stellen or STANDARD_STELLEN
			if not text.isdigit() or int(text) <= 0:
				frappe.throw(_("Seriennummern bestehen nur aus Ziffern, zum Beispiel {0}.").format("1".zfill(stellen)))
			von, bis = bereich(int(text), menge)
			if bis > hoechste(stellen):
				frappe.throw(_("Die Seriennummern {0} bis {1} passen nicht in {2} Stellen.").format(str(von).zfill(stellen), bis, stellen))
			werte.update({"serien_von": von, "serien_bis": bis, "serien_stellen": stellen})
	elif not p.get("auftrag"):
		frappe.throw(_("Jede Position braucht ein Bauteil oder eine Auftragsposition."))
	return werte


@frappe.whitelist(methods=["POST"])
def anlegen(kunde, positionen, bemerkung="", kundenbestellnr="", lieferdatum=None):
	"""Legt einen Lieferschein an und bucht die Mengen aus dem Fertigbauteil Lager ab. Ist weniger auf Lager, wird der Bestand
	negativ und gleicht sich aus, sobald die Fertigung einbucht.

	`positionen`: [{ bauteilId, menge, auftrag, auftragsposition, serienStart }], mit Auftrag oder frei aus den Bauteilen des Kunden."""
	nur_cnc()
	if isinstance(positionen, str):
		positionen = frappe.parse_json(positionen)
	if not positionen:
		frappe.throw(_("Der Lieferschein braucht mindestens eine Position."))
	k = frappe.get_doc("Kunde", kunde)
	doc = frappe.new_doc("Lieferschein")
	doc.kunde = k.name
	doc.status = "Bereit"
	doc.lieferdatum = lieferdatum or None
	doc.kundenbestellnr = (kundenbestellnr or "").strip()
	doc.lieferadresse = "\n".join(adresse_zeilen(k))
	doc.bemerkung = (bemerkung or "").strip()
	bereits = {}
	for p in positionen:
		doc.append("positionen", _position(k.name, p, bereits))
	doc.insert()
	for z in doc.positionen:
		lager.buchen(z.bauteil, -z.menge, "Lieferschein", lieferschein=doc.name, auftrag=z.auftrag or None)
	return lieferschein_ui(doc)


def _geladen(id):
	doc = frappe.get_doc("Lieferschein", id)
	doc.check_permission("write")
	return doc


@frappe.whitelist(methods=["POST"])
def geliefert_setzen(id):
	"""Markiert den Lieferschein als geliefert (Ware ist raus)."""
	nur_cnc()
	doc = _geladen(id)
	if doc.status != "Bereit":
		frappe.throw(_("Nur ein bereiter Lieferschein lässt sich als geliefert markieren."))
	doc.status = "Geliefert"
	doc.geliefert_am = today()
	doc.save()
	return lieferschein_ui(doc)


@frappe.whitelist(methods=["POST"])
def stornieren(id):
	"""Storniert den Lieferschein und bucht die Mengen zurück ins Lager. Die gelieferte Menge im Auftrag sinkt entsprechend."""
	nur_cnc()
	doc = _geladen(id)
	if doc.status == "Storniert":
		frappe.throw(_("Der Lieferschein ist schon storniert."))
	doc.status = "Storniert"
	doc.save()
	for z in doc.positionen:
		lager.buchen(z.bauteil, z.menge, "Storno Lieferschein", lieferschein=doc.name, auftrag=z.auftrag or None)
	return lieferschein_ui(doc)
