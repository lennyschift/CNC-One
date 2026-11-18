// Angebote der Lieferanten vergleichen. Anfragen, die zusammen verschickt wurden (eine Mail, Lieferanten in BCC), bilden
// einen Vorgang mit gemeinsamer Nummer. Reine Funktionen, getestet in vergleich.test.js.
import { isoAusName } from './iso.js';

const r2 = (x) => Math.round(x * 100) / 100;

export const vorgangVon = (a) => a.vorgang || a.id;

// Alle Anfragen eines Vorgangs, nach Nummer
export const imVorgang = (liste, vorgang) => liste.filter((a) => vorgangVon(a) === vorgang).sort((x, y) => x.id.localeCompare(y.id));

// Vorgänge der Liste: [{ vorgang, anfragen }], neueste zuerst wie die Liste
export function vorgaenge(liste) {
  const map = new Map();
  for (const a of liste) {
    const v = vorgangVon(a);
    if (!map.has(v)) map.set(v, []);
    map.get(v).push(a);
  }
  return [...map.entries()].map(([vorgang, anfragen]) => ({ vorgang, anfragen: anfragen.sort((x, y) => x.id.localeCompare(y.id)) }));
}

// Preis eines Lieferanten für eine Position und Menge: { proStk, einmalig, gesamt } oder null (kein Preis)
function zelle(a, posKey, menge) {
  const q = (a.antwort?.preise ?? []).find((x) => x.posKey === posKey && Number(x.menge) === Number(menge));
  if (!q || !(Number(q.proStk) > 0 || Number(q.einmalig) > 0)) return null;
  const proStk = Number(q.proStk) || 0;
  const einmalig = Number(q.einmalig) || 0;
  return { proStk, einmalig, gesamt: r2(proStk * menge + einmalig) };
}

const guenstigster = (zellen) => {
  let best = null;
  for (const [id, z] of Object.entries(zellen)) if (z && (!best || z.gesamt < best.gesamt)) best = { id, gesamt: z.gesamt };
  return best?.id ?? null;
};

// Vergleich der Anfragen eines Vorgangs:
// { lieferanten: [...], zeilen: [{ key, posKey, nr, teil, agName, abmessung, einheit, menge, ersteZeile, zellen: { [anfrageId]: zelle|null }, bester }],
//   summen: [{ stufe, je: { [anfrageId]: { betrag, vollstaendig } }, bester }] }
// Summe je Stufe: die erste (zweite, …) Menge jeder Position zusammen; der Beste zählt nur unter den vollständigen.
export function vergleich(anfragen) {
  const basis = anfragen[0];
  if (!basis) return { lieferanten: [], zeilen: [], summen: [] };
  const lieferanten = anfragen.map((a) => ({
    id: a.id, name: a.lieferantName, status: a.status, zuschlag: !!a.zuschlag, neueAntwort: !!a.neueAntwort,
    angebotsnr: a.antwort?.angebotsnr ?? '', gueltigBis: a.antwort?.gueltigBis ?? '', lieferzeit: a.antwort?.lieferzeit ?? '',
    hatPreise: (a.antwort?.preise ?? []).some((q) => Number(q.proStk) > 0 || Number(q.einmalig) > 0),
  }));
  const zeilen = [];
  basis.positionen.forEach((p, i) => {
    p.mengen.forEach((m, stufe) => {
      const zellen = Object.fromEntries(anfragen.map((a) => [a.id, zelle(a, p.key, m)]));
      zeilen.push({
        key: `${p.key}|${m}`, posKey: p.key, nr: i + 1, stufe, teil: p.teil, agName: p.agName, abmessung: p.abmessung ?? '', einheit: p.einheit || 'Stk',
        menge: m, ersteZeile: stufe === 0, stufen: p.mengen.length, zellen, bester: guenstigster(zellen),
      });
    });
  });
  const anzahlStufen = Math.max(0, ...basis.positionen.map((p) => p.mengen.length));
  const summen = [];
  if (basis.positionen.length > 1 || anzahlStufen > 1) {
    for (let stufe = 0; stufe < anzahlStufen; stufe++) {
      // je Position die Menge dieser Stufe (hat sie weniger Mengen, ihre letzte)
      const teil = basis.positionen.map((p) => zeilen.find((z) => z.posKey === p.key && z.stufe === Math.min(stufe, p.mengen.length - 1)));
      const je = Object.fromEntries(anfragen.map((a) => {
        const werte = teil.map((z) => z.zellen[a.id]);
        return [a.id, { betrag: r2(werte.reduce((s, z) => s + (z?.gesamt ?? 0), 0)), vollstaendig: werte.every(Boolean) }];
      }));
      const voll = Object.fromEntries(Object.entries(je).map(([id, x]) => [id, x.vollstaendig ? { gesamt: x.betrag } : null]));
      summen.push({ stufe, je, bester: guenstigster(voll) });
    }
  }
  return { lieferanten, zeilen, summen };
}

// ---------------------------------------------------------------- Vorlagen: Lieferanten je Werkstoff oder Leistung
export const stichwortListe = (v) => String(v?.stichwoerter ?? '').split(/[,\n]/).map((s) => s.trim().toLowerCase()).filter(Boolean);

// Passt eine Vorlage zu einer Anfrage? `texte`: Werkstoffe, Bezeichnungen, Arbeitsgänge der Positionen
export function vorlagePasst(v, { art = '', texte = [] } = {}) {
  if (!v || v.aktiv === false) return false;
  if (v.art && art && v.art !== art) return false;
  const t = texte.filter(Boolean).map((x) => String(x).toLowerCase());
  if (stichwortListe(v).some((w) => t.some((x) => x.includes(w)))) return true;
  return !!v.isoGruppe && texte.some((x) => x && isoAusName(x) === v.isoGruppe);
}

export const passendeVorlagen = (vorlagen, kontext) => (vorlagen ?? []).filter((v) => vorlagePasst(v, kontext));
