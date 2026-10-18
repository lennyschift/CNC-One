<script setup>
import { Calculator, FileText, ClipboardList, Factory, Truck, Receipt, Users, Package, Settings, Send } from '@lucide/vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const punkte = [
  { id: 'workbench', label: 'Workbench', icon: Calculator, to: '/workbench' },
  { id: 'angebote', label: 'Angebote', icon: FileText, to: '/angebote' },
  { id: 'auftraege', label: 'Aufträge', icon: ClipboardList, to: '/auftraege' },
  { id: 'fertigung', label: 'Fertigung', icon: Factory, to: '/fertigung' },
  { id: 'anfragen', label: 'Lieferantenanfragen', icon: Send, to: '/anfragen' },
  { id: 'lieferscheine', label: 'Lieferscheine', icon: Truck },
  { id: 'rechnungen', label: 'Rechnungen', icon: Receipt },
  { id: 'kunden', label: 'Kunden', icon: Users },
  { id: 'teile', label: 'Teile', icon: Package },
];
</script>

<template>
  <nav class="flex w-[68px] shrink-0 flex-col items-center gap-1 border-r border-line bg-surface py-3">
    <div class="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-accent text-sm font-semibold tracking-tight text-white shadow-sm">C1</div>
    <template v-for="p in punkte" :key="p.id">
      <RouterLink
        v-if="p.to"
        :to="p.to"
        class="group relative grid h-11 w-11 place-items-center rounded-xl text-mute transition hover:bg-surface2 hover:text-ink"
        :class="route.meta.bereich === p.id ? '!bg-accent-soft !text-accent' : ''"
        :title="p.label"
      >
        <component :is="p.icon" :size="20" :stroke-width="1.8" />
        <span v-if="route.meta.bereich === p.id" class="absolute -left-[13px] h-5 w-1 rounded-r-full bg-accent" />
        <span class="pointer-events-none absolute left-full z-20 ml-3 whitespace-nowrap rounded-lg bg-ink px-2 py-1 text-xs text-bg opacity-0 transition group-hover:opacity-100">{{ p.label }}</span>
      </RouterLink>
      <div
        v-else
        class="group relative grid h-11 w-11 cursor-not-allowed place-items-center rounded-xl text-mute/40"
        :title="`${p.label} (folgt)`"
      >
        <component :is="p.icon" :size="20" :stroke-width="1.8" />
        <span class="pointer-events-none absolute left-full z-20 ml-3 whitespace-nowrap rounded-lg bg-ink px-2 py-1 text-xs text-bg opacity-0 transition group-hover:opacity-100">{{ p.label }} · folgt</span>
      </div>
    </template>
    <RouterLink
      to="/stammdaten"
      class="group relative mt-auto grid h-11 w-11 place-items-center rounded-xl text-mute transition hover:bg-surface2 hover:text-ink"
      :class="route.meta.bereich === 'stammdaten' ? '!bg-accent-soft !text-accent' : ''"
      title="Stammdaten"
    >
      <Settings :size="20" :stroke-width="1.8" />
      <span class="pointer-events-none absolute left-full z-20 ml-3 whitespace-nowrap rounded-lg bg-ink px-2 py-1 text-xs text-bg opacity-0 transition group-hover:opacity-100">Stammdaten</span>
    </RouterLink>
  </nav>
</template>
