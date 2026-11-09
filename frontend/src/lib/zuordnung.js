// Zeichnung und 3D-Modell eines Bauteils zusammenfinden – beim Hineinziehen in die Workbench und bei Mail-Anfragen.
// Stufe 1: gleicher Name, bereinigt (Typwörter wie step/ipt/dra/zeichnung, Vorsilben wie „step_“, Trennzeichen und
//          Zeitstempel zählen nicht): „F03_912_101_Q.pdf“ ↔ „step_F03_912_101_Q.stp“
// Stufe 2: im selben Paket (ZIP-Ordner, ZIP, Mail, einmal Hineinziehen) genau eine Zeichnung und ein Modell
// Stufe 3: ähnlichster Name (gemeinsame Nummern, Revision): „216067_10242029_dra_B“ ↔ „216067_10242028_ipt_B“ – nur wenn
//          beide sich gegenseitig eindeutig am besten passen. Was nicht eindeutig ist, bleibt getrennt (in der Workbench
//          lässt es sich von Hand zusammenführen).

const TYPWOERTER = new Set([
  'step', 'stp', '3d', 'model', 'modell', 'ipt', 'iam', 'sldprt', 'prt', 'dra', 'drw', 'idw', 'dwg', 'slddrw', 'zeichnung', 'drawing',
  'zchn', 'zng', 'pdf', 'sap', 'released', 'freigegeben',
]);
const ZEITSTEMPEL = /^\d{12,}$/;

export const istZeichnung = (d) => d.art === 'Zeichnung' || /\.pdf$/i.test(d.name ?? '');
export const istModell = (d) => d.art === 'STEP' || /\.(stp|step)$/i.test(d.name ?? '');
const ohneEndung = (n) => (/^(.*?)(\.[^.]+)?$/.exec(n ?? '')?.[1] ?? n ?? '').trim();

// Bestandteile zum Vergleichen: „step_F03_912_101_Q“ → ["f03", "912", "101", "q"]
export function bestandteile(name) {
  return ohneEndung(name).toLowerCase().split(/[\s_.-]+/).filter((t) => t && !TYPWOERTER.has(t) && !ZEITSTEMPEL.test(t));
}
const schluessel = (name) => bestandteile(name).join(' ');

// Name des Bauteils aus dem Dateinamen: Unterstriche zu Leerzeichen, Typwörter und Zeitstempel weg; Bindestriche und Punkte
// bleiben (Teilenummern wie „ZZ-3D-001“ oder „F03.912.101“). Leer, wenn nur Allgemeines übrig bleibt („Zeichnung.pdf“).
export function anzeigename(name) {
  return ohneEndung(name).split(/[\s_]+/).filter((t) => t && !TYPWOERTER.has(t.toLowerCase()) && !ZEITSTEMPEL.test(t)).join(' ');
}

// Gemeinsame Bestandteile: jede gemeinsame Nummer (mit Ziffer, ab 3 Zeichen) zählt voll, alles andere (Revision) halb.
// Ohne gemeinsame Nummer passen zwei Namen nicht zusammen.
function aehnlichkeit(a, b) {
  const gemeinsam = [...a].filter((t) => b.has(t));
  const nummern = gemeinsam.filter((t) => t.length >= 3 && /\d/.test(t)).length;
  return nummern ? nummern + (gemeinsam.length - nummern) / 2 : 0;
}

const paketVon = (d) => d.paket ?? `${d.aus ?? ''}/${d.ordner ?? ''}`;

// dateien: [{ name, art?, aus?, ordner?, paket? }]; vorhandene: Bauteile der Workbench [{ id, name, dateien }] (beim Hineinziehen).
// Liefert [{ basis, dateien, teilId }] je Bauteil in der Reihenfolge der Dateien; teilId gesetzt = zu einem vorhandenen Bauteil.
export function gruppieren(dateien, { vorhandene = [] } = {}) {
  let gruppen = [
    ...vorhandene.map((t) => ({ teilId: t.id, name: t.name, alt: t.dateien ?? [], neu: [] })),
    ...dateien.map((d) => ({ teilId: null, name: '', alt: [], neu: [d] })),
  ];
  const alle = (g) => [...g.alt, ...g.neu];
  const hatZ = (g) => alle(g).some(istZeichnung);
  const hatM = (g) => alle(g).some(istModell);
  const halb = (g) => hatZ(g) !== hatM(g);
  const schluessel_ = (g) => new Set([...alle(g).map((d) => schluessel(d.name)), ...(g.name ? [schluessel(g.name)] : [])].filter(Boolean));
  const teile_ = (g) => new Set(alle(g).flatMap((d) => bestandteile(d.name)).concat(g.name ? bestandteile(g.name) : []));
  const zusammen = (a, b) => {
    a.teilId ??= b.teilId;
    a.name ||= b.name;
    a.alt.push(...b.alt);
    a.neu.push(...b.neu);
    gruppen = gruppen.filter((g) => g !== b);
  };
  const erlaubt = (a, b) => a !== b && !(a.teilId && b.teilId);

  // Stufe 1: gleicher bereinigter Name
  for (let weiter = true; weiter;) {
    weiter = false;
    suche: for (const a of gruppen) {
      const ka = schluessel_(a);
      for (const b of gruppen) {
        if (erlaubt(a, b) && [...schluessel_(b)].some((k) => ka.has(k))) { zusammen(a, b); weiter = true; break suche; }
      }
    }
  }

  // Stufe 2: genau eine Zeichnung und ein Modell im selben Paket – außer einer der beiden passt anderswo klar besser
  // (z. B. beim Hineinziehen zu einem Bauteil, das schon in der Workbench liegt)
  const passtBesser = (g, partner) => {
    const tg = teile_(g);
    const w = aehnlichkeit(tg, teile_(partner));
    return gruppen.some((k) => k !== partner && erlaubt(g, k) && halb(k) && hatZ(k) !== hatZ(g) && aehnlichkeit(tg, teile_(k)) > w);
  };
  const pakete = new Map();
  for (const d of dateien) {
    if (!istZeichnung(d) && !istModell(d)) continue;
    const p = paketVon(d);
    pakete.set(p, [...(pakete.get(p) ?? []), d]);
  }
  for (const liste of pakete.values()) {
    const z = liste.filter(istZeichnung);
    const m = liste.filter(istModell);
    if (z.length !== 1 || m.length !== 1) continue;
    const a = gruppen.find((g) => g.neu.includes(z[0]));
    const b = gruppen.find((g) => g.neu.includes(m[0]));
    if (a && b && erlaubt(a, b) && halb(a) && halb(b) && !hatM(a) && !hatZ(b) && !passtBesser(a, b) && !passtBesser(b, a)) zusammen(a, b);
  }

  // Stufe 3: ähnlichster Name, nur gegenseitig eindeutig
  for (let weiter = true; weiter;) {
    weiter = false;
    const zs = gruppen.filter((g) => halb(g) && hatZ(g));
    const ms = gruppen.filter((g) => halb(g) && hatM(g));
    const bester = (g, kandidaten) => {
      const tg = teile_(g);
      const werte = kandidaten.filter((k) => erlaubt(g, k)).map((k) => ({ k, w: aehnlichkeit(tg, teile_(k)) })).filter((x) => x.w > 0);
      const max = Math.max(0, ...werte.map((x) => x.w));
      const oben = werte.filter((x) => x.w === max);
      return oben.length === 1 ? oben[0].k : null;
    };
    for (const z of zs) {
      const m = bester(z, ms);
      if (m && bester(m, zs) === z) { zusammen(z, m); weiter = true; break; }
    }
  }

  return gruppen.filter((g) => g.neu.length).map((g) => ({
    teilId: g.teilId,
    dateien: g.neu,
    basis: g.teilId ? g.name : (
      g.neu.filter(istZeichnung).map((d) => anzeigename(d.name)).find(Boolean)
      ?? g.neu.filter(istModell).map((d) => anzeigename(d.name)).find(Boolean)
      ?? g.neu.map((d) => d.ordner).find(Boolean)
      ?? ohneEndung(g.neu[0].name)
    ),
  }));
}
