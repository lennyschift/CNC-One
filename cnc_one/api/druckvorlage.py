"""Druckvorlagen in der Oberfläche ändern, mit Vorschau als PDF und Verlauf (siehe logic/vorlagen.py).

Ändern dürfen nur CNC Admin und System Manager. Jede Änderung legt einen „Druckvorlage Stand“ an, so lässt sich jeder
frühere Stand zurückholen. „In den Code übernehmen“ geht nur auf dem Testsystem (developer_mode).
"""

import base64

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import vorlagen

STAENDE = 30  # so viele frühere Stände je Vorlage werden behalten
RECHTE = ("System Manager", "CNC Admin")


def _darf_aendern():
	nur_cnc()
	if not set(RECHTE) & set(frappe.get_roles()):
		frappe.throw(_("Druckvorlagen ändern dürfen nur Administratoren."), frappe.PermissionError)


def _iso(dt):
	return dt.isoformat(sep=" ", timespec="seconds") if dt else ""


def _stand(datei, inhalt, aktion, notiz=""):
	frappe.get_doc({"doctype": "Druckvorlage Stand", "vorlage": datei, "inhalt": inhalt, "aktion": aktion, "notiz": (notiz or "")[:140]}).insert(ignore_permissions=True)
	alte = frappe.get_all("Druckvorlage Stand", filters={"vorlage": datei}, order_by="creation desc", pluck="name", start=STAENDE, limit=1000)
	for n in alte:
		frappe.delete_doc("Druckvorlage Stand", n, ignore_permissions=True, force=True)


def _eintrag(datei):
	bezeichnung, beleg, art = vorlagen.VORLAGEN[datei]
	code = vorlagen.aus_code(datei)
	zeile = frappe.db.get_value("Druckvorlage", datei, ["inhalt", "code_hash", "modified", "modified_by"], as_dict=True) if frappe.db.exists("Druckvorlage", datei) else None
	return {
		"datei": datei, "bezeichnung": bezeichnung, "beleg": beleg, "art": art,
		"geaendert": bool(zeile and zeile.inhalt),
		# Die Datei im Code hat sich geändert, seit die Vorlage in der Oberfläche geändert wurde (z. B. nach einem Update)
		"codeNeuer": bool(zeile and zeile.inhalt and zeile.code_hash and zeile.code_hash != vorlagen.pruefsumme(code)),
		"geaendertAm": _iso(zeile.modified) if zeile else "",
		"geaendertVon": (frappe.db.get_value("User", zeile.modified_by, "full_name") or zeile.modified_by) if zeile else "",
	}


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return {"vorlagen": [_eintrag(d) for d in vorlagen.VORLAGEN], "inDenCode": bool(frappe.conf.developer_mode), "darfAendern": bool(set(RECHTE) & set(frappe.get_roles()))}


@frappe.whitelist(methods=["POST"])
def holen(datei):
	"""Gültiger Stand, Stand im Code und die früheren Stände (ohne Inhalt)."""
	nur_cnc()
	vorlagen.pruefe_datei(datei)
	staende = frappe.get_all(
		"Druckvorlage Stand", filters={"vorlage": datei}, fields=["name", "aktion", "notiz", "creation", "owner"], order_by="creation desc", limit=STAENDE,
	)
	return {
		**_eintrag(datei),
		"inhalt": vorlagen.lesen(datei),
		"code": vorlagen.aus_code(datei),
		"staende": [{"id": s.name, "aktion": s.aktion or "", "notiz": s.notiz or "", "zeit": _iso(s.creation), "von": frappe.db.get_value("User", s.owner, "full_name") or s.owner} for s in staende],
	}


@frappe.whitelist(methods=["POST"])
def stand_inhalt(id):
	nur_cnc()
	return frappe.db.get_value("Druckvorlage Stand", id, "inhalt") or ""


@frappe.whitelist(methods=["POST"])
def speichern(datei, inhalt, notiz=""):
	"""Speichert den Stand. Gleicht er der Datei im Code, wird die Änderung entfernt (dann gilt wieder der Code)."""
	_darf_aendern()
	vorlagen.pruefe_datei(datei)
	inhalt = (inhalt or "").replace("\r\n", "\n")
	fehler = vorlagen.syntax_fehler(datei, inhalt)
	if fehler:
		frappe.throw(_("Die Vorlage enthält einen Fehler: {0}").format(fehler))
	code = vorlagen.aus_code(datei)
	vorher = vorlagen.lesen(datei)
	if inhalt == vorher:
		return holen(datei)
	if inhalt == code:
		if frappe.db.exists("Druckvorlage", datei):
			frappe.delete_doc("Druckvorlage", datei, ignore_permissions=True, force=True)
	elif frappe.db.exists("Druckvorlage", datei):
		doc = frappe.get_doc("Druckvorlage", datei)
		doc.inhalt = inhalt
		doc.code_hash = vorlagen.pruefsumme(code)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({
			"doctype": "Druckvorlage", "datei": datei, "bezeichnung": vorlagen.VORLAGEN[datei][0], "inhalt": inhalt, "code_hash": vorlagen.pruefsumme(code),
		}).insert(ignore_permissions=True)
	_stand(datei, inhalt, "gespeichert", notiz)
	return holen(datei)


@frappe.whitelist(methods=["POST"])
def zuruecksetzen(datei):
	"""Wieder der Stand im Code. Der geänderte Stand bleibt im Verlauf."""
	_darf_aendern()
	vorlagen.pruefe_datei(datei)
	alt = vorlagen.geaendert(datei)
	if alt is not None:
		frappe.delete_doc("Druckvorlage", datei, ignore_permissions=True, force=True)
		_stand(datei, alt, "vor dem Zurücksetzen")
	return holen(datei)


@frappe.whitelist(methods=["POST"])
def in_den_code(datei):
	"""Nur Testsystem: schreibt den geänderten Stand in die Datei unter templates/ (kommt mit dem nächsten Commit nach
	GitHub und ins Produktivsystem) und entfernt die Änderung aus der Datenbank."""
	_darf_aendern()
	if not frappe.conf.developer_mode:
		frappe.throw(_("In den Code übernehmen geht nur auf dem Testsystem."))
	vorlagen.pruefe_datei(datei)
	inhalt = vorlagen.geaendert(datei)
	if inhalt is None:
		frappe.throw(_("Die Vorlage ist nicht geändert."))
	vorlagen.in_datei_schreiben(datei, inhalt)
	frappe.delete_doc("Druckvorlage", datei, ignore_permissions=True, force=True)
	_stand(datei, inhalt, "in den Code übernommen")
	return holen(datei)


# ------------------------------------------------------------------ Vorschau
def _pdf(beleg, id):
	"""PDF eines Belegs, frisch erzeugt (nichts wird abgelegt)."""
	from cnc_one.api import belegdruck, erechnung
	from cnc_one.api.angebot import pdf_erzeugen
	from cnc_one.api.firma import firma_ui
	from cnc_one.logic import briefbogen, pdf

	if beleg == "Firma":
		f = firma_ui()
		return pdf.pdf_a3(briefbogen.muster_html(f), titel="Briefbogen", autor=f.get("firmenname", ""))
	doc = frappe.get_doc(beleg, id)
	doc.check_permission("read")
	if beleg == "Angebot":
		return pdf_erzeugen(doc)
	if beleg == "Auftrag":
		return belegdruck.ab_pdf_erzeugen(doc)
	if beleg == "Lieferschein":
		return belegdruck.lieferschein_pdf_erzeugen(doc)
	if beleg == "Mahnung":
		return belegdruck.mahnung_pdf_erzeugen(doc)
	if beleg == "Rechnung":
		firma = erechnung._firma(doc)
		return pdf.pdf_a3(erechnung._html(doc, firma), titel="Rechnung (Vorschau)", autor=firma.get("firmenname", ""))
	frappe.throw(_("Für {0} gibt es keine Vorschau.").format(beleg))


def fehlertext(e):
	"""Kurzer Fehlertext für die Vorschau: Zeile in der Vorlage und Ursache statt des ganzen Tracebacks."""
	import html
	import re

	text = html.unescape(re.sub(r"<[^>]+>", "", str(e)))
	zeilen = [z.strip() for z in text.splitlines() if z.strip()]
	ursache = zeilen[-1] if zeilen else type(e).__name__
	ursache = re.sub(r"^jinja2\.exceptions\.", "", ursache)
	stelle = re.findall(r'File "<template>", line (\d+)', text)
	return (_("Zeile {0}: ").format(stelle[-1]) if stelle else "") + ursache


BELEGE = ("Angebot", "Auftrag", "Lieferschein", "Rechnung", "Mahnung")


@frappe.whitelist(methods=["POST"])
def belege(beleg):
	"""Die letzten Belege einer Art für die Auswahl der Vorschau."""
	nur_cnc()
	if beleg not in BELEGE:
		return []
	felder = ["name"] + (["kunde_name"] if frappe.get_meta(beleg).has_field("kunde_name") else [])
	return [{"id": d.name, "text": f"{d.name} · {d.get('kunde_name')}" if d.get("kunde_name") else d.name} for d in frappe.get_list(beleg, fields=felder, order_by="modified desc", limit=25)]


@frappe.whitelist(methods=["POST"])
def vorschau(datei, inhalt, beleg, id=""):
	"""Der Beleg als PDF mit dem (noch nicht gespeicherten) Stand der Vorlage. Liefert { pdf (base64) } oder { fehler }."""
	nur_cnc()
	vorlagen.pruefe_datei(datei)
	inhalt = (inhalt or "").replace("\r\n", "\n")
	fehler = vorlagen.syntax_fehler(datei, inhalt)
	if fehler:
		return {"fehler": fehler}
	if beleg != "Firma" and not id:
		return {"fehler": _("Bitte einen Beleg für die Vorschau wählen.")}
	try:
		with vorlagen.probe(datei, inhalt):
			daten = _pdf(beleg, id)
	except frappe.PermissionError:
		raise
	except Exception as e:  # Fehler in der Vorlage (z. B. unbekannte Variable) lesbar zurückgeben
		frappe.clear_last_message()
		return {"fehler": fehlertext(e)}
	return {"pdf": base64.b64encode(daten).decode()}
