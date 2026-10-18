"""Lager: Bestand je Bauteil im Fertigbauteil Lager, Buchungsverlauf und Korrekturen. Das Rohmaterial Lager folgt später."""

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import lager
from cnc_one.logic.daten import iso


def bestand_ui():
	"""Bestand je Bauteil, bei dem es Buchungen gibt (auch 0 und negative)."""
	zeilen = frappe.db.sql(
		"""select l.bauteil, sum(l.menge) as bestand, max(l.zeit) as zuletzt from `tabLagerbuchung` l
		where l.lager = %s and l.bauteil is not null group by l.bauteil""",
		(lager.FERTIG,), as_dict=True,
	)
	out = []
	for z in zeilen:
		b = frappe.db.get_value("Bauteil", z.bauteil, ["kunde", "teilenummer", "bezeichnung", "zeichnungsnr", "serien_stellen"], as_dict=True)
		if not b:
			continue
		out.append({
			"bauteilId": z.bauteil,
			"teil": {"name": b.bezeichnung or "", "teilenummer": b.teilenummer or "", "zeichnungsnr": b.zeichnungsnr or "", "vorschaubild": ""},
			"kundeId": b.kunde,
			"kundeName": frappe.db.get_value("Kunde", b.kunde, "kundenname") or "",
			"bestand": int(z.bestand or 0),
			"zuletzt": iso(z.zuletzt),
		})
	return sorted(out, key=lambda x: (x["kundeName"].lower(), x["teil"]["teilenummer"].lower()))


@frappe.whitelist(methods=["POST"])
def bestand():
	nur_cnc()
	return {"lager": lager.FERTIG, "bestand": bestand_ui()}


@frappe.whitelist(methods=["POST"])
def buchungen(bauteil, limit=100):
	"""Die letzten Buchungen eines Bauteils im Fertigbauteil Lager, neueste zuerst."""
	nur_cnc()
	rows = frappe.get_all(
		"Lagerbuchung", filters={"bauteil": bauteil, "lager": lager.FERTIG},
		fields=["name", "zeit", "menge", "art", "lieferschein", "fertigungsbauteil", "auftrag", "bemerkung", "benutzer"],
		order_by="zeit desc, name desc", limit_page_length=int(limit),
	)
	return [
		{
			"id": r.name, "zeit": iso(r.zeit), "menge": r.menge, "art": r.art, "lieferschein": r.lieferschein or "",
			"fertigungsbauteil": r.fertigungsbauteil or "", "auftrag": r.auftrag or "", "bemerkung": r.bemerkung or "", "benutzer": r.benutzer or "",
		}
		for r in rows
	]


@frappe.whitelist(methods=["POST"])
def korrigieren(bauteil, menge, grund):
	"""Korrekturbuchung (z. B. nach dem Zählen). Plus erhöht, minus verringert den Bestand. Ein Grund ist Pflicht."""
	frappe.only_for(("CNC Admin", "CNC Fertigung", "System Manager"))
	menge = int(menge or 0)
	if not menge:
		frappe.throw(_("Die Korrekturmenge darf nicht null sein."))
	if not (grund or "").strip():
		frappe.throw(_("Bitte einen Grund für die Korrektur angeben."))
	if not frappe.db.exists("Bauteil", bauteil):
		frappe.throw(_("Das Bauteil gibt es nicht."))
	lager.buchen(bauteil, menge, "Korrektur", bemerkung=grund.strip())
	return {"bauteilId": bauteil, "bestand": lager.bestand(bauteil)}
