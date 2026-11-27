import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { felderVon, produziert, zeitenNoetigBeiBuchung, zeitenNoetigBeiFertig, startPruefen, materialFehlt, wirdFertig } from '../lib/fertigung.js';
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
      if (neu) { ag.status = neu.status; ag.serie = neu.serie; }
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

  // Rohmaterial: Rohteil ändern, Charge wählen, Entnahme aus dem Lager (mit Reststück) und zurücknehmen. Beim
  // Fertigmelden fragt MaterialEntnahmeDialog (App.vue) nach, falls noch nichts entnommen ist:
  // {} = entnommen, { ohne: Grund } = ohne Lagerentnahme, null = abgebrochen.
  const rohSetzen = (fbId, werte) => aendern(fbId, 'roh_setzen', werte);
  async function materialEntnehmen(fbId, werte) {
    const res = await aendern(fbId, 'material_entnehmen', werte);
    if (res) ui.toast('Entnahme gebucht, Lager aktualisiert', 'ok');
    return res;
  }
  const entnahmeZurueck = (fbId, entnahme) => aendern(fbId, 'entnahme_zurueck', { entnahme });
  const materialAnfrage = ref(null);
  function materialAbfragen(fbId, pflicht = false) {
    return new Promise((resolve) => { materialAnfrage.value = { fbId, pflicht, resolve }; });
  }
  function materialFreigeben(fbId) {
    return materialFehlt(bauteil(fbId)) ? materialAbfragen(fbId, true) : Promise.resolve({});
  }
  function materialAntwort(antwort) {
    const a = materialAnfrage.value;
    materialAnfrage.value = null;
    a?.resolve(antwort);
  }

  // Checkliste vor dem Start: abhaken (mit Notiz), eigene Punkte. Sind beim Start noch Pflichtpunkte offen, zeigt
  // CheckStartDialog (App.vue) sie an: { trotzdem: 0 } = alles da, { trotzdem: 1 } = bewusst ohne, null = abgebrochen.
  const checkSetzen = (fbId, punkt, werte) => aendern(fbId, 'check_setzen', { punkt, ...werte });
  const checkEigen = (fbId, text, pflicht = false) => aendern(fbId, 'check_eigen', { text, pflicht: pflicht ? 1 : 0 });
  const checkWeg = (fbId, punkt) => aendern(fbId, 'check_weg', { punkt });
  const startAnfrage = ref(null);
  function startFreigeben(fbId, status = 'In Fertigung') {
    if (!startPruefen(bauteil(fbId), status)) return Promise.resolve({ trotzdem: 0 });
    return new Promise((resolve) => { startAnfrage.value = { fbId, status, resolve }; });
  }
  function startAntwort(antwort) {
    const a = startAnfrage.value;
    startAnfrage.value = null;
    a?.resolve(antwort);
  }

  // Zeiten beim Abschließen: der Dialog (ZeitenDialog in App.vue) fragt sie ab; null = abgebrochen.
  const zeitenAnfrage = ref(null);
  function zeitenAbfragen(fb, ags, titel) {
    if (!ags.length) return Promise.resolve([]);
    return new Promise((resolve) => { zeitenAnfrage.value = { fb, ags, titel, resolve }; });
  }
  function zeitenAntwort(zeiten) {
    const a = zeitenAnfrage.value;
    zeitenAnfrage.value = null;
    a?.resolve(zeiten);
  }
  async function zeitenMelden(fbId, agIds) {
    const fb = bauteil(fbId);
    if (!fb) return;
    const zeiten = await zeitenAbfragen(fb, fb.arbeitsgaenge.filter((a) => agIds.includes(a.id)), 'Zeiten melden');
    if (zeiten?.length && await aendern(fbId, 'zeiten_melden', { zeiten })) ui.toast('Zeiten gespeichert', 'ok');
  }

  async function buchen(fbId, agId, menge) {
    const m = Math.floor(Number(menge));
    if (!(m > 0)) return;
    const frei = await startFreigeben(fbId);
    if (!frei) return;
    const mat = wirdFertig(bauteil(fbId), agId, m) ? await materialFreigeben(fbId) : {};
    if (!mat) return;
    const fb = bauteil(fbId);
    const zeiten = fb ? await zeitenAbfragen(fb, zeitenNoetigBeiBuchung(fb, agId, m), 'Arbeitsgang abschließen') : [];
    if (zeiten === null) return;
    const res = await aendern(fbId, 'buchen', { ag_id: agId, menge: m, zeiten, trotzdem: frei.trotzdem, ohne_material: mat.ohne ?? '' });
    if (!res) return;
    if (res.nachgeholt) ui.toast(`${res.nachgeholt} vorherige${res.nachgeholt === 1 ? 'r' : ''} Arbeitsgang${res.nachgeholt === 1 ? '' : 'e'} mit abgehakt`);
    const ag = res.fb.arbeitsgaenge.find((x) => x.id === agId);
    if (ag && ag.gebucht > res.fb.menge) ui.toast(`Überproduktion: ${ag.gebucht - res.fb.menge} Stk über Soll, später ins Lager`);
  }

  const buchungLoeschen = (fbId, buchungId) => aendern(fbId, 'buchung_loeschen', { buchung: buchungId });
  const arbeitsgangHinzu = (fbId, typ, name = '') => aendern(fbId, 'arbeitsgang_hinzu', { typ, name });
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
    const frei = await startFreigeben(fbId, status);
    if (!frei) return;
    const mat = status === 'Fertig' ? await materialFreigeben(fbId) : {};
    if (!mat) return;
    const vorher = produziert(fb);
    const zeiten = status === 'Fertig' ? await zeitenAbfragen(fb, zeitenNoetigBeiFertig(fb), 'Bauteil fertig melden') : [];
    if (zeiten === null) return;
    const res = await aendern(fbId, 'status_setzen', { status, zeiten, trotzdem: frei.trotzdem, ohne_material: mat.ohne ?? '' });
    if (res && status === 'Fertig' && vorher < fb.menge) ui.toast('Restmenge in allen Arbeitsgängen gebucht');
  }

  // nach einer Auftragsänderung (Menge, Termin, neue oder entfallene Positionen)
  async function neuLaden() {
    try { liste.value = await call('cnc_one.api.fertigung.liste'); } catch { /* der alte Stand bleibt sichtbar */ }
  }

  return {
    neuLaden, liste, offen, bauteil, fuerAuftrag, ausAuftrag, buchen, buchungLoeschen, felderPlanen, flush,
    arbeitsgangHinzu, arbeitsgangWeg, arbeitsgangVerschieben, vorlageAnwenden, planAmBauteilSpeichern,
    sendungAnlegen, sendungWeg, sendungZurueck, sendungLoeschen, statusSetzen,
    zeitenAnfrage, zeitenAntwort, zeitenMelden,
    checkSetzen, checkEigen, checkWeg, startAnfrage, startAntwort,
    rohSetzen, materialEntnehmen, entnahmeZurueck, materialAnfrage, materialAbfragen, materialAntwort,
  };
});
