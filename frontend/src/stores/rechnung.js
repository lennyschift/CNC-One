import { defineStore } from 'pinia';
import { ref } from 'vue';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useBelege } from './belege.js';
import { useLieferung } from './lieferung.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));

// Rechnungen, Zahlungen und Mahnungen liegen in Frappe. Rechnungen entstehen nur aus einem Auftrag. Jede Änderung ändert auch den
// Abrechnungsstand im Auftrag und in den Lieferscheinen, deshalb werden die danach neu geholt.
export const useRechnung = defineStore('rechnung', () => {
  const ui = useUi();
  const belege = useBelege();
  const lieferung = useLieferung();
  const rechnungen = ref(kopie(stammdatenRoh().rechnungen ?? []));
  const mahnungen = ref(kopie(stammdatenRoh().mahnungen ?? []));

  const rechnung = (id) => rechnungen.value.find((x) => x.id === id) ?? null;
  const mahnung = (id) => mahnungen.value.find((x) => x.id === id) ?? null;
  const fuerAuftrag = (auftragId) => rechnungen.value.filter((x) => x.auftragId === auftragId);

  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  function einsetzen(liste, rec, vorne = true) {
    const i = liste.value.findIndex((x) => x.id === rec.id);
    if (i >= 0) liste.value[i] = rec;
    else if (vorne) liste.value.unshift(rec);
    else liste.value.push(rec);
    return rec;
  }

  const nachAenderung = () => Promise.all([belege.auftraegeNeuLaden(), lieferung.neuLaden(), neuLaden()]);

  async function neuLaden() {
    const [r, m] = await Promise.all([call('cnc_one.api.rechnung.liste'), call('cnc_one.api.mahnung.liste')]);
    rechnungen.value = r;
    mahnungen.value = m;
  }

  // ---- Rechnung
  const vorschlag = (auftrag) => sicher(() => call('cnc_one.api.rechnung.vorschlag', { auftrag }));

  async function anlegen(werte) {
    const rec = await sicher(() => call('cnc_one.api.rechnung.anlegen', werte));
    if (!rec) return null;
    einsetzen(rechnungen, rec);
    await sicher(nachAenderung);
    ui.toast('Rechnungsentwurf angelegt', 'ok');
    return rec;
  }

  async function speichern(id, felder) {
    const rec = await sicher(() => call('cnc_one.api.rechnung.speichern', { id, felder }));
    if (rec) einsetzen(rechnungen, rec);
    return rec;
  }

  async function verwerfen(id) {
    if (!(await sicher(() => call('cnc_one.api.rechnung.verwerfen', { id })))) return false;
    rechnungen.value = rechnungen.value.filter((x) => x.id !== id);
    await sicher(nachAenderung);
    ui.toast('Entwurf verworfen');
    return true;
  }

  async function festschreiben(id) {
    const rec = await sicher(() => call('cnc_one.api.rechnung.festschreiben', { id }));
    if (!rec) return null;
    einsetzen(rechnungen, rec);
    await sicher(nachAenderung);
    ui.toast(`${rec.nummer} festgeschrieben`, 'ok');
    return rec;
  }

  async function stornieren(id, grund) {
    const res = await sicher(() => call('cnc_one.api.rechnung.stornieren', { id, grund }));
    if (!res) return null;
    einsetzen(rechnungen, res.original);
    einsetzen(rechnungen, res.storno);
    await sicher(nachAenderung);
    ui.toast(`${res.original.nummer} storniert, Stornorechnung ${res.storno.nummer}`, 'ok');
    return res;
  }

  async function eRechnungNeu(id) {
    const rec = await sicher(() => call('cnc_one.api.erechnung.neu_erzeugen', { id }));
    if (rec) { einsetzen(rechnungen, rec); ui.toast(rec.eRechnung.hinweis ? 'E-Rechnung erzeugt, es fehlen noch Angaben' : 'E-Rechnung erzeugt', rec.eRechnung.hinweis ? 'warn' : 'ok'); }
    return rec;
  }

  // ---- Zahlung
  async function zahlungErfassen(rechnungId, werte) {
    const rec = await sicher(() => call('cnc_one.api.rechnung.zahlung_erfassen', { rechnung: rechnungId, ...werte }));
    if (!rec) return null;
    einsetzen(rechnungen, rec);
    await sicher(nachAenderung);
    ui.toast('Zahlung erfasst', 'ok');
    return rec;
  }

  async function zahlungStornieren(id, grund) {
    const rec = await sicher(() => call('cnc_one.api.rechnung.zahlung_stornieren', { id, grund }));
    if (!rec) return null;
    einsetzen(rechnungen, rec);
    await sicher(nachAenderung);
    ui.toast('Zahlung storniert');
    return rec;
  }

  // ---- Mahnwesen
  const mahnVorschlag = () => sicher(() => call('cnc_one.api.mahnung.vorschlag'));

  async function mahnungAnlegen(rechnungId, stufe = null) {
    const rec = await sicher(() => call('cnc_one.api.mahnung.anlegen', { rechnung: rechnungId, stufe }));
    if (!rec) return null;
    einsetzen(mahnungen, rec);
    await sicher(neuLaden);
    ui.toast(`${rec.stufe} angelegt`, 'ok');
    return rec;
  }

  async function mahnungVersendet(id) {
    const rec = await sicher(() => call('cnc_one.api.mahnung.versendet_setzen', { id }));
    if (rec) { einsetzen(mahnungen, rec); await sicher(neuLaden); ui.toast('Als versendet markiert', 'ok'); }
    return rec;
  }

  async function mahnungZurueckziehen(id) {
    const rec = await sicher(() => call('cnc_one.api.mahnung.zurueckziehen', { id }));
    if (rec) { einsetzen(mahnungen, rec); await sicher(neuLaden); ui.toast('Mahnung zurückgezogen'); }
    return rec;
  }

  return {
    rechnungen, mahnungen, rechnung, mahnung, fuerAuftrag, neuLaden, vorschlag, anlegen, speichern, verwerfen, festschreiben, stornieren, eRechnungNeu,
    zahlungErfassen, zahlungStornieren, mahnVorschlag, mahnungAnlegen, mahnungVersendet, mahnungZurueckziehen,
  };
});
