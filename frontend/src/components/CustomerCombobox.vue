<script setup>
import { ref, computed, onMounted } from 'vue';
import { onClickOutside } from '@vueuse/core';
import { ChevronsUpDown, Check, Building2 } from '@lucide/vue';
import { repo } from '../data/repo.js';

const model = defineModel({ type: String, default: '' });
const emit = defineEmits(['gewaehlt']);

const kunden = ref([]);
const offen = ref(false);
const suche = ref('');
const index = ref(0);
const wurzel = ref(null);
const eingabe = ref(null);

onMounted(async () => { kunden.value = await repo.kunden.liste(); });
onClickOutside(wurzel, () => { offen.value = false; });

const gewaehlt = computed(() => kunden.value.find((k) => k.id === model.value) ?? null);
const treffer = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return q ? kunden.value.filter((k) => k.name.toLowerCase().includes(q) || k.id.toLowerCase().includes(q)) : kunden.value;
});

function oeffnen() {
  offen.value = true;
  suche.value = '';
  index.value = 0;
  setTimeout(() => eingabe.value?.focus(), 0);
}
function waehlen(k) {
  model.value = k.id;
  emit('gewaehlt', k);
  offen.value = false;
}
function taste(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); index.value = Math.min(index.value + 1, treffer.value.length - 1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); index.value = Math.max(index.value - 1, 0); }
  else if (e.key === 'Enter') { e.preventDefault(); if (treffer.value[index.value]) waehlen(treffer.value[index.value]); }
  else if (e.key === 'Escape') offen.value = false;
}
defineExpose({ oeffnen, gewaehltes: gewaehlt });
</script>

<template>
  <div ref="wurzel" class="relative">
    <span class="label mb-1 block">Kunde</span>
    <button type="button" class="field flex items-center gap-2 text-left" @click="oeffnen">
      <Building2 :size="16" class="shrink-0 text-mute" />
      <span class="flex-1 truncate" :class="gewaehlt ? '' : 'text-mute'">{{ gewaehlt?.name ?? 'Kunde wählen …' }}</span>
      <ChevronsUpDown :size="15" class="shrink-0 text-mute" />
    </button>
    <Transition name="pop">
      <div v-if="offen" class="card absolute left-0 right-0 z-30 mt-2 overflow-hidden shadow-xl">
        <input ref="eingabe" v-model="suche" class="w-full border-b border-line bg-transparent px-3.5 py-2.5 text-sm outline-none placeholder:text-mute" placeholder="Suchen …" @keydown="taste" @input="index = 0" />
        <ul class="max-h-64 overflow-auto p-1.5">
          <li v-for="(k, i) in treffer" :key="k.id">
            <button class="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm" :class="i === index ? 'bg-accent-soft' : 'hover:bg-surface2'" @mousemove="index = i" @click="waehlen(k)">
              <span class="flex-1 truncate">{{ k.name }}</span>
              <span class="text-xs text-mute">{{ k.id }}</span>
              <Check v-if="k.id === model" :size="14" class="text-accent" />
            </button>
          </li>
          <li v-if="!treffer.length" class="px-3 py-4 text-center text-sm text-mute">Kein Kunde gefunden</li>
        </ul>
      </div>
    </Transition>
  </div>
</template>
