<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';

const props = defineProps({
  value: { type: Number, default: 0 },
  format: { type: Function, default: (v) => String(v) },
  dauer: { type: Number, default: 420 },
});

const angezeigt = ref(props.value);
let raf = 0;

watch(() => props.value, (ziel) => {
  cancelAnimationFrame(raf);
  const start = angezeigt.value;
  if (start === ziel) return;
  const t0 = performance.now();
  const schritt = (jetzt) => {
    const t = Math.min(1, (jetzt - t0) / props.dauer);
    const e = 1 - Math.pow(1 - t, 3);
    angezeigt.value = start + (ziel - start) * e;
    if (t < 1) raf = requestAnimationFrame(schritt);
    else angezeigt.value = ziel;
  };
  raf = requestAnimationFrame(schritt);
});

onBeforeUnmount(() => cancelAnimationFrame(raf));
</script>

<template>
  <span class="tnum">{{ format(angezeigt) }}</span>
</template>
