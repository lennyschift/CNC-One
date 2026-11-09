<script setup>
import { onMounted, ref, computed } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { ClipboardList, Search } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektMarke from '../components/ProjektMarke.vue';
import { useBelege } from '../stores/belege.js';
import { eur } from '../lib/format.js';

const b = useBelege();
onMounted(() => b.auftraegeNeuLaden());
const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
const suche = ref('');
const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return b.auftraege.filter((x) => !q || `${x.id} ${x.projekt} ${x.kundeName} ${x.kontaktName} ${x.kundenbestellnr} ${x.angebotId} ${x.positionen.map((p) => `${p.teil.name} ${p.teil.teilenummer}`).join(' ')}`.toLowerCase().includes(q));
});
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <div v-if="b.auftraege.length" class="mb-5 flex flex-wrap items-center gap-3">
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Projekt, Kunde, Bestellung …" />
      </label>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ b.auftraege.length }}</span>
    </div>
    <div v-auto-animate class="space-y-2.5">
      <RouterLink v-for="x in zeilen" :key="x.id" :to="`/auftraege/${x.id}`" class="card flex items-center gap-5 p-4 transition hover:-translate-y-px hover:border-accent/40">
        <div class="flex -space-x-3">
          <PartImage v-for="p in x.positionen.slice(0, 3)" :key="p.key" :teil="p.teil" :groesse="46" class="ring-2 ring-surface" />
          <div v-if="x.positionen.length > 3" class="grid h-[46px] w-[46px] place-items-center rounded-xl border border-line bg-surface2 text-xs font-medium text-mute ring-2 ring-surface">+{{ x.positionen.length - 3 }}</div>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-3"><span class="font-semibold tnum">{{ x.id }}</span><StatusBadge :status="x.status" /><StatusBadge v-if="x.lieferung.geliefert" :status="x.lieferung.status" /><ProjektMarke :projekt="x.projekt" /></div>
          <div class="mt-0.5 truncate text-sm text-mute">{{ x.kundeName }}<template v-if="x.kontaktName"> · {{ x.kontaktName }}</template><template v-if="x.kundenbestellnr"> · Bestellung {{ x.kundenbestellnr }}</template> · aus {{ x.angebotId }}</div>
        </div>
        <div class="text-right">
          <div class="font-semibold tnum">{{ eur(x.netto) }}</div>
          <div class="text-xs text-mute">{{ de(x.datum) }}</div>
        </div>
      </RouterLink>

      <div v-if="!b.auftraege.length" class="card grid place-items-center px-6 py-16 text-center">
        <ClipboardList :size="36" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">Noch keine Aufträge</p>
        <p class="mt-1 text-xs text-mute">Aufträge entstehen aus einem gesendeten Angebot über „In Auftrag übernehmen“.</p>
        <RouterLink to="/angebote" class="btn mt-4">Zu den Angeboten</RouterLink>
      </div>
    </div>
  </div>
</template>
