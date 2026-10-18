"""Seriennummern: fortlaufende Bereiche je Auftragsposition. Reine Zahlen ohne Präfix.

Der Kunde nennt die Nummern bei der Bestellung, sie laufen ohne Lücke von der Startnummer an. Die höchste vergebene
Nummer wird am Bauteil festgehalten, damit der nächste Auftrag dort weitermachen kann.
"""


STANDARD_STELLEN = 4


def hoechste(stellen):
	"""Größte Nummer, die in `stellen` Stellen passt (4 Stellen: 9999)."""
	return 10 ** int(stellen or STANDARD_STELLEN) - 1


def formatiert(nr, stellen=STANDARD_STELLEN):
	"""Seriennummern stehen immer mit führenden Nullen da: 1 wird 0001, 10 wird 0010."""
	return str(int(nr)).zfill(int(stellen or STANDARD_STELLEN)) if nr else ""


def bereich(start, menge):
	"""(von, bis) einer Auftragsposition mit `menge` Stück ab der Startnummer."""
	von = int(start or 0)
	return von, von + max(0, int(menge or 0)) - 1


def ueberschneidet(a, b):
	"""Teilen sich zwei Bereiche (von, bis) mindestens eine Nummer?"""
	return a[0] <= b[1] and b[0] <= a[1]


def erledigt(von, bis, gebucht):
	"""Die ersten `gebucht` Nummern des Bereichs sind angebracht. Liefert (von, bis) der erledigten Nummern oder None."""
	n = min(max(0, int(gebucht or 0)), bis - von + 1) if von and bis else 0
	return (von, von + n - 1) if n > 0 else None


def offen(von, bis, gebucht):
	"""Der Rest des Bereichs, der noch fehlt, oder None."""
	if not (von and bis):
		return None
	n = min(max(0, int(gebucht or 0)), bis - von + 1)
	return (von + n, bis) if von + n <= bis else None
