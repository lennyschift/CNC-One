// Aufmaß des Rohteils (wie die Rohteil-Einstellung in CAM-Programmen). Gespeichert am Bauteil als Zahl (alt: mm je Seite
// rundum) oder als Objekt { art, ... }:
//   gleich   – ein Wert rundum (wert)
//   seiten   – Quader: X± und Y± (seite), oben Z+ (oben), unten Z− (unten); Rund: Durchmesser (radial) und je Stirnseite (stirn)
//   einzeln  – Quader: jede Richtung (xm, xp, ym, yp, zm, zp); Rund: radial, Stirnseite Anfang (l1) und Ende (l2)
//   fest     – feste Rohteilgröße, mittig ums Bauteil: Quader x, y, z; Rund d, l
// Alle Werte in mm, je Seite (radial = je Seite, also Durchmesser + 2·radial).

export const AUFMASS_ARTEN = [
  { id: 'gleich', label: 'Rundum', titel: 'Ein Aufmaß an allen Seiten' },
  { id: 'seiten', label: 'Seiten · Oben · Unten', titel: 'Seiten (X und Y) gemeinsam, oben und unten getrennt; bei Rund: Durchmesser und Stirnseiten' },
  { id: 'einzeln', label: 'Je Richtung', titel: 'Jede Richtung einzeln (X−, X+, Y−, Y+, Z−, Z+; bei Rund Durchmesser und jede Stirnseite)' },
  { id: 'fest', label: 'Feste Größe', titel: 'Rohteilmaße direkt vorgeben (z. B. Lagermaß), mittig ums Bauteil' },
];

const n = (v) => Math.max(0, Number(v) || 0);

// Einheitliche Form mit allen Feldern (fehlende aus dem Rundum-Wert)
export function aufmassNorm(a) {
  if (a == null || typeof a !== 'object') {
    const w = n(a);
    return { art: 'gleich', wert: w, seite: w, oben: w, unten: w, xm: w, xp: w, ym: w, yp: w, zm: w, zp: w, radial: w, stirn: w, l1: w, l2: w, x: 0, y: 0, z: 0, d: 0, l: 0 };
  }
  const w = n(a.wert);
  const g = (k) => (a[k] == null ? w : n(a[k]));
  return {
    art: AUFMASS_ARTEN.some((x) => x.id === a.art) ? a.art : 'gleich',
    wert: w, seite: g('seite'), oben: g('oben'), unten: g('unten'),
    xm: g('xm'), xp: g('xp'), ym: g('ym'), yp: g('yp'), zm: g('zm'), zp: g('zp'),
    radial: g('radial'), stirn: g('stirn'), l1: g('l1'), l2: g('l2'),
    x: n(a.x), y: n(a.y), z: n(a.z), d: n(a.d), l: n(a.l),
  };
}

// Zugaben am Quader: minus = [X−, Y−, Z−], plus = [X+, Y+, Z+]; fest = [x, y, z] oder null
export function quaderZugaben(a) {
  const m = aufmassNorm(a);
  if (m.art === 'fest') return { minus: [0, 0, 0], plus: [0, 0, 0], fest: m.x && m.y && m.z ? [m.x, m.y, m.z] : null };
  if (m.art === 'seiten') return { minus: [m.seite, m.seite, m.unten], plus: [m.seite, m.seite, m.oben], fest: null };
  if (m.art === 'einzeln') return { minus: [m.xm, m.ym, m.zm], plus: [m.xp, m.yp, m.zp], fest: null };
  return { minus: [m.wert, m.wert, m.wert], plus: [m.wert, m.wert, m.wert], fest: null };
}

// Zugaben am Rundmaterial: radial (je Seite), l1 am Anfang, l2 am Ende der Achse; fest = { d, l } oder null
export function rundZugaben(a) {
  const m = aufmassNorm(a);
  if (m.art === 'fest') return { radial: 0, l1: 0, l2: 0, fest: m.d && m.l ? { d: m.d, l: m.l } : null };
  if (m.art === 'seiten') return { radial: m.radial, l1: m.stirn, l2: m.stirn, fest: null };
  if (m.art === 'einzeln') return { radial: m.radial, l1: m.l1, l2: m.l2, fest: null };
  return { radial: m.wert, l1: m.wert, l2: m.wert, fest: null };
}

// Beim Umschalten der Art: die neue Art aus den aktuell wirksamen Zugaben vorbelegen (wie beim Umschalten in Fusion),
// feste Größe aus dem aktuellen Rohteil auf volle mm aufgerundet.
export function aufmassUmschalten(a, art, rohteil = null) {
  const m = aufmassNorm(a);
  const q = quaderZugaben(m);
  const r = rundZugaben(m);
  const neu = { ...m, art };
  if (m.art !== 'fest') {
    neu.seite = Math.max(q.minus[0], q.plus[0], q.minus[1], q.plus[1]);
    neu.oben = q.plus[2];
    neu.unten = q.minus[2];
    [neu.xm, neu.ym, neu.zm] = q.minus;
    [neu.xp, neu.yp, neu.zp] = q.plus;
    neu.radial = r.radial;
    neu.stirn = Math.max(r.l1, r.l2);
    neu.l1 = r.l1;
    neu.l2 = r.l2;
    neu.wert = art === 'gleich' ? Math.max(...q.minus, ...q.plus, r.radial) : m.wert;
  }
  if (art === 'fest' && rohteil) {
    const auf = (v) => Math.ceil((v || 0) - 1e-6);
    if (rohteil.art === 'Quader') Object.assign(neu, { x: auf(rohteil.x), y: auf(rohteil.y), z: auf(rohteil.z) });
    else Object.assign(neu, { d: auf(rohteil.durchmesser), l: auf(rohteil.laenge) });
  }
  return neu;
}

const mm = (v) => String(Math.round(v * 10) / 10).replace('.', ',');

// Kurztext, z. B. für die Rohmaterial-Karte
export function aufmassText(a, form = 'Quader') {
  const m = aufmassNorm(a);
  const rund = form === 'Rund';
  if (m.art === 'gleich') return `${mm(m.wert)} mm je Seite`;
  if (m.art === 'fest') return 'feste Rohteilgröße';
  if (m.art === 'seiten') return rund ? `⌀ +${mm(2 * m.radial)}, Stirnseiten je ${mm(m.stirn)} mm` : `Seiten ${mm(m.seite)}, oben ${mm(m.oben)}, unten ${mm(m.unten)} mm`;
  return rund
    ? `⌀ +${mm(2 * m.radial)}, Stirnseiten ${mm(m.l1)} / ${mm(m.l2)} mm`
    : `X −${mm(m.xm)}/+${mm(m.xp)}, Y −${mm(m.ym)}/+${mm(m.yp)}, Z −${mm(m.zm)}/+${mm(m.zp)} mm`;
}

// Nur die Felder speichern, die die Art braucht (rundum bleibt eine Zahl wie bisher)
export function aufmassSpeicherform(m) {
  if (m.art === 'gleich') return m.wert;
  const felder = { seiten: ['seite', 'oben', 'unten', 'radial', 'stirn'], einzeln: ['xm', 'xp', 'ym', 'yp', 'zm', 'zp', 'radial', 'l1', 'l2'], fest: ['x', 'y', 'z', 'd', 'l'] }[m.art];
  return Object.fromEntries([['art', m.art], ...felder.map((k) => [k, m[k]])]);
}
