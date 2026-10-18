<script setup>
// Liste mit Suche und Bearbeiten-Dialog für einfache Stammdaten (Lieferanten, Maschinen, Materialien).
// Welche Spalten und Felder es gibt, steht in der Beschreibung `felder`, die die Seite übergibt.
import { ref, computed, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Search } from '@lucide/vue';
import StammNav from './StammNav.vue';
import StammDialog from './StammDialog.vue';
import NumField from './NumField.vue';
import Toggle from './Toggle.vue';
import { useStammdaten } from '../stores/stammdaten.js';
import { eur } from '../lib/format.js';

const props = defineProps({
  art: { type: String, required: true },
  einzahl: { type: String, required: true },
  icon: { type: Object, required: true },
  beschreibung: { type: String, default: '' },
  // [{ key, label, typ: 'text' | 'zahl' | 'euro' | 'kurz' | 'text-lang', suffix, hinweis, zeile }]
  felder: { type: Array, required: true },
  // Spalten der Liste: Schlüssel der Felder
  spalten: { type: Array, required: true },
});

const store = useStammdaten();
onMounted(() => store.laden(props.art));

const suche = ref('');
const inaktive = ref(false);
const liste = computed(() => store.listen[props.art] ?? []);
const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return liste.value.filter((x) => (inaktive.value || x.aktiv) && (!q || Object.values(x).some((v) => typeof v === 'string' && v.toLowerCase().includes(q))));
});

const leer = () => ({ id: '', name: '', aktiv: true, ...Object.fromEntries(props.felder.map((f) => [f.key, f.typ === 'zahl' || f.typ === 'euro' ? 0 : ''])) });
const bearbeitet = ref(null);
const speichert = ref(false);
const neu = computed(() => !bearbeitet.value?.id);
const darf = computed(() => store.darf(props.art));

function oeffnen(x) { bearbeitet.value = x ? JSON.parse(JSON.stringify(x)) : leer(); }
async function speichern() {
  speichert.value = true;
  const rec = await store.speichern(props.art, bearbeitet.value);
  speichert.value = false;
  if (rec) bearbeitet.value = null;
}
async function loeschen() {
  if (await store.loeschen(props.art, bearbeitet.value.id)) bearbeitet.value = null;
}
const anzeige = (x, key) => {
  const f = key === 'name' ? { typ: 'text' } : props.felder.find((g) => g.key === key);
  const v = x[key];
  if (f?.typ === 'euro') return eur(v);
  if (f?.typ === 'zahl') return v ? `${v}${f.suffix ? ' ' + f.suffix : ''}` : '–';
  return v || '–';
};
const kopf = (key) => (key === 'name' ? 'Name' : props.felder.find((g) => g.key === key)?.label ?? key);
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <StammNav />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <div class="mr-auto"><p class="text-sm text-mute">{{ beschreibung }}</p></div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-60 !pl-9" :placeholder="`${einzahl} suchen …`" />
      </label>
      <Toggle v-model="inaktive" klein label="Inaktive anzeigen" />
      <button v-if="darf" class="btn btn-primary" @click="oeffnen()"><Plus :size="16" /> Neu</button>
    </div>

    <div class="card overflow-hidden">
      <div class="grid items-center gap-4 border-b border-line bg-surface2 px-5 py-2.5 text-xs font-medium text-mute" :style="{ gridTemplateColumns: `minmax(180px,1.4fr) repeat(${spalten.length}, minmax(80px,1fr))` }">
        <span>Name</span><span v-for="s in spalten" :key="s">{{ kopf(s) }}</span>
      </div>
      <div v-auto-animate>
        <button v-for="x in zeilen" :key="x.id" class="grid w-full items-center gap-4 border-b border-line px-5 py-3 text-left text-sm transition last:border-0 hover:bg-surface2" :style="{ gridTemplateColumns: `minmax(180px,1.4fr) repeat(${spalten.length}, minmax(80px,1fr))` }" @click="oeffnen(x)">
          <span class="flex items-center gap-2.5 font-medium"><component :is="icon" :size="16" class="text-mute" />{{ x.name }}<span v-if="!x.aktiv" class="rounded-full bg-surface2 px-2 py-0.5 text-[10px] font-normal text-mute">inaktiv</span></span>
          <span v-for="s in spalten" :key="s" class="truncate text-mute tnum">{{ anzeige(x, s) }}</span>
        </button>
      </div>
      <p v-if="!zeilen.length" class="px-6 py-12 text-center text-sm text-mute">{{ store.listen[art] === null ? 'Lädt …' : liste.length ? 'Keine Treffer.' : `Noch keine ${einzahl}-Einträge.` }}</p>
    </div>

    <StammDialog v-if="bearbeitet" :titel="neu ? `Neu: ${einzahl}` : bearbeitet.name" :untertitel="neu ? '' : einzahl" :neu="neu" :schreibgeschuetzt="!darf" :speichert="speichert" :gueltig="!!bearbeitet.name.trim()" @schliessen="bearbeitet = null" @speichern="speichern" @loeschen="loeschen">
      <label class="block"><span class="label mb-1 block">Name</span>
        <input v-model="bearbeitet.name" class="field" :disabled="!neu || !darf" autofocus />
        <span v-if="!neu" class="mt-1 block text-[11px] text-mute">Der Name lässt sich nach dem Anlegen nicht mehr ändern, weil Angebote und Arbeitspläne ihn verwenden.</span>
      </label>
      <div class="grid gap-3 sm:grid-cols-2">
        <template v-for="f in felder" :key="f.key">
          <NumField v-if="f.typ === 'zahl' || f.typ === 'euro'" v-model="bearbeitet[f.key]" :label="f.label" :unit="f.suffix" :decimals="f.decimals ?? 2" />
          <label v-else-if="f.typ === 'text-lang'" class="block sm:col-span-2"><span class="label mb-1 block">{{ f.label }}</span><textarea v-model="bearbeitet[f.key]" rows="2" class="field resize-y" :disabled="!darf" /></label>
          <label v-else class="block"><span class="label mb-1 block">{{ f.label }}</span><input v-model="bearbeitet[f.key]" class="field" :placeholder="f.hinweis" :disabled="!darf" /></label>
        </template>
      </div>
      <Toggle v-model="bearbeitet.aktiv" label="Aktiv (in Auswahllisten sichtbar)" />
    </StammDialog>
  </div>
</template>
