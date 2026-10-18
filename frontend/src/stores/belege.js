import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { angebotStatus } from '../lib/beleg.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));

// Angebote und Aufträge liegen in Frappe; der Speicher hier ist nur der Zwischenspeicher der Oberfläche.
export const useBelege = defineStore('belege', () => {
  const ui = useUi();
  const angebote = ref(kopie(stammdatenRoh().angebote ?? []));
  const auftraege = ref(kopie(stammdatenRoh().auftraege ?? []));

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

  // Lieferstand und Fertigung ändern Aufträge, deshalb nach Lieferscheinen neu holen
  async function auftraegeNeuLaden() {
    try { auftraege.value = await call('cnc_one.api.auftrag.liste'); } catch { /* der alte Stand bleibt sichtbar */ }
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

  // Auftrag aus einem gesendeten Angebot. Der Server rechnet Preise und Summen selbst und liefert den Auftrag zurück.
  async function auftragAnlegen({ angebotId, kundenbestellnr, positionen }) {
    const rec = await sicher(() => call('cnc_one.api.auftrag.aus_angebot', { angebot: angebotId, kundenbestellnr, positionen }));
    if (!rec) return null;
    auftraege.value.unshift(rec);
    ui.toast(`${rec.id} angelegt`, 'ok');
    return rec;
  }

  // Antworten der Fertigung ändern Status oder Inhalt eines Auftrags
  function auftragEinsetzen(rec) {
    const i = auftraege.value.findIndex((a) => a.id === rec.id);
    if (i >= 0) auftraege.value[i] = rec;
    else auftraege.value.unshift(rec);
  }
  function auftragStatusSetzen(id, status) {
    const a = auftrag(id);
    if (a && status) a.status = status;
  }

  return { angebote, auftraege, bestelltFuer, statusVon, angebot, auftrag, angebotSpeichern, angebotSenden, angebotAblehnen, angebotLoeschen, auftragAnlegen, auftragEinsetzen, auftragStatusSetzen, auftraegeNeuLaden };
});
