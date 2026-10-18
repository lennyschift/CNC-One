import { defineStore } from 'pinia';
import { ref, watch } from 'vue';
import { nummer, normalisiereAnfrage, gehoertZu } from '../lib/anfrage.js';
import { useUi } from './ui.js';

const KEY = 'cnc-one:anfragen:v1';

function laden() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* egal */ }
  return null;
}

const kopf = (t) => ({ name: t.name, teilenummer: t.teilenummer, zeichnungsnr: t.zeichnungsnr, material: t.material, vorschaubild: t.vorschaubild ?? '' });

// Lieferantenanfragen für Fremdvergabe. Eine Anfrage geht an einen Lieferanten und enthält mehrere Positionen.
// Aktuell im Browser, später über die Frappe-API.
export const useAnfragen = defineStore('anfragen', () => {
  const ui = useUi();
  const g = laden();
  const liste = ref((g?.liste ?? []).map(normalisiereAnfrage));
  const zaehler = ref(g?.zaehler ?? 0);

  watch([liste, zaehler], () => {
    try { localStorage.setItem(KEY, JSON.stringify({ liste: liste.value, zaehler: zaehler.value })); } catch { /* egal */ }
  }, { deep: true });

  const anfrage = (id) => liste.value.find((x) => x.id === id) ?? null;
  const fuerArbeitsgang = (agId) => liste.value.filter((x) => x.positionen.some((p) => p.agId === agId));
  // Anfragen zu einem Angebot oder Entwurf: ziel = { entwurfId, angebotId }
  const fuerAngebot = (ziel) => liste.value.filter((x) => gehoertZu(x, ziel));

  // Beim ersten Speichern des Entwurfs als Angebot bekommen seine Anfragen die Angebotsnummer.
  function verknuepfen(entwurfId, angebotId) {
    if (!entwurfId || !angebotId) return 0;
    const treffer = liste.value.filter((x) => x.entwurfId === entwurfId && x.angebotId !== angebotId);
    for (const x of treffer) x.angebotId = angebotId;
    return treffer.length;
  }

  // positionen: [{ teil, agId, agName, mengen }], pro Lieferant entsteht eine Anfrage mit eigener Nummer.
  function anlegen({ lieferanten, positionen, notiz, bezug }) {
    const neu = lieferanten.map((l) => {
      zaehler.value += 1;
      return {
        id: nummer(zaehler.value),
        lieferantId: l.id,
        lieferantName: l.name,
        erstellt: new Date().toISOString(),
        status: 'Gesendet',
        notiz: notiz || '',
        entwurfId: bezug?.entwurfId ?? '',
        angebotId: bezug?.angebotId ?? '',
        kundeName: bezug?.kundeName ?? '',
        positionen: positionen.map((p) => ({ key: `${p.teil.id ?? ''}:${p.agId}`, teilId: p.teil.id ?? '', teil: kopf(p.teil), agId: p.agId, agName: p.agName, mengen: [...p.mengen] })),
        antwort: null,
      };
    });
    liste.value.unshift(...neu);
    ui.toast(`${neu.map((x) => x.id).join(', ')} angelegt`, 'ok');
    return neu;
  }

  function antwortErfassen(id, antwort) {
    const a = anfrage(id);
    if (!a) return;
    a.antwort = JSON.parse(JSON.stringify(antwort));
    a.status = 'Angebot erhalten';
    ui.toast(`Angebot zu ${id} erfasst`, 'ok');
  }

  function absagen(id) {
    const a = anfrage(id);
    if (a) { a.status = 'Abgesagt'; ui.toast(`${id} als abgesagt markiert`); }
  }

  return { liste, anfrage, fuerArbeitsgang, fuerAngebot, verknuepfen, anlegen, antwortErfassen, absagen };
});
