"""Einstellungen je Benutzer, die in der Oberfläche angepasst werden (zurzeit die Filter der Listen).
Jeder Benutzer liest und schreibt nur seine eigenen."""

import json

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc

MAX_GROESSE = 100_000


def _modul(modul):
	modul = (modul or "").strip()
	if not modul or len(modul) > 80:
		frappe.throw(_("Ungültige Liste."))
	return modul


@frappe.whitelist(methods=["POST"])
def filter_holen(modul):
	"""Filter, angeheftete Felder und Ansichten des angemeldeten Benutzers für eine Liste (oder None)."""
	nur_cnc()
	roh = frappe.db.get_value("Listenfilter", {"benutzer": frappe.session.user, "modul": _modul(modul)}, "daten")
	return json.loads(roh) if isinstance(roh, str) and roh else (roh or None)


@frappe.whitelist(methods=["POST"])
def filter_speichern(modul, daten):
	"""Speichert die Filter des angemeldeten Benutzers für eine Liste."""
	nur_cnc()
	if isinstance(daten, str):
		daten = frappe.parse_json(daten)
	if not isinstance(daten, dict):
		frappe.throw(_("Ungültige Filter."))
	text = json.dumps({k: daten.get(k) or [] for k in ("filter", "angeheftet", "ansichten")}, ensure_ascii=False)
	if len(text) > MAX_GROESSE:
		frappe.throw(_("Zu viele gespeicherte Filter."))
	modul = _modul(modul)
	name = frappe.db.get_value("Listenfilter", {"benutzer": frappe.session.user, "modul": modul}, "name")
	if name:
		frappe.db.set_value("Listenfilter", name, "daten", text)
	else:
		frappe.get_doc({"doctype": "Listenfilter", "benutzer": frappe.session.user, "modul": modul, "daten": text}).insert(ignore_permissions=True)
	return {"ok": True}
