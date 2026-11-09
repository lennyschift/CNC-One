<script setup>
// Projektname (intern) und Ansprechpartner im Detail von Angebot und Auftrag; das Projekt lässt sich hier ändern
import { ref, watch } from 'vue';
import { FolderKanban, UserRound, Pencil, Check, X } from '@lucide/vue';

const props = defineProps({
  projekt: { type: String, default: '' },
  kontaktName: { type: String, default: '' },
  kontaktEmail: { type: String, default: '' },
});
const emit = defineEmits(['speichern']);
const bearbeiten = ref(false);
const wert = ref(props.projekt);
watch(() => props.projekt, (v) => { wert.value = v; });

function fertig() {
  bearbeiten.value = false;
  if (wert.value.trim() !== props.projekt) emit('speichern', wert.value.trim());
}
function abbrechen() {
  bearbeiten.value = false;
  wert.value = props.projekt;
}
</script>

<template>
  <div class="space-y-2 text-sm">
    <div class="flex items-center gap-2 rounded-xl bg-surface2 px-3 py-2">
      <FolderKanban :size="15" class="shrink-0 text-accent" />
      <template v-if="bearbeiten">
        <input v-model="wert" class="field !py-1 text-sm" placeholder="Projektname" autofocus @keydown.enter="fertig" @keydown.esc="abbrechen" />
        <button class="text-ok" title="Übernehmen" @click="fertig"><Check :size="16" /></button>
        <button class="text-mute hover:text-ink" title="Abbrechen" @click="abbrechen"><X :size="16" /></button>
      </template>
      <template v-else>
        <span class="min-w-0 flex-1 truncate" :class="projekt ? 'font-medium' : 'text-mute'">{{ projekt || 'Kein Projekt' }}</span>
        <button class="text-mute hover:text-ink" title="Projekt ändern (nur intern, steht nicht auf den Belegen)" @click="bearbeiten = true"><Pencil :size="13" /></button>
      </template>
    </div>
    <div v-if="kontaktName || kontaktEmail" class="flex items-start gap-2 rounded-xl bg-surface2 px-3 py-2">
      <UserRound :size="15" class="mt-0.5 shrink-0 text-mute" />
      <div class="min-w-0"><div class="truncate">{{ kontaktName || kontaktEmail }}</div><div v-if="kontaktName && kontaktEmail" class="truncate text-xs text-mute">{{ kontaktEmail }}</div></div>
    </div>
  </div>
</template>
