// Rohmaterial-Baum (Werkstoffe, Zustände, Ausführungen, Abmessungen, Anforderungen) und Chargen im Rohmaterial-Lager.
// Reaktiv für alle Ansichten; neue Einträge aus jeder Stufe der Auswahl landen sofort hier und in den Stammdaten.
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { call, hochladen } from '../data/api.js';
import { stammdatenRoh, repo } from '../data/repo.js';
import { useUi } from './ui.js';

export const useWerkstoff = defineStore('werkstoff', () => {
  const ui = useUi();
  const materialien = ref([...(stammdatenRoh().materialien ?? [])]);
  const baum = ref(stammdatenRoh().werkstoffbaum ?? { zustaende: [], ausfuehrungen: [], abmessungen: [], anforderungen: [] });
  const chargenListe = ref(null); // vorrätige Chargen, beim ersten Bedarf geladen

  const zustandText = computed(() => Object.fromEntries(baum.value.zustaende.map((z) => [z.code, z.beschreibung])));
  const werkstoff = (name) => materialien.value.find((m) => m.name === name) ?? null;

  async function sicher(fn, ok) {
    try {
      const r = await fn();
      if (ok) ui.toast(typeof ok === 'function' ? ok(r) : ok, 'ok');
      return r;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  function werkstoffMerken(m) {
    const i = materialien.value.findIndex((x) => x.name === m.name);
    materialien.value = i >= 0 ? materialien.value.map((x, j) => (j === i ? { ...x, ...m } : x)) : [...materialien.value, m].sort((a, b) => a.name.localeCompare(b.name, 'de'));
    repo.materialien.merken(m);
  }
  function inBaum(teil, eintrag, key) {
    const l = baum.value[teil];
    const i = l.findIndex((x) => x[key] === eintrag[key]);
    baum.value = { ...baum.value, [teil]: i >= 0 ? l.map((x, j) => (j === i ? eintrag : x)) : [...l, eintrag] };
    stammdatenRoh().werkstoffbaum = baum.value;
  }

  // ---- In jeder Stufe neu anlegen
  async function werkstoffAnlegen(d) {
    const m = await sicher(() => call('cnc_one.api.werkstoff.werkstoff_anlegen', d), (x) => `Werkstoff „${x.name}“ angelegt`);
    if (m) werkstoffMerken(m);
    return m;
  }
  async function zustandHinzu(werkstoffName, code, beschreibung = '') {
    const r = await sicher(() => call('cnc_one.api.werkstoff.zustand_hinzu', { werkstoff: werkstoffName, code, beschreibung }), (x) => `Zustand „${x.zustand.code}“ bei ${werkstoffName} ergänzt`);
    if (!r) return null;
    werkstoffMerken(r.werkstoff);
    inBaum('zustaende', r.zustand, 'code');
    return r.zustand;
  }
  async function zustandHinzuOhneWerkstoff(code, beschreibung = '') {
    const r = await sicher(() => call('cnc_one.api.werkstoff.zustand_hinzu', { werkstoff: '', code, beschreibung }), (x) => `Zustand „${x.zustand.code}“ angelegt`);
    if (r) inBaum('zustaende', r.zustand, 'code');
    return r?.zustand ?? null;
  }
  async function formFreigeben(werkstoffName, form) {
    const m = await sicher(() => call('cnc_one.api.werkstoff.form_freigeben', { werkstoff: werkstoffName, form }), `${form} für ${werkstoffName} freigegeben`);
    if (m) werkstoffMerken(m);
    return m;
  }
  async function ausfuehrungHinzu(form, bezeichnung, isoGruppen = '') {
    const a = await sicher(() => call('cnc_one.api.werkstoff.ausfuehrung_hinzu', { form, bezeichnung, iso_gruppen: isoGruppen }), (x) => `Ausführung „${x.name}“ angelegt`);
    if (a) inBaum('ausfuehrungen', a, 'id');
    return a;
  }
  async function abmessungHinzu(form, mass1, mass2 = 0) {
    const a = await sicher(() => call('cnc_one.api.werkstoff.abmessung_hinzu', { form, mass1, mass2 }), (x) => `Abmessung ${form} ${x.text} angelegt`);
    if (!a) return null;
    const l = baum.value.abmessungen.filter((x) => x.id !== a.id);
    const formen = ['Rund', 'Vierkant', 'Flach', 'Sechskant', 'Rohr', 'Platte'];
    baum.value = { ...baum.value, abmessungen: [...l, a].sort((x, y) => formen.indexOf(x.form) - formen.indexOf(y.form) || x.m1 - y.m1 || x.m2 - y.m2) };
    stammdatenRoh().werkstoffbaum = baum.value;
    return a;
  }
  async function anforderungHinzu(bezeichnung) {
    const a = await sicher(() => call('cnc_one.api.werkstoff.anforderung_hinzu', { bezeichnung }), (x) => `Anforderung „${x.name}“ angelegt`);
    if (a) inBaum('anforderungen', a, 'name');
    return a;
  }

  // ---- Stammdaten-Pflege
  async function neuLaden(alle = false) {
    const b = await sicher(() => call('cnc_one.api.werkstoff.baum_laden', { alle: alle ? 1 : 0 }));
    if (b && !alle) { baum.value = b; stammdatenRoh().werkstoffbaum = b; }
    return b;
  }
  async function eintragSetzen(art, id, werte) {
    const b = await sicher(() => call('cnc_one.api.werkstoff.eintrag_setzen', { art, id, ...werte }));
    if (b) await neuLaden();
    return b;
  }
  async function eintragLoeschen(art, id) {
    const b = await sicher(() => call('cnc_one.api.werkstoff.eintrag_loeschen', { art, id }), 'Gelöscht');
    if (b) {
      await neuLaden();
      if (art === 'zustand') materialien.value = materialien.value.map((m) => ({ ...m, zustaende: (m.zustaende ?? []).filter((z) => z !== id) }));
    }
    return b;
  }
  // nach stammdatenAktualisieren (Stammdaten-Seiten): Liste und Baum neu aus den Stammdaten
  function materialienAktualisieren() {
    materialien.value = [...(stammdatenRoh().materialien ?? [])];
    if (stammdatenRoh().werkstoffbaum) baum.value = stammdatenRoh().werkstoffbaum;
  }

  // ---- Chargen
  async function chargenLaden(neu = false, alle = false) {
    if (chargenListe.value && !neu && !alle) return chargenListe.value;
    const l = await sicher(() => call('cnc_one.api.werkstoff.chargen', { alle: alle ? 1 : 0 }));
    if (l && !alle) chargenListe.value = l;
    return l ?? [];
  }
  async function chargeSpeichern(daten, datei = null) {
    let c = await sicher(() => call('cnc_one.api.werkstoff.charge_speichern', { daten }));
    if (!c) return null;
    if (datei) {
      const f = await sicher(() => hochladen(datei, { doctype: 'Rohmaterialcharge', docname: c.id }));
      if (f?.file_url) c = (await sicher(() => call('cnc_one.api.werkstoff.charge_speichern', { daten: { id: c.id, zeugnisDatei: f.file_url } }))) ?? c;
    }
    const l = (chargenListe.value ?? []).filter((x) => x.id !== c.id);
    chargenListe.value = c.status === 'Vorrätig' ? [c, ...l] : l;
    ui.toast(daten.id ? 'Charge gespeichert' : `Charge ${c.id} eingebucht`, 'ok');
    return c;
  }

  return {
    materialien, baum, zustandText, werkstoff, chargenListe,
    werkstoffAnlegen, zustandHinzu, zustandHinzuOhneWerkstoff, formFreigeben, ausfuehrungHinzu, abmessungHinzu, anforderungHinzu,
    neuLaden, eintragSetzen, eintragLoeschen, materialienAktualisieren, chargenLaden, chargeSpeichern,
  };
});
