// Preise aus der Historie eines Bauteils wieder verwenden (Wiederholanfrage). Die Historie selbst liest der Server aus
// den Belegen (api/historie.py), hier wird nur übernommen: die ganze Kalkulation eines früheren Angebots oder nur dessen
// Stückpreis(e) als festen Preis.

// Felder der Kalkulation; Bezeichnung, Nummern, Dateien, Menge und Notizen des aktuellen Bauteils bleiben
export const KALKULATION = [
  'maschine', 'satzRuest', 'satzStueck', 'ruestMin', 'stueckMin', 'material', 'materialPreisKg', 'gewichtKg', 'aufmass',
  'pauschalMaterial', 'pauschalAlsZeile', 'messkosten', 'sonderkosten', 'expresskosten', 'inStueckpreis', 'preisart',
  'festpreis', 'staffel', 'arbeitsgaenge', 'roh',
];

const kopie = (x) => (x === undefined ? undefined : JSON.parse(JSON.stringify(x)));

// Ganze Kalkulation eines früheren Angebots übernehmen. `neueId` vergibt neue Kennungen für die Arbeitsgänge
// (Anfragen an Lieferanten gehören zum alten Angebot und werden nicht mitgenommen).
export function kalkulationUebernehmen(teil, alt, neueId) {
  for (const k of KALKULATION) if (alt?.[k] !== undefined) teil[k] = kopie(alt[k]);
  teil.arbeitsgaenge = (teil.arbeitsgaenge ?? []).map((ag) => ({ ...ag, id: neueId(), anfrageId: '' }));
  return teil;
}

// Stückpreis(e) als festen Preis übernehmen. `eintrag`: Angebot der Historie ({ preise: [{ menge, einzel }] }) oder
// Auftrag ({ einzelpreis, jeStueck, menge }). `umgelegt`: beim Auftrag den Stückpreis inklusive Kosten nehmen.
export function festpreisUebernehmen(teil, eintrag, { umgelegt = false } = {}) {
  teil.preisart = 'fest';
  const preise = eintrag?.preise ?? [];
  if (preise.length > 1) {
    teil.festpreis = preise[0].einzel;
    teil.staffel = { aktiv: true, stufen: preise.map((p) => ({ menge: p.menge, extra: 0, preis: p.einzel })) };
  } else {
    teil.festpreis = preise[0]?.einzel ?? (umgelegt ? eintrag?.jeStueck : eintrag?.einzelpreis) ?? 0;
    if (teil.staffel) teil.staffel.aktiv = false;
  }
  return teil;
}

// Kurzer Preistext einer Historienzeile: "25 Stk 28,40 € · 100 Stk 24,10 €"
export function preisText(eintrag, eur) {
  if (eintrag?.preise?.length) return eintrag.preise.map((p) => `${p.menge} Stk ${eur(p.einzel)}`).join(' · ');
  if (eintrag?.einzelpreis != null) return `${eintrag.menge} Stk ${eur(eintrag.einzelpreis)}`;
  return '';
}
