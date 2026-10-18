"""Kleine Helfer für Werte zwischen Frappe und Oberfläche."""

import json

from frappe.utils import get_datetime


def als_json(wert):
	"""Inhalt eines JSON-Feldes als Python-Objekt, auch wenn Frappe ihn als Text liefert."""
	if wert in (None, ""):
		return {}
	return json.loads(wert) if isinstance(wert, str) else wert


def iso(wert):
	return get_datetime(wert).isoformat() if wert else None


def datum(wert):
	"""Datum als 'JJJJ-MM-TT' oder leer, wie es die Oberfläche in Datumsfeldern erwartet."""
	return str(wert)[:10] if wert else ""
