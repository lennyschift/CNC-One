import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { berechne, summe } from '../lib/calc.js';
import { angebotStatus } from '../lib/beleg.js';
import { useUi } from './ui.js';

const KEY = 'cnc-one:belege:v1';
const kopie = (o) => JSON.parse(JSON.stringify(o));
const nummer = (prefix, n) => `${prefix}-${new Date().getFullYear()}-${String(n).padStart(4, '0')}`;

function laden() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* egal */ }
  return null;
}

// Gespeicherte Belege. Aktuell im Browser, später über die Frappe-API (siehe data/repo.js).
export const useBelege = defineStore('belege', () => {
  const ui = useUi();
  const g = laden();
  const angebote = ref(g?.angebote ?? []);
  const auftraege = ref(g?.auftraege ?? []);
  const zaehler = ref(g?.zaehler ?? { ANG: 0, AUF: 0 });

  watch([angebote, auftraege, zaehler], () => {
    try { localStorage.setItem(KEY, JSON.stringify({ angebote: angebote.value, auftraege: auftraege.value, zaehler: zaehler.value })); } catch { /* egal */ }
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

  function angebotSpeichern(entwurf, kunde) {
    const positionen = entwurf.teile.map((t) => ({ key: t.id, teil: kopie(t), ergebnis: berechne(t) }));
    const daten = {
      kopf: { ...kopie(entwurf.kopf), kundeName: kunde.name, kunde: kopie(kunde) },
      positionen,
      entwurfId: entwurf.entwurfId ?? '',
      netto: summe(positionen.map((p) => p.ergebnis)),
      geaendert: new Date().toISOString(),
    };
    const vorhanden = entwurf.angebotId ? angebot(entwurf.angebotId) : null;
    if (vorhanden && vorhanden.status === 'Entwurf') {
      Object.assign(vorhanden, daten);
      return vorhanden;
    }
    zaehler.value.ANG += 1;
    const neu = { id: nummer('ANG', zaehler.value.ANG), status: 'Entwurf', erstellt: new Date().toISOString(), versandt: null, ...daten };
    angebote.value.unshift(neu);
    return neu;
  }

  function angebotSenden(id) {
    const a = angebot(id);
    if (!a || a.status !== 'Entwurf') return;
    a.status = 'Gesendet';
    a.versandt = new Date().toISOString();
    ui.toast(`${a.id} als gesendet markiert`, 'ok');
  }

  function angebotAblehnen(id) {
    const a = angebot(id);
    if (a) { a.status = 'Abgelehnt'; ui.toast(`${a.id} als abgelehnt markiert`); }
  }

  function angebotLoeschen(id) {
    const a = angebot(id);
    if (!a || a.status !== 'Entwurf') return;
    angebote.value = angebote.value.filter((x) => x.id !== id);
    ui.toast(`Entwurf ${id} gelöscht`);
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
