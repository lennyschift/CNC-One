<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Search, Truck } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektMarke from '../components/ProjektMarke.vue';
import LieferscheinDialog from '../components/LieferscheinDialog.vue';
import { useLieferung } from '../stores/lieferung.js';
import { useBelege } from '../stores/belege.js';

const l = useLieferung();
const belege = useBelege();
const router = useRouter();
onMounted(() => belege.auftraegeNeuLaden());

const filter = ref('Alle');
const suche = ref('');
const dialog = ref(false);
const filterListe = ['Alle', 'Bereit', 'Geliefert', 'Storniert'];

// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'status': 'Status', 'kundeName': 'Kunde', 'projekt': 'Projekt', 'lieferdatum': 'Lieferdatum', 'positionen.teil.name': 'Bauteil', 'positionen.teil.teilenummer': 'Teilenummer', 'positionen.auftragId': 'Auftrag'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return l.lieferscheine.filter((x) => (filter.value === 'Alle' || x.status === filter.value)
    && (!q || `${x.id} ${x.kundeName} ${x.kundenbestellnr} ${projekteVon(x).join(' ')} ${x.positionen.map((p) => `${p.teil.name} ${p.teil.teilenummer} ${p.auftragId}`).join(' ')}`.toLowerCase().includes(q)));
});
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const auftraegeVon = (x) => [...new Set(x.positionen.map((p) => p.auftragId).filter(Boolean))];
const projekteVon = (x) => [...new Set(auftraegeVon(x).map((id) => belege.auftrag(id)?.projekt).filter(Boolean))];
const stueck = (x) => x.positionen.reduce((n, p) => n + p.menge, 0);
const SPALTEN = [
  { key: 'id', label: 'Nummer', breite: '130px' },
  { key: 'bauteile', label: 'Bauteile', wert: (x) => x.positionen.length },
  { key: 'kundeName', label: 'Kunde' },
  { key: 'projekt', label: 'Projekt', wert: (x) => projekteVon(x).join(', ') },
  { key: 'auftraege', label: 'Aufträge', wert: (x) => auftraegeVon(x).join(', ') },
  { key: 'menge', label: 'Menge', rechts: true, wert: stueck },
  { key: 'datum', label: 'Datum', wert: (x) => x.gelieferAm || x.lieferdatum || x.erstellt },
  { key: 'status', label: 'Status' },
];
function angelegt(rec) { dialog.value = false; router.push(`/lieferscheine/${rec.id}`); }
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Projekt, Kunde, Bauteil …" />
      </label>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ l.lieferscheine.length }}</span>
      <button class="btn btn-primary" @click="dialog = true"><Plus :size="16" /> Neuer Lieferschein</button>
    </div>

    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="lieferscheine" :beschriftungen="beschriftungen" :standard-angeheftet="['kundeName']" />
    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" :link="(x) => `/lieferscheine/${x.id}`" min-breite="1000px">
      <template #id="{ x }"><span class="font-semibold tnum" :class="x.status === 'Storniert' ? 'text-mute line-through' : ''">{{ x.id }}</span></template>
      <template #bauteile="{ x }"><div class="flex max-w-[330px] flex-wrap gap-1.5">
              <span v-for="(p, i) in x.positionen.slice(0, 12)" :key="i" :title="[p.teil.name, p.teil.teilenummer].filter(Boolean).join(' · ') || 'Bauteil'"><PartImage :teil="p.teil" :groesse="40" /></span>
              <span v-if="x.positionen.length > 12" class="grid h-10 w-10 place-items-center rounded-lg border border-line bg-surface2 text-[11px] font-medium text-mute">+{{ x.positionen.length - 12 }}</span>
              <span v-if="!x.positionen.length" class="text-mute">–</span>
            </div></template>
      <template #projekt="{ x }"><div class="flex flex-wrap gap-1"><ProjektMarke v-for="pr in projekteVon(x)" :key="pr" :projekt="pr" /><span v-if="!projekteVon(x).length" class="text-mute">–</span></div></template>
      <template #auftraege="{ x }"><span class="text-xs tnum">{{ auftraegeVon(x).join(', ') || 'ohne Auftrag' }}</span></template>
      <template #menge="{ x }">{{ stueck(x) }} Stk</template>
      <template #datum="{ x }"><span class="tnum">{{ de(x.gelieferAm || x.lieferdatum || x.erstellt) || '–' }}</span></template>
      <template #status="{ x }"><StatusBadge :status="x.status" /></template>
      <template #leer>
        <div class="grid place-items-center px-6 py-16 text-center">
          <Truck :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ l.lieferscheine.length ? 'Keine Lieferscheine in diesem Filter' : 'Noch keine Lieferscheine' }}</p>
          <p class="mt-1 max-w-sm text-xs text-mute">Lieferscheine entstehen im Auftrag über „Lieferschein erstellen“ oder hier frei aus den Bauteilen eines Kunden. Sie dürfen auch schon vor der Fertigung angelegt werden.</p>
        </div>
      </template>
    </ListenTabelle>

    <LieferscheinDialog v-if="dialog" @schliessen="dialog = false" @angelegt="angelegt" />
  </div>
</template>
