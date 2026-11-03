"""Archivregeln: Aufbewahrungsfristen je Dokumentart, Löschsperre für abgeschlossene Dokumente, Protokoll.

Die Frist beginnt mit dem Schluss des Kalenderjahres, in dem das Dokument entstanden ist (§ 147 Abs. 4 AO).
Gesperrt ist ein Dokument, wenn sein Beleg abgeschlossen ist (Rechnung festgeschrieben, Angebot gesendet, Lieferschein
geliefert, Mahnung versendet, Anfrage mit Angebot, Zeichnung einer bestellten Revision) und die Frist noch läuft.
Entwürfe bleiben frei, damit sie sich ändern lassen.
"""

from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from cnc_one.logic import dokumente

# Vorbelegung; in Stammdaten > Archiv änderbar (mit dem Steuerberater abstimmen)
STANDARD = {
	"Rechnung": (8, "Buchungsbeleg, § 147 Abs. 1 Nr. 4 und Abs. 3 AO (seit 2025 acht Jahre)"),
	"E-Rechnung (XML)": (8, "Buchungsbeleg wie die Rechnung"),
	"Angebot": (6, "Handels- und Geschäftsbrief, § 147 Abs. 1 Nr. 2 und 3 AO"),
	"Lieferschein": (6, "Geschäftsbrief"),
	"Mahnung": (6, "Geschäftsbrief"),
	"Bestellung": (6, "Geschäftsbrief"),
	"Mail-Anhang": (6, "Geschäftsbrief (Anfrage, aus der ein Angebot wurde)"),
	"Zeichnung": (10, "Fertigungsunterlage einer bestellten Revision (Produkthaftung)"),
	"3D-Modell": (10, "Fertigungsunterlage einer bestellten Revision (Produkthaftung)"),
	"Sonstiges": (0, ""),
}


def fristen():
	"""{ art: jahre } aus den Einstellungen, fehlende Arten mit der Vorbelegung."""
	out = {a: j for a, (j, _g) in STANDARD.items()}
	if frappe.db.exists("DocType", "Archiv Einstellungen"):
		for z in frappe.get_single("Archiv Einstellungen").fristen:
			out[z.art] = max(0, int(z.jahre or 0))
	return out


def aufbewahren_bis(datum, jahre):
	if not jahre or not datum:
		return None
	return date(getdate(datum).year + int(jahre), 12, 31)


def _revision_der_datei(bauteil, url):
	zeilen = frappe.get_all("Bauteil Revision", filters={"parent": bauteil, "parenttype": "Bauteil"}, fields=["revision", "zeichnung", "step_datei"])
	rev = next((z.revision for z in zeilen if url in (z.zeichnung, z.step_datei)), None)
	if rev is None and url in (frappe.db.get_value("Bauteil", bauteil, ["zeichnung", "step_datei"]) or ()):
		rev = frappe.db.get_value("Bauteil", bauteil, "revision")
	return rev


def abgeschlossen(dt, name, url=""):
	"""Ist der Beleg abgeschlossen, sodass seine Dokumente aufbewahrt werden müssen?"""
	if not dt or not name or not frappe.db.exists(dt, name):
		return False
	if dt in ("Rechnung", "Angebot"):
		return frappe.db.get_value(dt, name, "status") != "Entwurf"
	if dt == "Lieferschein":
		return frappe.db.get_value(dt, name, "status") != "Bereit"
	if dt == "Mahnung":
		return frappe.db.get_value(dt, name, "status") != "Angelegt"
	if dt == "Mail Anfrage":
		a = frappe.db.get_value(dt, name, ["angebot", "status"], as_dict=True)
		return bool(a.angebot) or a.status == "Beantwortet"
	if dt == "Bauteil":
		# Fertigungsunterlage: nach dieser Revision wurde bestellt bzw. gefertigt
		rev = _revision_der_datei(name, url)
		if rev is None:
			return False
		r = (rev or "").strip().lower()
		return any((x or "").strip().lower() == r for t in ("Auftragsposition", "Fertigungsbauteil") for x in frappe.get_all(t, filters={"bauteil": name}, pluck="revision"))
	return dt == "Auftrag"


def stand(eintraege, art):
	"""(abgeschlossen, aufbewahren_bis, gesperrt) eines Dokuments aus seinen Dateieinträgen."""
	fertig = any(abgeschlossen(f.attached_to_doctype, f.attached_to_name, f.file_url) for f in eintraege)
	bis = aufbewahren_bis(min(getdate(f.creation) for f in eintraege), fristen().get(art, 0))
	return fertig, bis, bool(fertig and bis and getdate(today()) <= bis)


def _relevant(f):
	return f.attached_to_doctype in dokumente.BELEGE and not dokumente._kein_dokument(f) and not f.is_folder


def loeschen_pruefen(f):
	"""Vor dem Löschen einer Datei: abgeschlossene Dokumente in der Aufbewahrungsfrist sind gesperrt."""
	if frappe.flags.archivsperre_aus or not _relevant(f):
		return
	art = dokumente.art_von(f)
	bis = aufbewahren_bis(f.creation or now_datetime(), fristen().get(art, 0))
	if bis and getdate(today()) <= bis and abgeschlossen(f.attached_to_doctype, f.attached_to_name, f.file_url):
		frappe.throw(
			_("„{0}“ gehört zu einem abgeschlossenen Beleg ({1} {2}) und muss bis {3} aufbewahrt werden ({4}).").format(
				f.file_name, f.attached_to_doctype, f.attached_to_name, bis.strftime("%d.%m.%Y"), art
			),
			title=_("Aufbewahrungspflicht"),
		)


def protokollieren(aktion, titel="", art="", beleg_typ="", beleg="", content_hash="", details="", zeit=None, benutzer=None):
	frappe.get_doc({
		"doctype": "Dokument Protokoll", "zeit": zeit or now_datetime(), "benutzer": benutzer or frappe.session.user, "aktion": aktion,
		"titel": titel, "art": art, "beleg_typ": beleg_typ, "beleg": beleg, "content_hash": content_hash, "details": details,
	}).insert(ignore_permissions=True)


def datei_protokollieren(aktion, f):
	if _relevant(f):
		protokollieren(aktion, f.file_name, dokumente.art_von(f), f.attached_to_doctype, f.attached_to_name, f.content_hash or "")


def datei_abgelegt(doc, method=None):
	"""Hook nach dem Anlegen einer Datei."""
	datei_protokollieren("Abgelegt", doc)
