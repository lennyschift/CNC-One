<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Send, Search, FileText, Plus, Package } from '@lucide/vue';
import FreieAnfrageDialog from '../components/FreieAnfrageDialog.vue';
import { istFrei, freieZeile } from '../lib/anfrage.js';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { useBelege } from '../stores/belege.js';

const route = useRoute();
const router = useRouter();
const a = useAnfragen();
const belege = useBelege();

const filter = ref('Alle');
const neuDialog = ref(false);
function angelegt(neu) { neuDialog.value = false; if (neu?.length) router.push({ path: `/anfragen/${neu[0].id}`, query: { senden: 1 } }); }
const suche = ref('');
const filterListe = ['Alle', 'Gesendet', 'Angebot erhalten', 'Abgesagt'];

// Angebotsfilter: 'alle' oder eine Angebotsnummer
const angebotFilter = ref(route.query.angebot ? String(route.query.angebot) : 'alle');
watch(angebotFilter, (v) => {
  router.replace({ query: v === 'alle' ? {} : { angebot: v } });
});

// Angebote, zu denen es Anfragen gibt
const angebotOptionen = computed(() => {
  const ids = [...new Set(a.liste.map((x) => x.angebotId).filter(Boolean))];
  return ids.map((id) => ({ id, label: `${id} · ${belege.angebot(id)?.kopf.kundeName ?? ''}` }));
});

const passtZuAngebot = (x) => angebotFilter.value === 'alle' || x.angebotId === angebotFilter.value;

// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'status': 'Status', 'lieferantName': 'Lieferant', 'art': 'Art', 'angebotId': 'Angebot', 'kundeName': 'Kunde', 'vorgang': 'Vorgang', 'positionen.teil.name': 'Bezeichnung / Bauteil', 'positionen.teil.material': 'Werkstoff', 'positionen.agName': 'Leistung', 'erstellt': 'Angelegt am', 'zuschlag': 'Zuschlag', 'neueAntwort': 'Neue Antwort', 'versendetAm': 'Per Mail versendet am'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return a.liste.filter((x) => {
    if (filter.value !== 'Alle' && x.status !== filter.value) return false;
    if (!passtZuAngebot(x)) return false;
    if (!q) return true;
    const text = `${x.id} ${x.lieferantName} ${x.angebotId} ${x.kundeName} ${x.positionen.map((p) => `${p.teil.name} ${p.teil.teilenummer} ${p.agName}`).join(' ')}`.toLowerCase();
    return text.includes(q);
  });
});

const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
const kunde = (x) => x.kundeName || belege.angebot(x.angebotId)?.kopf.kundeName || '';
const SPALTEN = [
  { key: 'id', label: 'Nummer', breite: '130px' },
  { key: 'inhalt', label: 'Inhalt', wert: (x) => titel(x) },
  { key: 'lieferantName', label: 'Lieferant' },
  { key: 'bezug', label: 'Bezug', wert: (x) => x.angebotId || x.art },
  { key: 'kunde', label: 'Kunde', wert: kunde },
  { key: 'erstellt', label: 'Angelegt' },
  { key: 'status', label: 'Status' },
];
const titel = (x) => {
  if (istFrei(x)) return x.positionen.length === 1 ? freieZeile(x.positionen[0]) : `${x.positionen.length} Positionen: ${x.positionen.map((p) => p.teil.name).join(', ')}`;
  return x.positionen.length === 1 ? `${x.positionen[0].agName || 'Fremdvergabe'} · ${x.positionen[0].teil.name}` : `${x.positionen.length} Positionen: ${x.positionen.map((p) => p.teil.name).join(', ')}`;
};
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <select v-model="angebotFilter" class="field !w-auto">
        <option value="alle">Alle Angebote</option>
        <option v-for="o in angebotOptionen" :key="o.id" :value="o.id">{{ o.label }}</option>
      </select>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-60 !pl-9" placeholder="Nummer, Lieferant, Bauteil …" />
      </label>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ a.liste.length }}</span>
      <button class="btn btn-primary" @click="neuDialog = true"><Plus :size="16" /> Neue Anfrage</button>
    </div>
    <FreieAnfrageDialog v-if="neuDialog" @schliessen="neuDialog = false" @angelegt="angelegt" />

    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="anfragen" :beschriftungen="beschriftungen" :standard-angeheftet="['lieferantName']" />
    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" :link="(x) => `/anfragen/${x.id}`" min-breite="1000px">
      <template #id="{ x }"><span class="font-semibold tnum">{{ x.id }}</span></template>
      <template #inhalt="{ x }"><div class="flex items-center gap-3">
              <div class="flex shrink-0 -space-x-2.5">
                <PartImage v-for="(p, i) in x.positionen.slice(0, 3)" :key="i" :teil="p.teil" :groesse="34" class="ring-2 ring-surface" />
                <div v-if="x.positionen.length > 3" class="grid h-[34px] w-[34px] place-items-center rounded-lg border border-line bg-surface2 text-[10px] font-medium text-mute ring-2 ring-surface">+{{ x.positionen.length - 3 }}</div>
              </div>
              <div class="min-w-0 max-w-[220px]"><div class="truncate font-medium">{{ titel(x) }}</div><div class="truncate text-xs text-mute">{{ x.positionen.length }} Position{{ x.positionen.length === 1 ? '' : 'en' }}</div></div>
            </div></template>
      <template #bezug="{ x }">
        <span v-if="x.angebotId" class="inline-flex items-center gap-1 text-xs tnum"><FileText :size="12" class="text-mute" /> {{ x.angebotId }}</span>
        <span v-else class="inline-flex items-center gap-1 text-xs"><Package :size="12" class="text-mute" /> {{ x.art }}</span>
      </template>
      <template #kunde="{ x }">{{ kunde(x) || '–' }}</template>
      <template #erstellt="{ x }"><span class="tnum">{{ de(x.erstellt) }}</span></template>
      <template #status="{ x }"><StatusBadge :status="x.status" /></template>
      <template #leer>
        <div class="grid place-items-center px-6 py-16 text-center">
          <Send :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ a.liste.length ? 'Keine Anfragen mit diesen Filtern' : 'Noch keine Lieferantenanfragen' }}</p>
          <p class="mt-1 max-w-sm text-xs text-mute">Fremdvergaben fragst du in der Workbench an, Material und anderes hier über „Neue Anfrage“.</p>
          <button class="btn btn-primary mt-4" @click="neuDialog = true"><Plus :size="16" /> Neue Anfrage</button>
        </div>
      </template>
    </ListenTabelle>
  </div>
</template>
