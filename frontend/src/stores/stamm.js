import { defineStore } from 'pinia';
import { ref } from 'vue';
import { uid } from '../lib/format.js';
import { planAus } from '../lib/fertigung.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));

// Arbeitsgangarten, Vorlagen und die Arbeitspläne der Bauteile liegen in Frappe.
// `plaene` ist nur der Zwischenspeicher im Browser, abgelegt nach Kunde und Teilenummer.
export const useStamm = defineStore('stamm', () => {
  const ui = useUi();
  const roh = stammdatenRoh();
  const arten = ref(kopie(roh.arten));
  const vorlagen = ref(kopie(roh.vorlagen));
  const plaene = ref({});

  // Fehler der API werden angezeigt, die Oberfläche bleibt bedienbar.
  async function sicher(fn) {
    try { return await fn(); } catch (e) { ui.toast(e.message, 'warn'); return null; }
  }

  const teilKey = (kundeId, teilenummer) => {
    const t = String(teilenummer ?? '').trim().toLowerCase();
    return kundeId && t ? `${kundeId}|${t}` : '';
  };
  const hatPlan = (kundeId, teilenummer) => !!plaene.value[teilKey(kundeId, teilenummer)]?.length;
  for (const b of roh.bauteile ?? []) {
    if (b.arbeitsgaenge.length) plaene.value[teilKey(b.kundeId, b.teilenummer)] = kopie(b.arbeitsgaenge);
  }

  function planFuer(kundeId, teilenummer) {
    const p = plaene.value[teilKey(kundeId, teilenummer)];
    return p?.length ? kopie(p) : null;
  }
  // Speichert den Arbeitsplan am Bauteil in Frappe. `info` (name, zeichnungsnr, material) füllt ein neues Bauteil.
  async function planSpeichern(kundeId, teilenummer, arbeitsgaenge, info = {}) {
    const k = teilKey(kundeId, teilenummer);
    if (!k) return false;
    const b = await sicher(() => call('cnc_one.api.bauteil.plan_speichern', {
      kunde: kundeId,
      teilenummer: String(teilenummer).trim(),
      arbeitsgaenge: planAus(arbeitsgaenge, uid),
      name: info.name ?? '',
      zeichnungsnr: info.zeichnungsnr ?? '',
      material: info.material ?? '',
    }));
    if (!b) return false;
    plaene.value[k] = kopie(b.arbeitsgaenge);
    return true;
  }

  // Übernimmt einen Arbeitsplan, den der Server schon am Bauteil gespeichert hat (z. B. beim Anlegen eines Auftrags).
  function planEintragen(kundeId, teilenummer, arbeitsgaenge) {
    const k = teilKey(kundeId, teilenummer);
    if (k) plaene.value[k] = kopie(arbeitsgaenge);
  }

  const vorlagenFuer = (kundeId) => vorlagen.value.filter((v) => !v.kundeId || v.kundeId === kundeId);

  // Arbeitsgänge einer Vorlage mit neuen Ids, damit mehrfaches Anwenden nichts vermischt.
  function vorlageKopie(vorlageId) {
    const v = vorlagen.value.find((x) => x.id === vorlageId);
    return v ? v.arbeitsgaenge.map((a) => ({ ...kopie(a), id: uid() })) : [];
  }

  async function vorlageNeu(werte = {}) {
    const v = await sicher(() => call('cnc_one.api.stamm.vorlage_speichern', { vorlage: { name: 'Neue Vorlage', kundeId: '', arbeitsgaenge: [], ...werte } }));
    if (v) vorlagen.value.push(v);
    return v;
  }
  async function vorlageSpeichern(v) {
    return sicher(() => call('cnc_one.api.stamm.vorlage_speichern', { vorlage: kopie(v) }));
  }
  async function vorlageLoeschen(id) {
    if (await sicher(() => call('cnc_one.api.stamm.vorlage_loeschen', { id }))) vorlagen.value = vorlagen.value.filter((v) => v.id !== id);
  }

  async function artHinzu(name, typ) {
    const n = String(name ?? '').trim();
    if (!n || arten.value.some((a) => a.name.toLowerCase() === n.toLowerCase())) return false;
    const a = await sicher(() => call('cnc_one.api.stamm.art_speichern', { name: n, typ }));
    if (a) arten.value.push(a);
    return !!a;
  }
  async function artSpeichern(art) {
    return sicher(() => call('cnc_one.api.stamm.art_speichern', { name: art.name, typ: art.typ, id: art.id }));
  }
  async function artLoeschen(id) {
    if (await sicher(() => call('cnc_one.api.stamm.art_loeschen', { id }))) arten.value = arten.value.filter((a) => a.id !== id);
  }

  return { arten, vorlagen, plaene, teilKey, hatPlan, planFuer, planSpeichern, planEintragen, vorlagenFuer, vorlageKopie, vorlageNeu, vorlageSpeichern, vorlageLoeschen, artHinzu, artSpeichern, artLoeschen };
});
