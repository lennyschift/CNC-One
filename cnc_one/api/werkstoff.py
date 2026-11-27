"""Rohmaterial-Baum für die Oberfläche: ISO-Gruppe → Werkstoff (Material) → Zustand → Form → Ausführung → Abmessung,
dazu Materialanforderungen und die Chargen im Rohmaterial-Lager (mit Werkszeugnis).

Alles ist Auswahl aus Stammdaten; in jeder Stufe lässt sich direkt ein neuer Eintrag anlegen (…_hinzu), der dann für
alle gilt. Formen sind feste Geometrien (für Gewicht und Rohteil), ein Werkstoff schränkt nur ein, welche es gibt.
"""

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, today

from cnc_one.api.stamm import nur_cnc
from cnc_one.setup.werkstoffbaum import abmessung_text

FORMEN = ("Rund", "Vierkant", "Flach", "Sechskant", "Rohr", "Platte")
ISO = ("P", "M", "K", "N", "S", "H", "O")
ZEUGNISSE = ("", "2.2", "3.1", "3.2")


def _t(v, n=140):
	return (str(v or "")).strip()[:n]


def zeilen(text):
	return [z.strip() for z in (text or "").splitlines() if z.strip()]


def _form(form):
	if form not in FORMEN:
		frappe.throw(_("Unbekannte Form {0}.").format(form))
	return form


# ----------------------------------------------------------------- Lesen
def werkstoff_ui(d):
	"""Ein Werkstoff für Auswahllisten (gleiche Form wie in bootstrap.materialien, erweitert)."""
	return {
		"name": d.name, "preisKg": d.preis_kg or 0, "dichte": d.dichte or 0, "schreibweisen": zeilen(d.schreibweisen), "isoGruppe": d.iso_gruppe or "",
		"kurz": d.kurzname or "", "zustaende": zeilen(d.zustaende), "formen": zeilen(d.formen),
	}


def ausfuehrung_ui(d):
	return {"id": d.name, "form": d.form, "name": d.bezeichnung, "iso": (d.iso_gruppen or "").split(), "aktiv": bool(d.aktiv)}


def abmessung_ui(d):
	return {"id": d.name, "form": d.form, "m1": d.mass1 or 0, "m2": d.mass2 or 0, "text": d.bezeichnung or abmessung_text(d.form, d.mass1, d.mass2), "aktiv": bool(d.aktiv)}


def baum(alle=False):
	"""Zustände, Ausführungen, Abmessungen und Anforderungen (für bootstrap und Stammdaten)."""
	f = {} if alle else {"aktiv": 1}
	return {
		"zustaende": [
			{"code": r.name, "beschreibung": r.beschreibung or "", "aktiv": bool(r.aktiv)}
			for r in frappe.get_list("Werkstoffzustand", filters=f, fields=["name", "beschreibung", "aktiv"], order_by="name asc", limit_page_length=0)
		],
		"ausfuehrungen": [
			ausfuehrung_ui(r)
			for r in frappe.get_list("Rohmaterial Ausfuehrung", filters=f, fields=["name", "form", "bezeichnung", "iso_gruppen", "aktiv"], order_by="creation asc", limit_page_length=0)
		],
		"abmessungen": sorted(
			(abmessung_ui(r) for r in frappe.get_list("Rohmaterial Abmessung", filters=f, fields=["name", "form", "mass1", "mass2", "bezeichnung", "aktiv"], limit_page_length=0)),
			key=lambda a: (FORMEN.index(a["form"]) if a["form"] in FORMEN else 9, a["m1"], a["m2"]),
		),
		"anforderungen": [
			{"name": r.name, "aktiv": bool(r.aktiv)}
			for r in frappe.get_list("Materialanforderung", filters=f, fields=["name", "aktiv"], order_by="creation asc", limit_page_length=0)
		],
	}


@frappe.whitelist(methods=["POST"])
def baum_laden(alle=0):
	nur_cnc()
	return baum(bool(cint(alle)))


# ----------------------------------------------------------------- In jeder Stufe neu anlegen
@frappe.whitelist(methods=["POST"])
def werkstoff_anlegen(name, iso, kurz="", dichte=0, preisKg=0, formen=None):
	"""Neuer Werkstoff in einer ISO-Gruppe (Name = Werkstoffnummer bzw. EN-Bezeichnung, z. B. EN AW-7075)."""
	nur_cnc()
	name = _t(name)
	if not name:
		frappe.throw(_("Bitte den Werkstoff benennen, z. B. 1.4301 oder EN AW-7075."))
	if iso not in ISO:
		frappe.throw(_("Bitte eine ISO-Gruppe wählen."))
	if frappe.db.exists("Material", name):
		frappe.throw(_("Den Werkstoff {0} gibt es schon.").format(name))
	formen = frappe.parse_json(formen) if isinstance(formen, str) else formen
	doc = frappe.get_doc({
		"doctype": "Material", "materialname": name, "iso_gruppe": iso, "kurzname": _t(kurz), "dichte": flt(dichte), "preis_kg": flt(preisKg),
		"schreibweisen": _t(kurz), "formen": "\n".join(f for f in (formen or []) if f in FORMEN), "aktiv": 1,
	}).insert()
	return werkstoff_ui(doc)


@frappe.whitelist(methods=["POST"])
def zustand_hinzu(werkstoff="", code="", beschreibung=""):
	"""Zustand am Werkstoff ergänzen; gibt es ihn noch nicht, wird er auch in der Zustandsliste angelegt."""
	nur_cnc()
	code = _t(code, 40)
	if not code:
		frappe.throw(_("Bitte den Zustand angeben, z. B. T651 oder +QT."))
	if not frappe.db.exists("Werkstoffzustand", code):
		frappe.get_doc({"doctype": "Werkstoffzustand", "code": code, "beschreibung": _t(beschreibung), "aktiv": 1}).insert()
	zustand = {"code": code, "beschreibung": frappe.db.get_value("Werkstoffzustand", code, "beschreibung") or "", "aktiv": True}
	if not werkstoff:  # nur in der Zustandsliste (Stammdaten)
		return {"werkstoff": None, "zustand": zustand}
	doc = frappe.get_doc("Material", werkstoff)
	liste = zeilen(doc.zustaende)
	if code not in liste:
		doc.zustaende = "\n".join([*liste, code])
		doc.save()
	return {"werkstoff": werkstoff_ui(doc), "zustand": zustand}


@frappe.whitelist(methods=["POST"])
def form_freigeben(werkstoff, form):
	"""Eine Form für den Werkstoff zulassen (leere Formenliste = alle Formen)."""
	nur_cnc()
	_form(form)
	doc = frappe.get_doc("Material", werkstoff)
	liste = zeilen(doc.formen)
	if liste and form not in liste:
		doc.formen = "\n".join(f for f in FORMEN if f in [*liste, form])
		doc.save()
	return werkstoff_ui(doc)


@frappe.whitelist(methods=["POST"])
def ausfuehrung_hinzu(form, bezeichnung, iso_gruppen=""):
	nur_cnc()
	_form(form)
	name = _t(bezeichnung, 80)
	if not name:
		frappe.throw(_("Bitte die Ausführung benennen, z. B. gezogen h9."))
	iso = " ".join(g for g in ISO if g in (iso_gruppen or "").upper().split())
	vorhanden = frappe.db.get_value("Rohmaterial Ausfuehrung", {"form": form, "bezeichnung": name})
	if vorhanden:
		# gibt es sie schon: wieder aktiv und für die neuen Gruppen mit freigeben (leer = alle Gruppen)
		doc = frappe.get_doc("Rohmaterial Ausfuehrung", vorhanden)
		doc.aktiv = 1
		if doc.iso_gruppen:
			doc.iso_gruppen = " ".join(g for g in ISO if g in set(doc.iso_gruppen.split()) | set(iso.split())) if iso else ""
		doc.save()
		return ausfuehrung_ui(doc)
	doc = frappe.get_doc({"doctype": "Rohmaterial Ausfuehrung", "form": form, "bezeichnung": name, "iso_gruppen": iso, "aktiv": 1}).insert()
	return ausfuehrung_ui(doc)


def _masse_pruefen(form, m1, m2):
	if m1 <= 0:
		frappe.throw(_("Bitte das Maß angeben."))
	if form in ("Flach", "Rohr") and m2 <= 0:
		frappe.throw(_("Bitte auch {0} angeben.").format(_("die Höhe") if form == "Flach" else _("die Wandstärke")))
	if form == "Rohr" and 2 * m2 >= m1:
		frappe.throw(_("Die Wandstärke ist zu groß für den Durchmesser."))
	if form not in ("Flach", "Rohr"):
		m2 = 0
	return m1, m2


@frappe.whitelist(methods=["POST"])
def abmessung_hinzu(form, mass1, mass2=0):
	"""Neue Abmessung in der Reihe der Form (gibt es sie schon, wird sie zurückgegeben und wieder aktiv)."""
	nur_cnc()
	_form(form)
	m1, m2 = _masse_pruefen(form, flt(mass1, 3), flt(mass2, 3))
	text = abmessung_text(form, m1, m2)
	vorhanden = frappe.db.get_value("Rohmaterial Abmessung", {"form": form, "bezeichnung": text})
	if vorhanden:
		doc = frappe.get_doc("Rohmaterial Abmessung", vorhanden)
		if not doc.aktiv:
			doc.aktiv = 1
			doc.save()
		return abmessung_ui(doc)
	doc = frappe.get_doc({"doctype": "Rohmaterial Abmessung", "form": form, "mass1": m1, "mass2": m2, "bezeichnung": text, "aktiv": 1}).insert()
	return abmessung_ui(doc)


@frappe.whitelist(methods=["POST"])
def anforderung_hinzu(bezeichnung):
	nur_cnc()
	name = _t(bezeichnung, 80)
	if not name:
		frappe.throw(_("Bitte die Anforderung benennen, z. B. Ultraschallgeprüft."))
	if frappe.db.exists("Materialanforderung", name):
		frappe.db.set_value("Materialanforderung", name, "aktiv", 1)
	else:
		frappe.get_doc({"doctype": "Materialanforderung", "bezeichnung": name, "aktiv": 1}).insert()
	return {"name": name, "aktiv": True}


# ----------------------------------------------------------------- Pflege in den Stammdaten (Zustände, Ausführungen, Abmessungen, Anforderungen)
ARTEN = {"zustand": "Werkstoffzustand", "ausfuehrung": "Rohmaterial Ausfuehrung", "abmessung": "Rohmaterial Abmessung", "anforderung": "Materialanforderung"}


def _doctype(art):
	if art not in ARTEN:
		frappe.throw(_("Unbekannte Art {0}.").format(art))
	return ARTEN[art]


@frappe.whitelist(methods=["POST"])
def eintrag_setzen(art, id, aktiv=None, beschreibung=None, iso_gruppen=None):
	"""Aktiv/inaktiv, Beschreibung (Zustand) oder ISO-Gruppen (Ausführung) ändern."""
	nur_cnc()
	doc = frappe.get_doc(_doctype(art), id)
	if aktiv is not None:
		doc.aktiv = 1 if cint(aktiv) else 0
	if beschreibung is not None and art == "zustand":
		doc.beschreibung = _t(beschreibung)
	if iso_gruppen is not None and art == "ausfuehrung":
		doc.iso_gruppen = " ".join(g for g in ISO if g in (iso_gruppen or "").upper().split())
	doc.save()
	return baum(True)


@frappe.whitelist(methods=["POST"])
def eintrag_loeschen(art, id):
	"""Löscht einen Eintrag. Ein Zustand verschwindet dabei auch aus den Werkstoffen; Abmessungen mit Chargen bleiben (nur deaktivieren)."""
	nur_cnc()
	dt = _doctype(art)
	if art == "abmessung" and frappe.db.exists("Rohmaterialcharge", {"abmessung": id}):
		frappe.throw(_("Zu dieser Abmessung gibt es Chargen im Lager. Bitte stattdessen deaktivieren."))
	frappe.delete_doc(dt, id)
	if art == "zustand":
		for m in frappe.get_all("Material", filters={"zustaende": ["like", f"%{id}%"]}, pluck="name"):
			doc = frappe.get_doc("Material", m)
			liste = zeilen(doc.zustaende)
			if id in liste:
				doc.zustaende = "\n".join(z for z in liste if z != id)
				doc.save()
	return baum(True)


# ----------------------------------------------------------------- Chargen im Rohmaterial-Lager
def charge_ui(d):
	return {
		"id": d.name, "interneNr": d.interne_nr or "", "chargennr": d.chargennr or "", "werkstoff": d.material, "zustand": d.zustand or "", "form": d.form, "abmessung": d.abmessung,
		"abmessungText": d.abmessung_text or "", "ausfuehrung": d.ausfuehrung or "", "lieferant": d.lieferant or "", "lieferantKurz": _lieferant_kurz(d.lieferant), "eingang": str(d.eingang or ""),
		"laenge": d.laenge or 0, "breite": d.breite or 0, "stueck": d.stueck or 0, "zeugnis": d.zeugnis or "", "pruefungen": zeilen(d.pruefungen),
		"zeugnisDatei": d.zeugnis_datei or "", "lagerplatz": d.lagerplatz or "", "status": d.status or "Vorrätig", "bemerkung": d.bemerkung or "",
		"rest": (d.bemerkung or "").startswith("Reststück"),
	}


def _lieferant_kurz(lieferant):
	"""Kürzel des Lieferanten (Stammdaten), sonst die ersten Buchstaben seines Namens; einmal je Anfrage."""
	if not lieferant:
		return ""
	if not hasattr(frappe.local, "cnc_lieferant_kurz"):
		frappe.local.cnc_lieferant_kurz = {}
	cache = frappe.local.cnc_lieferant_kurz
	if lieferant not in cache:
		cache[lieferant] = frappe.db.get_value("Lieferant", lieferant, "kuerzel") or lieferant.split()[0][:12]
	return cache[lieferant]


@frappe.whitelist(methods=["POST"])
def chargen(werkstoff=None, alle=0):
	"""Chargen im Rohmaterial-Lager, neueste zuerst; ohne `alle` nur vorrätige."""
	nur_cnc()
	f = {} if cint(alle) else {"status": "Vorrätig"}
	if werkstoff:
		f["material"] = werkstoff
	namen = frappe.get_list("Rohmaterialcharge", filters=f, pluck="name", order_by="eingang desc, creation desc", limit_page_length=0)
	return [charge_ui(frappe.get_doc("Rohmaterialcharge", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def charge_speichern(daten):
	"""Wareneingang (ohne `id`) oder Änderung einer Charge (Bestand, Lagerplatz, Zeugnis, Status …)."""
	nur_cnc()
	d = frappe.parse_json(daten) if isinstance(daten, str) else daten
	doc = frappe.get_doc("Rohmaterialcharge", d["id"]) if d.get("id") else frappe.new_doc("Rohmaterialcharge")
	if doc.is_new():
		if not frappe.db.exists("Material", d.get("werkstoff") or ""):
			frappe.throw(_("Bitte einen Werkstoff wählen."))
		abm = frappe.db.get_value("Rohmaterial Abmessung", d.get("abmessung") or "", ["form", "bezeichnung"], as_dict=True)
		if not abm:
			frappe.throw(_("Bitte eine Abmessung wählen."))
		doc.material = d["werkstoff"]
		doc.abmessung = d["abmessung"]
		doc.form = abm.form
		doc.abmessung_text = abm.bezeichnung
		doc.zustand = _t(d.get("zustand"), 40)
		doc.ausfuehrung = _t(d.get("ausfuehrung"), 80)
	if "lieferant" in d:
		doc.lieferant = d.get("lieferant") if d.get("lieferant") and frappe.db.exists("Lieferant", d.get("lieferant")) else None
	if "chargennr" in d:
		doc.chargennr = _t(d.get("chargennr"))
	if "interneNr" in d:
		doc.interne_nr = _t(d.get("interneNr"), 40)
	if "eingang" in d or doc.is_new():
		doc.eingang = getdate(d.get("eingang") or today())
	for k in ("laenge", "breite"):
		if k in d:
			doc.set(k, max(0, flt(d.get(k))))
	if "stueck" in d:
		doc.stueck = max(0, cint(d.get("stueck")))
	if "zeugnis" in d:
		doc.zeugnis = d.get("zeugnis") if d.get("zeugnis") in ZEUGNISSE else ""
	if "pruefungen" in d:
		doc.pruefungen = "\n".join(p for p in (d.get("pruefungen") or []) if frappe.db.exists("Materialanforderung", p))
	if "lagerplatz" in d:
		doc.lagerplatz = _t(d.get("lagerplatz"), 40)
	if "bemerkung" in d:
		doc.bemerkung = (d.get("bemerkung") or "").strip()
	if "zeugnisDatei" in d:
		doc.zeugnis_datei = d.get("zeugnisDatei") or ""
	if "status" in d:
		doc.status = d.get("status") if d.get("status") in ("Vorrätig", "Aufgebraucht") else "Vorrätig"
	if doc.form == "Platte" and doc.is_new() and not (doc.laenge and doc.breite):
		frappe.throw(_("Bitte Länge und Breite der Platte angeben."))
	if doc.form != "Platte" and doc.is_new() and not doc.laenge:
		frappe.throw(_("Bitte die Länge angeben."))
	if doc.is_new() and not doc.interne_nr:
		doc.interne_nr = interne_nr(chargen_muster(), doc.lieferant, doc.eingang)
	doc.save() if not doc.is_new() else doc.insert()
	return charge_ui(doc)


# ----------------------------------------------------------------- Interne Chargennummer
STANDARD_MUSTER = "{kuerzel}{MM}{JJ}"


def chargen_muster():
	m = frappe.db.get_single_value("Fertigung Einstellungen", "chargen_muster") if frappe.db.exists("DocType", "Fertigung Einstellungen") else ""
	return m or STANDARD_MUSTER


def interne_nr(muster, lieferant, eingang):
	"""Interne Chargennummer nach dem Muster, z. B. {kuerzel}{MM}{JJ} → BIK1126; mit {nr} die nächste freie Nummer."""
	kuerzel = (frappe.db.get_value("Lieferant", lieferant, "kuerzel") if lieferant else "") or (lieferant or "").replace(" ", "")[:3].upper()
	d = getdate(eingang or today())
	t = (muster or STANDARD_MUSTER).replace("{kuerzel}", kuerzel).replace("{JJJJ}", f"{d.year}").replace("{JJ}", f"{d.year % 100:02d}") \
		.replace("{MM}", f"{d.month:02d}").replace("{TT}", f"{d.day:02d}")
	if "{nr}" in t:
		n = 1
		while frappe.db.exists("Rohmaterialcharge", {"interne_nr": t.replace("{nr}", str(n))}):
			n += 1
		t = t.replace("{nr}", str(n))
	return t[:40]


@frappe.whitelist(methods=["POST"])
def chargen_muster_laden():
	nur_cnc()
	return {"muster": chargen_muster(), "darf": bool(set(frappe.get_roles()) & {"CNC Admin", "CNC Fertigung", "CNC Vertrieb", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def chargen_muster_speichern(muster):
	frappe.only_for(("CNC Admin", "CNC Fertigung", "CNC Vertrieb", "System Manager"))
	muster = (muster or "").strip()[:60] or STANDARD_MUSTER
	frappe.db.set_single_value("Fertigung Einstellungen", "chargen_muster", muster)
	return {"muster": muster}


# ----------------------------------------------------------------- Für Auftrag und Fertigung
def _z(v):
	return f"{flt(v):g}".replace(".", ",")


def roh_angaben(teil):
	"""Rohmaterial eines Bauteils (Workbench-Kalkulation) als Text für die Fertigungskarte:
	(Info, Charge, Lagerplatz), z. B. („Rund Ø40 · T7351 · gezogen h11 · Zuschnitt 82 mm · Zeugnis 3.1, Ultraschallgeprüft“, …)."""
	roh = (teil or {}).get("roh") or {}
	if not roh:
		return "", "", ""
	teile = []
	if roh.get("abmessung"):
		teile.append(f"{roh.get('form') or ''} {roh['abmessung']}".strip())
	teile += [x for x in (roh.get("zustand"), roh.get("ausfuehrung")) if x]
	if flt(roh.get("laenge")):
		zuschnitt = f"{_z(roh.get('breite'))} × {_z(roh['laenge'])}" if roh.get("form") == "Platte" and flt(roh.get("breite")) else _z(roh["laenge"])
		teile.append(f"Zuschnitt {zuschnitt} mm")
	anf = roh.get("anforderungen") or {"zeugnis": roh.get("zeugnis") or "", "pruefungen": []}
	nachweise = [f"Zeugnis {anf['zeugnis']}"] if anf.get("zeugnis") else []
	nachweise += anf.get("pruefungen") or []
	if nachweise:
		teile.append(", ".join(nachweise))
	charge = roh.get("charge") or ""
	platz = frappe.db.get_value("Rohmaterialcharge", charge, "lagerplatz") if charge and frappe.db.exists("Rohmaterialcharge", charge) else ""
	return " · ".join(teile)[:140], charge, platz or ""
