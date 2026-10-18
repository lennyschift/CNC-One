<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Search, Truck } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
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

const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return l.lieferscheine.filter((x) => (filter.value === 'Alle' || x.status === filter.value)
    && (!q || `${x.id} ${x.kundeName} ${x.kundenbestellnr} ${x.positionen.map((p) => `${p.teil.name} ${p.teil.teilenummer} ${p.auftragId}`).join(' ')}`.toLowerCase().includes(q)));
});
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const auftraegeVon = (x) => [...new Set(x.positionen.map((p) => p.auftragId).filter(Boolean))];
const stueck = (x) => x.positionen.reduce((n, p) => n + p.menge, 0);
function angelegt(rec) { dialog.value = false; router.push(`/lieferscheine/${rec.id}`); }
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Kunde, Bauteil, Auftrag …" />
      </label>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ l.lieferscheine.length }}</span>
      <button class="btn btn-primary" @click="dialog = true"><Plus :size="16" /> Neuer Lieferschein</button>
    </div>

    <div v-auto-animate class="space-y-2.5">
      <RouterLink v-for="x in zeilen" :key="x.id" :to="`/lieferscheine/${x.id}`" class="card flex items-center gap-5 p-4 transition hover:-translate-y-px hover:border-accent/40" :class="x.status === 'Storniert' ? 'opacity-60' : ''">
        <div class="flex -space-x-3">
          <PartImage v-for="(p, i) in x.positionen.slice(0, 3)" :key="i" :teil="p.teil" :groesse="46" class="ring-2 ring-surface" />
          <div v-if="x.positionen.length > 3" class="grid h-[46px] w-[46px] place-items-center rounded-xl border border-line bg-surface2 text-xs font-medium text-mute ring-2 ring-surface">+{{ x.positionen.length - 3 }}</div>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1"><span class="font-semibold tnum">{{ x.id }}</span><StatusBadge :status="x.status" /></div>
          <div class="mt-0.5 truncate text-sm text-mute">{{ x.kundeName }} · {{ x.positionen.map((p) => p.teil.name).join(', ') }}</div>
          <div class="mt-0.5 truncate text-xs text-mute">{{ auftraegeVon(x).length ? `aus ${auftraegeVon(x).join(', ')}` : 'ohne Auftrag' }}</div>
        </div>
        <div class="text-right text-sm">
          <div class="tnum">{{ stueck(x) }} Stk · {{ x.positionen.length }} Pos.</div>
          <div class="text-xs text-mute">{{ de(x.gelieferAm || x.lieferdatum || x.erstellt) }}</div>
        </div>
      </RouterLink>

      <div v-if="!zeilen.length" class="card grid place-items-center px-6 py-16 text-center">
        <Truck :size="36" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">{{ l.lieferscheine.length ? 'Keine Lieferscheine in diesem Filter' : 'Noch keine Lieferscheine' }}</p>
        <p class="mt-1 max-w-sm text-xs text-mute">Lieferscheine entstehen im Auftrag über „Lieferschein erstellen“ oder hier frei aus den Bauteilen eines Kunden. Sie dürfen auch schon vor der Fertigung angelegt werden.</p>
      </div>
    </div>

    <LieferscheinDialog v-if="dialog" @schliessen="dialog = false" @angelegt="angelegt" />
  </div>
</template>
