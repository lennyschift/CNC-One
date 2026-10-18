<script setup>
import { ref, computed } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Search, LayoutGrid, Cog, Truck, Factory, Flame } from '@lucide/vue';
import FertigungKarte from '../components/FertigungKarte.vue';
import PartImage from '../components/PartImage.vue';
import { useFertigung } from '../stores/fertigung.js';
import { STATUS, lasten, produziert, restMinuten } from '../lib/fertigung.js';
import { zahl } from '../lib/format.js';

const f = useFertigung();
const ansicht = ref('board');
const suche = ref('');
const nurEilig = ref(false);
const ziel = ref('');
let ziehend = '';

const gefiltert = computed(() => f.liste.filter((x) => {
  const q = suche.value.trim().toLowerCase();
  const text = `${x.teil.name} ${x.teil.teilenummer} ${x.auftragId} ${x.kundeName} ${x.id}`.toLowerCase();
  return (!q || text.includes(q)) && (!nurEilig.value || x.prioritaet !== 'Normal');
}));
const spalten = computed(() => STATUS.map((s) => ({ name: s, items: gefiltert.value.filter((x) => x.status === s) })));
const lanes = computed(() => lasten(gefiltert.value));

function drop(status) {
  ziel.value = '';
  if (ziehend) f.statusSetzen(ziehend, status);
  ziehend = '';
}
const stunden = (min) => zahl(min / 60, 1);
const akzent = { Offen: 'bg-mute', 'In Fertigung': 'bg-warn', Fertig: 'bg-ok' };
</script>

<template>
  <div class="mx-auto max-w-[1600px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="ansicht === 'board' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="ansicht = 'board'"><LayoutGrid :size="15" /> Board</button>
        <button class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="ansicht === 'maschinen' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="ansicht = 'maschinen'"><Cog :size="15" /> Maschinen</button>
      </div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Bauteil, Auftrag, Kunde …" />
      </label>
      <button class="btn" :class="nurEilig ? '!border-accent !bg-accent-soft !text-accent' : ''" @click="nurEilig = !nurEilig"><Flame :size="15" /> Nur eilige</button>
      <div class="ml-auto text-sm text-mute"><span class="font-medium text-ink tnum">{{ f.offen.length }}</span> offen · <span class="tnum">{{ f.liste.length }}</span> gesamt</div>
    </div>

    <!-- Board -->
    <div v-if="ansicht === 'board' && f.liste.length" class="grid items-start gap-4 lg:grid-cols-3">
      <section
        v-for="s in spalten"
        :key="s.name"
        class="min-h-[320px] rounded-2xl border border-dashed p-3 transition"
        :class="ziel === s.name ? 'border-accent bg-accent-soft/50' : 'border-line bg-surface2/60'"
        @dragover.prevent="ziel = s.name"
        @dragleave="ziel = ''"
        @drop.prevent="drop(s.name)"
      >
        <header class="mb-3 flex items-center gap-2 px-1">
          <span class="h-2 w-2 rounded-full" :class="akzent[s.name]" />
          <h2 class="text-sm font-semibold">{{ s.name }}</h2>
          <span class="rounded-full bg-surface px-2 py-0.5 text-xs text-mute tnum">{{ s.items.length }}</span>
        </header>
        <div v-auto-animate class="space-y-3">
          <FertigungKarte v-for="x in s.items" :key="x.id" :fb="x" @drag="ziehend = $event" />
        </div>
        <p v-if="!s.items.length" class="px-2 py-10 text-center text-xs text-mute">Hierher ziehen</p>
      </section>
    </div>

    <!-- Maschinen -->
    <div v-else-if="ansicht === 'maschinen' && f.liste.length" class="flex gap-4 overflow-x-auto pb-4">
      <section v-for="l in lanes" :key="l.name" class="w-[310px] shrink-0 rounded-2xl border border-line bg-surface2/60 p-3">
        <header class="mb-3 flex items-center gap-2 px-1">
          <component :is="l.fremd ? Truck : Cog" :size="16" class="text-accent" />
          <h2 class="min-w-0 flex-1 truncate text-sm font-semibold">{{ l.name }}</h2>
          <span v-if="!l.fremd" class="rounded-full bg-surface px-2 py-0.5 text-xs text-mute tnum">{{ stunden(l.minuten) }} h</span>
          <span v-else class="rounded-full bg-surface px-2 py-0.5 text-xs text-mute tnum">{{ l.eintraege.length }}</span>
        </header>
        <div v-auto-animate class="space-y-2">
          <RouterLink v-for="e in l.eintraege" :key="e.fb.id + e.ag.id" :to="`/fertigung/${e.fb.id}`" class="card flex items-center gap-3 p-2.5 transition hover:border-accent/40">
            <PartImage :teil="e.fb.teil" :groesse="40" />
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium">{{ e.fb.teil.name }}</div>
              <div class="truncate text-[11px] text-mute">{{ e.ag.name }} · {{ produziert(e.fb) }}/{{ e.fb.menge }} Stk</div>
            </div>
            <div class="text-right text-[11px] text-mute tnum">
              <div v-if="!l.fremd">{{ stunden(restMinuten(e.ag, e.fb.menge)) }} h</div>
              <div v-else>{{ e.ag.fremdStatus || 'Geplant' }}</div>
              <div v-if="e.fb.termin">{{ new Date(e.fb.termin).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) }}</div>
            </div>
          </RouterLink>
        </div>
      </section>
      <p v-if="!lanes.length" class="card w-full px-6 py-14 text-center text-sm text-mute">Keine offenen Arbeitsgänge.</p>
    </div>

    <div v-else-if="!f.liste.length" class="card grid place-items-center px-6 py-20 text-center">
      <Factory :size="38" class="text-mute" :stroke-width="1.4" />
      <p class="mt-3 text-sm font-medium">Noch keine Fertigungsbauteile</p>
      <p class="mt-1 max-w-sm text-xs text-mute">Sie entstehen aus einem Auftrag über „Fertigung starten“, ein Fertigungsbauteil pro Position.</p>
      <RouterLink to="/auftraege" class="btn mt-4">Zu den Aufträgen</RouterLink>
    </div>
  </div>
</template>
