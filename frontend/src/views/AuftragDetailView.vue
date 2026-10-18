<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, MapPin, UserRound, Hash, CalendarDays, Factory, Truck } from '@lucide/vue';
import LieferscheinDialog from '../components/LieferscheinDialog.vue';
import { bereichText } from '../lib/serien.js';
import WorkflowSteps from '../components/WorkflowSteps.vue';
import StatusBadge from '../components/StatusBadge.vue';
import PartImage from '../components/PartImage.vue';
import { useBelege } from '../stores/belege.js';
import { useFertigung } from '../stores/fertigung.js';
import { produziert, fortschritt } from '../lib/fertigung.js';
import { eur } from '../lib/format.js';

const route = useRoute();
const b = useBelege();
const f = useFertigung();
const auftrag = computed(() => b.auftrag(route.params.id));
onMounted(() => b.auftraegeNeuLaden());
const lieferDialog = ref(false);
const fbs = computed(() => (auftrag.value ? f.fuerAuftrag(auftrag.value.id) : []));
// Ein Haken gibt es erst, wenn der Schritt wirklich fertig ist. Ein Lieferschein vor der Fertigung hakt die Fertigung nicht ab.
const stand = computed(() => {
  if (!fbs.value.length) return 1;
  if (!fbs.value.every((x) => x.status === 'Fertig')) return 2;
  return auftrag.value?.lieferung?.status === 'Geliefert' ? 4 : 3;
});
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
const fbZu = (key) => fbs.value.find((x) => x.auftragPosKey === key);
</script>

<template>
  <div v-if="auftrag" class="mx-auto max-w-[1200px] space-y-4">
    <RouterLink to="/auftraege" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Aufträge</RouterLink>

    <section class="card p-6">
      <div class="flex flex-wrap items-start justify-between gap-6">
        <div>
          <div class="flex items-center gap-3"><h2 class="text-xl font-semibold tnum">{{ auftrag.id }}</h2><StatusBadge :status="auftrag.status" /></div>
          <p class="mt-1 text-sm text-mute">aus <RouterLink :to="`/angebote/${auftrag.angebotId}`" class="text-accent hover:underline tnum">{{ auftrag.angebotId }}</RouterLink> · angelegt am {{ de(auftrag.datum) }}</p>
          <button v-if="!fbs.length" class="btn btn-primary mt-4" @click="f.ausAuftrag(auftrag.id)"><Factory :size="16" /> Fertigung starten</button>
          <RouterLink v-else to="/fertigung" class="btn mt-4"><Factory :size="16" /> Zur Fertigung</RouterLink>
          <button v-if="auftrag.lieferung.status !== 'Geliefert'" class="btn mt-4 ml-2" @click="lieferDialog = true"><Truck :size="16" /> Lieferschein erstellen</button>
          <span class="ml-2 mt-4 inline-block align-middle"><StatusBadge :status="auftrag.lieferung.status" /></span>
        </div>
        <div class="w-full max-w-xl"><WorkflowSteps :stand="stand" /></div>
      </div>
      <div class="mt-5 grid gap-3 text-sm md:grid-cols-3">
        <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><MapPin :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div class="font-medium">{{ auftrag.kundeName }}</div><div v-for="z in auftrag.kunde.adresse" :key="z" class="text-mute">{{ z }}</div></div></div>
        <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><UserRound :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div>{{ auftrag.kunde.kontakt?.name }}</div><div class="text-xs text-mute">{{ auftrag.kunde.kontakt?.email }}</div></div></div>
        <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><Hash :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div class="text-xs text-mute">Bestellnummer des Kunden</div><div>{{ auftrag.kundenbestellnr || '–' }}</div></div></div>
      </div>
    </section>

    <section class="card overflow-hidden">
      <header class="flex items-center justify-between border-b border-line px-6 py-4">
        <h3 class="text-sm font-semibold">Positionen</h3>
        <div class="text-right"><div class="text-xs text-mute">Auftragswert netto</div><div class="text-lg font-semibold tnum">{{ eur(auftrag.netto) }}</div></div>
      </header>
      <div v-for="(p, i) in auftrag.positionen" :key="p.key" class="flex gap-4 border-b border-line px-6 py-4 last:border-0">
        <PartImage :teil="p.teil" :groesse="64" />
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline justify-between gap-4">
            <div><span class="mr-2 text-mute">{{ i + 1 }}</span><span class="font-medium">{{ p.teil.name }}</span><span v-if="p.teil.teilenummer" class="ml-2 text-xs text-mute">{{ p.teil.teilenummer }}</span></div>
            <div class="text-sm tnum">{{ p.menge }} Stk × {{ eur(p.einzelpreis) }} = <span class="font-semibold">{{ eur(p.einzelpreis * p.menge) }}</span></div>
          </div>
          <div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-mute">
            <span v-if="p.teil.material">{{ p.teil.material }}</span>
            <span v-if="p.staffelMenge">Staffel {{ p.staffelMenge }} Stk</span>
            <span class="inline-flex items-center gap-1" :class="p.geliefert >= p.menge ? 'text-ok' : p.geliefert ? 'text-warn' : ''"><Truck :size="12" /> geliefert {{ p.geliefert }} / {{ p.menge }}</span>
            <span v-if="p.gefertigt || fbZu(p.key)">gefertigt {{ p.gefertigt }}</span>
            <RouterLink v-for="ls in p.lieferscheine" :key="ls.id" :to="`/lieferscheine/${ls.id}`" class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-accent hover:underline"><span class="tnum">{{ ls.id }}</span><span class="text-mute">{{ ls.menge }} Stk</span></RouterLink>
            <span v-if="p.serienVon" class="inline-flex items-center gap-1 text-ink"><Hash :size="12" /> Seriennummern {{ bereichText(p.serienVon, p.serienBis, p.serienStellen) }}</span>
            <span class="inline-flex items-center gap-1"><CalendarDays :size="12" /> Liefertermin {{ p.termin ? new Date(p.termin).toLocaleDateString('de-DE') : 'offen' }}</span>
          </div>
          <div v-for="k in p.kosten" :key="k.label" class="mt-1 flex justify-between pl-4 text-xs text-mute"><span>↳ {{ k.label }}</span><span class="tnum">{{ eur(k.betrag) }}</span></div>

          <RouterLink v-if="fbZu(p.key)" :to="`/fertigung/${fbZu(p.key).id}`" class="mt-3 flex items-center gap-3 rounded-xl bg-surface2 px-3.5 py-2.5 text-sm transition hover:bg-accent-soft">
            <Factory :size="15" class="text-accent" />
            <span class="tnum">{{ fbZu(p.key).id }}</span><StatusBadge :status="fbZu(p.key).status" />
            <span class="ml-auto text-xs text-mute tnum">{{ produziert(fbZu(p.key)) }} / {{ fbZu(p.key).menge }} Stk</span>
            <span class="h-1.5 w-24 overflow-hidden rounded-full bg-line"><span class="block h-full rounded-full" :class="fortschritt(fbZu(p.key)) >= 1 ? 'bg-ok' : 'bg-accent'" :style="{ width: fortschritt(fbZu(p.key)) * 100 + '%' }" /></span>
          </RouterLink>
        </div>
      </div>
    </section>
    <LieferscheinDialog v-if="lieferDialog" :auftrag-id="auftrag.id" @schliessen="lieferDialog = false" @angelegt="lieferDialog = false" />
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Auftrag nicht gefunden</p>
    <RouterLink to="/auftraege" class="btn mt-4">Zur Auftragsliste</RouterLink>
  </div>
</template>
