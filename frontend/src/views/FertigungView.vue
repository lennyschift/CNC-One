<script setup>
// Fertigungsübersicht mit mehreren Ansichten: Kanban (nach Status, Arbeitsgang oder Maschine), Liste, Kalender (Einplanen
// per Drag and Drop auf Tag und Maschine), Auslastung je Maschine und Woche sowie die Auswertung der gemeldeten Zeiten.
import { ref, computed, watch, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Search, Factory, Flame, Columns3, List, CalendarDays, Gauge, BarChart3, ClipboardList, X } from '@lucide/vue';
import { useRoute, useRouter } from 'vue-router';
import FertigungKarte from '../components/FertigungKarte.vue';
import FertigungListe from '../components/FertigungListe.vue';
import FertigungKalender from '../components/FertigungKalender.vue';
import FertigungAuslastung from '../components/FertigungAuslastung.vue';
import FertigungAuswertung from '../components/FertigungAuswertung.vue';
import FilterLeiste from '../components/FilterLeiste.vue';
import { useFertigung } from '../stores/fertigung.js';
import { useBelege } from '../stores/belege.js';
import { useUi } from '../stores/ui.js';
import { repo } from '../data/repo.js';
import { STATUS, maschinenFuer, restMinuten } from '../lib/fertigung.js';
import { zahl } from '../lib/format.js';

const f = useFertigung();
const b = useBelege();
const ui = useUi();
const maschinen = ref([]);
onMounted(async () => { maschinen.value = await repo.maschinen.liste(); });

// gewählte Ansicht und Kanban-Gruppierung je Browser merken
const lesen = (k, d) => { try { return localStorage.getItem(k) || d; } catch { return d; } };
const merken = (k, v) => { try { localStorage.setItem(k, v); } catch { /* ohne Speicher geht es auch */ } };
const ANSICHTEN = [
  { id: 'kanban', label: 'Kanban', icon: Columns3 },
  { id: 'liste', label: 'Liste', icon: List },
  { id: 'kalender', label: 'Kalender', icon: CalendarDays },
  { id: 'auslastung', label: 'Auslastung', icon: Gauge },
  { id: 'auswertung', label: 'Auswertung', icon: BarChart3 },
];
const ansicht = ref(lesen('fertigung.ansicht', 'kanban'));
if (!ANSICHTEN.some((a) => a.id === ansicht.value)) ansicht.value = 'kanban';
const gruppe = ref(lesen('fertigung.gruppe', 'status'));
watch(ansicht, (v) => merken('fertigung.ansicht', v));
watch(gruppe, (v) => merken('fertigung.gruppe', v));

const suche = ref('');
const nurEilig = ref(false);
// Aus dem Auftrag kommend (?auftrag=…): alle Positionen dieses Auftrags, gespeicherte Filter gelten dann nicht
const route = useRoute();
const router = useRouter();
const auftragFilter = computed(() => String(route.query.auftrag ?? ''));
const auftragAus = () => router.replace({ path: '/fertigung' });
// Anpassbare Filter und Sortierung (je Benutzer gespeichert); Standard: Liefertermin, früheste zuerst
const zeilen = ref([]);
const beschriftungen = {
  kundeName: 'Kunde', termin: 'Liefertermin', prioritaet: 'Priorität', status: 'Status', 'arbeitsgaenge.maschine': 'Maschine',
  'arbeitsgaenge.lieferant': 'Lieferant (Fremdvergabe)', 'arbeitsgaenge.name': 'Arbeitsgang', auftragId: 'Auftrag', 'teil.name': 'Bauteil',
  'teil.teilenummer': 'Teilenummer', 'teil.material': 'Werkstoff', menge: 'Menge', 'rohmaterial.werkstoff': 'Rohmaterial', projekt: 'Projekt',
};
const rang = { prioritaet: ['Eilig', 'Hoch', 'Normal'], status: ['In Fertigung', 'Offen', 'Fertig'] };

const vorgefiltert = computed(() => f.liste.map((x) => ({ ...x, projekt: b.auftrag(x.auftragId)?.projekt ?? '' })).filter((x) => {
  const q = suche.value.trim().toLowerCase();
  const text = `${x.teil.name} ${x.teil.teilenummer} ${x.auftragId} ${x.kundeName} ${x.id} ${b.auftrag(x.auftragId)?.projekt ?? ''}`.toLowerCase();
  return (!q || text.includes(q)) && (!nurEilig.value || x.prioritaet !== 'Normal') && (!auftragFilter.value || x.auftragId === auftragFilter.value);
}));
const gefiltert = computed(() => (auftragFilter.value
  ? vorgefiltert.value.map((z) => f.liste.find((x) => x.id === z.id)).filter(Boolean).sort((a, b) => (a.auftragPosKey || '').localeCompare(b.auftragPosKey || '', 'de', { numeric: true }))
  : zeilen.value.map((z) => f.liste.find((x) => x.id === z.id)).filter(Boolean)));

// ---- Kanban: Spalten nach Status, Arbeitsgang oder Maschine (des aktuellen Arbeitsgangs)
const aktuell = (fb) => fb.arbeitsgaenge.find((a) => a.gebucht < fb.menge) ?? null;
const spalten = computed(() => {
  if (gruppe.value === 'status') return STATUS.map((s) => ({ name: s, items: gefiltert.value.filter((x) => x.status === s) }));
  const offen = gefiltert.value.filter((x) => x.status !== 'Fertig');
  const key = (fb) => {
    const a = aktuell(fb);
    if (!a) return fb.arbeitsgaenge.length ? '' : 'Ohne Arbeitsgänge';
    if (gruppe.value === 'art') return a.name || 'Ohne Namen';
    return a.typ === 'fremd' ? `Extern · ${a.lieferant || 'Lieferant offen'}` : a.maschine || 'Ohne Maschine';
  };
  const namen = gruppe.value === 'maschine' ? maschinen.value.map((m) => m.name) : [];
  const g = new Map(namen.map((n) => [n, []]));
  for (const fb of offen) {
    const k = key(fb);
    if (!k) continue;
    if (!g.has(k)) g.set(k, []);
    g.get(k).push(fb);
  }
  return [...g.entries()].map(([name, items]) => ({ name, items, minuten: items.reduce((s, fb) => s + (aktuell(fb) ? restMinuten(aktuell(fb), fb.menge) : 0), 0) }));
});
const ziel = ref('');
let ziehend = '';
function drop(spalte) {
  ziel.value = '';
  const id = ziehend;
  ziehend = '';
  if (!id) return;
  if (gruppe.value === 'status') { f.statusSetzen(id, spalte); return; }
  if (gruppe.value !== 'maschine') return;
  const fb = f.bauteil(id);
  const a = fb && aktuell(fb);
  const m = maschinen.value.find((x) => x.name === spalte);
  if (!a || !m || a.typ !== 'intern' || a.maschine === m.name) return;
  if (!maschinenFuer([m], a.name).length) { ui.toast(`${m.name} kann „${a.name}“ laut Stammdaten nicht`, 'warn'); return; }
  a.maschine = m.name;
  f.felderPlanen(fb.id);
  ui.toast(`${a.name} von ${fb.teil.name} auf ${m.name}`, 'ok');
}
const akzent = { Offen: 'bg-mute', 'In Fertigung': 'bg-warn', Fertig: 'bg-ok' };
</script>

<template>
  <div class="mx-auto max-w-[1600px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="a in ANSICHTEN" :key="a.id" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="ansicht === a.id ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="ansicht = a.id"><component :is="a.icon" :size="15" /> {{ a.label }}</button>
      </div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Bauteil, Auftrag, Kunde …" />
      </label>
      <button class="btn" :class="nurEilig ? '!border-accent !bg-accent-soft !text-accent' : ''" @click="nurEilig = !nurEilig"><Flame :size="15" /> Nur eilige</button>
      <div class="ml-auto text-sm text-mute"><span class="font-medium text-ink tnum">{{ f.offen.length }}</span> offen · <span class="tnum">{{ gefiltert.length }}</span> von <span class="tnum">{{ f.liste.length }}</span></div>
    </div>
    <div v-if="auftragFilter" class="mb-4 flex flex-wrap items-center gap-2 rounded-xl bg-accent-soft px-3.5 py-2 text-sm text-accent">
      <ClipboardList :size="15" /> Alle Positionen von <RouterLink :to="`/auftraege/${auftragFilter}`" class="font-semibold underline-offset-2 hover:underline tnum">{{ auftragFilter }}</RouterLink>
      <span class="text-xs opacity-80">· gespeicherte Filter sind dabei ausgeschaltet</span>
      <button class="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs hover:bg-surface" @click="auftragAus"><X :size="13" /> Auftragsfilter entfernen</button>
    </div>
    <FilterLeiste v-show="!auftragFilter" v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="fertigung" :beschriftungen="beschriftungen" :standard-angeheftet="['kundeName', 'arbeitsgaenge.maschine', 'termin']" sortierbar :standard-sortierung="{ pfad: 'termin', richtung: 'auf' }" :rang="rang" />

    <div v-if="!f.liste.length" class="card grid place-items-center px-6 py-20 text-center">
      <Factory :size="38" class="text-mute" :stroke-width="1.4" />
      <p class="mt-3 text-sm font-medium">Noch keine Fertigungsbauteile</p>
      <p class="mt-1 max-w-sm text-xs text-mute">Sie entstehen aus einem Auftrag über „Fertigung starten“, ein Fertigungsbauteil pro Position.</p>
      <RouterLink to="/auftraege" class="btn mt-4">Zu den Aufträgen</RouterLink>
    </div>

    <!-- Kanban -->
    <template v-else-if="ansicht === 'kanban'">
      <div class="mb-3 flex flex-wrap items-center gap-2 text-xs text-mute">
        Spalten nach
        <span class="flex gap-0.5 rounded-lg border border-line bg-surface p-0.5" role="radiogroup" aria-label="Spalten nach">
          <button v-for="[k, l] in [['status', 'Status'], ['art', 'Arbeitsgang'], ['maschine', 'Maschine']]" :key="k" class="rounded-md px-2.5 py-1" :class="gruppe === k ? 'bg-accent-soft font-medium text-accent' : 'hover:text-ink'" @click="gruppe = k">{{ l }}</button>
        </span>
        <span v-if="gruppe === 'maschine'">Karte auf eine Maschine ziehen: Der aktuelle Arbeitsgang läuft dann dort.</span>
        <span v-else-if="gruppe === 'art'">Offene Bauteile nach ihrem aktuellen Arbeitsgang.</span>
      </div>
      <div class="flex items-start gap-4 overflow-x-auto pb-4" :class="gruppe === 'status' ? 'lg:grid lg:grid-cols-3' : ''">
        <section
          v-for="s in spalten"
          :key="s.name"
          class="min-h-[320px] shrink-0 rounded-2xl border border-dashed p-3 transition"
          :class="[ziel === s.name ? 'border-accent bg-accent-soft/50' : 'border-line bg-surface2/60', gruppe === 'status' ? 'w-[320px] lg:w-auto' : 'w-[310px]']"
          @dragover.prevent="ziel = s.name"
          @dragleave="ziel = ''"
          @drop.prevent="drop(s.name)"
        >
          <header class="mb-3 flex items-center gap-2 px-1">
            <span v-if="gruppe === 'status'" class="h-2 w-2 rounded-full" :class="akzent[s.name]" />
            <h2 class="min-w-0 flex-1 truncate text-sm font-semibold">{{ s.name }}</h2>
            <span v-if="s.minuten" class="rounded-full bg-surface px-2 py-0.5 text-xs text-mute tnum">{{ zahl(s.minuten / 60, 1) }} h</span>
            <span class="rounded-full bg-surface px-2 py-0.5 text-xs text-mute tnum">{{ s.items.length }}</span>
          </header>
          <div v-auto-animate class="space-y-3">
            <FertigungKarte v-for="x in s.items" :key="x.id" :fb="x" @drag="ziehend = $event" />
          </div>
          <p v-if="!s.items.length" class="px-2 py-10 text-center text-xs text-mute">{{ gruppe === 'art' ? 'Nichts offen' : 'Hierher ziehen' }}</p>
        </section>
      </div>
    </template>

    <FertigungListe v-else-if="ansicht === 'liste'" :liste="gefiltert" />
    <FertigungKalender v-else-if="ansicht === 'kalender'" :liste="gefiltert" :maschinen="maschinen" />
    <FertigungAuslastung v-else-if="ansicht === 'auslastung'" :liste="gefiltert" :maschinen="maschinen" />
    <FertigungAuswertung v-else-if="ansicht === 'auswertung'" :liste="gefiltert" />
  </div>
</template>
