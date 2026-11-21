<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { onMounted, ref, computed } from 'vue';
import { ClipboardList, Search, FileUp } from '@lucide/vue';
import { useRouter } from 'vue-router';
import BestellungDialog from '../components/BestellungDialog.vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektMarke from '../components/ProjektMarke.vue';
import { useBelege } from '../stores/belege.js';
import { eur } from '../lib/format.js';

const b = useBelege();
onMounted(() => b.auftraegeNeuLaden());
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
// frühester Liefertermin der noch nicht entfallenen Positionen
const termin = (x) => x.positionen.filter((p) => !p.entfallen).map((p) => p.termin).filter(Boolean).sort()[0] ?? '';
const SPALTEN = [
  { key: 'id', label: 'Nummer', breite: '130px' },
  { key: 'bauteile', label: 'Bauteile', wert: (x) => x.positionen.length },
  { key: 'kunde', label: 'Kunde', wert: (x) => x.kundeName },
  { key: 'projekt', label: 'Projekt' },
  { key: 'kundenbestellnr', label: 'Bestellnr.' },
  { key: 'termin', label: 'Liefertermin', wert: termin },
  { key: 'netto', label: 'Netto', rechts: true },
  { key: 'datum', label: 'Angelegt' },
  { key: 'status', label: 'Status' },
];
const suche = ref('');
// Auftrag aus der Bestellung des Kunden (PDF)
const bestellung = ref(false);
const router = useRouter();
function bestellungFertig(rec) { bestellung.value = false; router.push(`/auftraege/${rec.id}`); }
// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'status': 'Status', 'kundeName': 'Kunde', 'projekt': 'Projekt', 'kundenbestellnr': 'Bestellnummer des Kunden', 'kontaktName': 'Ansprechpartner', 'netto': 'Netto', 'datum': 'Angelegt am', 'lieferung.status': 'Lieferstand', 'abrechnung.status': 'Abrechnung', 'positionen.teil.name': 'Bauteil', 'positionen.teil.teilenummer': 'Teilenummer', 'positionen.teil.material': 'Werkstoff', 'positionen.termin': 'Liefertermin', 'ab.gesendetAm': 'AB gesendet am'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return b.auftraege.filter((x) => !q || `${x.id} ${x.projekt} ${x.kundeName} ${x.kontaktName} ${x.kundenbestellnr} ${x.angebotId} ${x.positionen.map((p) => `${p.teil.name} ${p.teil.teilenummer}`).join(' ')}`.toLowerCase().includes(q));
});
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Projekt, Kunde, Bestellung …" />
      </label>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ b.auftraege.length }}</span>
      <button class="btn btn-primary" title="PDF der Bestellung einlesen, mit Angeboten und früheren Aufträgen abgleichen und als Auftrag anlegen" @click="bestellung = true"><FileUp :size="16" /> Auftrag aus Bestellung</button>
    </div>
    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="auftraege" :beschriftungen="beschriftungen" :standard-angeheftet="['kundeName']" />
    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" :link="(x) => `/auftraege/${x.id}`" min-breite="1100px">
      <template #id="{ x }"><div class="font-semibold tnum">{{ x.id }}</div><div class="truncate text-[11px] text-mute">{{ x.angebote?.length ? `aus ${x.angebote.join(', ')}` : 'aus Bestellung' }}</div></template>
      <template #bauteile="{ x }"><div class="flex max-w-[330px] flex-wrap gap-1.5">
              <span v-for="(p, i) in x.positionen.slice(0, 12)" :key="i" :title="[p.teil.name, p.teil.teilenummer].filter(Boolean).join(' · ') || 'Bauteil'"><PartImage :teil="p.teil" :groesse="40" /></span>
              <span v-if="x.positionen.length > 12" class="grid h-10 w-10 place-items-center rounded-lg border border-line bg-surface2 text-[11px] font-medium text-mute">+{{ x.positionen.length - 12 }}</span>
              <span v-if="!x.positionen.length" class="text-mute">–</span>
            </div></template>
      <template #kunde="{ x }"><div class="truncate">{{ x.kundeName || '–' }}</div><div v-if="x.kontaktName" class="truncate text-xs text-mute">{{ x.kontaktName }}</div></template>
      <template #projekt="{ x }"><ProjektMarke v-if="x.projekt" :projekt="x.projekt" /><span v-else class="text-mute">–</span></template>
      <template #kundenbestellnr="{ x }"><span class="tnum">{{ x.kundenbestellnr || '–' }}</span></template>
      <template #termin="{ x }"><span class="tnum">{{ de(termin(x)) }}</span></template>
      <template #netto="{ x }"><span class="font-semibold">{{ eur(x.netto) }}</span></template>
      <template #datum="{ x }"><span class="tnum">{{ de(x.datum) }}</span></template>
      <template #status="{ x }"><div class="flex flex-col items-start gap-1"><StatusBadge :status="x.status" /><StatusBadge v-if="x.lieferung.geliefert" :status="x.lieferung.status" /></div></template>
      <template #leer>
        <div class="grid place-items-center px-6 py-16 text-center">
          <ClipboardList :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ b.auftraege.length ? 'Keine Aufträge in diesem Filter' : 'Noch keine Aufträge' }}</p>
          <p class="mt-1 text-xs text-mute">Aufträge entstehen aus einem gesendeten Angebot über „In Auftrag übernehmen“ oder aus der Bestellung des Kunden (PDF).</p>
          <RouterLink to="/angebote" class="btn mt-4">Zu den Angeboten</RouterLink>
        </div>
      </template>
    </ListenTabelle>
    <BestellungDialog v-if="bestellung" @schliessen="bestellung = false" @fertig="bestellungFertig" />
  </div>
</template>
