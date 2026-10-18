<script setup>
// Reiter durch alle Stammdaten-Bereiche, oben auf jeder Stammdaten-Seite.
import { useRoute } from 'vue-router';
import { LayoutGrid } from '@lucide/vue';
import { STAMM_PUNKTE } from '../data/stammNav.js';

const route = useRoute();
</script>

<template>
  <nav class="mb-5 flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
    <RouterLink to="/stammdaten" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="route.path === '/stammdaten' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'"><LayoutGrid :size="15" /> Übersicht</RouterLink>
    <RouterLink v-for="p in STAMM_PUNKTE" :key="p.id" :to="p.to" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="route.path === p.to ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'">
      <component :is="p.icon" :size="15" /> {{ p.label }}
    </RouterLink>
  </nav>
</template>
