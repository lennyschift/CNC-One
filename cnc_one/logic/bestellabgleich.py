"""Abgleich einer Bestellposition des Kunden mit dem, was wir angeboten haben.

Viele Kunden (z. B. mit SAP) können keine Rüst-, Mess- oder Sonderkosten bestellen. Sie legen die Kosten auf den
Stückpreis um und bestellen nur einen Stückpreis. Verglichen wird deshalb der Betrag der ganzen Position:

    angeboten = Stückpreis × Menge + einmalige Kosten
    bestellt  = Stückpreis laut Bestellung × Menge (+ eigene Kostenzeilen der Bestellung)

Liegt der Unterschied innerhalb der Toleranz (Rundung des umgelegten Stückpreises auf Cent und der eingestellte
Prozentsatz), passt die Bestellung. Das Ergebnis sagt auch, wie sie passt: gleich wie angeboten oder umgelegt.
"""

from cnc_one.logic.beleg import optionen, position_fuer_auftrag
from cnc_one.logic.kalkulation import berechne, num, r2

GLEICH = "gleich"  # Stückpreis und Kosten wie angeboten
UMGELEGT = "umgelegt"  # Kosten im Stückpreis der Bestellung enthalten, Betrag passt
ABWEICHEND = "abweichend"  # Betrag weicht über die Toleranz hinaus ab
OHNE_PREIS = "ohne_preis"  # die Bestellung nennt keinen Preis
OHNE_VERGLEICH = "ohne_vergleich"  # nichts angeboten, womit sich vergleichen ließe


def toleranz(menge, betrag, prozent):
	"""Erlaubter Unterschied in Euro: Rundung des Stückpreises (je Stück bis 0,5 Cent) oder der Prozentsatz vom Betrag."""
	return max(0.005 * max(1, num(menge)) + 0.01, abs(num(betrag)) * num(prozent) / 100)


def vergleichen(erwartet, menge, preis, kosten_bestellt=0, prozent=0.5):
	"""Eine Bestellposition gegen die angebotene Position (`erwartet`: Ergebnis von position_fuer_auftrag).

	`preis`: Stückpreis laut Bestellung (schon durch die Preiseinheit geteilt), `kosten_bestellt`: eigene Kostenzeilen
	der Bestellung zu dieser Position. Liefert { status, angeboten, bestellt, differenz, umgelegt, toleranz, hinweis }.
	"""
	menge = max(1, int(num(menge) or erwartet.get("menge") or 1))
	kosten = r2(sum(num(k["betrag"]) for k in erwartet.get("kosten") or []))
	einzel = r2(num(erwartet.get("einzelpreis")))
	angeboten = r2(einzel * menge + kosten)
	umgelegt = r2(angeboten / menge)
	if preis in (None, "") or num(preis) <= 0:
		return {"status": OHNE_PREIS, "angeboten": angeboten, "bestellt": None, "differenz": None, "umgelegt": umgelegt, "toleranz": 0, "hinweis": ""}
	preis = num(preis)
	bestellt = r2(preis * menge + num(kosten_bestellt))
	differenz = r2(bestellt - angeboten)
	tol = r2(toleranz(menge, angeboten, prozent))
	gleich_einzel = abs(preis - einzel) < 0.005
	hinweis = ""
	if abs(differenz) <= tol:
		# ohne Kosten oder mit eigenen Kostenzeilen in der Bestellung: wie angeboten; sonst stecken die Kosten im Stückpreis
		status = GLEICH if not kosten or num(kosten_bestellt) else UMGELEGT
		if status == UMGELEGT:
			hinweis = f"Kosten ({_eur(kosten)}) auf den Stückpreis umgelegt: {_eur(umgelegt)} je Stück"
		elif kosten and num(kosten_bestellt):
			hinweis = "Stückpreis und Kosten wie angeboten"
	else:
		status = ABWEICHEND
		if gleich_einzel and kosten and not num(kosten_bestellt):
			hinweis = f"Stückpreis wie angeboten, die Kosten ({_eur(kosten)}) fehlen in der Bestellung"
		elif kosten:
			hinweis = f"Erwartet {_eur(einzel)} je Stück plus {_eur(kosten)} Kosten oder umgelegt {_eur(umgelegt)} je Stück"
		else:
			hinweis = f"Erwartet {_eur(einzel)} je Stück"
	return {"status": status, "angeboten": angeboten, "bestellt": bestellt, "differenz": differenz, "umgelegt": umgelegt, "toleranz": tol, "hinweis": hinweis}


def regulaere_option(teil, ergebnis, menge):
	"""Die Staffel, die zur bestellten Menge gehört: die größte, deren Menge erreicht ist, sonst die kleinste."""
	opts = optionen(teil, ergebnis)
	passend = [o for o in opts if num(o["menge"]) <= num(menge)]
	return (max(passend, key=lambda o: num(o["menge"])) if passend else min(opts, key=lambda o: num(o["menge"])))["id"]


def mit_angebot(teil, menge, preis, kosten_bestellt=0, prozent=0.5):
	"""Abgleich gegen eine Angebotsposition (Kalkulation `teil`). Bei Staffeln gilt die Staffel zur Menge; passt der
	Preis zu einer anderen Staffel, wird diese vorgeschlagen und im Hinweis genannt.

	Liefert { optionId, erwartet: { menge, einzelpreis, kosten, summe, staffelMenge }, abgleich }."""
	ergebnis = berechne(teil)
	regulaer = regulaere_option(teil, ergebnis, menge)

	def fuer(option_id):
		e = position_fuer_auftrag(teil, ergebnis, option_id, menge)
		return option_id, e, vergleichen(e, menge, preis, kosten_bestellt, prozent)

	gewaehlt = fuer(regulaer)
	if gewaehlt[2]["status"] == ABWEICHEND and len(optionen(teil, ergebnis)) > 1:
		andere = [fuer(o["id"]) for o in optionen(teil, ergebnis) if o["id"] != regulaer]
		passt = [x for x in andere if x[2]["status"] in (GLEICH, UMGELEGT)]
		if passt:
			gewaehlt = passt[0]
			gewaehlt[2]["hinweis"] = (f"Preis der Staffel {gewaehlt[1]['staffelMenge']} Stk (bestellt {int(num(menge))} Stk). " + gewaehlt[2]["hinweis"]).strip()
	option_id, e, abgleich = gewaehlt
	return {
		"optionId": option_id,
		"erwartet": {k: e[k] for k in ("menge", "einzelpreis", "kosten", "summe", "staffelMenge")},
		"abgleich": abgleich,
	}


def _eur(x):
	return f"{num(x):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
