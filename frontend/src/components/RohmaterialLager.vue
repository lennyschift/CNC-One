<script setup>
// Rohmaterial-Lager: Chargen je Wareneingang mit Werkstoff, Zustand, Abmessung, Bestand, Werkszeugnis (PDF) und bestätigten
// Anforderungen. Wareneingang wählt das Material genau wie die Workbench (RohmaterialWahl, auch mit „+ Neu“).
import { ref, reactive, computed, onMounted } from 'vue';
import { Layers, Plus, Search, FileBadge, ShieldCheck, Upload, Check } from '@lucide/vue';
import ListenTabelle from './ListenTabelle.vue';
import StammDialog from './StammDialog.vue';
import NumField from './NumField.vue';
import FormSymbol from './FormSymbol.vue';
import RohmaterialWahl from './RohmaterialWahl.vue';
import { isoGruppe } from '../lib/iso.js';
import { ZEUGNISSE, artikelText } from '../lib/werkstoffbaum.js';
import { zahl } from '../lib/format.js';
import { stammdatenRoh } from '../data/repo.js';
import { useWerkstoff } from '../stores/werkstoff.js';

const ws = useWerkstoff();
const alle = ref(false);
const liste = ref([]);
async function laden() { liste.value = await ws.chargenLaden(true, alle.value); }
onMounted(laden);

const suche = ref('');
const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return liste.value.filter((c) => !q || [c.id, c.chargennr, c.werkstoff, c.zustand, c.abmessungText, c.lieferant, c.lagerplatz].some((x) => (x || '').toLowerCase().includes(q)));
});
const iso = (c) => isoGruppe(c.werkstoff, ws.werkstoff(c.werkstoff)?.isoGruppe ?? '');
const bestand = (c) => (c.form === 'Platte' ? `${zahl(c.breite, 0)} × ${zahl(c.laenge, 0)} mm` : `${c.stueck} × ${zahl(c.laenge, 0)} mm`);
const SPALTEN = [
  { key: 'artikel', label: 'Material', wert: (c) => `${c.werkstoff} ${c.zustand} ${c.abmessungText}` },
  { key: 'id', label: 'Charge' },
  { key: 'lieferant', label: 'Lieferant' },
  { key: 'eingang', label: 'Eingang' },
  { key: 'bestand', label: 'Bestand', rechts: true, wert: (c) => c.laenge * (c.form === 'Platte' ? c.breite : c.stueck) },
  { key: 'zeugnis', label: 'Zeugnis' },
  { key: 'lagerplatz', label: 'Platz' },
];
const de = (d) => (d ? d.split('-').reverse().join('.') : '–');
const lieferanten = computed(() => stammdatenRoh().lieferanten ?? []);

// ---- Wareneingang / Bearbeiten
const bearbeitet = ref(null);
const wahl = reactive({ werkstoff: '', zustand: '', form: 'Rund', ausfuehrung: '', abmessungId: '' });
const datei = ref(null);
const speichert = ref(false);
function eingang() {
  Object.assign(wahl, { werkstoff: '', zustand: '', form: 'Rund', ausfuehrung: '', abmessungId: '' });
  datei.value = null;
  bearbeitet.value = { id: '', chargennr: '', lieferant: '', eingang: new Date().toISOString().slice(0, 10), laenge: 3000, breite: 0, stueck: 1, zeugnis: '3.1', pruefungen: [], lagerplatz: '', bemerkung: '', status: 'Vorrätig' };
}
function oeffnen(c) { datei.value = null; bearbeitet.value = JSON.parse(JSON.stringify(c)); }
const neu = computed(() => !bearbeitet.value?.id);
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
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <div class="rounded-2xl bg-surface2 px-4 py-2.5"><div class="label">Chargen vorrätig</div><div class="text-xl font-semibold tnum">{{ liste.filter((c) => c.status === 'Vorrätig').length }}</div></div>
      <label class="relative ml-auto">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-60 !pl-9" placeholder="Werkstoff, Charge, Lieferant …" />
      </label>
      <label class="flex cursor-pointer items-center gap-2 text-xs text-mute"><input v-model="alle" type="checkbox" class="accent-[var(--accent)]" @change="laden" /> auch aufgebrauchte</label>
      <button type="button" class="btn btn-primary" @click="eingang"><Plus :size="16" /> Wareneingang</button>
    </div>

    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" min-breite="900px" @oeffnen="oeffnen">
      <template #artikel="{ x }">
        <div class="flex items-center gap-2.5" :class="x.status === 'Aufgebraucht' ? 'opacity-50' : ''">
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-sm font-bold" :style="iso(x) ? { background: iso(x).farbe, color: iso(x).schrift } : {}">{{ iso(x)?.code ?? '?' }}</span>
          <FormSymbol :form="x.form" :groesse="22" :farbe="iso(x)?.farbe || ''" />
          <div class="min-w-0"><div class="truncate font-medium">{{ artikelText(x.werkstoff, { zustand: x.zustand, form: x.form, abmessung: x.abmessungText, ausfuehrung: x.ausfuehrung }) }}</div>
            <div v-if="x.pruefungen.length" class="truncate text-[11px] text-mute"><ShieldCheck :size="10" class="inline" /> {{ x.pruefungen.join(', ') }}</div></div>
        </div>
      </template>
      <template #id="{ x }"><div class="tnum">{{ x.id }}</div><div v-if="x.chargennr" class="text-[11px] text-mute">{{ x.chargennr }}</div></template>
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
          <p class="mt-1 max-w-md text-xs text-mute">Jede Lieferung wird als Charge eingebucht: Material, Länge, Werkszeugnis (PDF) und bestätigte Anforderungen. Die Workbench zeigt dann, welche Charge für ein Bauteil passt.</p>
        </div>
      </template>
    </ListenTabelle>

    <StammDialog v-if="bearbeitet" :titel="neu ? 'Wareneingang Rohmaterial' : `${bearbeitet.id} · ${bearbeitet.werkstoff} ${bearbeitet.zustand} ${bearbeitet.abmessungText}`" :untertitel="neu ? 'Neue Charge einbuchen' : 'Charge im Rohmaterial-Lager'" breite="1080px" neu :speichern-text="neu ? 'Charge einbuchen' : 'Speichern'" :speichert="speichert" :gueltig="gueltig" @schliessen="bearbeitet = null" @speichern="speichern">
      <RohmaterialWahl v-if="neu" :wahl="wahl" />
      <div class="grid gap-3 sm:grid-cols-3">
        <label class="block"><span class="label mb-1 block">Lieferant</span>
          <select v-model="bearbeitet.lieferant" class="field"><option value="">–</option><option v-for="l in lieferanten" :key="l.id" :value="l.name">{{ l.name }}</option></select></label>
        <label class="block"><span class="label mb-1 block">Charge / Schmelze des Lieferanten</span><input v-model="bearbeitet.chargennr" class="field" placeholder="aus dem Lieferschein / Zeugnis" /></label>
        <label class="block"><span class="label mb-1 block">Wareneingang</span><input v-model="bearbeitet.eingang" type="date" class="field" /></label>
        <NumField v-if="platte" v-model="bearbeitet.breite" label="Breite" unit="mm" :decimals="0" />
        <NumField v-model="bearbeitet.laenge" :label="platte ? 'Länge' : 'Länge je Stange'" unit="mm" :decimals="0" />
        <NumField v-if="!platte" v-model="bearbeitet.stueck" label="Stangen" unit="Stk" :decimals="0" />
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
