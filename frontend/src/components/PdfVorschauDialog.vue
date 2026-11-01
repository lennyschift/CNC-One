<script setup>
// Ein PDF vom Server ansehen (z. B. das Angebot, wie es verschickt wird), ohne es herunterzuladen.
import { defineAsyncComponent } from 'vue';
import { X, Download } from '@lucide/vue';

const DrawingViewer = defineAsyncComponent(() => import('./DrawingViewer.vue'));
defineProps({ url: { type: String, required: true }, name: { type: String, default: '' } });
const emit = defineEmits(['schliessen']);
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <div class="card flex h-[92vh] w-[min(980px,96vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center gap-3 border-b border-line px-5 py-3">
          <h2 class="min-w-0 flex-1 truncate text-sm font-semibold">{{ name }}</h2>
          <a :href="url" :download="name" class="btn !py-1 text-xs"><Download :size="14" /> Herunterladen</a>
          <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
        </header>
        <div class="min-h-0 flex-1 p-3"><DrawingViewer :url="url" :name="name" /></div>
      </div>
    </div>
  </Teleport>
</template>
