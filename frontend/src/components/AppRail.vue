<script setup>
import { ref, watch } from 'vue';
import { Calculator, FileText, ClipboardList, Factory, Truck, Receipt, Database, Send, Warehouse } from '@lucide/vue';
import { onClickOutside } from '@vueuse/core';
import { useRoute } from 'vue-router';
import { STAMM_PUNKTE } from '../data/stammNav.js';

const route = useRoute();
// Menü der Stammdaten (wie das Apps-Menü in Frappe): Klick auf das Symbol klappt die Bereiche auf
const stammOffen = ref(false);
const stammWurzel = ref(null);
onClickOutside(stammWurzel, () => { stammOffen.value = false; });
watch(() => route.path, () => { stammOffen.value = false; });
const punkte = [
  { id: 'workbench', label: 'Workbench', icon: Calculator, to: '/workbench' },
  { id: 'angebote', label: 'Angebote', icon: FileText, to: '/angebote' },
  { id: 'auftraege', label: 'Aufträge', icon: ClipboardList, to: '/auftraege' },
  { id: 'fertigung', label: 'Fertigung', icon: Factory, to: '/fertigung' },
  { id: 'anfragen', label: 'Lieferantenanfragen', icon: Send, to: '/anfragen' },
  { id: 'lieferscheine', label: 'Lieferscheine', icon: Truck, to: '/lieferscheine' },
  { id: 'lager', label: 'Lager', icon: Warehouse, to: '/lager' },
  { id: 'rechnungen', label: 'Rechnungen', icon: Receipt, to: '/rechnungen' },
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
    <div ref="stammWurzel" class="relative mt-auto">
      <button
        class="group relative grid h-11 w-11 place-items-center rounded-xl text-mute transition hover:bg-surface2 hover:text-ink"
        :class="route.meta.bereich === 'stammdaten' || stammOffen ? '!bg-accent-soft !text-accent' : ''"
        title="Stammdaten"
        aria-haspopup="menu"
        :aria-expanded="stammOffen"
        @click="stammOffen = !stammOffen"
      >
        <Database :size="20" :stroke-width="1.8" />
        <span v-if="route.meta.bereich === 'stammdaten'" class="absolute -left-[13px] h-5 w-1 rounded-r-full bg-accent" />
        <span v-if="!stammOffen" class="pointer-events-none absolute left-full z-20 ml-3 whitespace-nowrap rounded-lg bg-ink px-2 py-1 text-xs text-bg opacity-0 transition group-hover:opacity-100">Stammdaten</span>
      </button>
      <Transition name="pop">
        <div v-if="stammOffen" role="menu" class="card absolute bottom-0 left-full z-30 ml-3 w-72 p-2 shadow-2xl">
          <div class="px-3 pb-1.5 pt-2 text-[11px] font-medium uppercase tracking-wide text-mute">Stammdaten</div>
          <RouterLink
            v-for="p in STAMM_PUNKTE"
            :key="p.id"
            :to="p.to"
            role="menuitem"
            class="flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition hover:bg-surface2"
            :class="route.path === p.to ? 'bg-accent-soft text-accent' : ''"
          >
            <component :is="p.icon" :size="17" :stroke-width="1.8" class="shrink-0" />
            <span class="min-w-0"><span class="block font-medium">{{ p.label }}</span><span class="block truncate text-[11px] text-mute">{{ p.text }}</span></span>
          </RouterLink>
          <RouterLink to="/stammdaten" role="menuitem" class="mt-1 block rounded-xl border-t border-line px-3 pb-1.5 pt-2.5 text-xs text-accent hover:underline">Alle Stammdaten anzeigen</RouterLink>
        </div>
      </Transition>
    </div>
  </nav>
</template>
