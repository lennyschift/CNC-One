import { defineStore } from 'pinia';
import { ref } from 'vue';
import { gehoertZu } from '../lib/anfrage.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));
const kopf = (t) => ({ name: t.name, teilenummer: t.teilenummer, zeichnungsnr: t.zeichnungsnr, material: t.material });

// Lieferantenanfragen für Fremdvergabe liegen in Frappe. Eine Anfrage geht an einen Lieferanten und enthält mehrere Positionen.
export const useAnfragen = defineStore('anfragen', () => {
  const ui = useUi();
  const liste = ref(kopie(stammdatenRoh().anfragen ?? []));

  const anfrage = (id) => liste.value.find((x) => x.id === id) ?? null;
  const fuerArbeitsgang = (agId) => liste.value.filter((x) => x.positionen.some((p) => p.agId === agId));
  // Anfragen zu einem Angebot (auch der Entwurf ist ein gespeichertes Angebot): ziel = { angebotId }
  const fuerAngebot = (ziel) => liste.value.filter((x) => gehoertZu(x, ziel));

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
      positionen: positionen.map((p) => ({ teilId: p.teil.id ?? '', teil: kopf(p.teil), agId: p.agId, agName: p.agName, mengen: [...p.mengen] })),
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

  async function absagen(id) {
    const rec = await sicher(() => call('cnc_one.api.anfrage.absagen', { id }));
    if (rec) { einsetzen(rec); ui.toast(`${id} als abgesagt markiert`); }
    return rec;
  }

  return { liste, anfrage, fuerArbeitsgang, fuerAngebot, anlegen, antwortErfassen, absagen };
});
