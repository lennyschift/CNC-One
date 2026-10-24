// Wo steht ein Auftrag im Ablauf? Ein Haken gibt es erst, wenn der Schritt wirklich fertig ist, in der Reihenfolge
// Auftrag, Fertigung, Lieferung, Rechnung, Zahlung. Liefert den Index des aktuellen Schritts für die Ablaufleiste
// (0 Angebot, 1 Auftrag, 2 Fertigung, 3 Lieferung, 4 Rechnung, 5 Zahlung, 6 alles erledigt).

export function auftragStand({ fertigungsbauteile = [], lieferung, abrechnung, rechnungen = [] }) {
  if (!fertigungsbauteile.length) return 1;
  if (!fertigungsbauteile.every((x) => x.status === 'Fertig')) return 2;
  if (lieferung?.status !== 'Geliefert') return 3;
  const echte = rechnungen.filter((r) => r.art !== 'Storno' && r.status !== 'Storniert');
  const fest = echte.filter((r) => r.status !== 'Entwurf');
  if (abrechnung?.status !== 'Berechnet' || echte.length !== fest.length) return 4;
  if (!fest.every((r) => r.status === 'Bezahlt')) return 5;
  return 6;
}
