<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { BellRing, CheckCircle2 } from '@lucide/vue';
import RechnungNav from '../components/RechnungNav.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useRechnung } from '../stores/rechnung.js';
import { benutzer } from '../data/repo.js';
import { eur } from '../lib/format.js';

const store = useRechnung();
const router = useRouter();
const darf = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'CNC Buchhaltung', 'System Manager'].includes(x)));

const vorschlag = ref(null);
async function laden() { vorschlag.value = (await store.mahnVorschlag()) ?? []; }
onMounted(async () => { await store.neuLaden().catch(() => {}); await laden(); });

async function mahnen(v) {
  const m = await store.mahnungAnlegen(v.rechnungId);
  if (m) router.push(`/mahnungen/${m.id}`);
}

const filter = ref('Alle');
const filterListe = ['Alle', 'Angelegt', 'Versendet', 'Erledigt', 'Zurückgezogen'];
// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'status': 'Status', 'stufe': 'Stufe', 'kundeName': 'Kunde', 'datum': 'Datum'};
const vorgefiltert = computed(() => store.mahnungen.filter((m) => filter.value === 'Alle' || m.status === filter.value));
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const SPALTEN = [
  { key: 'id', label: 'Nummer', breite: '130px' },
  { key: 'stufe', label: 'Stufe' },
  { key: 'kundeName', label: 'Kunde' },
  { key: 'rechnungNummer', label: 'Rechnung' },
  { key: 'datum', label: 'Datum' },
  { key: 'betrag', label: 'Betrag', rechts: true, wert: (m) => m.offenerBetrag + m.gebuehr },
  { key: 'fristBis', label: 'Zahlen bis' },
  { key: 'status', label: 'Status' },
];
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <RechnungNav />

    <section class="mb-8">
      <h2 class="mb-1 text-sm font-semibold">Überfällige Rechnungen</h2>
      <p class="mb-3 text-xs text-mute">Die nächste Stufe wird erst vorgeschlagen, wenn die Frist der letzten Mahnung abgelaufen ist.</p>
      <div v-auto-animate class="space-y-2.5">
        <div v-for="v in vorschlag ?? []" :key="v.rechnungId" class="card flex flex-wrap items-center gap-4 p-4">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1"><RouterLink :to="`/rechnungen/${v.rechnungId}`" class="font-semibold text-accent hover:underline tnum">{{ v.nummer }}</RouterLink><span class="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">{{ v.tageUeberfaellig }} Tage überfällig</span></div>
            <div class="mt-0.5 truncate text-sm text-mute">{{ v.kundeName }} · fällig am {{ de(v.faelligAm) }}</div>
            <div class="mt-1.5 flex flex-wrap gap-1.5"><RouterLink v-for="m in v.mahnungen" :key="m.id" :to="`/mahnungen/${m.id}`" class="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface2 px-2.5 py-0.5 text-xs hover:border-accent/50"><span>{{ m.stufe }}</span><span class="text-mute">bis {{ de(m.fristBis) }}</span><StatusBadge :status="m.status" /></RouterLink></div>
          </div>
          <div class="text-right"><div class="font-semibold tnum">{{ eur(v.offen) }}</div><div class="text-xs text-mute">offen</div></div>
          <div class="w-52 text-right">
            <button v-if="v.naechsteStufe && darf" class="btn w-full justify-center" :class="v.bereit ? 'btn-primary' : 'pointer-events-none opacity-50'" :disabled="!v.bereit" @click="mahnen(v)"><BellRing :size="15" /> {{ v.naechsteStufe }} anlegen</button>
            <p v-if="v.naechsteStufe && !v.bereit" class="mt-1 text-[11px] text-mute">Frist der letzten Mahnung läuft noch.</p>
            <p v-if="!v.naechsteStufe" class="text-xs text-mute">Alle Mahnstufen sind durch.</p>
          </div>
        </div>
        <div v-if="vorschlag && !vorschlag.length" class="card grid place-items-center px-6 py-10 text-center"><CheckCircle2 :size="30" class="text-ok" :stroke-width="1.5" /><p class="mt-2 text-sm font-medium">Keine überfälligen Rechnungen</p></div>
        <p v-if="vorschlag === null" class="px-2 text-sm text-mute">Lädt …</p>
      </div>
    </section>

    <section>
      <div class="mb-3 flex flex-wrap items-center gap-3">
        <h2 class="mr-auto text-sm font-semibold">Mahnungen</h2>
        <div class="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1"><button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button></div>
      </div>
      <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="mahnungen" :beschriftungen="beschriftungen" :standard-angeheftet="[]" />
      <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" :link="(m) => `/mahnungen/${m.id}`" min-breite="900px" leer-text="Noch keine Mahnungen in diesem Filter.">
        <template #id="{ x }"><span class="font-semibold tnum" :class="x.status === 'Zurückgezogen' ? 'text-mute line-through' : ''">{{ x.id }}</span></template>
        <template #rechnungNummer="{ x }"><span class="tnum">{{ x.rechnungNummer || '–' }}</span></template>
        <template #datum="{ x }"><span class="tnum">{{ de(x.datum) || '–' }}</span></template>
        <template #betrag="{ x }"><span class="font-semibold">{{ eur(x.offenerBetrag + x.gebuehr) }}</span></template>
        <template #fristBis="{ x }"><span class="tnum">{{ de(x.fristBis) || '–' }}</span></template>
        <template #status="{ x }"><StatusBadge :status="x.status" /></template>
      </ListenTabelle>
    </section>
  </div>
</template>
