import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { felderVon, produziert } from '../lib/fertigung.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useBelege } from './belege.js';
import { useStamm } from './stamm.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));
const FELDER_PAUSE = 700;

// Fertigungsbauteile liegen in Frappe. Die Buchungsregeln (Abhaken, Sendungen, Status) rechnet der Server,
// der Browser zeigt nur das Ergebnis, das jede Antwort mitbringt.
export const useFertigung = defineStore('fertigung', () => {
  const ui = useUi();
  const belege = useBelege();
  const stamm = useStamm();
  const liste = ref(kopie(stammdatenRoh().fertigung ?? []));

  const bauteil = (id) => liste.value.find((x) => x.id === id) ?? null;
  const fuerAuftrag = (auftragId) => liste.value.filter((x) => x.auftragId === auftragId);
  const offen = computed(() => liste.value.filter((x) => x.status !== 'Fertig'));

  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  // Stand der bearbeitbaren Felder, den der Server schon kennt (verhindert unnötiges Speichern)
  const stand = {};
  const standVon = (fb) => JSON.stringify(felderVon(fb));

  for (const fb of liste.value) stand[fb.id] = standVon(fb);

  function einsetzen(fb) {
    const i = liste.value.findIndex((x) => x.id === fb.id);
    if (i >= 0) liste.value[i] = fb;
    else liste.value.push(fb);
    stand[fb.id] = standVon(fb);
  }

  // Antwort einer Änderung: Fertigungsbauteil ersetzen, Auftragsstatus nachziehen
  function uebernehmen(res) {
    einsetzen(res.fb);
    belege.auftragStatusSetzen(res.fb.auftragId, res.auftragStatus);
    return res;
  }

  // Ungespeicherte Feldänderungen gehen vor jeder anderen Änderung raus, damit die Antwort sie nicht überschreibt.
  const timer = {};
  async function flush(id) {
    if (!timer[id]) return;
    clearTimeout(timer[id]);
    delete timer[id];
    await felderSpeichern(id);
  }

  async function aendern(id, methode, args = {}) {
    await flush(id);
    const res = await sicher(() => call(`cnc_one.api.fertigung.${methode}`, { id, ...args }));
    return res ? uebernehmen(res) : null;
  }

  // Automatisches Speichern der frei bearbeitbaren Felder
  function felderPlanen(id) {
    const fb = bauteil(id);
    if (!fb || standVon(fb) === stand[id]) return;
    clearTimeout(timer[id]);
    timer[id] = setTimeout(() => felderSpeichern(id), FELDER_PAUSE);
  }

  async function felderSpeichern(id) {
    delete timer[id];
    const fb = bauteil(id);
    if (!fb) return;
    const gesendet = standVon(fb);
    if (gesendet === stand[id]) return;
    const res = await sicher(() => call('cnc_one.api.fertigung.felder_speichern', { id, felder: felderVon(fb) }));
    if (!res) return;
    stand[id] = gesendet;
    // Nur abgeleitete Werte zurückholen, damit Eingaben während des Speicherns nicht überschrieben werden
    fb.status = res.fb.status;
    for (const ag of fb.arbeitsgaenge) {
      const neu = res.fb.arbeitsgaenge.find((x) => x.id === ag.id);
      if (neu) ag.status = neu.status;
    }
    belege.auftragStatusSetzen(fb.auftragId, res.auftragStatus);
  }

  async function ausAuftrag(auftragId) {
    const res = await sicher(() => call('cnc_one.api.fertigung.starten', { auftrag: auftragId }));
    if (!res) return;
    for (const fb of res.fertigung) einsetzen(fb);
    belege.auftragEinsetzen(res.auftrag);
    const n = res.fertigung.length;
    ui.toast(res.ohnePlan
      ? `${n} Fertigungsbauteile angelegt, ${res.ohnePlan} ohne Arbeitsgänge`
      : `${n} Fertigungsbauteil${n === 1 ? '' : 'e'} angelegt`, res.ohnePlan ? 'warn' : 'ok');
  }

  async function buchen(fbId, agId, menge) {
    const m = Math.floor(Number(menge));
    if (!(m > 0)) return;
    const res = await aendern(fbId, 'buchen', { ag_id: agId, menge: m });
    if (!res) return;
    if (res.nachgeholt) ui.toast(`${res.nachgeholt} vorherige${res.nachgeholt === 1 ? 'r' : ''} Arbeitsgang${res.nachgeholt === 1 ? '' : 'e'} mit abgehakt`);
    const ag = res.fb.arbeitsgaenge.find((x) => x.id === agId);
    if (ag && ag.gebucht > res.fb.menge) ui.toast(`Überproduktion: ${ag.gebucht - res.fb.menge} Stk über Soll, später ins Lager`);
  }

  const buchungLoeschen = (fbId, buchungId) => aendern(fbId, 'buchung_loeschen', { buchung: buchungId });
  const arbeitsgangHinzu = (fbId, typ) => aendern(fbId, 'arbeitsgang_hinzu', { typ });
  const arbeitsgangWeg = (fbId, agId) => aendern(fbId, 'arbeitsgang_weg', { ag_id: agId });
  const arbeitsgangVerschieben = (fbId, agId, richtung) => aendern(fbId, 'arbeitsgang_verschieben', { ag_id: agId, richtung });

  async function vorlageAnwenden(fbId, vorlageId) {
    const res = await aendern(fbId, 'vorlage_anwenden', { vorlage: vorlageId });
    if (res) ui.toast(`${res.hinzugefuegt} Arbeitsgänge aus der Vorlage hinzugefügt`, 'ok');
  }

  async function planAmBauteilSpeichern(fbId) {
    await flush(fbId);
    const fb = bauteil(fbId);
    const res = await sicher(() => call('cnc_one.api.fertigung.plan_am_bauteil_speichern', { id: fbId }));
    if (!res || !fb) return;
    stamm.planEintragen(fb.kundeId, fb.teil.teilenummer, res.bauteil.arbeitsgaenge);
    ui.toast('Arbeitsplan am Bauteil gespeichert', 'ok');
  }

  // Fremdvergabe in Sendungen: jede Sendung kann eine Teilmenge sein.
  const sendungAnlegen = (fbId, agId, menge) => aendern(fbId, 'sendung_anlegen', { ag_id: agId, menge: menge ? Math.floor(Number(menge)) : null });
  const sendungWeg = (fbId, agId, sendungId) => aendern(fbId, 'sendung_weg', { ag_id: agId, sendung: sendungId });
  const sendungLoeschen = (fbId, agId, sendungId) => aendern(fbId, 'sendung_loeschen', { ag_id: agId, sendung: sendungId });
  async function sendungZurueck(fbId, agId, sendungId) {
    if (await aendern(fbId, 'sendung_zurueck', { ag_id: agId, sendung: sendungId })) ui.toast('Ware vom Lieferanten zurück gebucht', 'ok');
  }

  // Manuelle Statusänderung (Board). Fertig bucht den Rest, Offen ist nur ohne Buchungen möglich.
  async function statusSetzen(fbId, status) {
    const fb = bauteil(fbId);
    if (!fb || fb.status === status) return;
    const vorher = produziert(fb);
    const res = await aendern(fbId, 'status_setzen', { status });
    if (res && status === 'Fertig' && vorher < fb.menge) ui.toast('Restmenge in allen Arbeitsgängen gebucht');
  }

  return {
    liste, offen, bauteil, fuerAuftrag, ausAuftrag, buchen, buchungLoeschen, felderPlanen, flush,
    arbeitsgangHinzu, arbeitsgangWeg, arbeitsgangVerschieben, vorlageAnwenden, planAmBauteilSpeichern,
    sendungAnlegen, sendungWeg, sendungZurueck, sendungLoeschen, statusSetzen,
  };
});
