<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed, onMounted } from 'vue';
import { Search, Receipt } from '@lucide/vue';
import RechnungNav from '../components/RechnungNav.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektMarke from '../components/ProjektMarke.vue';
import { useBelege } from '../stores/belege.js';
import { useRechnung } from '../stores/rechnung.js';
import { eur } from '../lib/format.js';

const store = useRechnung();
const belege = useBelege();
const projektVon = (r) => belege.auftrag(r.auftragId)?.projekt ?? '';
onMounted(() => store.neuLaden().catch(() => {}));

const filter = ref('Alle');
const suche = ref('');
const filterListe = ['Alle', 'Entwurf', 'Offen', 'Überfällig', 'Bezahlt', 'Storniert'];

const offene = computed(() => store.rechnungen.filter((r) => r.status === 'Offen' || r.status === 'Teilbezahlt'));
const ueberfaellige = computed(() => offene.value.filter((r) => r.tageUeberfaellig > 0));
const summe = (l) => l.reduce((n, r) => n + r.offen, 0);

const passt = (r) => {
  switch (filter.value) {
    case 'Entwurf': return r.status === 'Entwurf';
    case 'Offen': return r.status === 'Offen' || r.status === 'Teilbezahlt';
    case 'Überfällig': return r.tageUeberfaellig > 0;
    case 'Bezahlt': return r.status === 'Bezahlt';
    case 'Storniert': return r.status === 'Storniert' || r.status === 'Gutschrift';
    default: return true;
  }
};
// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'status': 'Status', 'kundeName': 'Kunde', 'nummer': 'Rechnungsnummer', 'projekt': 'Projekt', 'netto': 'Netto', 'brutto': 'Brutto', 'datum': 'Rechnungsdatum', 'faelligAm': 'Fällig am', 'tageUeberfaellig': 'Tage überfällig', 'auftragId': 'Auftrag'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return store.rechnungen.filter((r) => passt(r) && (!q || `${r.nummer} ${r.id} ${r.kundeName} ${r.auftragId} ${r.kundenbestellnr} ${projektVon(r)}`.toLowerCase().includes(q)));
});
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
const offenStatus = (r) => r.status === 'Offen' || r.status === 'Teilbezahlt';
const SPALTEN = [
  { key: 'nummer', label: 'Nummer', breite: '140px' },
  { key: 'kundeName', label: 'Kunde' },
  { key: 'projekt', label: 'Projekt', wert: projektVon },
  { key: 'auftragId', label: 'Auftrag' },
  { key: 'art', label: 'Art' },
  { key: 'rechnungsdatum', label: 'Datum' },
  { key: 'faelligAm', label: 'Fällig' },
  { key: 'brutto', label: 'Brutto', rechts: true },
  { key: 'offen', label: 'Offen', rechts: true, wert: (r) => (offenStatus(r) ? r.offen : 0) },
  { key: 'status', label: 'Status' },
];
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <RechnungNav />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <div class="rounded-2xl bg-surface2 px-4 py-2.5"><div class="label">Offene Posten</div><div class="text-xl font-semibold tnum">{{ eur(summe(offene)) }}</div><div class="text-[11px] text-mute">{{ offene.length }} Rechnung{{ offene.length === 1 ? '' : 'en' }}</div></div>
      <div v-if="ueberfaellige.length" class="rounded-2xl bg-accent-soft px-4 py-2.5 text-accent"><div class="label !text-accent">Überfällig</div><div class="text-xl font-semibold tnum">{{ eur(summe(ueberfaellige)) }}</div><div class="text-[11px]">{{ ueberfaellige.length }} Rechnung{{ ueberfaellige.length === 1 ? '' : 'en' }}</div></div>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ store.rechnungen.length }}</span>
    </div>
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Projekt, Kunde, Auftrag …" />
      </label>
    </div>

    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="rechnungen" :beschriftungen="beschriftungen" :standard-angeheftet="['kundeName']" />
    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" :link="(r) => `/rechnungen/${r.id}`" min-breite="1100px">
      <template #nummer="{ x }"><span class="font-semibold tnum" :class="x.status === 'Storniert' ? 'text-mute line-through' : ''">{{ x.nummer || 'Entwurf' }}</span></template>
      <template #kundeName="{ x }"><div class="truncate">{{ x.kundeName }}</div><div v-if="x.kundenbestellnr" class="truncate text-xs text-mute">Bestellung {{ x.kundenbestellnr }}</div></template>
      <template #projekt="{ x }"><ProjektMarke v-if="projektVon(x)" :projekt="projektVon(x)" /><span v-else class="text-mute">–</span></template>
      <template #auftragId="{ x }"><span class="tnum">{{ x.auftragId || '–' }}</span></template>
      <template #art="{ x }"><span class="text-xs">{{ x.art || 'Rechnung' }}</span></template>
      <template #rechnungsdatum="{ x }"><span class="tnum">{{ de(x.rechnungsdatum) }}</span></template>
      <template #faelligAm="{ x }"><span class="tnum" :class="x.tageUeberfaellig > 0 && offenStatus(x) ? 'font-semibold text-accent' : ''">{{ de(x.faelligAm) }}</span><div v-if="x.tageUeberfaellig > 0 && offenStatus(x)" class="text-[11px] text-accent">{{ x.tageUeberfaellig }} Tage überfällig</div></template>
      <template #brutto="{ x }"><span class="font-semibold" :class="x.brutto < 0 ? 'text-accent' : ''">{{ eur(x.brutto) }}</span></template>
      <template #offen="{ x }"><span :class="offenStatus(x) ? 'text-warn' : 'text-mute'">{{ offenStatus(x) ? eur(x.offen) : '–' }}</span></template>
      <template #status="{ x }"><StatusBadge :status="x.status" /></template>
      <template #leer>
        <div class="grid place-items-center px-6 py-16 text-center">
          <Receipt :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ store.rechnungen.length ? 'Keine Rechnungen in diesem Filter' : 'Noch keine Rechnungen' }}</p>
          <p class="mt-1 max-w-sm text-xs text-mute">Rechnungen entstehen immer im Auftrag über „Rechnung erstellen“, als Gesamtrechnung oder Teilrechnung aus Lieferscheinen.</p>
          <RouterLink to="/auftraege" class="btn mt-4">Zu den Aufträgen</RouterLink>
        </div>
      </template>
    </ListenTabelle>
  </div>
</template>
