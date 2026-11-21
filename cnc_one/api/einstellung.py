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
	sortierung = daten.get("sortierung")
	if not (isinstance(sortierung, dict) and sortierung.get("pfad")):
		sortierung = None
	else:
		sortierung = {"pfad": str(sortierung["pfad"])[:200], "richtung": "ab" if sortierung.get("richtung") == "ab" else "auf"}
	stand = {k: daten.get(k) or [] for k in ("filter", "angeheftet", "ansichten")}
	stand["sortierung"] = sortierung
	text = json.dumps(stand, ensure_ascii=False)
	if len(text) > MAX_GROESSE:
		frappe.throw(_("Zu viele gespeicherte Filter."))
	modul = _modul(modul)
	name = frappe.db.get_value("Listenfilter", {"benutzer": frappe.session.user, "modul": modul}, "name")
	if name:
		frappe.db.set_value("Listenfilter", name, "daten", text)
	else:
		frappe.get_doc({"doctype": "Listenfilter", "benutzer": frappe.session.user, "modul": modul, "daten": text}).insert(ignore_permissions=True)
	return {"ok": True}


# ----------------------------------------------------------------- Mail-Einstellungen je Benutzer
PROFIL = {"anzeigename": "anzeigename", "funktion": "funktion", "telefon": "telefon", "mobil": "mobil", "email": "email", "nameAlsAbsender": "name_als_absender", "signatur": "signatur"}


def _profil(user=None):
	user = user or frappe.session.user
	return frappe.get_doc("Benutzereinstellung", user) if frappe.db.exists("Benutzereinstellung", user) else None


def signatur_erzeugen(d, firma):
	"""Signatur aus den Angaben: Name, Funktion, Firma, Telefon und Mobil, E-Mail (leere Zeilen fallen weg)."""
	telefone = " · ".join(x for x in (f"Telefon {d['telefon']}" if d.get("telefon") else "", f"Mobil {d['mobil']}" if d.get("mobil") else "") if x)
	return "\n".join(x for x in (d.get("anzeigename"), d.get("funktion"), firma, telefone, d.get("email")) if x)


def absender_fuer(firma, absender_name="", user=None):
	"""(Signatur, Absendername) für Mails des angemeldeten Benutzers. `firma`: Absendername der Mail-Einstellungen bzw.
	Firmenname. Ohne eigene Einstellungen bleibt es beim gemeinsamen Absender (Signatur = Firmenname)."""
	basis = absender_name or firma
	p = _profil(user)
	if not p:
		return basis, basis
	user = p.benutzer
	name = (p.anzeigename or "").strip() or frappe.db.get_value("User", user, "full_name") or ""
	d = {"anzeigename": name, "funktion": p.funktion or "", "telefon": p.telefon or "", "mobil": p.mobil or "", "email": (p.email or "").strip() or user}
	text = (p.signatur or "").strip() or signatur_erzeugen(d, firma)
	return text, (f"{name} | {basis}" if p.name_als_absender and name else basis)


def profil_ui(user=None):
	user = user or frappe.session.user
	p = _profil(user)
	voll = frappe.db.get_value("User", user, "full_name") or ""
	out = {ui: (p.get(feld) if p else None) for ui, feld in PROFIL.items()}
	out.update(
		benutzer=user, angelegt=bool(p), nameAlsAbsender=bool(p.name_als_absender) if p else True,
		vorschlagName=voll, vorschlagEmail=user if "@" in user else "",
	)
	for k in ("anzeigename", "funktion", "telefon", "mobil", "email", "signatur"):
		out[k] = out[k] or ""
	return out


@frappe.whitelist(methods=["POST"])
def profil():
	"""Die Mail-Einstellungen des angemeldeten Benutzers mit Vorschau der Signatur und des Absenders."""
	nur_cnc()
	from cnc_one.api.firma import firma_ui
	from cnc_one.logic import mail

	s = mail.einstellungen()
	firma = firma_ui().get("firmenname", "")
	text, name = absender_fuer(firma, s.absender_name)
	return {**profil_ui(), "vorschauSignatur": text, "vorschauAbsender": name, "firma": firma}


@frappe.whitelist(methods=["POST"])
def profil_speichern(daten):
	"""Speichert die Mail-Einstellungen des angemeldeten Benutzers (nur die eigenen)."""
	nur_cnc()
	daten = frappe.parse_json(daten) if isinstance(daten, str) else (daten or {})
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Bitte anmelden."))
	p = _profil(user) or frappe.get_doc({"doctype": "Benutzereinstellung", "benutzer": user})
	for ui, feld in PROFIL.items():
		if ui not in daten:
			continue
		wert = daten[ui]
		if feld == "name_als_absender":
			wert = 1 if wert else 0
		else:
			wert = str(wert or "").strip()[:2000 if feld == "signatur" else 140]
		p.set(feld, wert)
	if p.email and "@" not in p.email:
		frappe.throw(_("Bitte eine gültige E-Mail-Adresse eintragen."))
	p.save(ignore_permissions=True) if not p.is_new() else p.insert(ignore_permissions=True)
	return profil()
