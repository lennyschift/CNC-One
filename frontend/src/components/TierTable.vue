<script setup>
import { computed } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, X } from '@lucide/vue';
import NumField from './NumField.vue';
import { eur } from '../lib/format.js';

const props = defineProps({ teil: { type: Object, required: true }, ergebnis: { type: Object, required: true } });

const stufen = computed(() => props.teil.staffel.stufen);
const kleinste = computed(() => Math.min(...stufen.value.map((s) => Math.floor(Number(s.menge)) || Infinity)));

function werte(s) {
  return props.ergebnis.stufen.find((r) => r.menge === Math.floor(Number(s.menge)) && r.extra === Number(s.extra)) ?? null;
}
function hinzu() {
  const letzte = Math.max(0, ...stufen.value.map((s) => Number(s.menge) || 0));
  stufen.value.push({ menge: letzte ? letzte * 2 : 5, extra: 0 });
}
function weg(i) {
  if (stufen.value.length > 1) stufen.value.splice(i, 1);
}
</script>

<template>
  <div>
    <div class="grid grid-cols-[1fr_1fr_1fr_1fr_28px] items-center gap-2 px-1 pb-1.5">
      <span class="label">Menge</span><span class="label">Aufschlag / Stk</span><span class="label text-right">Stückpreis</span><span class="label text-right">Gesamt</span><span />
    </div>
    <div v-auto-animate class="space-y-2">
      <div v-for="(s, i) in stufen" :key="i" class="grid grid-cols-[1fr_1fr_1fr_1fr_28px] items-center gap-2">
        <NumField v-model="s.menge" :decimals="0" :min="1" />
        <NumField v-model="s.extra" unit="€" />
        <div class="text-right text-sm tnum">{{ werte(s) ? eur(werte(s).stueckpreis) : '–' }}</div>
        <div class="text-right text-sm font-medium tnum">
          {{ werte(s) ? eur(werte(s).gesamt) : '–' }}
          <div v-if="Math.floor(Number(s.menge)) === kleinste" class="text-[10px] font-normal text-accent">zählt für Summe</div>
        </div>
        <button class="grid h-7 w-7 place-items-center rounded-lg text-mute transition hover:bg-accent-soft hover:text-accent disabled:opacity-30" :disabled="stufen.length <= 1" title="Staffel entfernen" @click="weg(i)">
          <X :size="15" />
        </button>
      </div>
    </div>
    <button class="btn mt-3" @click="hinzu"><Plus :size="15" /> Staffel</button>
  </div>
</template>
