import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { call } from '../data/api.js';
import { benutzer, stammdatenAktualisieren } from '../data/repo.js';
import { useStamm } from './stamm.js';
import { useUi } from './ui.js';

// Wer welche Art pflegen darf. Die Rechte prüft der Server, hier werden nur die Knöpfe ausgeblendet.
const SCHREIBEN = {
  kunde: ['CNC Admin', 'CNC Vertrieb', 'System Manager'],
  lieferant: ['CNC Admin', 'CNC Vertrieb', 'System Manager'],
  maschine: ['CNC Admin', 'System Manager'],
  material: ['CNC Admin', 'System Manager'],
  bauteil: ['CNC Admin', 'CNC Vertrieb', 'CNC Fertigung', 'System Manager'],
  arbeitsgaenge: ['CNC Admin', 'System Manager'],
};

// Kunden, Bauteile, Lieferanten, Maschinen und Materialien. Die Listen werden beim ersten Öffnen geladen.
export const useStammdaten = defineStore('stammdaten', () => {
  const ui = useUi();
  const stamm = useStamm();
  const listen = reactive({ kunde: null, lieferant: null, maschine: null, material: null, bauteil: null });

  const darf = (art) => (benutzer()?.rollen ?? []).some((r) => (SCHREIBEN[art] ?? []).includes(r));

  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  async function laden(art, neu = false) {
    if (listen[art] && !neu) return;
    const l = await sicher(() => call('cnc_one.api.stammdaten.liste', { art }));
    if (l) listen[art] = l;
  }

  const planKey = (b) => ({ kunde: b.kundeId, nr: b.teilenummer });

  async function speichern(art, daten) {
    const vorher = art === 'bauteil' && daten.id ? listen.bauteil?.find((x) => x.id === daten.id) : null;
    const rec = await sicher(() => call('cnc_one.api.stammdaten.speichern', { art, daten }));
    if (!rec) return null;
    const l = listen[art] ?? (listen[art] = []);
    const i = l.findIndex((x) => x.id === rec.id);
    if (i >= 0) l[i] = rec;
    else l.push(rec);
    await sicher(stammdatenAktualisieren);
    if (art === 'bauteil') {
      if (vorher) stamm.planEintragen(planKey(vorher).kunde, planKey(vorher).nr, []);
      stamm.planEintragen(rec.kundeId, rec.teilenummer, rec.arbeitsgaenge);
    }
    ui.toast('Gespeichert', 'ok');
    return rec;
  }

  async function loeschen(art, id) {
    const alt = art === 'bauteil' ? listen.bauteil?.find((x) => x.id === id) : null;
    if (!(await sicher(() => call('cnc_one.api.stammdaten.loeschen', { art, id })))) return false;
    listen[art] = (listen[art] ?? []).filter((x) => x.id !== id);
    await sicher(stammdatenAktualisieren);
    if (alt) stamm.planEintragen(alt.kundeId, alt.teilenummer, []);
    ui.toast('Gelöscht');
    return true;
  }

  return { listen, darf, laden, speichern, loeschen };
});
