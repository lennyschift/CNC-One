<script setup>
// Rahmen für das Bearbeiten eines Stammdaten-Eintrags: Kopf, Inhalt, Fußzeile mit Löschen, Abbrechen und Speichern.
import { ref, onMounted, nextTick } from 'vue';
import { X, Trash2, Save, Loader } from '@lucide/vue';

defineProps({
  titel: { type: String, required: true },
  untertitel: { type: String, default: '' },
  breite: { type: String, default: '640px' },
  neu: { type: Boolean, default: false },
  schreibgeschuetzt: { type: Boolean, default: false },
  speichert: { type: Boolean, default: false },
  gueltig: { type: Boolean, default: true },
  speichernText: { type: String, default: 'Speichern' },
});
const emit = defineEmits(['schliessen', 'speichern', 'loeschen']);
const wurzel = ref(null);
onMounted(() => nextTick(() => wurzel.value?.querySelector('input:not([disabled]):not([type=radio]):not([type=checkbox]), textarea:not([disabled])')?.focus()));
// Löschen braucht eine zweite Bestätigung
const frage = ref(false);
function loeschen() {
  if (!frage.value) { frage.value = true; setTimeout(() => { frage.value = false; }, 4000); return; }
  emit('loeschen');
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <form ref="wurzel" class="card flex max-h-[92vh] flex-col overflow-hidden shadow-2xl" :style="{ width: `min(${breite}, 96vw)` }" @submit.prevent="emit('speichern')">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div><h2 class="text-base font-semibold">{{ titel }}</h2><p v-if="untertitel" class="text-xs text-mute">{{ untertitel }}</p></div>
            <button type="button" class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>
          <div class="min-h-0 flex-1 space-y-4 overflow-auto px-6 py-5"><slot /></div>
          <footer class="flex items-center gap-2 border-t border-line bg-surface2 px-6 py-4">
            <button v-if="!neu && !schreibgeschuetzt" type="button" class="btn" :class="frage ? '!border-accent !bg-accent-soft !text-accent' : '!text-mute'" @click="loeschen"><Trash2 :size="15" /> {{ frage ? 'Wirklich löschen?' : 'Löschen' }}</button>
            <span class="ml-auto" />
            <button type="button" class="btn" @click="emit('schliessen')">{{ schreibgeschuetzt ? 'Schließen' : 'Abbrechen' }}</button>
            <button v-if="!schreibgeschuetzt" type="submit" class="btn btn-primary" :disabled="!gueltig || speichert" :class="!gueltig || speichert ? 'pointer-events-none opacity-40' : ''">
              <Loader v-if="speichert" :size="15" class="animate-spin" /><Save v-else :size="15" /> {{ speichernText }}
            </button>
          </footer>
        </form>
      </Transition>
    </div>
  </Teleport>
</template>
