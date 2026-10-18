import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { angebotStatus } from '../lib/beleg.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useUi } from './ui.js';

const KEY = 'cnc-one:belege:v2';
const kopie = (o) => JSON.parse(JSON.stringify(o));
const nummer = (prefix, n) => `${prefix}-${new Date().getFullYear()}-${String(n).padStart(4, '0')}`;

function laden() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* egal */ }
  return null;
}

// Angebote liegen in Frappe. Aufträge liegen noch im Browser und ziehen im nächsten Schritt um.
export const useBelege = defineStore('belege', () => {
  const ui = useUi();
  const g = laden();
  const angebote = ref(kopie(stammdatenRoh().angebote ?? []));
  const auftraege = ref(g?.auftraege ?? []);
  const zaehler = ref(g?.zaehler ?? { AUF: 0 });

  watch([auftraege, zaehler], () => {
    try { localStorage.setItem(KEY, JSON.stringify({ auftraege: auftraege.value, zaehler: zaehler.value })); } catch { /* egal */ }
  }, { deep: true });

  // bestellte Menge je Angebotsposition, aus den Aufträgen berechnet
  const bestellt = computed(() => {
    const m = {};
    for (const a of auftraege.value) {
      for (const p of a.positionen) {
        m[a.angebotId] ??= {};
        m[a.angebotId][p.angebotKey] = (m[a.angebotId][p.angebotKey] ?? 0) + p.menge;
      }
    }
    return m;
  });

  const bestelltFuer = (angebotId) => bestellt.value[angebotId] ?? {};
  const statusVon = (a) => angebotStatus(a, bestelltFuer(a.id));
  const angebot = (id) => angebote.value.find((a) => a.id === id) ?? null;
  const auftrag = (id) => auftraege.value.find((a) => a.id === id) ?? null;

  // Antwort des Servers in die Liste übernehmen
  function einsetzen(rec) {
    const i = angebote.value.findIndex((a) => a.id === rec.id);
    if (i >= 0) angebote.value[i] = rec;
    else angebote.value.unshift(rec);
    return rec;
  }

  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  // Fehler gehen an den Aufrufer (die Workbench zeigt sie beim Speichern an)
  async function angebotSpeichern({ angebotId, kopf, teile }) {
    const rec = await call('cnc_one.api.angebot.entwurf_speichern', { angebot: { id: angebotId, kopf, teile } });
    return einsetzen(rec);
  }

  async function angebotSenden(id) {
    const rec = await sicher(() => call('cnc_one.api.angebot.senden', { id }));
    if (rec) { einsetzen(rec); ui.toast(`${rec.id} als gesendet markiert`, 'ok'); }
    return rec;
  }

  async function angebotAblehnen(id) {
    const rec = await sicher(() => call('cnc_one.api.angebot.ablehnen', { id }));
    if (rec) { einsetzen(rec); ui.toast(`${rec.id} als abgelehnt markiert`); }
    return rec;
  }

  async function angebotLoeschen(id) {
    if (await sicher(() => call('cnc_one.api.angebot.loeschen', { id }))) {
      angebote.value = angebote.value.filter((x) => x.id !== id);
      ui.toast(`Entwurf ${id} gelöscht`);
      return true;
    }
    return false;
  }

  function auftragAnlegen({ angebotId, kundenbestellnr, positionen }) {
    const a = angebot(angebotId);
    zaehler.value.AUF += 1;
    const neu = {
      id: nummer('AUF', zaehler.value.AUF),
      angebotId,
      kundeName: a.kopf.kundeName,
      kunde: kopie(a.kopf.kunde),
      kundenbestellnr: kundenbestellnr || '',
      datum: new Date().toISOString(),
      status: 'Offen',
      positionen,
      netto: positionen.reduce((s, p) => s + p.summe, 0),
    };
    auftraege.value.unshift(neu);
    ui.toast(`${neu.id} angelegt`, 'ok');
    return neu;
  }

  return { angebote, auftraege, bestelltFuer, statusVon, angebot, auftrag, angebotSpeichern, angebotSenden, angebotAblehnen, angebotLoeschen, auftragAnlegen };
});
