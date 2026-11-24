"""Ähnliche Bauteile finden. Reine Funktionen (ohne Datenbank), getestet in tests/test_aehnlichkeit.py.

Bewertet werden, jeweils mit einem Grund für die Anzeige:
1. Teilenummer: anderer Index am Ende (4711-A → 4711-C), andere Baustufe vorne (8F8-1234 → P28-1234), eine Stelle
   anders, sonst allgemein ähnliche Nummer; dazu gleiche Zeichnung und ähnliche Bezeichnung.
2. Werkstoff und Rohteil: gleicher Werkstoff, Rohteil gleicher Form mit ähnlichen Maßen.
3. Geometrie: Fingerabdruck aus dem STEP-Modell (lib/geometrie.js): Maße entlang der Hauptachsen, Volumen, Füllgrad
   und die Verteilung der Abstände zwischen Punkten auf der Oberfläche (unabhängig von Lage und Größe).

Die Punkte liegen zwischen 0 und 1; ab SCHWELLE wird ein Bauteil vorgeschlagen.
"""

import math
import re
from difflib import SequenceMatcher

SCHWELLE = 0.45
TRENNER = re.compile(r"[\s\-_./]+")


def norm(s):
	"""Nummer ohne Leer- und Trennzeichen, klein: „ZN 3003-01“ = „zn3003.01“."""
	return TRENNER.sub("", (s or "").lower())


def segmente(s):
	return [x for x in TRENNER.split((s or "").strip().lower()) if x]


def stamm_index(nr):
	"""(Stamm, Index): ein bis zwei Buchstaben nach einer Ziffer am Ende sind der Index („4711-123B“ → 4711123, b),
	ebenso ein kurzes letztes Segment („4711-123-02“ → 4711123, 02)."""
	n = norm(nr)
	m = re.match(r"^(.*\d)([a-z]{1,2})$", n)
	if m:
		return m.group(1), m.group(2)
	s = segmente(nr)
	if len(s) >= 2 and len(s[-1]) <= 2 and len("".join(s[:-1])) >= 3:
		return "".join(s[:-1]), s[-1]
	return n, ""


def _gemeinsames_ende(a, b):
	n = 0
	while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
		n += 1
	return n


def nummer(a, b):
	"""Beziehung zweier Teilenummern: (Punkte, Grund) oder None."""
	na, nb = norm(a), norm(b)
	if len(na) < 3 or len(nb) < 3:
		return None
	if na == nb:
		return 1.0, "gleiche Teilenummer"
	sa, ia = stamm_index(a)
	sb, ib = stamm_index(b)
	if sa == sb and len(sa) >= 3:
		return 0.95, f"anderer Index ({(ia or '–').upper()} → {(ib or '–').upper()})"
	ga, gb = segmente(a), segmente(b)
	if len(ga) == len(gb) >= 2:
		anders = [i for i in range(len(ga)) if ga[i] != gb[i]]
		if anders == [0]:
			return 0.9, f"andere Baustufe ({ga[0].upper()} → {gb[0].upper()})"
		if len(anders) == 1:
			i = anders[0]
			return 0.8, f"eine Stelle anders ({ga[i].upper()} → {gb[i].upper()})"
	# ohne Trennzeichen: gleiches Ende, anderer kurzer Anfang (Baustufe)
	ende = _gemeinsames_ende(na, nb)
	if ende >= 5 and ende >= 0.6 * max(len(na), len(nb)) and len(na) - ende <= 4 and len(nb) - ende <= 4:
		return 0.85, f"andere Baustufe ({na[:len(na) - ende].upper() or '–'} → {nb[:len(nb) - ende].upper() or '–'})"
	q = SequenceMatcher(None, na, nb).ratio()
	if q >= 0.8 and min(len(na), len(nb)) >= 5:
		return round(q * 0.75, 3), "ähnliche Teilenummer"
	return None


WORT = re.compile(r"[a-zäöüß]{3,}")


def bezeichnung(a, b):
	"""Ähnliche Bezeichnung über gemeinsame Wörter: (Punkte, Grund) oder None."""
	wa, wb = set(WORT.findall((a or "").lower())), set(WORT.findall((b or "").lower()))
	if not wa or not wb:
		return None
	j = len(wa & wb) / len(wa | wb)
	if j >= 0.5 or (j >= 0.3 and any(len(w) >= 6 for w in wa & wb)):
		return round(0.3 + 0.25 * j, 3), "gleiche Bezeichnung" if j == 1 else "ähnliche Bezeichnung"
	return None


def _verh(a, b):
	a, b = abs(float(a or 0)), abs(float(b or 0))
	if a <= 0 or b <= 0:
		return 0.0
	return min(a, b) / max(a, b)


def roh_masse(r):
	"""Form und Maße eines Rohteils (Workbench-Feld roh): ('Rund', [Ø, L]) oder (Form, [größtes … kleinstes])."""
	if not isinstance(r, dict):
		return None
	f = r.get("form") or ""
	if f in ("Rund", "Rohr"):
		m = [r.get("durchmesser"), r.get("laenge")]
	elif f == "Sechskant":
		m = [r.get("schluesselweite"), r.get("laenge")]
	else:
		m = sorted((float(r.get(k) or 0) for k in ("laenge", "breite", "hoehe")), reverse=True)
	m = [float(x or 0) for x in m]
	return (f, m) if f and all(x > 0 for x in m) else None


def rohteil(a, b, toleranz=0.85):
	"""Rohteile gleicher Form mit Maßen innerhalb ±15 %: (Punkte, Grund) oder None."""
	ra, rb = roh_masse(a), roh_masse(b)
	if not ra or not rb or ra[0] != rb[0] or len(ra[1]) != len(rb[1]):
		return None
	v = [_verh(x, y) for x, y in zip(ra[1], rb[1])]
	if min(v) < toleranz:
		return None
	return round(0.25 + 0.15 * (sum(v) / len(v)), 3), f"ähnliches Rohteil ({ra[0]} {' × '.join(_z(x) for x in rb[1])})"


def _z(x):
	return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def geometrie(fa, fb):
	"""Vergleich zweier Fingerabdrücke: {form, groesse, gesamt} je 0…1, oder None."""
	if not isinstance(fa, dict) or not isinstance(fb, dict) or fa.get("v") != fb.get("v"):
		return None
	da, db = fa.get("d2") or [], fb.get("d2") or []
	if not da or len(da) != len(db):
		return None
	sa, sb = sum(da) or 1, sum(db) or 1
	verteilung = 1 - 0.5 * sum(abs(x / sa - y / sb) for x, y in zip(da, db))
	fuell = 1 - min(1.0, abs(float(fa.get("fuell") or 0) - float(fb.get("fuell") or 0)) * 2)
	form = 0.75 * verteilung + 0.25 * fuell
	ma, mb = fa.get("masse") or [], fb.get("masse") or []
	groessen = [_verh(x, y) for x, y in zip(ma, mb)] + [_verh(fa.get("volumen"), fb.get("volumen")) ** (1 / 3)]
	groesse = sum(groessen) / len(groessen) if groessen else 0
	return {"form": round(form, 3), "groesse": round(groesse, 3), "gesamt": round(0.6 * form + 0.4 * groesse, 3)}


def geometrie_grund(g):
	"""(Punkte, Grund) aus einem Geometrie-Vergleich oder None."""
	if not g:
		return None
	if g["form"] >= 0.9 and g["groesse"] >= 0.85:
		return round(0.4 + 0.55 * g["gesamt"], 3), f"ähnliche Geometrie ({round(g['gesamt'] * 100)} %)"
	if g["form"] >= 0.93:
		return 0.5, f"gleiche Form, andere Größe ({round(g['form'] * 100)} %)"
	return None


def bewerten(a, b):
	"""Wie ähnlich ist Bauteil b dem Bauteil a? a/b: {teilenummer, bezeichnung, zeichnungsnr, material, roh, geo}.
	Liefert (Punkte, [Gründe]); die stärkste Beziehung zählt, jede weitere erhöht etwas."""
	treffer = []
	for r in (
		nummer(a.get("teilenummer"), b.get("teilenummer")),
		(0.85, "gleiche Zeichnung") if norm(a.get("zeichnungsnr")) and norm(a.get("zeichnungsnr")) == norm(b.get("zeichnungsnr")) else None,
		bezeichnung(a.get("bezeichnung"), b.get("bezeichnung")),
		rohteil(a.get("roh"), b.get("roh")),
		geometrie_grund(geometrie(a.get("geo"), b.get("geo"))),
	):
		if r:
			treffer.append(r)
	gleicher_werkstoff = bool(a.get("material")) and (a.get("material") or "").lower() == (b.get("material") or "").lower()
	if not treffer:
		return 0.0, []
	treffer.sort(reverse=True)
	punkte = treffer[0][0] + 0.12 * sum(p for p, _g in treffer[1:]) + (0.08 if gleicher_werkstoff else 0)
	gruende = [g for _p, g in treffer] + (["gleicher Werkstoff"] if gleicher_werkstoff else [])
	return round(min(punkte, 0.99), 3), gruende


def finden(a, kandidaten, grenze=8, schwelle=SCHWELLE):
	"""Die ähnlichsten Kandidaten (Liste von dicts mit „name“) zu a: [(Punkte, Gründe, Kandidat)], beste zuerst."""
	out = []
	for b in kandidaten:
		p, g = bewerten(a, b)
		if p >= schwelle:
			out.append((p, g, b))
	out.sort(key=lambda x: (-x[0], x[2].get("name") or ""))
	return out[:grenze]


# ----------------------------------------------------------------- Teilefamilien vorschlagen
def familien_vorschlaege(bauteile):
	"""Gruppen von Bauteilen (ohne Familie), die Varianten eines Teils sein könnten: gleiche Zeichnung mit mehreren
	Teilenummern, oder gleicher Nummernstamm mit verschiedenem Index beim selben Kunden.
	bauteile: [{name, kunde, teilenummer, zeichnungsnr, teilefamilie}]. Liefert [{grund, schluessel, bauteile, varianten}]."""
	frei = [b for b in bauteile if not b.get("teilefamilie")]
	gruppen, vergeben = [], set()
	nach_zeichnung = {}
	for b in frei:
		z = norm(b.get("zeichnungsnr"))
		if len(z) >= 3:
			nach_zeichnung.setdefault(z, []).append(b)
	for z, liste in sorted(nach_zeichnung.items()):
		if len({norm(b.get("teilenummer")) for b in liste}) >= 2:
			gruppen.append({"grund": f"gleiche Zeichnung {liste[0].get('zeichnungsnr')}", "schluessel": f"z:{z}", "bauteile": liste})
			vergeben.update(b["name"] for b in liste)
	nach_stamm = {}
	for b in frei:
		if b["name"] in vergeben:
			continue
		s, i = stamm_index(b.get("teilenummer"))
		if i:
			nach_stamm.setdefault((b.get("kunde") or "", s), []).append(b)
	for (k, s), liste in sorted(nach_stamm.items()):
		if len(liste) >= 2:
			gruppen.append({"grund": f"gleiche Nummer, verschiedener Index ({', '.join(stamm_index(b.get('teilenummer'))[1].upper() for b in liste)})", "schluessel": f"s:{k}:{s}", "bauteile": liste})
	for g in gruppen:
		g["varianten"] = varianten_vorschlag([b.get("teilenummer") or "" for b in g["bauteile"]])
	return gruppen


def varianten_vorschlag(nummern):
	"""Je Teilenummer der Teil, der sich von den anderen unterscheidet (Vorschlag für das Feld „Variante“)."""
	stamm = [stamm_index(n) for n in nummern]
	if stamm and all(i for _s, i in stamm) and len({s for s, _i in stamm}) == 1:
		return [i.upper() for _s, i in stamm]
	segs = [segmente(n) for n in nummern]
	if segs and all(len(s) == len(segs[0]) for s in segs) and len(segs[0]) >= 2:
		anders = [i for i in range(len(segs[0])) if len({s[i] for s in segs}) > 1]
		if anders:
			return [" ".join(s[i].upper() for i in anders) for s in segs]
	return ["" for _n in nummern]
