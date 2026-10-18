<script setup>
// Eingabe einer Seriennummer: nur Ziffern, immer mit führenden Nullen in der Stellenzahl des Bauteils (0001, 0010).
import { computed } from 'vue';
import { formatNr } from '../lib/serien.js';

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  stellen: { type: Number, default: 4 },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
});
const emit = defineEmits(['update:modelValue']);

const text = computed(() => (props.modelValue === '' || props.modelValue === null ? '' : String(props.modelValue)));

// Beim Tippen fallen alle Zeichen außer Ziffern weg, mehr Stellen als erlaubt gibt es nicht
function eingabe(e) {
  const nur = e.target.value.replace(/\D/g, '').slice(0, props.stellen);
  if (e.target.value !== nur) e.target.value = nur;
  emit('update:modelValue', nur);
}
// Beim Verlassen wird auf die volle Stellenzahl aufgefüllt
function fertig(e) {
  const v = formatNr(e.target.value, props.stellen);
  e.target.value = v;
  emit('update:modelValue', v);
}
</script>

<template>
  <label class="block">
    <span v-if="label" class="label mb-1 block">{{ label }}</span>
    <input class="field tnum" inputmode="numeric" autocomplete="off" :placeholder="'0'.repeat(Math.max(0, stellen - 1)) + '1'" :maxlength="stellen" :value="text" @input="eingabe" @blur="fertig" />
    <span v-if="hint" class="mt-1 block text-[11px] text-mute">{{ hint }}</span>
  </label>
</template>
