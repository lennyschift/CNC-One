"""Anfragen aus dem gemeinsamen Postfach holen (IMAP).

Geholt werden nur Mails mit einem Stichwort im Betreff. Die Suche läuft auf dem Mailserver, andere Mails werden gar nicht
übertragen. Das Postfach bleibt unverändert: Der Ordner wird nur lesend geöffnet, Mails bleiben ungelesen.
Antwortet ein Kunde im Verlauf, kommt seine Mail zur bestehenden Anfrage.
"""

import base64
import email
import hashlib
import imaplib
import io
import json
import re
import smtplib
import ssl
import time
import zipfile
from email.policy import default as POLICY
from email.utils import getaddresses, parsedate_to_datetime
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import get_system_timezone, getdate, now_datetime

# Bei diesen Anbietern sagt die Domain nichts über den Kunden
FREEMAIL = {
	"gmail.com", "googlemail.com", "web.de", "gmx.de", "gmx.net", "gmx.at", "t-online.de", "outlook.com", "outlook.de",
	"hotmail.com", "hotmail.de", "live.com", "live.de", "yahoo.com", "yahoo.de", "icloud.com", "me.com", "aol.com",
	"freenet.de", "posteo.de", "mailbox.org", "arcor.de", "online.de", "ionos.de",
}
MONATE = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MAX_TEXT = 200_000
MAX_HTML = 500_000
# Aus ZIP-Anhängen werden Zeichnungen und CAD-Dateien übernommen, der Rest bleibt in der ZIP
AUS_ZIP = ("pdf", "stp", "step", "igs", "iges", "dxf", "dwg")
ZIP_MAX_DATEIEN = 500
ZIP_MAX_MB = 500
ZIP_BALLAST = (".ds_store", "thumbs.db", "desktop.ini")


def einstellungen():
	return frappe.get_single("Mail Einstellungen")


def stichwoerter(s):
	return [z.strip() for z in (s.stichwoerter or "").splitlines() if z.strip()]


# ----------------------------------------------------------------- Verbindung
def _ssl():
	return ssl.create_default_context()


def imap_verbinden(s):
	"""Angemeldete IMAP-Verbindung mit den Einstellungen."""
	if not (s.imap_server and s.benutzer):
		frappe.throw(_("Bitte zuerst Server und Benutzer des Postfachs eintragen."))
	passwort = s.get_password("passwort", raise_exception=False)
	if not passwort:
		frappe.throw(_("Bitte zuerst das Passwort des Postfachs eintragen."))
	port = int(s.imap_port or (993 if s.verschluesselung == "SSL/TLS" else 143))
	if s.verschluesselung == "SSL/TLS":
		m = imaplib.IMAP4_SSL(s.imap_server, port, ssl_context=_ssl(), timeout=30)
	else:
		m = imaplib.IMAP4(s.imap_server, port, timeout=30)
		if s.verschluesselung == "STARTTLS":
			m.starttls(_ssl())
	m.login(s.benutzer, passwort)
	return m


def ordnername(name):
	"""Ordnername für IMAP: in Anführungszeichen, Umlaute als modifiziertes UTF-7 (RFC 3501)."""
	out, puffer = [], ""

	def leeren():
		nonlocal puffer
		if puffer:
			b = base64.b64encode(puffer.encode("utf-16-be")).decode().rstrip("=").replace("/", ",")
			out.append(f"&{b}-")
			puffer = ""

	for z in name or "INBOX":
		if 0x20 <= ord(z) <= 0x7E:
			leeren()
			out.append("&-" if z == "&" else z)
		else:
			puffer += z
	leeren()
	return '"' + "".join(out).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_datum(d):
	"""Datum für IMAP SINCE („01-Nov-2026“). Frappe liefert gespeicherte Datumsfelder auch als Text („2026-11-01“)."""
	d = getdate(d)
	return f"{d.day:02d}-{MONATE[d.month - 1]}-{d.year}"


def suchen(m, woerter, ab=None):
	"""UIDs der Mails, deren Betreff eines der Stichwörter enthält (Suche auf dem Server)."""
	uids = set()
	datum = ["SINCE", _imap_datum(ab)] if ab else []
	for w in woerter:
		if w.isascii():
			_typ, daten = m.uid("SEARCH", *datum, "SUBJECT", '"' + w.replace("\\", "\\\\").replace('"', '\\"') + '"')
		else:
			m.literal = w.encode("utf-8")
			_typ, daten = m.uid("SEARCH", "CHARSET", "UTF-8", *datum, "SUBJECT")
		for u in (daten[0] or b"").split():
			uids.add(int(u))
	return sorted(uids)


def kopfzeilen(m, uids):
	"""{ uid: (message_id, absender) } aus den Kopfzeilen, ohne die Mails zu laden."""
	out = {}
	if not uids:
		return out
	_typ, daten = m.uid("FETCH", ",".join(str(u) for u in uids), "(UID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID FROM)])")
	for teil in daten:
		if not isinstance(teil, tuple):
			continue
		treffer = re.search(rb"UID (\d+)", teil[0])
		if not treffer:
			continue
		kopf = email.message_from_bytes(teil[1], policy=POLICY)
		out[int(treffer.group(1))] = ((kopf.get("Message-ID") or "").strip(), absender(kopf.get("From"))[1])
	return out


def absender(wert):
	"""(Name, Adresse) des Absenders; die erste Angabe mit @, auch bei einem Komma im Namen ohne Anführungszeichen."""
	paare = getaddresses([str(wert or "")])
	for i, (name, adresse) in enumerate(paare):
		if "@" in adresse:
			vorher = [n or a for n, a in paare[:i] if "@" not in a]
			return (", ".join([*vorher, name]) if vorher and name else name or ", ".join(vorher)).strip(), adresse.lower()
	return "", ""


def laden(m, uid):
	_typ, daten = m.uid("FETCH", str(uid), "(BODY.PEEK[])")
	for teil in daten:
		if isinstance(teil, tuple):
			return teil[1]
	return None


def smtp_senden(s, msg, empfaenger):
	"""Verschickt die Mail über den SMTP-Server des Postfachs."""
	if not (s.smtp_server and s.benutzer):
		frappe.throw(_("Bitte zuerst den SMTP-Server und den Benutzer des Postfachs eintragen."))
	passwort = s.get_password("passwort", raise_exception=False)
	if not passwort:
		frappe.throw(_("Bitte zuerst das Passwort des Postfachs eintragen."))
	port = int(s.smtp_port or (465 if s.verschluesselung == "SSL/TLS" else 587))
	if s.verschluesselung == "SSL/TLS":
		k = smtplib.SMTP_SSL(s.smtp_server, port, context=_ssl(), timeout=30)
	else:
		k = smtplib.SMTP(s.smtp_server, port, timeout=30)
		if s.verschluesselung == "STARTTLS":
			k.starttls(context=_ssl())
	try:
		k.login(s.benutzer, passwort)
		k.send_message(msg, from_addr=s.benutzer, to_addrs=empfaenger)
	finally:
		try:
			k.quit()
		except Exception:
			pass


def gesendet_ablegen(s, msg):
	"""Legt eine Kopie in den Gesendet-Ordner (gelesen). Liefert "" oder einen Hinweis; verschickt ist die Mail so oder so."""
	ordner = s.gesendet_ordner or "Sent"
	try:
		m = imap_verbinden(s)
		try:
			typ, daten = m.append(ordnername(ordner), r"(\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
		finally:
			try:
				m.logout()
			except Exception:
				pass
		if typ != "OK":
			return _("Die Kopie liegt nicht im Ordner „{0}“: {1}").format(ordner, (daten[0] or b"").decode(errors="replace")[:200])
	except Exception as e:
		frappe.clear_messages()
		return _("Die Kopie liegt nicht im Ordner „{0}“: {1}").format(ordner, str(e)[:200])
	return ""


# ----------------------------------------------------------------- Abholen
def abholen(s=None):
	"""Holt neue Anfragen. Liefert die Anzahl der neu angelegten Anfragen und Antworten im Verlauf."""
	from frappe.utils.synchronization import filelock

	s = s or einstellungen()
	woerter = stichwoerter(s)
	if not woerter:
		frappe.throw(_("Bitte mindestens ein Stichwort für den Betreff eintragen."))
	neu = 0
	with filelock("cnc_one_mail_abruf", timeout=60):
		m = imap_verbinden(s)
		try:
			typ, _antwort = m.select(ordnername(s.postfach_ordner or "INBOX"), readonly=True)
			if typ != "OK":
				frappe.throw(_("Den Ordner {0} gibt es im Postfach nicht.").format(s.postfach_ordner or "INBOX"))
			kandidaten = kopfzeilen(m, suchen(m, woerter, s.abholen_ab))
			bekannt = set(frappe.get_all("Mail Nachricht", filters={"message_id": ["in", [mid for mid, _v in kandidaten.values() if mid] or [""]]}, pluck="message_id"))
			eigene = (s.benutzer or "").lower()
			for uid, (mid, von) in kandidaten.items():
				if (mid and mid in bekannt) or von == eigene:
					continue
				roh = laden(m, uid)
				if roh and verarbeiten(roh):
					neu += 1
				frappe.db.commit()
		finally:
			try:
				m.logout()
			except Exception:
				pass
	frappe.db.set_single_value("Mail Einstellungen", {"letzter_abruf": now_datetime(), "letzter_fehler": ""})
	frappe.db.commit()
	return neu


def geplant():
	"""Alle 5 Minuten (Scheduler), nur wenn eingeschaltet. Fehler landen in den Einstellungen und im Fehlerprotokoll."""
	s = einstellungen()
	if not s.aktiv:
		return
	try:
		abholen(s)
	except Exception as e:
		frappe.db.rollback()
		frappe.db.set_single_value("Mail Einstellungen", {"letzter_abruf": now_datetime(), "letzter_fehler": str(e)[:1000]})
		frappe.db.commit()
		frappe.log_error(title="CNC One: Mail-Abruf")


# ----------------------------------------------------------------- Eine Mail verarbeiten
def _datum(msg):
	try:
		d = parsedate_to_datetime(str(msg.get("Date")))
	except (TypeError, ValueError):
		return now_datetime()
	if d.tzinfo:
		d = d.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)
	return d


def _adressen(wert):
	return ", ".join(f"{n} <{a}>" if n else a for n, a in getaddresses([str(wert)]) if a) if wert else ""


def _inhalt(teil):
	try:
		return teil.get_content()
	except (LookupError, UnicodeDecodeError):
		return (teil.get_payload(decode=True) or b"").decode("utf-8", "replace")


def _roh_html(msg):
	teil = msg.get_body(preferencelist=("html",))
	return _inhalt(teil) if teil is not None else ""


def html_zu_text(html):
	"""Text aus HTML; jede Tabellenzeile bleibt eine Zeile (Zellen mit | getrennt), damit Teilenummer und Menge zusammenstehen."""
	from bs4 import BeautifulSoup
	from frappe.core.utils import html_to_plain_text

	soup = BeautifulSoup(html or "", "html.parser")
	for tr in soup.find_all("tr"):
		zellen = [" ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["td", "th"])]
		neu = soup.new_tag("p")
		neu.string = " | ".join(zellen) if any(zellen) else ""
		tr.replace_with(neu)
	for t in soup.find_all(["table", "tbody", "thead"]):
		t.unwrap()
	return html_to_plain_text(str(soup))


def _text(msg):
	html = _roh_html(msg)
	if html:
		inhalt = html_zu_text(html)
	else:
		teil = msg.get_body(preferencelist=("plain",))
		inhalt = _inhalt(teil) if teil is not None else ""
	return re.sub(r"\n{3,}", "\n\n", inhalt.replace("\r\n", "\n")).strip()[:MAX_TEXT]


def html_bereinigen(html, bilder=None):
	"""HTML einer Mail sicher machen: ohne Skripte und Ereignisse (Frappe/nh3), ohne Stylesheets und Bilder fremder Server.
	Eingebettete Bilder (cid:) zeigen auf die gespeicherten Dateien in `bilder` { cid: url }. Liefert den Inhalt des body."""
	from bs4 import BeautifulSoup
	from frappe.utils.html_utils import sanitize_html

	soup = BeautifulSoup(sanitize_html(html or "", always_sanitize=True), "html.parser")
	for t in soup.find_all(["link", "meta", "base", "title", "head"]):
		t.decompose()
	for img in soup.find_all("img"):
		src = (img.get("src") or "").strip()
		url = (bilder or {}).get(src[4:].strip("<>")) if src.lower().startswith("cid:") else None
		if url:
			img["src"] = url
		elif not src.startswith("data:image/"):
			img.decompose()
	for t in soup.find_all(style=True):
		if "url(" in t["style"].lower():
			t["style"] = re.sub(r"url\([^)]*\)", "none", t["style"], flags=re.I)
	for t in soup.find_all(background=True):
		del t["background"]
	koerper = soup.body.decode_contents() if soup.body else str(soup)
	return koerper.strip()[:MAX_HTML]


def tabellen(html):
	"""Tabellen einer Mail als Zeilen mit Zellentexten (für Teilenummer und Menge). Äußere Layout-Tabellen fallen weg."""
	from bs4 import BeautifulSoup

	out = []
	for t in BeautifulSoup(html or "", "html.parser").find_all("table"):
		if t.find("table"):
			continue
		zeilen = [z for z in _raster(t) if any(z)]
		if len(zeilen) >= 2:
			out.append(zeilen)
	return out


def _spannweite(zelle, attr):
	try:
		return max(1, min(50, int(zelle.get(attr) or 1)))
	except ValueError:
		return 1


def _raster(tabelle):
	"""Zellentexte als gleichmäßiges Raster: eine über mehrere Spalten verbundene Zelle (colspan) belegt alle ihre
	Spalten (Text in der ersten, die übrigen leer), eine über Zeilen verbundene (rowspan) gilt auch in den Zeilen darunter."""
	zeilen, offen = [], {}  # offen: Spalte -> [verbleibende Zeilen, Text]
	for tr in tabelle.find_all("tr"):
		z, spalte = [], 0
		zellen = iter(tr.find_all(["td", "th"]))
		zelle = next(zellen, None)
		while zelle is not None or any(s >= spalte for s in offen):
			if spalte in offen:
				rest, text = offen[spalte]
				z.append(text)
				offen[spalte] = [rest - 1, text]
				if rest - 1 <= 0:
					del offen[spalte]
				spalte += 1
				continue
			if zelle is None:
				z.append("")
				spalte += 1
				continue
			text = " ".join(zelle.get_text(" ", strip=True).split())
			breit, hoch = _spannweite(zelle, "colspan"), _spannweite(zelle, "rowspan")
			for i in range(breit):
				z.append(text if i == 0 else "")
				if hoch > 1:
					offen[spalte + i] = [hoch - 1, text if i == 0 else ""]
			spalte += breit
			zelle = next(zellen, None)
		zeilen.append(z)
	breite = max((len(z) for z in zeilen), default=0)
	return [z + [""] * (breite - len(z)) for z in zeilen]


def _inline_bilder(msg):
	"""(cid, Dateiname, Inhalt) der eingebetteten Bilder (z. B. Screenshots im Text)."""
	out = []
	for teil in msg.walk():
		cid = (teil.get("Content-ID") or "").strip().strip("<>")
		if cid and teil.get_content_type().startswith("image/") and teil.get_content_disposition() != "attachment":
			inhalt = teil.get_payload(decode=True)
			if inhalt:
				endung = teil.get_content_subtype().replace("jpeg", "jpg")
				out.append((cid, teil.get_filename() or f"bild-{len(out) + 1}.{endung}", inhalt))
	return out


def _anhaenge(msg):
	"""(Dateiname, Inhalt) der Anhänge. Bilder aus der Signatur (eingebettet, ohne Anhang-Kennzeichen) bleiben weg."""
	out = []
	for teil in msg.iter_attachments():
		name = teil.get_filename()
		typ = teil.get_content_type()
		if not name or typ == "message/rfc822":
			continue
		if typ.startswith("image/") and teil.get("Content-ID") and teil.get_content_disposition() != "attachment":
			continue
		inhalt = teil.get_payload(decode=True)
		if inhalt:
			out.append((name, inhalt))
	return out


def _zip_name(info):
	"""Pfad im ZIP mit richtigen Umlauten: ohne UTF-8-Kennzeichen steht er im DOS-Zeichensatz (deutsches Windows: cp850)."""
	if info.flag_bits & 0x800:
		return info.filename
	roh = info.filename.encode("cp437")
	try:
		return roh.decode("utf-8")
	except UnicodeDecodeError:
		return roh.decode("cp850")


def zip_auspacken(name, inhalt, tiefe=0):
	"""Dateien aus einem ZIP-Anhang: ([(dateiname, ordner, inhalt)], [hinweise]).

	Pfade aus dem Archiv werden nie als Pfad benutzt: Es zählt nur der Dateiname, dazu der letzte Ordner (oft die
	Teilenummer, wenn die Dateien nur „Zeichnung.pdf“ und „Modell.stp“ heißen). Eine ZIP in der ZIP wird eine Ebene
	tief mit ausgepackt; ihr Name gilt dann als Ordner."""
	try:
		z = zipfile.ZipFile(io.BytesIO(inhalt))
		infos = [i for i in z.infolist() if not i.is_dir()]
	except (zipfile.BadZipFile, ValueError):
		return [], [_("{0}: kein gültiges ZIP-Archiv, nicht ausgepackt").format(name)]
	if len(infos) > ZIP_MAX_DATEIEN or sum(i.file_size for i in infos) > ZIP_MAX_MB * 1024 * 1024:
		return [], [_("{0}: zu groß zum Auspacken (höchstens {1} Dateien und {2} MB)").format(name, ZIP_MAX_DATEIEN, ZIP_MAX_MB)]
	out, hinweise, rest = [], [], []
	for i in infos:
		teile = [t for t in _zip_name(i).replace("\\", "/").split("/") if t not in ("", ".", "..")]
		if not teile or any(t.lower() == "__macosx" for t in teile):
			continue
		datei, ordner = teile[-1], teile[-2] if len(teile) > 1 else ""
		if datei.startswith("._") or datei.lower() in ZIP_BALLAST:
			continue
		endung = datei.rsplit(".", 1)[-1].lower() if "." in datei else ""
		if i.flag_bits & 0x1:
			hinweise.append(_("{0}: {1} ist verschlüsselt, nicht ausgepackt").format(name, datei))
			continue
		try:
			if endung == "zip" and tiefe == 0:
				innen, h = zip_auspacken(datei, z.read(i), tiefe=1)
				out += [(n, o or datei.rsplit(".", 1)[0], x) for n, o, x in innen]
				hinweise += h
			elif endung in AUS_ZIP:
				out.append((datei, ordner, z.read(i)))
			else:
				rest.append(datei)
		except (zipfile.BadZipFile, NotImplementedError, OSError, EOFError) as e:
			hinweise.append(_("{0}: {1} nicht lesbar ({2})").format(name, datei, str(e)[:100]))
	if rest:
		hinweise.append(_("{0}: in der ZIP belassen: {1}").format(name, ", ".join(rest[:10]) + (" …" if len(rest) > 10 else "")))
	return out, hinweise


def _ids(*werte):
	return [x for w in werte if w for x in re.findall(r"<[^>]+>", str(w))]


def kunde_zur_adresse(adresse):
	"""Kunde, bei dem diese Adresse als Kontakt hinterlegt ist."""
	if not adresse:
		return None
	r = frappe.db.sql("select parent from `tabKunde Kontakt` where parenttype = 'Kunde' and lower(email) = %s limit 1", adresse.lower())
	return r[0][0] if r else None


def kunde_vorschlag(adresse):
	"""Kunde mit einem Kontakt derselben Domain (nicht bei Freemail-Anbietern)."""
	domain = (adresse or "").rsplit("@", 1)[-1].lower()
	if not domain or "@" not in (adresse or "") or domain in FREEMAIL:
		return None
	r = frappe.db.sql("select parent from `tabKunde Kontakt` where parenttype = 'Kunde' and lower(email) like %s limit 1", "%@" + domain)
	return r[0][0] if r else None


def _verlauf(ids):
	"""Bestehende Anfrage, zu deren Verlauf eine der Message-IDs gehört."""
	if not ids:
		return None
	r = frappe.get_all("Mail Nachricht", filters={"message_id": ["in", ids], "parenttype": "Mail Anfrage"}, pluck="parent", limit=1)
	return r[0] if r else None


def verarbeiten(roh):
	"""Legt eine Mail als Anfrage an oder hängt sie an den Verlauf einer bestehenden. Liefert die Anfrage oder None (schon da)."""
	msg = email.message_from_bytes(roh, policy=POLICY)
	mid = (msg.get("Message-ID") or "").strip() or f"<ohne-id-{hashlib.sha1(roh).hexdigest()}@cnc-one>"
	if frappe.db.exists("Mail Nachricht", {"message_id": mid}):
		return None
	von_name, von = absender(msg.get("From"))
	betreff = str(msg.get("Subject") or "").strip()
	datum = _datum(msg)
	in_reply_to = (msg.get("In-Reply-To") or "").strip()
	referenzen = str(msg.get("References") or "").strip()
	zeile = {
		"richtung": "Eingang", "datum": datum, "von_email": von, "von_name": von_name, "an": _adressen(msg.get("To")),
		"cc": _adressen(msg.get("Cc")), "betreff": betreff, "message_id": mid, "in_reply_to": in_reply_to,
		"referenzen": referenzen, "text": _text(msg),
	}

	bestehend = _verlauf(_ids(in_reply_to, referenzen))
	if bestehend:
		doc = frappe.get_doc("Mail Anfrage", bestehend)
		if doc.status == "Keine Anfrage":
			# Verlauf wurde verworfen: nur merken, dass es die Mail gibt
			doc.append("nachrichten", {**zeile, "text": ""})
			doc.save(ignore_permissions=True)
			return None
		doc.neue_antwort = 1
		doc.letzte_nachricht = datum
		doc.append("nachrichten", zeile)
		doc.save(ignore_permissions=True)
	else:
		kunde = kunde_zur_adresse(von)
		doc = frappe.get_doc({
			"doctype": "Mail Anfrage", "status": "Neu", "betreff": betreff, "von_email": von, "von_name": von_name,
			"datum": datum, "letzte_nachricht": datum, "kunde": kunde, "kunde_vorschlag": None if kunde else kunde_vorschlag(von),
		})
		doc.append("nachrichten", zeile)
		doc.insert(ignore_permissions=True)

	anhaenge, hinweise = [], []
	for name, inhalt in _anhaenge(msg):
		# Die ZIP bleibt als Original erhalten, ihre Zeichnungen und Modelle kommen als eigene Anhänge dazu (mit Herkunft)
		dateien = [(name, inhalt, {})]
		if name.lower().endswith(".zip"):
			ausgepackt, h = zip_auspacken(name, inhalt)
			hinweise += h
			dateien += [(n, x, {"aus": name, "ordner": o}) for n, o, x in ausgepackt]
		for dateiname, daten, herkunft in dateien:
			# abgelegt mit dem Ordner im Namen: "4711-A Zeichnung.pdf" statt vieler gleicher "Zeichnung.pdf"
			ordner = herkunft.get("ordner") or ""
			ablage = f"{ordner} {dateiname}" if ordner and ordner.lower() not in dateiname.lower() else dateiname
			try:
				f = frappe.get_doc({"doctype": "File", "file_name": ablage, "attached_to_doctype": "Mail Anfrage", "attached_to_name": doc.name, "is_private": 1, "content": daten})
				f.insert(ignore_permissions=True)
				anhaenge.append({"name": dateiname, "url": f.file_url, "groesse": len(daten), **herkunft})
			except Exception as e:  # zu groß, beschädigtes PDF usw.: die Anfrage kommt trotzdem
				frappe.clear_messages()
				hinweise.append(_("{0} nicht übernommen: {1}").format(dateiname, frappe.utils.strip_html(str(e))[:200]))
	roh = _roh_html(msg)
	bilder = {}
	if roh:
		for cid, name, inhalt in _inline_bilder(msg):
			if f"cid:{cid}" not in roh:
				continue
			try:
				f = frappe.get_doc({"doctype": "File", "file_name": name, "attached_to_doctype": "Mail Anfrage", "attached_to_name": doc.name, "is_private": 1, "content": inhalt})
				bilder[cid] = f.insert(ignore_permissions=True).file_url
			except Exception:
				frappe.clear_messages()
	html = html_bereinigen(roh, bilder) if roh else ""
	if anhaenge or hinweise or html:
		z = next(x for x in doc.nachrichten if x.message_id == mid)
		z.db_set({"anhaenge": json.dumps(anhaenge, ensure_ascii=False), "hinweis": "\n".join(hinweise), "html": html}, update_modified=False)
	return doc
