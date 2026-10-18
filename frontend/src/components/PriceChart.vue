<script setup>
import { computed, ref } from 'vue';
import { stueckpreisBei, gueltigeStufen } from '../lib/calc.js';
import { eur } from '../lib/format.js';

const props = defineProps({ teil: { type: Object, required: true } });

const W = 380, H = 160, PL = 46, PR = 14, PT = 14, PB = 26;

const stufen = computed(() => (props.teil.staffel?.aktiv ? gueltigeStufen(props.teil) : []));
const maxMenge = computed(() => Math.max(20, Math.max(props.teil.menge || 1, ...stufen.value.map((s) => s.menge)) * 2));
const lnMax = computed(() => Math.log(maxMenge.value));
const x = (q) => PL + (Math.log(Math.max(1, q)) / lnMax.value) * (W - PL - PR);
const qVon = (px) => Math.exp(((px - PL) / (W - PL - PR)) * lnMax.value);

const punkte = computed(() => Array.from({ length: 56 }, (_, i) => {
  const q = Math.exp((lnMax.value * i) / 55);
  return { q, p: stueckpreisBei(props.teil, q) };
}));
const maxP = computed(() => Math.max(0.01, punkte.value[0].p));
const y = (p) => PT + (1 - p / maxP.value) * (H - PT - PB);

const linie = computed(() => punkte.value.map((pt, i) => `${i ? 'L' : 'M'}${x(pt.q).toFixed(1)} ${y(pt.p).toFixed(1)}`).join(' '));
const flaeche = computed(() => `${linie.value} L${x(maxMenge.value).toFixed(1)} ${H - PB} L${x(1).toFixed(1)} ${H - PB} Z`);

const marker = computed(() => {
  const liste = stufen.value.length ? stufen.value.map((s) => s.menge) : [Math.max(1, Math.floor(props.teil.menge || 1))];
  return liste.map((q) => ({ q, p: stueckpreisBei(props.teil, q) + (stufen.value.find((s) => s.menge === q)?.extra ?? 0) }));
});

const ticks = computed(() => [1, 10, 100, 1000, 10000].filter((t) => t <= maxMenge.value));

const hover = ref(null);
function bewegen(e) {
  const r = e.currentTarget.getBoundingClientRect();
  const px = ((e.clientX - r.left) / r.width) * W;
  if (px < PL || px > W - PR) { hover.value = null; return; }
  const q = Math.max(1, Math.round(qVon(px)));
  hover.value = { q, p: stueckpreisBei(props.teil, q) };
}
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" class="w-full select-none" @pointermove="bewegen" @pointerleave="hover = null">
    <defs>
      <linearGradient id="verlauf" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.22" />
        <stop offset="100%" stop-color="var(--accent)" stop-opacity="0" />
      </linearGradient>
    </defs>
    <line v-for="t in ticks" :key="t" :x1="x(t)" :x2="x(t)" :y1="PT" :y2="H - PB" stroke="var(--line)" stroke-dasharray="2 4" />
    <text v-for="t in ticks" :key="'l' + t" :x="x(t)" :y="H - 8" text-anchor="middle" font-size="10" fill="var(--mute)">{{ t }}</text>
    <text :x="PL - 8" :y="PT + 8" text-anchor="end" font-size="10" fill="var(--mute)">{{ eur(maxP) }}</text>
    <text :x="PL - 8" :y="H - PB" text-anchor="end" font-size="10" fill="var(--mute)">0</text>
    <path :d="flaeche" fill="url(#verlauf)" />
    <path :d="linie" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    <g v-for="m in marker" :key="m.q">
      <line :x1="x(m.q)" :x2="x(m.q)" :y1="y(m.p)" :y2="H - PB" stroke="var(--accent)" stroke-opacity="0.35" stroke-dasharray="3 3" />
      <circle :cx="x(m.q)" :cy="y(m.p)" r="4.5" fill="var(--surface)" stroke="var(--accent)" stroke-width="2" />
    </g>
    <g v-if="hover" pointer-events="none">
      <line :x1="x(hover.q)" :x2="x(hover.q)" :y1="PT" :y2="H - PB" stroke="var(--ink)" stroke-opacity="0.25" />
      <circle :cx="x(hover.q)" :cy="y(hover.p)" r="3.5" fill="var(--ink)" />
      <rect :x="Math.min(x(hover.q) + 8, W - 118)" :y="PT" width="108" height="34" rx="8" fill="var(--ink)" />
      <text :x="Math.min(x(hover.q) + 8, W - 118) + 10" :y="PT + 14" font-size="10" fill="var(--bg)">{{ hover.q }} Stück</text>
      <text :x="Math.min(x(hover.q) + 8, W - 118) + 10" :y="PT + 27" font-size="11" font-weight="600" fill="var(--bg)">{{ eur(hover.p) }} / Stk</text>
    </g>
  </svg>
</template>
