<script setup>
import { ref, computed, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Search, Receipt } from '@lucide/vue';
import RechnungNav from '../components/RechnungNav.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useRechnung } from '../stores/rechnung.js';
import { eur } from '../lib/format.js';

const store = useRechnung();
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
const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return store.rechnungen.filter((r) => passt(r) && (!q || `${r.nummer} ${r.id} ${r.kundeName} ${r.auftragId} ${r.kundenbestellnr}`.toLowerCase().includes(q)));
});
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
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
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Nummer, Kunde, Auftrag …" />
      </label>
    </div>

    <div v-auto-animate class="space-y-2.5">
      <RouterLink v-for="r in zeilen" :key="r.id" :to="`/rechnungen/${r.id}`" class="card flex items-center gap-5 p-4 transition hover:-translate-y-px hover:border-accent/40" :class="r.status === 'Storniert' ? 'opacity-60' : ''">
        <span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-surface2 text-mute"><Receipt :size="20" /></span>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="font-semibold tnum">{{ r.nummer || 'Entwurf' }}</span><StatusBadge :status="r.status" />
            <span v-if="r.art === 'Teilrechnung'" class="rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute">Teilrechnung</span>
            <span v-if="r.tageUeberfaellig > 0" class="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">{{ r.tageUeberfaellig }} Tage überfällig</span>
          </div>
          <div class="mt-0.5 truncate text-sm text-mute">{{ r.kundeName }} · aus {{ r.auftragId }}<template v-if="r.kundenbestellnr"> · Bestellung {{ r.kundenbestellnr }}</template></div>
        </div>
        <div class="text-right">
          <div class="font-semibold tnum" :class="r.brutto < 0 ? 'text-accent' : ''">{{ eur(r.brutto) }}</div>
          <div class="text-xs text-mute">{{ r.status === 'Offen' || r.status === 'Teilbezahlt' ? `fällig ${de(r.faelligAm)}` : de(r.rechnungsdatum) }}</div>
          <div v-if="r.status === 'Teilbezahlt'" class="text-[11px] text-warn tnum">offen {{ eur(r.offen) }}</div>
        </div>
      </RouterLink>
      <div v-if="!zeilen.length" class="card grid place-items-center px-6 py-16 text-center">
        <Receipt :size="36" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">{{ store.rechnungen.length ? 'Keine Rechnungen in diesem Filter' : 'Noch keine Rechnungen' }}</p>
        <p class="mt-1 max-w-sm text-xs text-mute">Rechnungen entstehen immer im Auftrag über „Rechnung erstellen“, als Gesamtrechnung oder Teilrechnung aus Lieferscheinen.</p>
        <RouterLink to="/auftraege" class="btn mt-4">Zu den Aufträgen</RouterLink>
      </div>
    </div>
  </div>
</template>
