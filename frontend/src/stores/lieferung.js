import { defineStore } from 'pinia';
import { ref } from 'vue';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useBelege } from './belege.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));

// Lieferscheine und das Fertigbauteil Lager liegen in Frappe. Jeder Lieferschein bucht im Lager ab und ändert den Lieferstand
// im Auftrag, deshalb werden danach die Aufträge neu geholt.
export const useLieferung = defineStore('lieferung', () => {
  const ui = useUi();
  const belege = useBelege();
  const lieferscheine = ref(kopie(stammdatenRoh().lieferscheine ?? []));
  const lager = ref(kopie(stammdatenRoh().lager ?? []));

  const lieferschein = (id) => lieferscheine.value.find((x) => x.id === id) ?? null;
  const fuerAuftrag = (auftragId) => lieferscheine.value.filter((l) => l.positionen.some((p) => p.auftragId === auftragId));

  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  function einsetzen(rec) {
    const i = lieferscheine.value.findIndex((x) => x.id === rec.id);
    if (i >= 0) lieferscheine.value[i] = rec;
    else lieferscheine.value.unshift(rec);
    return rec;
  }

  // Nach Rechnungen ändert sich in den Lieferscheinen der Verweis „berechnet in …“
  async function neuLaden() {
    try { lieferscheine.value = await call('cnc_one.api.lieferschein.liste'); } catch { /* alter Stand bleibt */ }
  }

  const vorschlag = (auftrag) => sicher(() => call('cnc_one.api.lieferschein.vorschlag', { auftrag }));

  async function nachLieferung() {
    await Promise.all([belege.auftraegeNeuLaden(), lagerLaden()]);
  }

  async function anlegen(werte) {
    const rec = await sicher(() => call('cnc_one.api.lieferschein.anlegen', werte));
    if (!rec) return null;
    einsetzen(rec);
    await sicher(nachLieferung);
    ui.toast(`${rec.id} angelegt`, 'ok');
    return rec;
  }

  async function geliefertSetzen(id) {
    const rec = await sicher(() => call('cnc_one.api.lieferschein.geliefert_setzen', { id }));
    if (rec) { einsetzen(rec); ui.toast(`${id} als geliefert markiert`, 'ok'); }
    return rec;
  }

  async function stornieren(id) {
    const rec = await sicher(() => call('cnc_one.api.lieferschein.stornieren', { id }));
    if (rec) { einsetzen(rec); await sicher(nachLieferung); ui.toast(`${id} storniert, Menge zurück im Lager`); }
    return rec;
  }

  async function lagerLaden() {
    const r = await call('cnc_one.api.lager.bestand');
    lager.value = r.bestand;
    return r.bestand;
  }

  const buchungen = (bauteil) => sicher(() => call('cnc_one.api.lager.buchungen', { bauteil }));

  async function korrigieren(bauteil, menge, grund) {
    const r = await sicher(() => call('cnc_one.api.lager.korrigieren', { bauteil, menge, grund }));
    if (r) { await sicher(lagerLaden); ui.toast('Korrekturbuchung gespeichert', 'ok'); }
    return r;
  }

  return { lieferscheine, lager, lieferschein, fuerAuftrag, neuLaden, vorschlag, anlegen, geliefertSetzen, stornieren, lagerLaden, buchungen, korrigieren };
});
