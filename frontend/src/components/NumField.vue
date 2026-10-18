<script setup>
import { ref, watch } from 'vue';
import { parseDe, zahl } from '../lib/format.js';

const props = defineProps({
  modelValue: { type: [Number, String], default: 0 },
  label: { type: String, default: '' },
  unit: { type: String, default: '' },
  step: { type: Number, default: 1 },
  min: { type: Number, default: 0 },
  decimals: { type: Number, default: 2 },
  hint: { type: String, default: '' },
});
const emit = defineEmits(['update:modelValue']);

const text = ref(zahl(props.modelValue, props.decimals));
const fokus = ref(false);
const ungueltig = ref(false);

watch(() => props.modelValue, (v) => {
  if (!fokus.value) text.value = zahl(v, props.decimals);
});

function eingabe(e) {
  text.value = e.target.value;
  const n = parseDe(text.value);
  ungueltig.value = Number.isNaN(n);
  if (!ungueltig.value) emit('update:modelValue', Math.max(props.min, n));
}

function schritt(e) {
  if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
  e.preventDefault();
  const faktor = e.shiftKey ? 10 : e.altKey ? 0.1 : 1;
  const basis = Number.isNaN(parseDe(text.value)) ? 0 : parseDe(text.value);
  const n = Math.max(props.min, Math.round((basis + (e.key === 'ArrowUp' ? 1 : -1) * props.step * faktor) * 1e6) / 1e6);
  text.value = zahl(n, props.decimals);
  ungueltig.value = false;
  emit('update:modelValue', n);
}

function verlassen() {
  fokus.value = false;
  const n = parseDe(text.value);
  ungueltig.value = false;
  text.value = zahl(Number.isNaN(n) ? props.modelValue : n, props.decimals);
}
</script>

<template>
  <label class="block">
    <span v-if="label" class="label mb-1 flex items-center justify-between">
      <span>{{ label }}</span>
      <span v-if="hint" class="font-normal opacity-80">{{ hint }}</span>
    </span>
    <span class="relative block">
      <input
        :value="text"
        inputmode="decimal"
        class="field tnum"
        :class="[unit ? 'pr-10' : '', ungueltig ? '!border-accent' : '']"
        @input="eingabe"
        @keydown="schritt"
        @focus="(e) => { fokus = true; e.target.select(); }"
        @blur="verlassen"
      />
      <span v-if="unit" class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-mute">{{ unit }}</span>
    </span>
  </label>
</template>
