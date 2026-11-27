<script setup>
// Rohmaterial-Lager: Chargen je Wareneingang mit Werkstoff, Zustand, Abmessung, Bestand, Werkszeugnis (PDF) und bestätigten
// Anforderungen. Filter nach Werkstoff, Form, Abmessung, Zustand und Nachweis; die Tabelle fasst je Material zusammen
// (z. B. „7075 Rund Ø60“: alle Chargen mit Längen, Stangen und Besonderheiten). Interne Chargennummer nach eigenem Muster
// (z. B. Lieferantenkürzel + Eingangsdatum). Wareneingang wählt das Material genau wie die Workbench (RohmaterialWahl).
import { ref, reactive, computed, watch, onMounted } from 'vue';
import { Layers, Plus, Search, FileBadge, ShieldCheck, Upload, Check, Rows3, List, Settings2, X } from '@lucide/vue';
import ListenTabelle from './ListenTabelle.vue';
import StammDialog from './StammDialog.vue';
import NumField from './NumField.vue';
import FormSymbol from './FormSymbol.vue';
import RohmaterialWahl from './RohmaterialWahl.vue';
import { isoGruppe } from '../lib/iso.js';
import { ZEUGNISSE, artikelText, interneChargennr, lagerFiltern, lagerGruppen } from '../lib/werkstoffbaum.js';
import { zahl } from '../lib/format.js';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useWerkstoff } from '../stores/werkstoff.js';
import { useUi } from '../stores/ui.js';

const ws = useWerkstoff();
const ui = useUi();
const alle = ref(false);
const liste = ref([]);
async function laden() { liste.value = await ws.chargenLaden(true, alle.value); }
onMounted(async () => {
  laden();
  try { const r = await call('cnc_one.api.werkstoff.chargen_muster_laden'); muster.value = r.muster; darfMuster.value = r.darf; } catch { /* Standard */ }
});

// ---- Filter
const filter = reactive({ suche: '', werkstoff: '', form: '', abmessung: '', zustand: '', pruefung: '' });
const gruppiert = ref(true);
const eindeutig = (werte) => [...new Set(werte.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), 'de', { numeric: true }));
const werkstoffe = computed(() => eindeutig(liste.value.map((c) => c.werkstoff)));
const formen = computed(() => eindeutig(liste.value.filter((c) => !filter.werkstoff || c.werkstoff === filter.werkstoff).map((c) => c.form)));
const abmessungen = computed(() => {
  const m = new Map();
  for (const c of liste.value) if ((!filter.werkstoff || c.werkstoff === filter.werkstoff) && (!filter.form || c.form === filter.form)) m.set(c.abmessung, c.abmessungText);
  return [...m].sort((a, b) => String(a[1]).localeCompare(String(b[1]), 'de', { numeric: true }));
});
const zustaende = computed(() => eindeutig(liste.value.filter((c) => !filter.werkstoff || c.werkstoff === filter.werkstoff).map((c) => c.zustand)));
const pruefungen = computed(() => eindeutig(liste.value.flatMap((c) => c.pruefungen ?? [])));
watch(() => filter.werkstoff, () => { filter.form = ''; filter.abmessung = ''; filter.zustand = ''; });
watch(() => filter.form, () => { filter.abmessung = ''; });
const gefiltert = computed(() => lagerFiltern(liste.value, filter));
const gruppen = computed(() => lagerGruppen(gefiltert.value));
const aktiv = computed(() => Object.values(filter).some(Boolean));
function zuruecksetzen() { Object.assign(filter, { suche: '', werkstoff: '', form: '', abmessung: '', zustand: '', pruefung: '' }); }

const iso = (c) => isoGruppe(c.werkstoff, ws.werkstoff(c.werkstoff)?.isoGruppe ?? '');
const bestand = (c) => (c.form === 'Platte' ? `${c.stueck > 1 ? `${c.stueck} × ` : ''}${zahl(c.breite, 0)} × ${zahl(c.laenge, 0)} mm` : `${c.stueck} × ${zahl(c.laenge, 0)} mm`);
const summe = (g) => (g.form === 'Platte' ? `${g.stueck} Platte${g.stueck === 1 ? '' : 'n'} · ${zahl(g.qm, 2)} m²` : `${g.stueck} Stange${g.stueck === 1 ? '' : 'n'} · ${zahl(g.meter, 2)} m`);
const SPALTEN = [
  { key: 'artikel', label: 'Material', wert: (c) => `${c.werkstoff} ${c.zustand} ${c.abmessungText}` },
  { key: 'id', label: 'Charge', wert: (c) => c.interneNr || c.id },
  { key: 'lieferant', label: 'Lieferant' },
  { key: 'eingang', label: 'Eingang' },
  { key: 'bestand', label: 'Bestand', rechts: true, wert: (c) => c.laenge * (c.form === 'Platte' ? c.breite : c.stueck) },
  { key: 'zeugnis', label: 'Zeugnis' },
  { key: 'lagerplatz', label: 'Platz' },
];
const de = (d) => (d ? d.split('-').reverse().join('.') : '–');
const lieferanten = computed(() => stammdatenRoh().lieferanten ?? []);

// ---- Muster der internen Chargennummer
const muster = ref('{kuerzel}{MM}{JJ}');
const MUSTER_VORSCHLAEGE = [['{kuerzel}{MM}{JJ}', 'Kürzel + Monat + Jahr'], ['{kuerzel}{MM}{JJ}-{nr}', '… mit laufender Nummer'], ['{kuerzel}{JJ}{MM}{TT}', 'Kürzel + Datum']];
const darfMuster = ref(false);
const musterOffen = ref(false);
const musterEdit = ref('');
async function musterSpeichern() {
  try { muster.value = (await call('cnc_one.api.werkstoff.chargen_muster_speichern', { muster: musterEdit.value })).muster; musterOffen.value = false; ui.toast('Muster gespeichert', 'ok'); } catch (e) { ui.toast(e.message, 'warn'); }
}
const kuerzelVon = (name) => lieferanten.value.find((l) => l.name === name)?.kuerzel || (name || '').replace(/\s/g, '').slice(0, 3).toUpperCase();

// ---- Wareneingang / Bearbeiten
const bearbeitet = ref(null);
const wahl = reactive({ werkstoff: '', zustand: '', form: 'Rund', ausfuehrung: '', abmessungId: '' });
const datei = ref(null);
const speichert = ref(false);
const nrVonHand = ref(false);
function eingang() {
  Object.assign(wahl, { werkstoff: filter.werkstoff || '', zustand: filter.zustand || '', form: filter.form || 'Rund', ausfuehrung: '', abmessungId: filter.abmessung || '' });
  datei.value = null;
  nrVonHand.value = false;
  bearbeitet.value = { id: '', interneNr: '', chargennr: '', lieferant: '', eingang: new Date().toISOString().slice(0, 10), laenge: 3000, breite: 0, stueck: 1, zeugnis: '3.1', pruefungen: [], lagerplatz: '', bemerkung: '', status: 'Vorrätig' };
  nrVorschlagen();
}
function oeffnen(c) { datei.value = null; nrVonHand.value = true; bearbeitet.value = JSON.parse(JSON.stringify(c)); }
const neu = computed(() => !bearbeitet.value?.id);
function nrVorschlagen() {
  if (bearbeitet.value && neu.value && !nrVonHand.value) bearbeitet.value.interneNr = interneChargennr(muster.value, kuerzelVon(bearbeitet.value.lieferant), bearbeitet.value.eingang);
}
watch(() => [bearbeitet.value?.lieferant, bearbeitet.value?.eingang], nrVorschlagen);
const platte = computed(() => (neu.value ? wahl.form : bearbeitet.value?.form) === 'Platte');
const gueltig = computed(() => !neu.value || (!!wahl.werkstoff && !!wahl.abmessungId && bearbeitet.value.laenge > 0 && (!platte.value || bearbeitet.value.breite > 0)));
const pruefung = (p) => { const l = bearbeitet.value.pruefungen; bearbeitet.value.pruefungen = l.includes(p) ? l.filter((x) => x !== p) : [...l, p]; };
async function speichern() {
  speichert.value = true;
  const d = { ...bearbeitet.value };
  if (neu.value) Object.assign(d, { werkstoff: wahl.werkstoff, zustand: wahl.zustand, abmessung: wahl.abmessungId, ausfuehrung: wahl.ausfuehrung });
  const c = await ws.chargeSpeichern(d, datei.value);
  speichert.value = false;
  if (c) { bearbeitet.value = null; await laden(); }
}
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-3">
      <div class="rounded-2xl bg-surface2 px-4 py-2.5"><div class="label">Chargen vorrätig</div><div class="text-xl font-semibold tnum">{{ liste.filter((c) => c.status === 'Vorrätig').length }}</div></div>
      <label class="relative ml-auto">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="filter.suche" class="field !w-64 !pl-9" placeholder="Charge, Lieferant, Lagerplatz …" />
      </label>
      <label class="flex cursor-pointer items-center gap-2 text-xs text-mute"><input v-model="alle" type="checkbox" class="accent-[var(--accent)]" @change="laden" /> auch aufgebrauchte</label>
      <button type="button" class="btn" :title="`Interne Chargennummer: ${muster}`" @click="musterEdit = muster; musterOffen = true"><Settings2 :size="15" /> Chargennummer</button>
      <button type="button" class="btn btn-primary" @click="eingang"><Plus :size="16" /> Wareneingang</button>
    </div>

    <!-- Filter -->
    <div class="mb-4 flex flex-wrap items-end gap-2 rounded-2xl border border-line bg-surface px-3 py-2.5">
      <label class="block"><span class="label mb-1 block">Werkstoff</span><select v-model="filter.werkstoff" class="field !w-48 !py-1.5 text-sm"><option value="">alle</option><option v-for="w in werkstoffe" :key="w">{{ w }}</option></select></label>
      <label class="block"><span class="label mb-1 block">Form</span><select v-model="filter.form" class="field !w-32 !py-1.5 text-sm"><option value="">alle</option><option v-for="f in formen" :key="f">{{ f }}</option></select></label>
      <label class="block"><span class="label mb-1 block">Abmessung</span><select v-model="filter.abmessung" class="field !w-36 !py-1.5 text-sm"><option value="">alle</option><option v-for="[id, t] in abmessungen" :key="id" :value="id">{{ t }}</option></select></label>
      <label class="block"><span class="label mb-1 block">Zustand</span><select v-model="filter.zustand" class="field !w-32 !py-1.5 text-sm"><option value="">alle</option><option v-for="z in zustaende" :key="z">{{ z }}</option></select></label>
      <label class="block"><span class="label mb-1 block">Nachweis</span><select v-model="filter.pruefung" class="field !w-48 !py-1.5 text-sm"><option value="">alle</option><option value="zeugnis31">Zeugnis 3.1 oder 3.2</option><option v-for="p in pruefungen" :key="p">{{ p }}</option></select></label>
      <button v-if="aktiv" type="button" class="btn !py-1.5 text-xs" @click="zuruecksetzen"><X :size="13" /> Filter löschen</button>
      <div class="ml-auto flex rounded-lg border border-line bg-surface2 p-0.5 text-xs">
        <button type="button" class="inline-flex items-center gap-1 rounded-md px-2 py-1" :class="gruppiert ? 'bg-surface font-medium text-accent shadow-sm' : 'text-mute'" @click="gruppiert = true"><Rows3 :size="13" /> je Material</button>
        <button type="button" class="inline-flex items-center gap-1 rounded-md px-2 py-1" :class="!gruppiert ? 'bg-surface font-medium text-accent shadow-sm' : 'text-mute'" @click="gruppiert = false"><List :size="13" /> Liste</button>
      </div>
    </div>

    <!-- je Material: alle Chargen mit Längen, Stangen und Besonderheiten -->
    <div v-if="gruppiert" class="space-y-3">
      <section v-for="g in gruppen" :key="g.key" class="card overflow-hidden">
        <header class="flex flex-wrap items-center gap-3 border-b border-line bg-surface2/60 px-4 py-2.5">
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-sm font-bold" :style="iso(g) ? { background: iso(g).farbe, color: iso(g).schrift } : {}">{{ iso(g)?.code ?? '?' }}</span>
          <FormSymbol :form="g.form" :groesse="24" :farbe="iso(g)?.farbe || ''" />
          <div class="min-w-0 font-semibold">{{ artikelText(g.werkstoff, { zustand: g.zustand, form: g.form, abmessung: g.abmessungText, ausfuehrung: g.ausfuehrung }) }}</div>
          <span class="ml-auto rounded-full bg-surface px-2.5 py-0.5 text-xs font-medium tnum">{{ summe(g) }}</span>
          <span class="text-xs text-mute">{{ g.chargen.length }} Charge{{ g.chargen.length === 1 ? '' : 'n' }}</span>
        </header>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[820px] text-sm">
            <thead><tr class="text-left text-[11px] uppercase tracking-wide text-mute">
              <th class="px-4 py-1.5 font-medium">Charge</th><th class="px-2 py-1.5 font-medium">Lieferant</th><th class="px-2 py-1.5 font-medium">Eingang</th>
              <th class="px-2 py-1.5 text-right font-medium">Bestand</th><th class="px-2 py-1.5 font-medium">Zeugnis</th><th class="px-2 py-1.5 font-medium">Besonderheiten</th><th class="px-4 py-1.5 font-medium">Platz</th>
            </tr></thead>
            <tbody>
              <tr v-for="c in g.chargen" :key="c.id" class="cursor-pointer border-t border-line transition hover:bg-surface2" :class="c.status === 'Aufgebraucht' ? 'opacity-50' : ''" @click="oeffnen(c)">
                <td class="px-4 py-2"><div class="font-medium tnum">{{ c.interneNr || c.id }}</div><div class="text-[11px] text-mute">{{ [c.interneNr ? c.id : '', c.chargennr].filter(Boolean).join(' · ') }}</div></td>
                <td class="px-2 py-2">{{ c.lieferant || '–' }}</td>
                <td class="px-2 py-2 tnum">{{ de(c.eingang) }}</td>
                <td class="px-2 py-2 text-right font-medium tnum">{{ c.status === 'Aufgebraucht' ? 'aufgebraucht' : bestand(c) }}</td>
                <td class="px-2 py-2">
                  <a v-if="c.zeugnisDatei" :href="c.zeugnisDatei" target="_blank" class="inline-flex items-center gap-1 text-accent hover:underline" @click.stop><FileBadge :size="14" /> {{ c.zeugnis || 'PDF' }}</a>
                  <span v-else class="text-mute">{{ c.zeugnis || '–' }}</span>
                </td>
                <td class="px-2 py-2">
                  <div class="flex flex-wrap gap-1">
                    <span v-for="p in c.pruefungen" :key="p" class="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent"><ShieldCheck :size="11" /> {{ p }}</span>
                    <span v-if="c.ausfuehrung && c.ausfuehrung !== g.ausfuehrung" class="rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute">{{ c.ausfuehrung }}</span>
                    <span v-if="c.bemerkung" class="max-w-[220px] truncate rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute" :title="c.bemerkung">{{ c.bemerkung }}</span>
                  </div>
                </td>
                <td class="px-4 py-2">{{ c.lagerplatz || '–' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <div v-if="!gruppen.length" class="card grid place-items-center px-6 py-16 text-center">
        <Layers :size="36" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">{{ liste.length ? 'Keine Charge passt zum Filter' : 'Noch keine Chargen im Rohmaterial-Lager' }}</p>
        <p class="mt-1 max-w-md text-xs text-mute">Jede Lieferung wird als Charge eingebucht: Material, Länge, Werkszeugnis (PDF) und bestätigte Anforderungen. Workbench und Fertigung zeigen dann, welche Charge passt.</p>
      </div>
    </div>

    <ListenTabelle v-else :spalten="SPALTEN" :zeilen="gefiltert" min-breite="900px" @oeffnen="oeffnen">
      <template #artikel="{ x }">
        <div class="flex items-center gap-2.5" :class="x.status === 'Aufgebraucht' ? 'opacity-50' : ''">
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-sm font-bold" :style="iso(x) ? { background: iso(x).farbe, color: iso(x).schrift } : {}">{{ iso(x)?.code ?? '?' }}</span>
          <FormSymbol :form="x.form" :groesse="22" :farbe="iso(x)?.farbe || ''" />
          <div class="min-w-0"><div class="truncate font-medium">{{ artikelText(x.werkstoff, { zustand: x.zustand, form: x.form, abmessung: x.abmessungText, ausfuehrung: x.ausfuehrung }) }}</div>
            <div v-if="x.pruefungen.length" class="truncate text-[11px] text-mute"><ShieldCheck :size="10" class="inline" /> {{ x.pruefungen.join(', ') }}</div></div>
        </div>
      </template>
      <template #id="{ x }"><div class="tnum">{{ x.interneNr || x.id }}</div><div class="text-[11px] text-mute">{{ [x.interneNr ? x.id : '', x.chargennr].filter(Boolean).join(' · ') }}</div></template>
      <template #lieferant="{ x }">{{ x.lieferant || '–' }}</template>
      <template #eingang="{ x }"><span class="tnum">{{ de(x.eingang) }}</span></template>
      <template #bestand="{ x }"><span class="tnum">{{ x.status === 'Aufgebraucht' ? 'aufgebraucht' : bestand(x) }}</span></template>
      <template #zeugnis="{ x }">
        <a v-if="x.zeugnisDatei" :href="x.zeugnisDatei" target="_blank" class="inline-flex items-center gap-1 text-accent hover:underline" @click.stop><FileBadge :size="14" /> {{ x.zeugnis || 'PDF' }}</a>
        <span v-else class="text-mute">{{ x.zeugnis || '–' }}</span>
      </template>
      <template #lagerplatz="{ x }">{{ x.lagerplatz || '–' }}</template>
      <template #leer>
        <div class="grid place-items-center px-6 py-16 text-center">
          <Layers :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ liste.length ? 'Keine Treffer' : 'Noch keine Chargen im Rohmaterial-Lager' }}</p>
        </div>
      </template>
    </ListenTabelle>

    <!-- Muster der internen Chargennummer -->
    <StammDialog v-if="musterOffen" titel="Interne Chargennummer" untertitel="Wie neue Chargen im Lager benannt werden" breite="560px" neu speichern-text="Muster speichern" :gueltig="darfMuster" @schliessen="musterOffen = false" @speichern="musterSpeichern">
      <label class="block"><span class="label mb-1 block">Muster</span><input v-model="musterEdit" class="field font-mono" :disabled="!darfMuster" /></label>
      <div class="flex flex-wrap gap-1.5"><button v-for="[m, t] in MUSTER_VORSCHLAEGE" :key="m" type="button" class="rounded-full border px-2.5 py-0.5 text-xs transition" :class="musterEdit === m ? 'border-accent bg-accent-soft text-accent' : 'border-line text-mute hover:text-ink'" :disabled="!darfMuster" @click="musterEdit = m">{{ t }} <span class="font-mono tnum">{{ interneChargennr(m, 'BIK', new Date().toISOString().slice(0, 10)) }}</span></button></div>
      <p class="text-xs text-mute">Platzhalter: <code>{kuerzel}</code> Kürzel des Lieferanten (Stammdaten → Lieferanten), <code>{JJJJ}</code> <code>{JJ}</code> <code>{MM}</code> <code>{TT}</code> Datum des Wareneingangs, <code>{nr}</code> laufende Nummer, falls es die Bezeichnung schon gibt. Zeichen dazwischen bleiben, z. B. <code>{kuerzel}-{TT}{MM}{JJ}</code>.</p>
      <div class="rounded-xl bg-surface2 px-3 py-2 text-sm">Beispiel: <span class="font-semibold tnum">{{ interneChargennr(musterEdit, 'BIK', new Date().toISOString().slice(0, 10)) }}</span> <span class="text-xs text-mute">(Lieferant mit Kürzel BIK, Eingang heute)</span></div>
    </StammDialog>

    <StammDialog v-if="bearbeitet" :titel="neu ? 'Wareneingang Rohmaterial' : `${bearbeitet.interneNr || bearbeitet.id} · ${bearbeitet.werkstoff} ${bearbeitet.zustand} ${bearbeitet.abmessungText}`" :untertitel="neu ? 'Neue Charge einbuchen' : `Charge ${bearbeitet.id} im Rohmaterial-Lager`" breite="1080px" neu :speichern-text="neu ? 'Charge einbuchen' : 'Speichern'" :speichert="speichert" :gueltig="gueltig" @schliessen="bearbeitet = null" @speichern="speichern">
      <RohmaterialWahl v-if="neu" :wahl="wahl" />
      <div class="grid gap-3 sm:grid-cols-3">
        <label class="block"><span class="label mb-1 block">Lieferant</span>
          <select v-model="bearbeitet.lieferant" class="field"><option value="">–</option><option v-for="l in lieferanten" :key="l.id" :value="l.name">{{ l.name }}{{ l.kuerzel ? ` (${l.kuerzel})` : '' }}</option></select></label>
        <label class="block"><span class="label mb-1 block">Wareneingang</span><input v-model="bearbeitet.eingang" type="date" class="field" /></label>
        <label class="block"><span class="label mb-1 block">Interne Charge</span><input v-model="bearbeitet.interneNr" class="field font-medium tnum" :placeholder="interneChargennr(muster, kuerzelVon(bearbeitet.lieferant), bearbeitet.eingang)" @input="nrVonHand = true" />
          <span class="mt-0.5 block text-[11px] text-mute">nach Muster {{ muster }}<button v-if="nrVonHand && neu" type="button" class="ml-1 text-accent hover:underline" @click="nrVonHand = false; nrVorschlagen()">Vorschlag</button></span></label>
        <label class="block"><span class="label mb-1 block">Charge / Schmelze des Lieferanten</span><input v-model="bearbeitet.chargennr" class="field" placeholder="aus dem Lieferschein / Zeugnis" /></label>
        <NumField v-if="platte" v-model="bearbeitet.breite" label="Breite" unit="mm" :decimals="0" />
        <NumField v-model="bearbeitet.laenge" :label="platte ? 'Länge' : 'Länge je Stange'" unit="mm" :decimals="0" />
        <NumField v-model="bearbeitet.stueck" :label="platte ? 'Platten' : 'Stangen'" unit="Stk" :decimals="0" />
        <label class="block"><span class="label mb-1 block">Lagerplatz</span><input v-model="bearbeitet.lagerplatz" class="field" placeholder="z. B. R-03" /></label>
        <label v-if="!neu" class="block"><span class="label mb-1 block">Status</span><select v-model="bearbeitet.status" class="field"><option>Vorrätig</option><option>Aufgebraucht</option></select></label>
      </div>
      <div class="flex flex-wrap items-start gap-5">
        <div><div class="label mb-1">Werkszeugnis (EN 10204)</div>
          <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1 text-xs">
            <button v-for="z in ZEUGNISSE" :key="z" type="button" class="rounded-lg px-3 py-1.5" :class="bearbeitet.zeugnis === z ? 'bg-surface font-medium shadow-sm' : 'text-mute hover:text-ink'" @click="bearbeitet.zeugnis = z">{{ z || 'keins' }}</button>
          </div>
        </div>
        <div class="min-w-0 flex-1"><div class="label mb-1">Bestätigte Anforderungen</div>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="a in ws.baum.anforderungen" :key="a.name" type="button" class="rounded-full border px-2.5 py-1 text-xs transition" :class="bearbeitet.pruefungen.includes(a.name) ? 'border-accent bg-accent-soft text-accent' : 'border-line text-mute hover:text-ink'" @click="pruefung(a.name)"><Check v-if="bearbeitet.pruefungen.includes(a.name)" :size="11" class="inline" /> {{ a.name }}</button>
          </div>
        </div>
      </div>
      <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-line px-4 py-3 text-sm text-mute hover:border-accent hover:text-ink">
        <Upload :size="16" /> {{ datei ? datei.name : bearbeitet.zeugnisDatei ? 'Zeugnis ersetzen (PDF)' : 'Zeugnis-PDF anhängen (liegt danach auch im DMS)' }}
        <a v-if="bearbeitet.zeugnisDatei && !datei" :href="bearbeitet.zeugnisDatei" target="_blank" class="ml-auto text-accent hover:underline" @click.stop>Ansehen</a>
        <input type="file" accept="application/pdf" class="hidden" @change="datei = $event.target.files?.[0] ?? null" />
      </label>
      <label class="block"><span class="label mb-1 block">Bemerkung</span><textarea v-model="bearbeitet.bemerkung" rows="2" class="field resize-y" /></label>
    </StammDialog>
  </div>
</template>
