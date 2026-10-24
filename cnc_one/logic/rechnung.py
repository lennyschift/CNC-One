"""Rechenregeln und Hilfen der Rechnung (ohne Datenbankzugriff, soweit möglich).

Ablauf: Entwurf (frei änderbar, ohne Nummer) -> Festschreiben (lückenlose Nummer, unveränderlich) -> Zahlungen -> Bezahlt.
Korrektur nur per Storno (Gutschrift mit eigener Nummer). Erstmal nur Inland 19 %.
"""

import hashlib
import json
from datetime import date, datetime, timedelta

from cnc_one.logic.kalkulation import _summe, r2

STEUERSATZ_STANDARD = 19.0
MAHNSTUFEN = ("Zahlungserinnerung", "1. Mahnung", "2. Mahnung")


def zeilenbetrag(menge, einzelpreis):
	return r2((menge or 0) * (einzelpreis or 0))


def summen(zeilen_netto, satz=STEUERSATZ_STANDARD):
	"""(netto, steuer, brutto) aus den Zeilenbeträgen. Die Steuer wird einmal auf die Summe gerechnet und auf Cent gerundet."""
	netto = r2(_summe(zeilen_netto))
	steuer = r2(netto * (satz or 0) / 100)
	return netto, steuer, r2(netto + steuer)


def _datum(wert):
	if isinstance(wert, datetime):
		return wert.date()
	if isinstance(wert, date):
		return wert
	return datetime.strptime(str(wert)[:10], "%Y-%m-%d").date()


def faellig_am(rechnungsdatum, tage):
	return _datum(rechnungsdatum) + timedelta(days=int(tage or 0))


def tage_ueberfaellig(faellig, heute=None):
	"""Wie viele Tage nach der Fälligkeit (negativ: noch nicht fällig)."""
	return ((heute and _datum(heute)) or date.today()).toordinal() - _datum(faellig).toordinal()


def naechste_mahnstufe(vorhandene):
	"""Nächste Mahnstufe nach den bisher angelegten (nicht zurückgezogenen); None, wenn alle Stufen durch sind."""
	for s in MAHNSTUFEN:
		if s not in vorhandene:
			return s
	return None


def inhalt_hash(inhalt):
	"""SHA-256 über den festgeschriebenen Inhalt (stabile JSON-Darstellung). Zeigt später, ob etwas verändert wurde."""
	text = json.dumps(inhalt, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iban_gueltig(iban):
	"""Prüft eine IBAN (Länge je Land bleibt unberücksichtigt, Prüfziffer nach ISO 13616 / Modulo 97)."""
	s = "".join((iban or "").split()).upper()
	if len(s) < 15 or len(s) > 34 or not s.isalnum():
		return False
	if s.startswith("DE") and len(s) != 22:
		return False
	umgestellt = s[4:] + s[:4]
	try:
		return int("".join(str(int(c, 36)) for c in umgestellt)) % 97 == 1
	except ValueError:
		return False


def iban_formatiert(iban):
	s = "".join((iban or "").split()).upper()
	return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


def euro(betrag):
	"""1234.5 -> '1.234,50 €'"""
	t = f"{(betrag or 0):,.2f}"
	return t.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def datum_de(wert):
	return _datum(wert).strftime("%d.%m.%Y") if wert else ""


def zuteilen(menge, freie):
	"""Verteilt `menge` auf Lieferscheinpositionen in der Reihenfolge der Liste. `freie`: [(schluessel, frei)].
	Liefert [(schluessel, zugeteilt)] und die nicht zugeteilte Restmenge (noch nicht geliefert)."""
	rest = int(menge or 0)
	out = []
	for schluessel, frei in freie:
		if rest <= 0:
			break
		n = min(rest, max(0, int(frei or 0)))
		if n > 0:
			out.append((schluessel, n))
			rest -= n
	return out, rest


def mahntext(stufe, rechnungsnummer, rechnungsdatum, brutto, offen, frist, gebuehr=0):
	"""Text der Mahnung. Sachlich und kurz, die Formulierungen sind Vorschläge."""
	kopf = f"zu unserer Rechnung {rechnungsnummer} vom {datum_de(rechnungsdatum)} über {euro(brutto)} konnten wir bis heute keinen vollständigen Zahlungseingang feststellen."
	betrag = f"Der offene Betrag beträgt {euro(offen)}."
	gebuehr_text = f" Zusätzlich berechnen wir eine Mahngebühr von {euro(gebuehr)}." if gebuehr else ""
	bis = f"Bitte überweisen Sie den Betrag bis zum {datum_de(frist)}."
	if stufe == "Zahlungserinnerung":
		return "\n".join([
			"Sehr geehrte Damen und Herren,", "", kopf + " Sicher handelt es sich um ein Versehen.", betrag, bis,
			"Sollte sich Ihre Zahlung mit diesem Schreiben überschnitten haben, betrachten Sie es bitte als gegenstandslos.",
		])
	if stufe == "1. Mahnung":
		return "\n".join([
			"Sehr geehrte Damen und Herren,", "", kopf + " Auch auf unsere Zahlungserinnerung haben wir keinen Zahlungseingang erhalten.",
			betrag + gebuehr_text, bis,
		])
	return "\n".join([
		"Sehr geehrte Damen und Herren,", "", kopf + " Trotz unserer bisherigen Schreiben ist der Betrag offen geblieben.",
		betrag + gebuehr_text, bis + " Andernfalls müssen wir weitere Schritte einleiten.",
	])
