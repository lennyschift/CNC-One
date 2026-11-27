<script setup>
// Bauteilbilder im PDF eines Belegs ein/aus (Angebot und Auftragsbestätigung mit, Lieferschein und Rechnung ohne als
// Standard). Ein schon abgelegtes PDF (gesendetes Angebot, gelieferter Lieferschein) erzeugt der Server dabei neu; mit
// „PDF neu erzeugen“ geht das auch ohne Umschalten (z. B. für ältere Angebote, die ohne Bilder abgelegt wurden).
import { ref, watch } from 'vue';
import { Image as ImageIcon, RefreshCw, Loader } from '@lucide/vue';
import Toggle from './Toggle.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ doctype: { type: String, required: true }, belegId: { type: String, required: true } });
const emit = defineEmits(['geaendert']);
const ui = useUi();
const stand = ref(null); // { an, aenderbar, abgelegt, hinweis }
const arbeitet = ref(false);

async function laden() {
  try { stand.value = await call('cnc_one.api.belegdruck.bilder', { doctype: props.doctype, id: props.belegId }); } catch { stand.value = null; }
}
watch(() => [props.doctype, props.belegId], laden, { immediate: true });

async function setzen(werte) {
  arbeitet.value = true;
  try {
    stand.value = await call('cnc_one.api.belegdruck.bilder', { doctype: props.doctype, id: props.belegId, ...werte });
    emit('geaendert');
  } catch (e) { ui.toast(e.message, 'warn'); await laden(); } finally { arbeitet.value = false; }
}
const umschalten = (an) => setzen({ an: an ? 1 : 0 });
</script>

<template>
  <div v-if="stand" class="flex flex-wrap items-center gap-3 text-xs" :title="stand.hinweis">
    <span class="flex items-center gap-1.5" :class="stand.aenderbar ? '' : 'pointer-events-none opacity-50'">
      <ImageIcon :size="14" class="text-mute" />
      <Toggle :model-value="stand.an" klein label="Bauteilbilder" @update:model-value="umschalten" />
    </span>
    <button v-if="stand.abgelegt && stand.aenderbar" type="button" class="inline-flex items-center gap-1 text-mute hover:text-accent" :disabled="arbeitet" title="Das abgelegte PDF mit dem aktuellen Stand der Vorlage neu erzeugen (Inhalt bleibt gleich)" @click="setzen({ neu_erzeugen: 1 })">
      <Loader v-if="arbeitet" :size="13" class="animate-spin" /><RefreshCw v-else :size="13" /> PDF neu erzeugen
    </button>
    <Loader v-else-if="arbeitet" :size="13" class="animate-spin text-mute" />
  </div>
</template>
