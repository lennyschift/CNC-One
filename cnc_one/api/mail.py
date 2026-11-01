"""Mail-Anbindung: Anfragen aus dem gemeinsamen Postfach, Kunde und Kontakt zuordnen, Einstellungen."""

import json
import re

import frappe
from frappe import _

from cnc_one.api.stamm import nur_cnc
from cnc_one.logic import mail

MAIL_PFLEGE = ("CNC Admin", "System Manager")
OFFEN = ("Neu", "In Bearbeitung")


def _iso(d):
	return d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "")


def _art(name):
	n = (name or "").lower()
	return "Zeichnung" if n.endswith(".pdf") else "STEP" if n.endswith((".stp", ".step")) else "Tabelle" if n.endswith((".xlsx", ".xls", ".csv")) else "Datei"


def kontakt_vorschlag(name):
	"""Anrede, Vor- und Nachname aus dem Absendernamen ("Max Mustermann" oder "Mustermann, Max")."""
	name = " ".join((name or "").replace('"', "").split())
	if "," in name:
		nach, _k, vor = name.partition(",")
		return {"anrede": "", "vorname": vor.strip(), "nachname": nach.strip()}
	teile = name.split(" ")
	return {"anrede": "", "vorname": " ".join(teile[:-1]), "nachname": teile[-1] if teile else ""}


def anfrage_kurz(d):
	return {
		"id": d.name, "status": d.status, "betreff": d.betreff or "", "vonEmail": d.von_email or "", "vonName": d.von_name or "",
		"datum": _iso(d.datum), "letzteNachricht": _iso(d.letzte_nachricht or d.datum), "neueAntwort": bool(d.neue_antwort),
		"kundeId": d.kunde or "", "kundeName": d.kunde_name or "", "angebotId": d.angebot or "",
	}


def anfrage_ui(d):
	vorschlag = d.kunde_vorschlag
	return {
		**anfrage_kurz(d),
		"kundeVorschlag": {"id": vorschlag, "name": frappe.db.get_value("Kunde", vorschlag, "kundenname") or ""} if vorschlag else None,
		"kontaktVorschlag": kontakt_vorschlag(d.von_name),
		"nachrichten": [
			{
				"richtung": n.richtung, "datum": _iso(n.datum), "vonEmail": n.von_email or "", "vonName": n.von_name or "",
				"an": n.an or "", "cc": n.cc or "", "betreff": n.betreff or "", "text": n.text or "", "hinweis": n.hinweis or "",
				"anhaenge": [{**a, "art": _art(a.get("name"))} for a in (json.loads(n.anhaenge) if isinstance(n.anhaenge, str) and n.anhaenge else n.anhaenge or [])],
			}
			for n in sorted(d.nachrichten, key=lambda x: (x.datum or d.datum, x.idx))
		],
	}


def liste_ui(alle=False):
	filters = {} if alle else {"status": ["!=", "Keine Anfrage"]}
	namen = frappe.get_list("Mail Anfrage", filters=filters, pluck="name", order_by="letzte_nachricht desc", limit_page_length=500)
	return [anfrage_kurz(frappe.get_doc("Mail Anfrage", n)) for n in namen]


@frappe.whitelist(methods=["POST"])
def liste():
	nur_cnc()
	return liste_ui()


@frappe.whitelist(methods=["POST"])
def anzahl():
	"""Offene Anfragen für das Abzeichen in der Navigation (neu oder mit neuer Antwort des Kunden)."""
	nur_cnc()
	return frappe.db.count("Mail Anfrage", {"status": "Neu"}) + frappe.db.count("Mail Anfrage", {"status": ["!=", "Neu"], "neue_antwort": 1})


@frappe.whitelist(methods=["POST"])
def detail(id):
	nur_cnc()
	d = frappe.get_doc("Mail Anfrage", id)
	d.check_permission("read")
	return anfrage_ui(d)


@frappe.whitelist(methods=["POST"])
def abrufen():
	"""Jetzt abholen (auch wenn das automatische Abholen aus ist)."""
	nur_cnc()
	neu = mail.abholen()
	return {"neu": neu, "liste": liste_ui()}


def _geladen(id):
	d = frappe.get_doc("Mail Anfrage", id)
	d.check_permission("write")
	return d


@frappe.whitelist(methods=["POST"])
def gelesen(id):
	"""Die neue Antwort des Kunden ist gesehen."""
	nur_cnc()
	d = _geladen(id)
	if d.neue_antwort:
		d.db_set("neue_antwort", 0, update_modified=False)
	return anfrage_ui(d)


@frappe.whitelist(methods=["POST"])
def kunde_zuordnen(id, kunde="", neuer_kunde="", kontakt=None):
	"""Ordnet die Anfrage einem Kunden zu. Ist die Absenderadresse dort noch kein Kontakt, wird sie als Kontakt angelegt.
	`neuer_kunde`: Name eines neu anzulegenden Kunden. `kontakt`: { anrede, vorname, nachname } für den neuen Kontakt."""
	nur_cnc()
	d = _geladen(id)
	if isinstance(kontakt, str):
		kontakt = frappe.parse_json(kontakt)
	kontakt = kontakt or {}
	if (neuer_kunde or "").strip():
		k = frappe.get_doc({"doctype": "Kunde", "kundenname": neuer_kunde.strip()})
	elif kunde and frappe.db.exists("Kunde", kunde):
		k = frappe.get_doc("Kunde", kunde)
	else:
		frappe.throw(_("Bitte einen Kunden wählen oder neu anlegen."))
	adresse = (d.von_email or "").lower()
	if adresse and not any((x.email or "").lower() == adresse for x in k.kontakte):
		nachname = (kontakt.get("nachname") or "").strip() or adresse.split("@")[0]
		k.append("kontakte", {
			"anrede": kontakt.get("anrede") if kontakt.get("anrede") in ("Herr", "Frau") else "",
			"vorname": (kontakt.get("vorname") or "").strip(), "nachname": nachname, "email": adresse,
		})
	k.save() if not k.is_new() else k.insert()
	d.kunde = k.name
	d.save()
	return anfrage_ui(d)


def anfrage_nummer(betreff):
	"""Anfrage-Nr. des Kunden aus dem Betreff, z. B. "Anfrage Nr. 4711-B" oder "RFQ 2026-118" (muss eine Ziffer enthalten)."""
	t = re.search(r"(?:anfrage|rfq|inquiry|request)\s*(?:-?nr\.?|-?nummer|no\.?|#)?\s*[:#]?\s*([A-Z0-9][\w\-/.]*\d[\w\-/.]*)", betreff or "", re.I)
	return t.group(1).rstrip(".") if t else ""


def _dateien_ans_angebot(d, angebot):
	"""Zeichnungen und Modelle der Anfrage ans Angebot hängen: je Datei ein eigener Dateieintrag, der auf dieselbe Datei
	auf der Platte zeigt (gleicher Prüfwert, so löscht keiner der beiden Einträge die Datei des anderen). Die Einträge
	wandern später ans Bauteil, die Mail behält ihre."""
	out = []
	for n in d.nachrichten:
		if n.richtung != "Eingang":
			continue
		for a in json.loads(n.anhaenge) if isinstance(n.anhaenge, str) and n.anhaenge else n.anhaenge or []:
			if _art(a.get("name")) not in ("Zeichnung", "STEP"):
				continue
			quelle = frappe.db.get_value("File", {"file_url": a["url"], "attached_to_doctype": "Mail Anfrage", "attached_to_name": d.name}, "name")
			if not quelle:
				continue
			f = frappe.get_doc("File", quelle).create_attachment_copy("Angebot", angebot, ignore_permissions=True)
			out.append({"id": f.name, "name": a["name"], "art": _art(a["name"]), "groesse": a.get("groesse") or 0, "url": f.file_url})
	return out


@frappe.whitelist(methods=["POST"])
def angebot_anlegen(id):
	"""Angebotsentwurf aus der Anfrage: Kunde, Anfrage-Nr. aus dem Betreff, Zeichnungen und Modelle am Angebot.
	Die Bauteile legt die Workbench daraus an (Erkennung der Zeichnung, Mengen aus dem Mailtext).
	Gibt es schon ein Angebot zu dieser Anfrage, wird es geliefert (`neu` = False)."""
	nur_cnc()
	from cnc_one.api.angebot import angebot_ui

	d = _geladen(id)
	if d.angebot and frappe.db.exists("Angebot", d.angebot):
		return {"angebot": angebot_ui(frappe.get_doc("Angebot", d.angebot)), "dateien": [], "text": "", "neu": False}
	if not d.kunde:
		frappe.throw(_("Bitte zuerst den Kunden zuordnen."))
	a = frappe.get_doc({"doctype": "Angebot", "kunde": d.kunde, "anfrage_nr": anfrage_nummer(d.betreff)})
	a.insert()
	dateien = _dateien_ans_angebot(d, a.name)
	d.angebot = a.name
	d.status = "In Bearbeitung"
	d.save()
	text = "\n\n".join(n.text or "" for n in d.nachrichten if n.richtung == "Eingang")
	return {"angebot": angebot_ui(a), "dateien": dateien, "text": text, "neu": True}


def zu_angebot(angebot):
	"""Die Anfrage, aus der ein Angebot entstanden ist: { id, betreff, vonName, vonEmail } oder None."""
	r = frappe.get_all("Mail Anfrage", filters={"angebot": angebot}, fields=["name", "betreff", "von_name", "von_email"], limit=1) if angebot else []
	return {"id": r[0].name, "betreff": r[0].betreff or "", "vonName": r[0].von_name or "", "vonEmail": r[0].von_email or ""} if r else None


@frappe.whitelist(methods=["POST"])
def keine_anfrage(id):
	"""Keine Anfrage: Text und Anhänge werden aus Frappe gelöscht, im Postfach bleibt die Mail. Gemerkt wird nur ihre
	Kennung, damit sie nicht wieder geholt wird."""
	nur_cnc()
	d = _geladen(id)
	if d.angebot:
		frappe.throw(_("Zu dieser Anfrage gibt es schon das Angebot {0}.").format(d.angebot))
	for f in frappe.get_all("File", filters={"attached_to_doctype": "Mail Anfrage", "attached_to_name": d.name}, pluck="name"):
		frappe.delete_doc("File", f, ignore_permissions=True)
	for n in d.nachrichten:
		n.text = ""
		n.anhaenge = None
		n.hinweis = ""
	d.status = "Keine Anfrage"
	d.neue_antwort = 0
	d.save()
	return {"id": d.name, "status": d.status}


# ----------------------------------------------------------------- Einstellungen
FELDER = {
	"aktiv": "aktiv", "benutzer": "benutzer", "absenderName": "absender_name", "verschluesselung": "verschluesselung",
	"imapServer": "imap_server", "imapPort": "imap_port", "smtpServer": "smtp_server", "smtpPort": "smtp_port",
	"stichwoerter": "stichwoerter", "abholenAb": "abholen_ab", "postfachOrdner": "postfach_ordner", "gesendetOrdner": "gesendet_ordner",
}


def einstellungen_ui(s=None):
	s = s or mail.einstellungen()
	out = {ui: s.get(feld) for ui, feld in FELDER.items()}
	out.update(
		aktiv=bool(s.aktiv), abholenAb=str(s.abholen_ab or ""), passwortGesetzt=bool(s.get_password("passwort", raise_exception=False)),
		letzterAbruf=_iso(s.letzter_abruf), letzterFehler=s.letzter_fehler or "",
	)
	return out


@frappe.whitelist(methods=["POST"])
def einstellungen():
	frappe.only_for(MAIL_PFLEGE)
	return einstellungen_ui()


@frappe.whitelist(methods=["POST"])
def einstellungen_speichern(daten):
	"""Speichert die Einstellungen. Das Passwort nur, wenn eines eingegeben wurde; es wird nie zurückgegeben."""
	frappe.only_for(MAIL_PFLEGE)
	if isinstance(daten, str):
		daten = frappe.parse_json(daten)
	s = mail.einstellungen()
	for ui, feld in FELDER.items():
		if ui not in daten:
			continue
		wert = daten[ui]
		if feld in ("imap_port", "smtp_port"):
			wert = int(wert or 0) or None
		elif feld == "aktiv":
			wert = 1 if wert else 0
		elif feld == "stichwoerter":
			wert = "\n".join(z.strip() for z in (wert or "").splitlines() if z.strip())
		elif isinstance(wert, str):
			wert = wert.strip() or None
		s.set(feld, wert)
	if daten.get("passwort"):
		s.passwort = daten["passwort"]
	if s.aktiv and not mail.stichwoerter(s):
		frappe.throw(_("Bitte mindestens ein Stichwort für den Betreff eintragen."))
	s.save()
	return einstellungen_ui(s)


@frappe.whitelist(methods=["POST"])
def verbindung_testen():
	"""Meldet sich am Postfach an und öffnet den Ordner (nur lesend). Liefert die Zahl der passenden Mails."""
	frappe.only_for(MAIL_PFLEGE)
	s = mail.einstellungen()
	m = mail.imap_verbinden(s)
	try:
		typ, _a = m.select(mail.ordnername(s.postfach_ordner or "INBOX"), readonly=True)
		if typ != "OK":
			frappe.throw(_("Den Ordner {0} gibt es im Postfach nicht.").format(s.postfach_ordner or "INBOX"))
		passend = len(mail.suchen(m, mail.stichwoerter(s), s.abholen_ab)) if mail.stichwoerter(s) else 0
	finally:
		try:
			m.logout()
		except Exception:
			pass
	return {"ok": True, "passend": passend}
