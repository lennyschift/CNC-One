<script setup>
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Send, Search, FileText } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { useBelege } from '../stores/belege.js';

const route = useRoute();
const router = useRouter();
const a = useAnfragen();
const belege = useBelege();

const filter = ref('Alle');
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

const zeilen = computed(() => {
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
const titel = (x) => (x.positionen.length === 1 ? `${x.positionen[0].agName || 'Fremdvergabe'} · ${x.positionen[0].teil.name}` : `${x.positionen.length} Positionen: ${x.positionen.map((p) => p.teil.name).join(', ')}`);
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
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
    </div>

    <div v-auto-animate class="space-y-2.5">
      <RouterLink v-for="x in zeilen" :key="x.id" :to="`/anfragen/${x.id}`" class="card flex items-center gap-5 p-4 transition hover:-translate-y-px hover:border-accent/40">
        <div class="flex -space-x-3">
          <PartImage v-for="p in x.positionen.slice(0, 3)" :key="p.key" :teil="p.teil" :groesse="46" class="ring-2 ring-surface" />
          <div v-if="x.positionen.length > 3" class="grid h-[46px] w-[46px] place-items-center rounded-xl border border-line bg-surface2 text-xs font-medium text-mute ring-2 ring-surface">+{{ x.positionen.length - 3 }}</div>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="font-semibold tnum">{{ x.id }}</span><StatusBadge :status="x.status" />
            <span class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute"><FileText :size="11" /> {{ x.angebotId }}<template v-if="kunde(x)"> · {{ kunde(x) }}</template></span>
          </div>
          <div class="mt-0.5 truncate text-sm text-mute">{{ x.lieferantName }} · {{ titel(x) }}</div>
        </div>
        <div class="text-right text-sm">
          <div class="tnum">{{ x.positionen.length }} Position{{ x.positionen.length === 1 ? '' : 'en' }}</div>
          <div class="text-xs text-mute">{{ de(x.erstellt) }}</div>
        </div>
      </RouterLink>

      <div v-if="!zeilen.length" class="card grid place-items-center px-6 py-16 text-center">
        <Send :size="36" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">{{ a.liste.length ? 'Keine Anfragen mit diesen Filtern' : 'Noch keine Lieferantenanfragen' }}</p>
        <p class="mt-1 max-w-sm text-xs text-mute">Anfragen entstehen in der Workbench über „Lieferantenanfrage“ oder am Arbeitsgang einer Fremdvergabe.</p>
        <RouterLink to="/workbench" class="btn mt-4">Zur Workbench</RouterLink>
      </div>
    </div>
  </div>
</template>
