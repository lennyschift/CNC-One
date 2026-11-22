import { defineStore } from 'pinia';
import { ref } from 'vue';
import { gehoertZu } from '../lib/anfrage.js';
import { imVorgang } from '../lib/vergleich.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useUi } from './ui.js';
import { artikelText } from '../lib/werkstoffbaum.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));
// Rohmaterial mit Zustand, Abmessung und Ausführung (z. B. „EN AW-7075 T7351 · Rund Ø40 · gezogen h11“), damit der Lieferant es kennt
const kopf = (t) => ({ name: t.name, teilenummer: t.teilenummer, zeichnungsnr: t.zeichnungsnr, material: artikelText(t.material, t.roh) || t.material || '' });
const anforderungenText = (t) => {
  const a = t?.roh?.anforderungen ?? { zeugnis: t?.roh?.zeugnis || '', pruefungen: [] };
  return [a.zeugnis && `Zeugnis ${a.zeugnis}`, ...(a.pruefungen ?? [])].filter(Boolean).join(', ');
};

// Lieferantenanfragen (Fremdvergabe aus der Workbench oder frei, z. B. Material) liegen in Frappe. Eine Anfrage geht an einen Lieferanten und enthält mehrere Positionen.
export const useAnfragen = defineStore('anfragen', () => {
  const ui = useUi();
  const liste = ref(kopie(stammdatenRoh().anfragen ?? []));

  const anfrage = (id) => liste.value.find((x) => x.id === id) ?? null;
  const fuerArbeitsgang = (agId) => liste.value.filter((x) => x.positionen.some((p) => p.agId === agId));
  // Anfragen zu einem Angebot (auch der Entwurf ist ein gespeichertes Angebot): ziel = { angebotId }
  const fuerAngebot = (ziel) => liste.value.filter((x) => gehoertZu(x, ziel));
  // Alle Anfragen, die zusammen verschickt wurden (gemeinsame Vorgangsnummer)
  const vorgang = (v) => imVorgang(liste.value, v);

  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  function einsetzen(rec) {
    const i = liste.value.findIndex((x) => x.id === rec.id);
    if (i >= 0) liste.value[i] = rec;
    else liste.value.unshift(rec);
    return rec;
  }

  // positionen: [{ teil, agId, agName, mengen }], pro Lieferant entsteht eine Anfrage mit eigener Nummer (vergibt der Server).
  async function anlegen({ lieferanten, positionen, notiz, angebotId }) {
    const neu = await sicher(() => call('cnc_one.api.anfrage.anlegen', {
      angebot: angebotId,
      lieferanten: lieferanten.map((l) => l.name),
      notiz: notiz || '',
      positionen: positionen.map((p) => ({ teilId: p.teil.id ?? '', teil: kopf(p.teil), agId: p.agId, agName: p.agName, anforderungen: anforderungenText(p.teil), mengen: [...p.mengen] })),
    }));
    if (!neu) return null;
    for (const x of neu) einsetzen(x);
    ui.toast(`${neu.map((x) => x.id).join(', ')} angelegt`, 'ok');
    return neu;
  }

  // Freie Anfrage ohne Angebot (z. B. Material): positionen = [{ teil: { name, material }, abmessung, einheit, mengen }]
  async function freiAnlegen({ lieferanten, positionen, notiz, art, angebotId = '' }) {
    const neu = await sicher(() => call('cnc_one.api.anfrage.anlegen', {
      angebot: angebotId, art, notiz: notiz || '', lieferanten: lieferanten.map((l) => l.name), positionen: kopie(positionen),
    }));
    if (!neu) return null;
    for (const x of neu) einsetzen(x);
    ui.toast(`${neu.map((x) => x.id).join(', ')} angelegt`, 'ok');
    return neu;
  }

  async function antwortErfassen(id, antwort) {
    const rec = await sicher(() => call('cnc_one.api.anfrage.antwort_erfassen', { id, antwort: kopie(antwort) }));
    if (rec) { einsetzen(rec); ui.toast(`Angebot zu ${id} erfasst`, 'ok'); }
    return rec;
  }

  // Nach dem Versand: die Anfragen des Vorgangs mit Mail im Verlauf
  function alleEinsetzen(recs) { for (const r of recs ?? []) einsetzen(r); }

  async function zuschlag(id, an) {
    const rec = await sicher(() => call('cnc_one.api.anfrage.zuschlag', { id, an: an ? 1 : 0 }));
    if (rec) { einsetzen(rec); ui.toast(an ? `Zuschlag an ${rec.lieferantName}` : 'Zuschlag zurückgenommen', 'ok'); }
    return rec;
  }

  async function gelesen(id) {
    const rec = await sicher(() => call('cnc_one.api.anfrage.gelesen', { id }));
    if (rec) einsetzen(rec);
  }

  async function absagen(id) {
    const rec = await sicher(() => call('cnc_one.api.anfrage.absagen', { id }));
    if (rec) { einsetzen(rec); ui.toast(`${id} als abgesagt markiert`); }
    return rec;
  }

  return { liste, anfrage, fuerArbeitsgang, fuerAngebot, vorgang, anlegen, freiAnlegen, antwortErfassen, absagen, alleEinsetzen, zuschlag, gelesen };
});
