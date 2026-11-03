"""Dokumentenregister: ein Eintrag je Dokument (gleicher Inhalt = ein Dokument, auch wenn er an mehreren Belegen hängt).

Die Dateien selbst bleiben, wo sie sind (private Dateien an Bauteil, Angebot, Rechnung, Mail-Anfrage …). Der Abgleich
liest alle Dateieinträge, fasst sie nach Inhalt zusammen und hält Art, Kunde, Teilenummer, Revision und Bezüge aktuell.
Schlagworte und Notiz pflegt der Benutzer, sie bleiben beim Abgleich erhalten. Für die Suche wird der Text aus PDF,
STEP und XML gelesen.
"""

import os
import re

import frappe
from frappe.utils import get_datetime, now_datetime

# Belege, an denen Dokumente hängen können, und woher der Kunde kommt
BELEGE = {
	"Bauteil": "kunde", "Angebot": "kunde", "Auftrag": "kunde", "Rechnung": "kunde", "Lieferschein": "kunde",
	"Mail Anfrage": "kunde", "Mahnung": "kunde", "Kunde": None,
}
# Je mehr Aussage, desto weiter vorne: ein Dokument an mehreren Belegen bekommt die genaueste Art
RANG = ["Rechnung", "E-Rechnung (XML)", "Angebot", "Lieferschein", "Mahnung", "Bestellung", "Zeichnung", "3D-Modell", "Mail-Anhang", "Sonstiges"]
MODELL = ("stp", "step", "igs", "iges")
BILD = ("png", "jpg", "jpeg", "gif", "webp", "bmp")
MAX_TEXT = 100_000
TEXT_JE_ABGLEICH = 25  # so viele Dateien werden je Abgleich gelesen, der Rest beim nächsten


def _endung(name):
	return (name or "").rsplit(".", 1)[-1].lower() if "." in (name or "") else ""


def art_von(f):
	"""Art eines einzelnen Dateieintrags aus dem Beleg, dem Feld und der Endung."""
	endung = _endung(f.file_name)
	dt = f.attached_to_doctype
	if dt == "Rechnung":
		return "E-Rechnung (XML)" if endung == "xml" else "Rechnung"
	if dt in ("Lieferschein", "Mahnung"):
		return dt
	if dt == "Angebot" and (f.file_name or "").startswith("Angebot "):
		return "Angebot"
	if endung in MODELL:
		return "3D-Modell"
	if dt == "Mail Anfrage":
		return "Mail-Anhang"
	if endung == "pdf" and dt in ("Bauteil", "Angebot"):
		return "Zeichnung"
	return "Sonstiges"


def _kein_dokument(f):
	"""Vorschaubilder und Bilder aus dem Mailtext sind keine Dokumente."""
	if f.attached_to_field == "vorschaubild" or (f.file_name or "").startswith("vorschau-"):
		return True
	return f.attached_to_doctype == "Mail Anfrage" and _endung(f.file_name) in BILD


class _Belege:
	"""Kunde und Bezeichnung der Belege, je Beleg nur einmal nachgeschlagen."""

	def __init__(self):
		self.cache = {}

	def __call__(self, dt, name):
		k = (dt, name)
		if k not in self.cache:
			self.cache[k] = self._laden(dt, name)
		return self.cache[k]

	def _laden(self, dt, name):
		if not frappe.db.exists(dt, name):
			return None
		if dt == "Kunde":
			return {"kunde": name, "bezeichnung": frappe.db.get_value("Kunde", name, "kundenname") or name}
		kunde = frappe.db.get_value(dt, name, BELEGE[dt]) if BELEGE.get(dt) else None
		bez = name
		if dt == "Bauteil":
			t = frappe.db.get_value("Bauteil", name, ["teilenummer", "bezeichnung", "revision", "zeichnung", "step_datei"], as_dict=True)
			bez = f"{name} · {t.teilenummer}" + (f" {t.bezeichnung}" if t.bezeichnung else "")
			return {"kunde": kunde, "bezeichnung": bez, "teil": t}
		if dt == "Rechnung":
			bez = frappe.db.get_value("Rechnung", name, "rechnungsnummer") or name
		elif dt == "Mail Anfrage":
			bez = f"{name} · {(frappe.db.get_value('Mail Anfrage', name, 'betreff') or '')[:60]}"
		return {"kunde": kunde, "bezeichnung": bez}


def _revision(url, bauteil, teil):
	"""(Revision, Fassung) einer Zeichnung oder eines Modells am Bauteil."""
	zeilen = frappe.get_all("Bauteil Revision", filters={"parent": bauteil, "parenttype": "Bauteil"}, fields=["revision", "zeichnung", "step_datei"], order_by="idx asc")
	rev = next((z.revision for z in reversed(zeilen) if url in (z.zeichnung, z.step_datei)), None)
	aktuell = url in (teil.zeichnung, teil.step_datei)
	if rev is None:
		rev = teil.revision if aktuell else ""
	return rev or "", "Aktuell" if aktuell else "Ältere Fassung"


def gruppen():
	"""Dateieinträge nach Inhalt zusammengefasst: { schlüssel: [einträge] }."""
	eintraege = frappe.db.sql(
		"""select name, file_name, file_url, content_hash, file_size, attached_to_doctype, attached_to_name,
		attached_to_field, creation from `tabFile` where is_folder = 0 and ifnull(attached_to_doctype, '') != ''
		order by creation asc""",
		as_dict=True,
	)
	out = {}
	for f in eintraege:
		if f.attached_to_doctype not in BELEGE or _kein_dokument(f) or not f.file_url:
			continue
		out.setdefault(f.content_hash or f.file_url, []).append(f)
	return out


def soll(eintraege, belege):
	"""Was im Register zu diesen Dateieinträgen stehen soll (ohne Schlagworte, Notiz, Text)."""
	arten = [art_von(f) for f in eintraege]
	art = min(arten, key=RANG.index)
	haupt = next(f for f, a in zip(eintraege, arten) if a == art)
	bezuege, kunde, teilenummer, revision, fassung = [], None, "", "", ""
	for f in eintraege:
		b = belege(f.attached_to_doctype, f.attached_to_name)
		if not b:
			continue
		if not any(x["beleg_typ"] == f.attached_to_doctype and x["beleg"] == f.attached_to_name for x in bezuege):
			bezuege.append({"beleg_typ": f.attached_to_doctype, "beleg": f.attached_to_name, "bezeichnung": b["bezeichnung"], "datei": f.name})
		kunde = kunde or b.get("kunde")
		if f.attached_to_doctype == "Bauteil" and b.get("teil"):
			teilenummer = b["teil"].teilenummer or teilenummer
			if art in ("Zeichnung", "3D-Modell"):
				revision, fassung = _revision(f.file_url, f.attached_to_name, b["teil"])
	return {
		"titel": haupt.file_name or "", "art": art, "datei": haupt.file_url, "groesse": haupt.file_size or 0, "endung": _endung(haupt.file_name),
		"datum": get_datetime(eintraege[0].creation), "kunde": kunde or None, "teilenummer": teilenummer, "revision": revision, "fassung": fassung,
		"bezuege": sorted(bezuege, key=lambda x: (x["beleg_typ"], x["beleg"])),
	}


def _vergleich(doc):
	return {
		"titel": doc.titel or "", "art": doc.art, "datei": doc.datei, "groesse": doc.groesse or 0, "endung": doc.endung or "",
		"datum": get_datetime(doc.datum) if doc.datum else None, "kunde": doc.kunde or None, "teilenummer": doc.teilenummer or "", "revision": doc.revision or "", "fassung": doc.fassung or "",
		"bezuege": sorted(({"beleg_typ": b.beleg_typ, "beleg": b.beleg, "bezeichnung": b.bezeichnung, "datei": b.datei} for b in doc.bezuege), key=lambda x: (x["beleg_typ"], x["beleg"])),
	}


def text_lesen(url, endung):
	"""Text einer Datei für die Suche (PDF-Text, STEP-Kopf und Produktnamen, XML-Inhalt)."""
	pfad = frappe.get_site_path(url.lstrip("/")) if url.startswith("/private/") else frappe.get_site_path("public", url.lstrip("/"))
	if not os.path.exists(pfad):
		return None  # Datei fehlt: später noch einmal versuchen
	try:
		if endung == "pdf":
			from pypdf import PdfReader

			leser = PdfReader(pfad)
			return "\n".join((s.extract_text() or "") for s in leser.pages[:30])[:MAX_TEXT]
		if endung in MODELL:
			with open(pfad, "rb") as fh:
				kopf = fh.read(400_000).decode("latin-1", "replace")
			worte = re.findall(r"(?:FILE_NAME|FILE_DESCRIPTION|PRODUCT|PRODUCT_DEFINITION)\s*\(\s*'([^']*)'(?:\s*,\s*'([^']*)')?", kopf)
			return " ".join(dict.fromkeys(w for paar in worte for w in paar if w))[:MAX_TEXT]
		if endung == "xml":
			with open(pfad, "rb") as fh:
				return re.sub(r"<[^>]+>", " ", fh.read(300_000).decode("utf-8", "replace"))[:MAX_TEXT]
	except Exception:
		frappe.clear_messages()
	return ""


def abgleichen():
	"""Register an die Dateien angleichen. Liefert { neu, geaendert, entfernt, gelesen }."""
	belege = _Belege()
	ziel = gruppen()
	vorhanden = {d.content_hash: d.name for d in frappe.get_all("Dokument", fields=["name", "content_hash"])}
	stand = {"neu": 0, "geaendert": 0, "entfernt": 0, "gelesen": 0}
	for schluessel, eintraege in ziel.items():
		s = soll(eintraege, belege)
		if not s["bezuege"]:
			continue
		if schluessel in vorhanden:
			doc = frappe.get_doc("Dokument", vorhanden[schluessel])
			if _vergleich(doc) == {**s, "bezuege": s["bezuege"]}:
				continue
			doc.update({k: v for k, v in s.items() if k != "bezuege"})
			doc.set("bezuege", s["bezuege"])
			if doc.datei != s["datei"]:
				doc.text_gelesen = 0
			doc.save(ignore_permissions=True)
			stand["geaendert"] += 1
		else:
			doc = frappe.get_doc({"doctype": "Dokument", "content_hash": schluessel, **s})
			doc.insert(ignore_permissions=True)
			stand["neu"] += 1
	for schluessel, name in vorhanden.items():
		if schluessel not in ziel or not soll(ziel[schluessel], belege)["bezuege"]:
			frappe.delete_doc("Dokument", name, ignore_permissions=True, force=True)
			stand["entfernt"] += 1
	for d in frappe.get_all("Dokument", filters={"text_gelesen": 0}, fields=["name", "datei", "endung"], limit=TEXT_JE_ABGLEICH):
		text = text_lesen(d.datei, d.endung)
		if text is None:
			continue
		frappe.db.set_value("Dokument", d.name, {"inhalt": text, "text_gelesen": 1}, update_modified=False)
		stand["gelesen"] += 1
	frappe.cache.set_value("cnc_one_dokumente_abgleich", str(now_datetime()))
	return stand


def geplant():
	"""Alle 5 Minuten (Scheduler)."""
	try:
		abgleichen()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="CNC One: Dokumente abgleichen")
