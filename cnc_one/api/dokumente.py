"""Dokumentenmanagement: alle Dokumente der App an einer Stelle, mit Suche (auch im Text der Dateien), Filtern und Pflege.

Sichtbar ist ein Dokument nur, wenn der Benutzer mindestens einen Beleg lesen darf, an dem es hängt.
"""

import re

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import dokumente

FELDER = ["name", "titel", "art", "kunde", "kunde_name", "teilenummer", "revision", "fassung", "datum", "datei", "groesse", "endung", "schlagworte", "notiz"]
NEU_ABGLEICHEN_NACH = 60  # Sekunden


def _iso(d):
	return d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "")


def _lesbare_belege():
	return {dt for dt in dokumente.BELEGE if frappe.has_permission(dt, "read")}


def _bezuege(namen):
	out = {}
	for b in frappe.get_all("Dokument Bezug", filters={"parent": ["in", namen or [""]], "parenttype": "Dokument"}, fields=["parent", "beleg_typ", "beleg", "bezeichnung"], order_by="idx asc"):
		out.setdefault(b.parent, []).append({"typ": b.beleg_typ, "id": b.beleg, "bezeichnung": b.bezeichnung})
	return out


def dokument_ui(d, bezuege, treffer=""):
	return {
		"id": d.name, "titel": d.titel or "", "art": d.art or "", "kundeId": d.kunde or "", "kundeName": d.kunde_name or "",
		"teilenummer": d.teilenummer or "", "revision": d.revision or "", "fassung": d.fassung or "", "datum": _iso(d.datum),
		"url": d.datei or "", "groesse": d.groesse or 0, "endung": d.endung or "", "schlagworte": d.schlagworte or "", "notiz": d.notiz or "",
		"bezuege": bezuege, "treffer": treffer,
	}


def _abgleich_wenn_alt():
	zuletzt = frappe.cache.get_value("cnc_one_dokumente_abgleich")
	if not zuletzt or (now_datetime() - get_datetime(zuletzt)).total_seconds() > NEU_ABGLEICHEN_NACH:
		dokumente.abgleichen()


def _ausschnitt(text, worte):
	"""Stelle im Dateitext, an der das erste Suchwort steht (für die Trefferanzeige)."""
	if not text or not worte:
		return ""
	m = re.search(re.escape(worte[0]), text, re.I)
	if not m:
		return ""
	a, b = max(0, m.start() - 60), min(len(text), m.end() + 60)
	return ("… " if a else "") + " ".join(text[a:b].split()) + (" …" if b < len(text) else "")


@frappe.whitelist(methods=["POST"])
def liste(suche="", art="", kunde="", grenze=300):
	"""Dokumente, neueste zuerst. `suche`: alle Wörter müssen vorkommen (Titel, Teilenummer, Kunde, Belege, Schlagworte,
	Notiz oder Text der Datei). Liefert { dokumente, arten: { art: anzahl } }."""
	nur_cnc()
	_abgleich_wenn_alt()
	lesbar = _lesbare_belege()
	worte = [w for w in (suche or "").split() if w][:8]
	bedingungen, werte = ["1=1"], []
	if art:
		bedingungen.append("d.art = %s")
		werte.append(art)
	if kunde:
		bedingungen.append("d.kunde = %s")
		werte.append(kunde)
	for w in worte:
		bedingungen.append(
			"(d.titel like %s or d.teilenummer like %s or d.kunde_name like %s or d.schlagworte like %s or d.notiz like %s"
			" or d.inhalt like %s or exists (select 1 from `tabDokument Bezug` b where b.parent = d.name and (b.beleg like %s or b.bezeichnung like %s)))"
		)
		werte += [f"%{w}%"] * 8
	zeilen = frappe.db.sql(
		f"""select d.name, d.inhalt, {', '.join('d.' + f for f in FELDER[1:])} from `tabDokument` d
		where {' and '.join(bedingungen)} order by d.datum desc limit %s""",
		[*werte, int(grenze)], as_dict=True,
	)
	bezuege = _bezuege([z.name for z in zeilen])
	sichtbar = [z for z in zeilen if any(b["typ"] in lesbar for b in bezuege.get(z.name, []))]
	arten = {}
	for z in sichtbar:
		arten[z.art] = arten.get(z.art, 0) + 1
	return {
		"dokumente": [dokument_ui(z, bezuege.get(z.name, []), _ausschnitt(z.inhalt, worte)) for z in sichtbar],
		"arten": arten,
	}


def _geladen(id, recht="read"):
	d = frappe.get_doc("Dokument", id)
	lesbar = _lesbare_belege()
	if not any(b.beleg_typ in lesbar for b in d.bezuege):
		frappe.throw(_("Kein Zugriff auf dieses Dokument."), frappe.PermissionError)
	if recht == "write":
		d.check_permission("write")
	return d


@frappe.whitelist(methods=["POST"])
def detail(id):
	nur_cnc()
	d = _geladen(id)
	return dokument_ui(d, _bezuege([d.name]).get(d.name, []))


@frappe.whitelist(methods=["POST"])
def pflegen(id, schlagworte=None, notiz=None):
	"""Schlagworte und Notiz eines Dokuments ändern."""
	nur_cnc()
	d = _geladen(id, "write")
	if schlagworte is not None:
		d.schlagworte = schlagworte
	if notiz is not None:
		d.notiz = (notiz or "").strip()
	d.save()
	return dokument_ui(d, _bezuege([d.name]).get(d.name, []))


@frappe.whitelist(methods=["POST"])
def abgleichen():
	"""Register jetzt mit den Dateien abgleichen."""
	nur_cnc()
	return dokumente.abgleichen()
