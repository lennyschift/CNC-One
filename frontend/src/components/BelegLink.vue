<script setup>
// Link auf ein PDF (Angebot, Anhang): Klick öffnet es im Belegfenster von CNC One (ein festes Fenster, gern auf dem
// zweiten Bildschirm; ein weiterer Klick tauscht nur den Inhalt). Strg/Mittelklick öffnet wie gewohnt einen Tab.
// Sperrt der Browser das Fenster, erscheint das PDF hier im Programm.
import { ref } from 'vue';
import { X, ExternalLink, MonitorUp } from '@lucide/vue';
import { oeffnen } from '../lib/fenster.js';

defineOptions({ inheritAttrs: false }); // Klasse, Titel usw. gehören an den Link, nicht an die Vorschau
const props = defineProps({ url: { type: String, required: true }, name: { type: String, default: '' }, titel: { type: String, default: '' } });
const imProgramm = ref(false);

function klick(e) {
  if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
  e.preventDefault();
  if (!oeffnen('beleg', { url: props.url, name: props.name, titel: props.titel })) imProgramm.value = true;
}
function imFenster() {
  if (oeffnen('beleg', { url: props.url, name: props.name, titel: props.titel })) imProgramm.value = false;
}
</script>

<template>
  <a :title="`${name || 'PDF'} im Belegfenster öffnen (Strg+Klick: neuer Tab)`" v-bind="$attrs" :href="url" target="_blank" rel="noopener" @click="klick"><slot /></a>
  <Teleport v-if="imProgramm" to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-3" @mousedown.self="imProgramm = false">
      <div class="card flex h-[95vh] w-[min(1100px,98vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center gap-3 border-b border-line px-5 py-3">
          <div class="min-w-0 flex-1 truncate text-sm font-semibold">{{ [titel, name].filter(Boolean).join(' · ') || 'PDF' }}</div>
          <button class="btn !py-1 text-xs" title="Der Browser hat das Fenster gesperrt: Popups für CNC One erlauben, dann hier klicken" @click="imFenster"><MonitorUp :size="14" /> Eigenes Fenster</button>
          <a :href="url" target="_blank" rel="noopener" class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" title="In neuem Tab"><ExternalLink :size="16" /></a>
          <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="imProgramm = false"><X :size="18" /></button>
        </header>
        <iframe :src="url" class="min-h-0 flex-1 bg-white" :title="name || 'PDF'" />
      </div>
    </div>
  </Teleport>
</template>
