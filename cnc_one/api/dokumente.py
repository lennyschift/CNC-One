"""Dokumentenmanagement: alle Dokumente der App an einer Stelle, mit Suche (auch im Text der Dateien), Filtern, Pflege,
Aufbewahrung, Protokoll und Export.

Sichtbar ist ein Dokument nur, wenn der Benutzer mindestens einen Beleg lesen darf, an dem es hängt.
"""

import csv
import hashlib
import io
import json
import os
import re
import zipfile

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import archiv, dokumente

FELDER = [
	"name", "titel", "art", "kunde", "kunde_name", "teilenummer", "revision", "fassung", "datum", "datei", "groesse", "endung",
	"schlagworte", "notiz", "content_hash", "abgeschlossen", "aufbewahren_bis", "gesperrt",
]
NEU_ABGLEICHEN_NACH = 60  # Sekunden
EXPORT_GRENZE = 1024 * 1024 * 1024  # 1 GB
ARCHIV_PFLEGE = ("CNC Admin", "CNC Buchhaltung", "System Manager")


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
		"abgeschlossen": bool(d.abgeschlossen), "aufbewahrenBis": _iso(d.aufbewahren_bis), "gesperrt": bool(d.gesperrt),
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


def _suchen(suche="", art="", kunde="", von="", bis="", grenze=300):
	"""Sichtbare Dokumente zu den Filtern: (zeilen, bezuege, worte)."""
	lesbar = _lesbare_belege()
	worte = [w for w in (suche or "").split() if w][:8]
	bedingungen, werte = ["1=1"], []
	if art:
		bedingungen.append("d.art = %s")
		werte.append(art)
	if kunde:
		bedingungen.append("d.kunde = %s")
		werte.append(kunde)
	if von:
		bedingungen.append("d.datum >= %s")
		werte.append(f"{getdate(von)} 00:00:00")
	if bis:
		bedingungen.append("d.datum <= %s")
		werte.append(f"{getdate(bis)} 23:59:59")
	for w in worte:
		bedingungen.append(
			"(d.titel like %s or d.teilenummer like %s or d.kunde_name like %s or d.schlagworte like %s or d.notiz like %s"
			" or d.inhalt like %s or exists (select 1 from `tabDokument Bezug` b where b.parent = d.name and (b.beleg like %s or b.bezeichnung like %s)))"
		)
		werte += [f"%{w}%"] * 8
	zeilen = frappe.db.sql(
		f"""select d.inhalt, {', '.join('d.' + f for f in FELDER)} from `tabDokument` d
		where {' and '.join(bedingungen)} order by d.datum desc limit %s""",
		[*werte, int(grenze)], as_dict=True,
	)
	bezuege = _bezuege([z.name for z in zeilen])
	return [z for z in zeilen if any(b["typ"] in lesbar for b in bezuege.get(z.name, []))], bezuege, worte


@frappe.whitelist(methods=["POST"])
def liste(suche="", art="", kunde="", von="", bis="", grenze=300):
	"""Dokumente, neueste zuerst. `suche`: alle Wörter müssen vorkommen (Titel, Teilenummer, Kunde, Belege, Schlagworte,
	Notiz oder Text der Datei). Liefert { dokumente, arten: { art: anzahl } }."""
	nur_cnc()
	_abgleich_wenn_alt()
	sichtbar, bezuege, worte = _suchen(suche, art, kunde, von, bis, grenze)
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


def verlauf(content_hash):
	return [
		{"zeit": _iso(p.zeit), "benutzer": p.benutzer or "", "aktion": p.aktion, "beleg": f"{p.beleg_typ} {p.beleg}".strip(), "details": p.details or ""}
		for p in frappe.get_all("Dokument Protokoll", filters={"content_hash": content_hash}, fields=["zeit", "benutzer", "aktion", "beleg_typ", "beleg", "details"], order_by="zeit desc", limit=50)
	] if content_hash else []


@frappe.whitelist(methods=["POST"])
def detail(id):
	nur_cnc()
	d = _geladen(id)
	return {**dokument_ui(d, _bezuege([d.name]).get(d.name, [])), "verlauf": verlauf(d.content_hash)}


@frappe.whitelist(methods=["POST"])
def pflegen(id, schlagworte=None, notiz=None):
	"""Schlagworte und Notiz eines Dokuments ändern (im Protokoll vermerkt)."""
	nur_cnc()
	d = _geladen(id, "write")
	vorher = {"Schlagworte": d.schlagworte or "", "Notiz": d.notiz or ""}
	if schlagworte is not None:
		d.schlagworte = schlagworte
	if notiz is not None:
		d.notiz = (notiz or "").strip()
	d.save()
	geaendert = [f"{k}: „{v}“ → „{n}“" for (k, v), n in zip(vorher.items(), (d.schlagworte or "", d.notiz or "")) if v != n]
	if geaendert:
		archiv.protokollieren("Geändert", d.titel, d.art, content_hash=d.content_hash, details="\n".join(geaendert))
	return {**dokument_ui(d, _bezuege([d.name]).get(d.name, [])), "verlauf": verlauf(d.content_hash)}


@frappe.whitelist(methods=["POST"])
def abgleichen():
	"""Register jetzt mit den Dateien abgleichen."""
	nur_cnc()
	return dokumente.abgleichen()


# ----------------------------------------------------------------- Export
def _pfad(url):
	return frappe.get_site_path(url.lstrip("/")) if url.startswith("/private/") else frappe.get_site_path("public", url.lstrip("/"))


def _sauber(name):
	return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", (name or "").strip()) or "_"


def export_zip(suche="", art="", kunde="", von="", bis=""):
	"""(Dateiname, ZIP-Inhalt, Anzahl) der gefilterten Dokumente mit Verzeichnis (CSV: Angaben und SHA-256 je Datei)."""
	sichtbar, bezuege, _w = _suchen(suche, art, kunde, von, bis, grenze=100_000)
	puffer, belegt, summe = io.BytesIO(), set(), 0
	verzeichnis = io.StringIO()
	schreiber = csv.writer(verzeichnis, delimiter=";")
	schreiber.writerow(["Pfad im Archiv", "Titel", "Art", "Kunde", "Teilenummer", "Revision", "Datum", "Abgeschlossen", "Aufzubewahren bis", "Bezüge", "Größe (Bytes)", "SHA-256", "Hinweis"])
	with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
		for d in sichtbar:
			pfad = _pfad(d.datei or "")
			ordner = f"{_sauber(d.kunde_name or 'ohne Kunde')}/{_sauber(d.art)}"
			ziel = f"{ordner}/{_sauber(d.titel)}"
			n = 2
			while ziel in belegt:
				stamm, punkt, endung = _sauber(d.titel).rpartition(".")
				ziel = f"{ordner}/{stamm or endung}_{n}{punkt}{endung if stamm else ''}"
				n += 1
			hinweis, sha = "", ""
			if os.path.exists(pfad):
				summe += os.path.getsize(pfad)
				if summe > EXPORT_GRENZE:
					frappe.throw(_("Der Export wäre größer als 1 GB. Bitte enger filtern (Kunde, Art oder Zeitraum)."))
				with open(pfad, "rb") as fh:
					inhalt = fh.read()
				sha = hashlib.sha256(inhalt).hexdigest()
				z.writestr(ziel, inhalt)
				belegt.add(ziel)
			else:
				hinweis, ziel = "Datei fehlt", ""
			schreiber.writerow([
				ziel, d.titel, d.art, d.kunde_name or "", d.teilenummer or "", d.revision or "", str(d.datum or "")[:19],
				"ja" if d.abgeschlossen else "nein", str(d.aufbewahren_bis or ""),
				", ".join(f"{b['typ']} {b['bezeichnung']}" for b in bezuege.get(d.name, [])), d.groesse or 0, sha, hinweis,
			])
		z.writestr("Verzeichnis.csv", "﻿" + verzeichnis.getvalue())
	stempel = now_datetime().strftime("%Y-%m-%d_%H%M")
	return f"Dokumente_{stempel}.zip", puffer.getvalue(), len(sichtbar)


@frappe.whitelist(methods=["GET"])
def export(suche="", art="", kunde="", von="", bis=""):
	"""ZIP der gefilterten Dokumente herunterladen (im Protokoll vermerkt)."""
	nur_cnc()
	_abgleich_wenn_alt()
	name, inhalt, anzahl = export_zip(suche, art, kunde, von, bis)
	filter_text = json.dumps({k: v for k, v in {"suche": suche, "art": art, "kunde": kunde, "von": von, "bis": bis}.items() if v}, ensure_ascii=False)
	archiv.protokollieren("Exportiert", f"{anzahl} Dokumente", details=f"Filter: {filter_text}")
	frappe.db.commit()
	frappe.local.response.filename = name
	frappe.local.response.filecontent = inhalt
	frappe.local.response.type = "download"


# ----------------------------------------------------------------- Aufbewahrungsfristen
def _fristen_ui():
	"""Aufbewahrungsfristen je Dokumentart (gepflegt oder Vorbelegung) und ob der Benutzer sie ändern darf."""
	gepflegt = {z.art: z for z in frappe.get_single("Archiv Einstellungen").fristen}
	zeilen = []
	for a in dokumente.RANG:
		jahre, grundlage = archiv.STANDARD.get(a, (0, ""))
		z = gepflegt.get(a)
		zeilen.append({"art": a, "jahre": int(z.jahre or 0) if z else jahre, "grundlage": (z.grundlage if z else grundlage) or "", "vorbelegt": jahre})
	return {"fristen": zeilen, "darf": bool(set(frappe.get_roles()) & set(ARCHIV_PFLEGE))}


@frappe.whitelist(methods=["POST"])
def fristen():
	nur_cnc()
	return _fristen_ui()


@frappe.whitelist(methods=["POST"])
def fristen_speichern(fristen):
	frappe.only_for(ARCHIV_PFLEGE)
	if isinstance(fristen, str):
		fristen = frappe.parse_json(fristen)
	s = frappe.get_single("Archiv Einstellungen")
	s.set("fristen", [])
	for z in fristen or []:
		if z.get("art") in dokumente.RANG:
			s.append("fristen", {"art": z["art"], "jahre": max(0, min(50, int(z.get("jahre") or 0))), "grundlage": (z.get("grundlage") or "").strip()})
	s.save()
	dokumente.abgleichen()
	return _fristen_ui()
