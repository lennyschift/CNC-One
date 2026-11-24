// Lieferantenanfrage. Reine Funktionen, getestet in anfrage.test.js.
// Eine Anfrage geht an einen Lieferanten und kann mehrere Positionen enthalten: aus der Workbench Bauteil + Arbeitsgang
// + Mengen (Fremdvergabe), frei erfasst (ohne Angebot) Bezeichnung, Werkstoff, Abmessung, Einheit und Mengen.
import { num } from './calc.js';

export const EINHEITEN = ['Stk', 'm', 'kg', 'Stangen', 'Platten', 'Zuschnitte'];

// Freie Anfrage: ohne Angebot, die Positionen sind selbst eingetragen
export const istFrei = (a) => (a.positionen ?? []).length > 0 && (a.positionen ?? []).every((p) => /^(frei|mat):/.test(String(p.key ?? '')));
// Abmessung einer Materialposition, wie sie in der Anfrage steht: Form und Maß aus dem Rohmaterial-Baum, Ausführung
// (falls gewählt) und die Länge je Einheit, bei Platten Länge × Breite des Zuschnitts. r = Rohmaterial-Auswahl.
// z. B. „Rund Ø20 · gezogen h9 · Stangenlänge 3000 mm“ oder „Platte 20 mm · Zuschnitt 500 × 300 mm“
export function materialAbmessung(r, einheit, laenge = 0, breite = 0) {
  if (!r) return '';
  const l = Math.round(num(laenge));
  const b = Math.round(num(breite));
  let mass = '';
  if (r.form === 'Platte') {
    if (l || b) mass = `${einheit === 'Platten' ? 'Plattenmaß' : 'Zuschnitt'} ${l || '?'} × ${b || '?'} mm`;
  } else if (l) mass = `${einheit === 'Stangen' ? 'Stangenlänge' : einheit === 'Zuschnitte' ? 'Zuschnitt' : 'Länge'} ${l} mm`;
  else if (einheit === 'Stangen') mass = 'Stangenlänge nach Ihrem Lager';
  return [`${r.form || ''} ${r.abmessung || ''}`.trim(), r.ausfuehrung, mass].filter(Boolean).join(' · ');
}

// „Rundstahl · 42CrMo4 · Ø 50 x 3000 mm“
export const freieZeile = (p) => [p.teil?.name, p.teil?.material, p.abmessung].filter(Boolean).join(' · ');

// Welche angefragten Mengen werden für ein Bauteil gebraucht: alle Staffeln oder die eine Menge.
export function mengenFuer(teil) {
  if (teil.staffel?.aktiv) {
    const m = (teil.staffel.stufen ?? []).map((s) => Math.floor(num(s.menge))).filter((x) => x > 0);
    if (m.length) return [...new Set(m)].sort((a, b) => a - b);
  }
  return [Math.max(1, Math.floor(num(teil.menge)) || 1)];
}

// Alle Fremdvergaben der Bauteile als mögliche Anfragepositionen.
export function fremdPositionen(teile) {
  const liste = [];
  for (const t of teile) {
    for (const ag of t.arbeitsgaenge ?? []) {
      if (ag.typ !== 'fremd') continue;
      liste.push({ key: `${t.id}:${ag.id}`, teilId: t.id, teil: t, ag, mengen: mengenFuer(t) });
    }
  }
  return liste;
}

// Preis aus dem Lieferantenangebot für eine Menge: gleiche Menge, sonst die nächstkleinere Staffel,
// sonst die kleinste vorhandene. Mit posKey werden nur die Preise dieser Position betrachtet.
export function preisFuerMenge(antwort, menge, posKey) {
  const preise = [...(antwort?.preise ?? [])]
    .filter((p) => num(p.menge) > 0 && (!posKey || !p.posKey || p.posKey === posKey))
    .sort((a, b) => a.menge - b.menge);
  if (!preise.length) return null;
  const q = num(menge);
  const gleich = preise.find((p) => p.menge === q);
  if (gleich) return gleich;
  const kleiner = preise.filter((p) => p.menge < q);
  return kleiner.length ? kleiner[kleiner.length - 1] : preise[0];
}

// Gehört die Anfrage zu diesem Angebot (auch der Entwurf ist ein gespeichertes Angebot)?
export const gehoertZu = (a, { angebotId }) => !!angebotId && a.angebotId === angebotId;

// Anzahl je Status, z. B. für die Anzeige "2 gesendet, 1 Angebot erhalten".
export function zusammenfassung(liste) {
  const z = { gesamt: liste.length, Gesendet: 0, 'Angebot erhalten': 0, Abgesagt: 0 };
  for (const a of liste) z[a.status] = (z[a.status] ?? 0) + 1;
  return z;
}

export function zusammenfassungText(z) {
  const t = [];
  if (z.Gesendet) t.push(`${z.Gesendet} gesendet`);
  if (z['Angebot erhalten']) t.push(`${z['Angebot erhalten']} Angebot erhalten`);
  if (z.Abgesagt) t.push(`${z.Abgesagt} abgesagt`);
  return t.join(', ');
}

const teilZeile = (t) => `${t.name}${t.teilenummer ? ` (Teilenummer ${t.teilenummer})` : ''}`;

// Text einer freien Anfrage (z. B. Material): je Position Bezeichnung, Werkstoff, Abmessung und Mengen mit Einheit
function freierText(a, firma) {
  const pos = a.positionen;
  const was = a.art === 'Material' ? 'folgendes Material' : 'folgende Positionen';
  const zeilen = ['Sehr geehrte Damen und Herren,', '', `bitte senden Sie uns ein Angebot für ${was}:`, ''];
  pos.forEach((p, i) => {
    zeilen.push(`${i + 1}. ${p.teil.name}`);
    if (p.teil.material) zeilen.push(`   Werkstoff: ${p.teil.material}`);
    if (p.abmessung) zeilen.push(`   Abmessung: ${p.abmessung}`);
    if (p.anforderungen) zeilen.push(`   Anforderungen: ${p.anforderungen}`);
    zeilen.push(`   Menge: ${p.mengen.map((m) => `${m} ${p.einheit || 'Stk'}`).join(' / ')}`);
    zeilen.push('');
  });
  if (a.notiz) zeilen.push(`Hinweis: ${a.notiz}`, '');
  zeilen.push(
    `Bitte nennen Sie in Ihrem Angebot unsere Anfragenummer ${a.id}, damit wir es zuordnen können.`,
    '',
    'Mit freundlichen Grüßen',
    firma,
  );
  const titel = pos.length === 1 ? `${pos[0].teil.name}${pos[0].teil.material ? ` ${pos[0].teil.material}` : ''}` : `${a.art || 'Material'}, ${pos.length} Positionen`;
  return { betreff: `Anfrage ${a.id}: ${titel}`, text: zeilen.join('\n') };
}

// Text der Anfrage. Die Anfragenummer steht im Betreff und im Text, der Lieferant soll sie im Angebot nennen.
export function mailText(a, firma = 'Hohenstein GmbH') {
  if (istFrei(a)) return freierText(a, firma);
  const pos = a.positionen;
  const einzel = pos.length === 1;
  const zeilen = [
    'Sehr geehrte Damen und Herren,',
    '',
    einzel
      ? `bitte senden Sie uns ein Angebot für folgende Leistung: ${pos[0].agName || 'Fremdvergabe'}.`
      : 'bitte senden Sie uns ein Angebot für die folgenden Leistungen:',
    '',
  ];
  pos.forEach((p, i) => {
    if (!einzel) zeilen.push(`${i + 1}. ${p.agName || 'Fremdvergabe'}`);
    zeilen.push(`${einzel ? '' : '   '}Bauteil: ${teilZeile(p.teil)}`);
    if (p.teil.zeichnungsnr) zeilen.push(`${einzel ? '' : '   '}Zeichnung: ${p.teil.zeichnungsnr}`);
    if (p.teil.material) zeilen.push(`${einzel ? '' : '   '}Rohmaterial: ${p.teil.material}`);
    if (p.anforderungen) zeilen.push(`${einzel ? '' : '   '}Anforderungen an das Material: ${p.anforderungen}`);
    zeilen.push(`${einzel ? '' : '   '}Angefragte Stückzahlen: ${p.mengen.join(', ')}`);
    if (!einzel) zeilen.push('');
  });
  if (a.notiz) zeilen.push(`${einzel ? '\n' : ''}Hinweis: ${a.notiz}`, '');
  zeilen.push(
    `Bitte nennen Sie in Ihrem Angebot unsere Anfragenummer ${a.id}, damit wir es zuordnen können.`,
    'Zeichnungen und Modelle finden Sie im Anhang.',
    '',
    'Mit freundlichen Grüßen',
    firma,
  );
  return {
    betreff: einzel ? `Anfrage ${a.id}: ${pos[0].agName || 'Fremdvergabe'} ${pos[0].teil.name}` : `Anfrage ${a.id}: Fremdvergabe, ${pos.length} Positionen`,
    text: zeilen.join('\n'),
  };
}
