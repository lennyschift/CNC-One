<script setup>
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { ClipboardList } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useBelege } from '../stores/belege.js';
import { eur } from '../lib/format.js';

const b = useBelege();
const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <div v-auto-animate class="space-y-2.5">
      <RouterLink v-for="x in b.auftraege" :key="x.id" :to="`/auftraege/${x.id}`" class="card flex items-center gap-5 p-4 transition hover:-translate-y-px hover:border-accent/40">
        <div class="flex -space-x-3">
          <PartImage v-for="p in x.positionen.slice(0, 3)" :key="p.key" :teil="p.teil" :groesse="46" class="ring-2 ring-surface" />
          <div v-if="x.positionen.length > 3" class="grid h-[46px] w-[46px] place-items-center rounded-xl border border-line bg-surface2 text-xs font-medium text-mute ring-2 ring-surface">+{{ x.positionen.length - 3 }}</div>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-3"><span class="font-semibold tnum">{{ x.id }}</span><StatusBadge :status="x.status" /></div>
          <div class="mt-0.5 truncate text-sm text-mute">{{ x.kundeName }}<template v-if="x.kundenbestellnr"> · Bestellung {{ x.kundenbestellnr }}</template> · aus {{ x.angebotId }}</div>
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
