<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, FileText, Send, Search } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektMarke from '../components/ProjektMarke.vue';
import { useBelege } from '../stores/belege.js';
import { useAngebot } from '../stores/angebot.js';
import { useAnfragen } from '../stores/anfragen.js';
import { eur } from '../lib/format.js';

const router = useRouter();
const b = useBelege();
const a = useAngebot();
const anfragen = useAnfragen();
const anfragenZu = (x) => anfragen.fuerAngebot({ angebotId: x.id });

const filter = ref('Alle');
// „Alle“ ohne ersetzte Fassungen (die gelten nicht mehr); die stehen unter „Ersetzt“
const filterListe = ['Alle', 'Entwurf', 'Gesendet', 'Bestellt', 'Ersetzt'];
const suche = ref('');
const ansprechpartner = (x) => x.kopf.kontaktName || x.mailAnfrage?.vonName || x.mailAnfrage?.vonEmail || '';
// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'status': 'Status', 'kopf.kundeName': 'Kunde', 'kopf.projekt': 'Projekt', 'kopf.anfrageNr': 'Anfragenummer des Kunden', 'kopf.kontaktName': 'Ansprechpartner', 'netto': 'Netto', 'datum': 'Datum', 'teile.name': 'Bauteil', 'teile.teilenummer': 'Teilenummer', 'teile.material': 'Werkstoff'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return b.angebote
    .map((x) => ({ ...x, anzeige: b.statusVon(x) }))
    .filter((x) => (filter.value === 'Alle' ? x.status !== 'Ersetzt' : x.anzeige.includes(filter.value)) || (filter.value === 'Bestellt' && x.anzeige === 'Teilweise bestellt'))
    .filter((x) => !q || `${x.id} ${x.kopf.projekt} ${x.kopf.kundeName} ${ansprechpartner(x)} ${x.kopf.anfrageNr} ${x.positionen.map((p) => `${p.teil.name} ${p.teil.teilenummer}`).join(' ')}`.toLowerCase().includes(q));
});

async function neu() {
  await a.neu();
  router.push('/workbench');
}
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
const SPALTEN = [
  { key: 'id', label: 'Nummer', breite: '130px' },
  { key: 'bauteile', label: 'Bauteile', wert: (x) => x.positionen.length },
  { key: 'kunde', label: 'Kunde', wert: (x) => x.kopf.kundeName },
  { key: 'projekt', label: 'Projekt', wert: (x) => x.kopf.projekt },
  { key: 'anfrageNr', label: 'Anfragenr.', wert: (x) => x.kopf.anfrageNr },
  { key: 'netto', label: 'Netto', rechts: true },
  { key: 'datum', label: 'Datum', wert: (x) => x.versandt ?? x.erstellt },
  { key: 'status', label: 'Status', wert: (x) => x.anzeige },
];
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <label class="relative mr-auto">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Projekt, Kunde, Kontakt …" />
      </label>
      <button class="btn btn-primary" @click="neu"><Plus :size="16" /> Neues Angebot</button>
    </div>

    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="angebote" :beschriftungen="beschriftungen" :standard-angeheftet="['kopf.kundeName']" />
    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" :link="(x) => `/angebote/${x.id}`" min-breite="1050px">
      <template #id="{ x }"><span class="font-semibold tnum">{{ x.id }}</span>
        <span v-if="anfragenZu(x).length" class="ml-1.5 inline-flex items-center gap-1 rounded-full bg-surface2 px-1.5 py-0.5 text-[10px]" :class="anfragenZu(x).every((z) => z.status !== 'Gesendet') ? 'text-ok' : 'text-warn'" title="Lieferantenanfragen zu diesem Angebot"><Send :size="10" />{{ anfragenZu(x).length }}</span>
      </template>
      <template #bauteile="{ x }"><div class="flex max-w-[330px] flex-wrap gap-1.5">
              <span v-for="(p, i) in x.positionen.slice(0, 12)" :key="i" :title="[p.teil.name, p.teil.teilenummer].filter(Boolean).join(' · ') || 'Bauteil'"><PartImage :teil="p.teil" :groesse="40" /></span>
              <span v-if="x.positionen.length > 12" class="grid h-10 w-10 place-items-center rounded-lg border border-line bg-surface2 text-[11px] font-medium text-mute">+{{ x.positionen.length - 12 }}</span>
              <span v-if="!x.positionen.length" class="text-mute">–</span>
            </div></template>
      <template #kunde="{ x }"><div class="truncate">{{ x.kopf.kundeName || '–' }}</div><div v-if="ansprechpartner(x)" class="truncate text-xs text-mute">{{ ansprechpartner(x) }}</div></template>
      <template #projekt="{ x }"><ProjektMarke v-if="x.kopf.projekt" :projekt="x.kopf.projekt" /><span v-else class="text-mute">–</span></template>
      <template #anfrageNr="{ x }"><span class="tnum">{{ x.kopf.anfrageNr || '–' }}</span></template>
      <template #netto="{ x }"><span class="font-semibold">{{ eur(x.netto) }}</span></template>
      <template #datum="{ x }"><span class="tnum">{{ de(x.versandt ?? x.erstellt) }}</span></template>
      <template #status="{ x }"><StatusBadge :status="x.anzeige" /></template>
      <template #leer>
        <div class="grid place-items-center px-6 py-16 text-center">
          <FileText :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ b.angebote.length ? 'Keine Angebote in diesem Filter' : 'Noch keine Angebote' }}</p>
          <p class="mt-1 text-xs text-mute">In der Workbench ein Angebot zusammenstellen und speichern.</p>
          <button class="btn btn-primary mt-4" @click="neu"><Plus :size="16" /> Neues Angebot</button>
        </div>
      </template>
    </ListenTabelle>
  </div>
</template>
