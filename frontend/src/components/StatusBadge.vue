<script setup>
import { computed } from 'vue';

const props = defineProps({ status: { type: String, required: true } });
const farbe = computed(() => ({
  Entwurf: 'var(--mute)',
  Gesendet: 'var(--warn)',
  'Teilweise bestellt': 'var(--ok)',
  Bestellt: 'var(--ok)',
  Abgelehnt: 'var(--accent)',
  Offen: 'var(--warn)',
  'In Fertigung': 'var(--warn)',
  Fertig: 'var(--ok)',
  Läuft: 'var(--warn)',
  'Angebot erhalten': 'var(--ok)',
  Abgesagt: 'var(--mute)',
  Bereit: 'var(--warn)',
  Geliefert: 'var(--ok)',
  Storniert: 'var(--mute)',
  'Nicht geliefert': 'var(--mute)',
  'Teilweise geliefert': 'var(--warn)',
}[props.status] ?? 'var(--mute)'));
</script>

<template>
  <span class="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface2 px-2.5 py-0.5 text-xs font-medium">
    <span class="h-1.5 w-1.5 rounded-full" :style="{ background: farbe }" />{{ status }}
  </span>
</template>
