<script setup>
// Reiter im Bereich Rechnungen: Rechnungen (mit offenen Posten) und Mahnwesen.
import { useRoute } from 'vue-router';
import { Receipt, BellRing } from '@lucide/vue';

const route = useRoute();
const punkte = [
  { to: '/rechnungen', label: 'Rechnungen', icon: Receipt, bereich: 'rechnungen' },
  { to: '/mahnwesen', label: 'Mahnwesen', icon: BellRing, bereich: 'mahnwesen' },
];
</script>

<template>
  <nav class="mb-5 flex gap-1 rounded-xl border border-line bg-surface p-1">
    <RouterLink v-for="p in punkte" :key="p.to" :to="p.to" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="route.meta.unterbereich === p.bereich ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'">
      <component :is="p.icon" :size="15" /> {{ p.label }}
    </RouterLink>
  </nav>
</template>
