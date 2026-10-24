<script setup>
// Kopf aller Belege auf Papier (Angebot, Lieferschein, Rechnung, Mahnung): Firma mit Anschrift. Das Logo folgt unter Stammdaten > Firma.
defineProps({ firma: { type: Object, default: null } });
</script>

<template>
  <header class="flex items-start justify-between border-b-2 pb-5" style="border-color: #d4242a">
    <div>
      <div class="text-2xl font-bold uppercase tracking-wide" style="color: #d4242a">{{ firma?.firmenname || 'Firma' }}</div>
      <div class="text-[11px] uppercase tracking-[0.2em] text-neutral-500">CNC-Fertigung</div>
    </div>
    <div class="text-right text-[11px] text-neutral-500">
      <div v-for="z in firma?.adresse ?? []" :key="z">{{ z }}</div>
      <div v-if="firma?.telefon">Tel. {{ firma.telefon }}</div>
      <div v-if="firma?.email">{{ firma.email }}</div>
    </div>
  </header>
</template>
