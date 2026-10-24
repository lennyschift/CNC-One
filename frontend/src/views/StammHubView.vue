<script setup>
// Übersicht der Stammdaten: eine Kachel je Bereich, wie das Apps-Menü in Frappe.
import { ArrowRight } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import { STAMM_PUNKTE } from '../data/stammNav.js';
import { stammdatenRoh } from '../data/repo.js';

const daten = stammdatenRoh();
const anzahl = (p) => (p.zaehler ? (daten[p.zaehler] ?? []).length : '');
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <StammNav />
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <RouterLink v-for="p in STAMM_PUNKTE" :key="p.id" :to="p.to" class="card group flex flex-col gap-3 p-5 transition hover:-translate-y-0.5 hover:border-accent/40">
        <div class="flex items-center justify-between">
          <span class="grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent"><component :is="p.icon" :size="22" :stroke-width="1.7" /></span>
          <span class="text-2xl font-semibold tnum">{{ anzahl(p) }}</span>
        </div>
        <div>
          <h2 class="font-semibold">{{ p.label }}</h2>
          <p class="mt-0.5 text-xs text-mute">{{ p.text }}</p>
        </div>
        <span class="mt-auto inline-flex items-center gap-1 text-xs text-accent opacity-0 transition group-hover:opacity-100">Öffnen <ArrowRight :size="12" /></span>
      </RouterLink>
    </div>
  </div>
</template>
