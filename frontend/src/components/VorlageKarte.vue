<script setup>
// Eine Vorlage für Arbeitsgänge. Änderungen werden kurz nach dem Tippen automatisch in Frappe gespeichert.
import { ref, watch, onBeforeUnmount } from 'vue';
import { Trash2, Copy, Check, Loader } from '@lucide/vue';
import ArbeitsplanEditor from './ArbeitsplanEditor.vue';
import { useStamm } from '../stores/stamm.js';

const props = defineProps({ vorlage: { type: Object, required: true }, kunden: { type: Array, default: () => [] } });
const emit = defineEmits(['kopieren', 'loeschen']);
const stamm = useStamm();

const stand = ref('gespeichert');
let timer = 0;
let laeuft = false;
let nochmal = false;

async function speichern() {
  if (laeuft) { nochmal = true; return; }
  laeuft = true;
  stand.value = 'speichert';
  await stamm.vorlageSpeichern(props.vorlage);
  laeuft = false;
  if (nochmal) { nochmal = false; speichern(); return; }
  stand.value = 'gespeichert';
}

watch(() => props.vorlage, () => {
  stand.value = 'offen';
  clearTimeout(timer);
  timer = setTimeout(speichern, 800);
}, { deep: true });

onBeforeUnmount(() => { clearTimeout(timer); if (stand.value === 'offen') speichern(); });
</script>

<template>
  <article class="card p-5">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <input v-model="vorlage.name" class="min-w-[200px] flex-1 bg-transparent text-base font-semibold outline-none" placeholder="Name der Vorlage" />
      <span class="inline-flex items-center gap-1 text-xs text-mute">
        <Loader v-if="stand !== 'gespeichert'" :size="13" class="animate-spin" /><Check v-else :size="13" class="text-ok" />
        {{ stand === 'gespeichert' ? 'Gespeichert' : 'Speichert …' }}
      </span>
      <select v-model="vorlage.kundeId" class="field !w-auto"><option value="">Für alle Kunden</option><option v-for="k in kunden" :key="k.id" :value="k.id">{{ k.name }}</option></select>
      <button class="btn" title="Vorlage kopieren" @click="emit('kopieren', vorlage)"><Copy :size="15" /></button>
      <button class="btn !text-mute hover:!text-accent" title="Vorlage löschen" @click="emit('loeschen', vorlage)"><Trash2 :size="15" /></button>
    </div>
    <ArbeitsplanEditor :arbeitsgaenge="vorlage.arbeitsgaenge" ohne-bauteil />
  </article>
</template>
