<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, FileText, Send } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
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
const filterListe = ['Alle', 'Entwurf', 'Gesendet', 'Beauftragt'];
const zeilen = computed(() => b.angebote
  .map((x) => ({ ...x, anzeige: b.statusVon(x) }))
  .filter((x) => filter.value === 'Alle' || x.anzeige.includes(filter.value) || (filter.value === 'Beauftragt' && x.anzeige === 'Teilweise beauftragt')));

async function neu() {
  await a.neu();
  router.push('/workbench');
}
const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in filterListe" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <button class="btn btn-primary" @click="neu"><Plus :size="16" /> Neues Angebot</button>
    </div>

    <div v-auto-animate class="space-y-2.5">
      <RouterLink v-for="x in zeilen" :key="x.id" :to="`/angebote/${x.id}`" class="card flex items-center gap-5 p-4 transition hover:-translate-y-px hover:border-accent/40">
        <div class="flex -space-x-3">
          <PartImage v-for="p in x.positionen.slice(0, 3)" :key="p.key" :teil="p.teil" :groesse="46" class="ring-2 ring-surface" />
          <div v-if="x.positionen.length > 3" class="grid h-[46px] w-[46px] place-items-center rounded-xl border border-line bg-surface2 text-xs font-medium text-mute ring-2 ring-surface">+{{ x.positionen.length - 3 }}</div>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-3"><span class="font-semibold tnum">{{ x.id }}</span><StatusBadge :status="x.anzeige" />
            <span v-if="anfragenZu(x).length" class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-[11px]" :class="anfragenZu(x).every((z) => z.status !== 'Gesendet') ? 'text-ok' : 'text-warn'" title="Lieferantenanfragen zu diesem Angebot"><Send :size="11" />{{ anfragenZu(x).length }}</span>
          </div>
          <div class="mt-0.5 truncate text-sm text-mute">{{ x.kopf.kundeName }} · {{ x.positionen.length }} Position{{ x.positionen.length === 1 ? '' : 'en' }}<template v-if="x.kopf.anfrageNr"> · Anfrage {{ x.kopf.anfrageNr }}</template></div>
        </div>
        <div class="text-right">
          <div class="font-semibold tnum">{{ eur(x.netto) }}</div>
          <div class="text-xs text-mute">{{ de(x.versandt ?? x.erstellt) }}</div>
        </div>
      </RouterLink>

      <div v-if="!zeilen.length" class="card grid place-items-center px-6 py-16 text-center">
        <FileText :size="36" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">{{ b.angebote.length ? 'Keine Angebote in diesem Filter' : 'Noch keine Angebote' }}</p>
        <p class="mt-1 text-xs text-mute">In der Workbench ein Angebot zusammenstellen und speichern.</p>
        <button class="btn btn-primary mt-4" @click="neu"><Plus :size="16" /> Neues Angebot</button>
      </div>
    </div>
  </div>
</template>
