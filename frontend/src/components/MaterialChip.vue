<script setup>
// Materialstand eines Fertigungsbauteils als kleiner Chip (Board, Liste, Kalender): im Lager, reserviert, teilweise,
// fehlt (noch nicht geliefert) oder entnommen. Fertige Bauteile zeigen nichts.
import { computed } from 'vue';
import { Layers } from '@lucide/vue';
import { MATERIAL } from '../lib/fertigung.js';

const props = defineProps({ fb: { type: Object, required: true }, klein: Boolean });
const st = computed(() => (props.fb.status === 'Fertig' || !props.fb.roh ? null : MATERIAL[props.fb.roh.status] ?? null));
</script>

<template>
  <span v-if="st" class="inline-flex max-w-full items-center gap-1 truncate rounded-md font-medium" :class="[st.klasse, klein ? 'px-1 py-px text-[9px]' : 'px-1.5 py-0.5 text-[10px]']" :title="fb.roh.text">
    <Layers :size="klein ? 9 : 11" class="shrink-0" />{{ klein ? st.kurz.replace('Material ', '') : st.kurz }}
  </span>
</template>
