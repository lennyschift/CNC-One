<script setup>
// Ein PDF vom Server ansehen (z. B. das Angebot, wie es verschickt wird), ohne es herunterzuladen.
import { defineAsyncComponent, ref, computed } from 'vue';
import { X, Download } from '@lucide/vue';
import BilderSchalter from './BilderSchalter.vue';

const DrawingViewer = defineAsyncComponent(() => import('./DrawingViewer.vue'));
// mit doctype und belegId: Schalter für die Bauteilbilder (z. B. Auftragsbestätigung)
const props = defineProps({ url: { type: String, required: true }, name: { type: String, default: '' }, doctype: { type: String, default: '' }, belegId: { type: String, default: '' } });
const neu = ref(0);
const adresse = computed(() => (neu.value ? `${props.url}${props.url.includes('?') ? '&' : '?'}b=${neu.value}` : props.url));
const emit = defineEmits(['schliessen']);
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <div class="card flex h-[92vh] w-[min(980px,96vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center gap-3 border-b border-line px-5 py-3">
          <h2 class="min-w-0 flex-1 truncate text-sm font-semibold">{{ name }}</h2>
          <BilderSchalter v-if="doctype && belegId" :doctype="doctype" :beleg-id="belegId" @geaendert="neu = Date.now()" />
          <a :href="adresse" :download="name" class="btn !py-1 text-xs"><Download :size="14" /> Herunterladen</a>
          <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
        </header>
        <div class="min-h-0 flex-1 p-3"><DrawingViewer :key="adresse" :url="adresse" :name="name" /></div>
      </div>
    </div>
  </Teleport>
</template>
