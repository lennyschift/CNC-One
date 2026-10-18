// Seriennummern: fortlaufende Bereiche je Auftragsposition. Spiegel von cnc_one/logic/serien.py, getestet in serien.test.js.
// Seriennummern bestehen nur aus Ziffern und stehen immer mit führenden Nullen in der Stellenzahl des Bauteils da (0001, 0010).

export const STANDARD_STELLEN = 4;

// Größte Nummer, die in `stellen` Stellen passt (4 Stellen: 9999).
export const hoechste = (stellen = STANDARD_STELLEN) => 10 ** stellen - 1;

// 1 wird 0001, "10" wird 0010. Leere Eingaben bleiben leer.
export function formatNr(nr, stellen = STANDARD_STELLEN) {
  const ziffern = String(nr ?? '').replace(/\D/g, '');
  if (!ziffern) return '';
  return ziffern.replace(/^0+(?=\d)/, '').padStart(stellen, '0');
}

export function bereichText(von, bis, stellen = STANDARD_STELLEN) {
  if (!von || !bis) return '';
  return von === bis ? formatNr(von, stellen) : `${formatNr(von, stellen)}–${formatNr(bis, stellen)}`;
}

// Die ersten `gebucht` Nummern des Bereichs sind angebracht (Überproduktion bekommt keine Nummer).
export function erledigt(von, bis, gebucht) {
  if (!von || !bis) return null;
  const n = Math.min(Math.max(0, Math.floor(Number(gebucht) || 0)), bis - von + 1);
  return n > 0 ? { von, bis: von + n - 1 } : null;
}

// Der Rest des Bereichs, der noch fehlt.
export function offen(von, bis, gebucht) {
  if (!von || !bis) return null;
  const n = Math.min(Math.max(0, Math.floor(Number(gebucht) || 0)), bis - von + 1);
  return von + n <= bis ? { von: von + n, bis } : null;
}

// Bereich einer Position ab der Startnummer (nur Ziffern).
export const bereich = (start, menge) => {
  const ziffern = String(start ?? '').trim();
  const von = /^\d+$/.test(ziffern) ? Number(ziffern) : 0;
  const m = Math.max(0, Math.floor(Number(menge) || 0));
  return von > 0 && m > 0 ? { von, bis: von + m - 1 } : null;
};
