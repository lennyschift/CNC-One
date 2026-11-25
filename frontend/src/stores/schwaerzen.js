import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { call } from '../data/api.js';
import { useUi } from './ui.js';

// Geschwärzte Fassungen der Zeichnungen (api/schwaerzen.py). Neue Zeichnungen werden im Hintergrund automatisch
// erkannt und geschwärzt (eine nach der anderen); an Partner geht eine Fassung aber erst, wenn ein Mensch sie geprüft
// und freigegeben hat (SchwaerzenDialog).
export const useSchwaerzen = defineStore('schwaerzen', () => {
  const ui = useUi();
  // url → Schwärzung (schwaerzung_ui) | null (keine) ; dazu Zustand der Hintergrund-Arbeit je url
  const stand = reactive({});
  const arbeit = reactive({}); // url → { phase: 'wartet' | 'läuft' | 'fehler', text }
  const regelnCache = new Map();
  let kette = Promise.resolve();

  async function statusLaden(urls) {
    const neu = [...new Set(urls.filter(Boolean))];
    if (!neu.length) return;
    try { Object.assign(stand, await call('cnc_one.api.schwaerzen.status', { urls: neu })); } catch { /* Anzeige bleibt leer */ }
  }

  function regelnFuer(kunde) {
    const k = kunde || '';
    if (!regelnCache.has(k)) regelnCache.set(k, call('cnc_one.api.schwaerzen.regeln_fuer', { kunde: k }).catch((e) => { regelnCache.delete(k); throw e; }));
    return regelnCache.get(k);
  }
  const regelnVergessen = () => regelnCache.clear();

  // Erkennen + schwärzen + ablegen; `bereiche` gegeben = von Hand bearbeitet (sonst automatische Erkennung)
  async function erzeugen(e, { bereiche = null, automatisch = false, onProgress } = {}) {
    const k = await import('../lib/schwaerzen/cncone.js');
    const { doc, sha } = await k.pdfLaden(e.url);
    try {
      const antwort = await regelnFuer(e.kunde);
      const regeln = k.regelnMitKunde(antwort);
      const erkannt = await k.erkennen(doc, regeln);
      const liste = bereiche ?? erkannt.bereiche;
      const { bytes, protokoll } = await k.schwaerzen({ doc, bereiche: liste, begriffe: k.pruefBegriffe(regeln, erkannt.annotationTexts), onProgress });
      protokoll.hinweise = erkannt.hinweise;
      const rec = await call('cnc_one.api.schwaerzen.speichern', {
        daten: {
          bauteil: e.bauteil || '', revision: e.revision || '', kunde: e.kunde || '', originalUrl: e.url, originalSha: sha,
          bereiche: liste.map(({ page, x0, y0, x1, y1, kind, source, reason }) => ({ page, x0, y0, x1, y1, kind, source, reason })),
          protokoll, automatisch: automatisch ? 1 : 0, regelsatz: antwort.regelsatz,
        },
        pdf: k.base64(bytes),
      });
      stand[e.url] = rec;
      return rec;
    } finally {
      await doc.loadingTask?.destroy?.();
    }
  }

  // Im Hintergrund: nur Zeichnungen ohne gültige Fassung, nacheinander
  async function automatisch(eintraege) {
    const pdfs = eintraege.filter((e) => e.url && /\.pdf$/i.test(e.url));
    await statusLaden(pdfs.filter((e) => !(e.url in stand)).map((e) => e.url));
    for (const e of pdfs) {
      if (stand[e.url] || arbeit[e.url]) continue;
      arbeit[e.url] = { phase: 'wartet', text: 'wartet …' };
      kette = kette.then(async () => {
        arbeit[e.url] = { phase: 'läuft', text: 'wird geschwärzt …' };
        try {
          await erzeugen(e, { automatisch: true });
          delete arbeit[e.url];
        } catch (err) {
          arbeit[e.url] = { phase: 'fehler', text: err?.message || 'Schwärzen fehlgeschlagen' };
        }
      });
    }
    return kette;
  }

  async function freigeben(url) {
    const s = stand[url];
    if (!s) return null;
    try {
      stand[url] = await call('cnc_one.api.schwaerzen.freigeben', { id: s.id });
      ui.toast(`${s.originalName}: geschwärzte Fassung freigegeben`, 'ok');
      return stand[url];
    } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  return { stand, arbeit, statusLaden, regelnFuer, regelnVergessen, erzeugen, automatisch, freigeben };
});
