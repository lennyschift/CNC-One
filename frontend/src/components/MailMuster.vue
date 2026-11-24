<script setup>
// Vorschau der Anfrage-Mail, bevor die Anfrage angelegt ist: Betreff, Text und Tabelle genau wie beim Senden (vom Server,
// cnc_one.api.anfrage.mail_muster). Wird kurz nach jeder Änderung neu geholt.
import { ref, watch, onBeforeUnmount } from 'vue';
import { Mail, Loader } from '@lucide/vue';
import MailHtml from './MailHtml.vue';
import { call } from '../data/api.js';

const props = defineProps({
  art: { type: String, default: 'Material' },
  notiz: { type: String, default: '' },
  positionen: { type: Array, required: true }, // wie beim Anlegen: [{ teil: { name, material }, agName, abmessung, einheit, mengen }]
  vorgang: { type: String, default: '' }, // beim Ändern: die bisherige Anfrage
  leerText: { type: String, default: 'Bitte eine Bezeichnung und eine Menge eintragen.' },
});
const vorschau = ref(null);
const laedt = ref(false);
let zeitgeber = null;
let nr = 0;
watch(() => JSON.stringify([props.art, props.notiz, props.positionen, props.vorgang]), () => {
  clearTimeout(zeitgeber);
  if (!props.positionen.length) { vorschau.value = null; return; }
  zeitgeber = setTimeout(async () => {
    const meins = ++nr;
    laedt.value = true;
    try {
      const v = await call('cnc_one.api.anfrage.mail_muster', { art: props.art, notiz: props.notiz, positionen: JSON.parse(JSON.stringify(props.positionen)), vorgang: props.vorgang });
      if (meins === nr) vorschau.value = v;
    } catch { /* nur eine Hilfe */ } finally { if (meins === nr) laedt.value = false; }
  }, vorschau.value ? 350 : 0);
}, { immediate: true });
onBeforeUnmount(() => clearTimeout(zeitgeber));
</script>

<template>
  <div class="min-w-0">
    <div class="label mb-2 flex items-center gap-1.5"><Mail :size="13" /> So sieht die Mail aus <span class="normal-case tracking-normal">(Text im nächsten Schritt änderbar)</span><Loader v-if="laedt" :size="12" class="animate-spin" /></div>
    <div class="rounded-xl border border-line bg-white p-4">
      <template v-if="vorschau && positionen.length">
        <div class="mb-3 border-b border-[#e5e5e5] pb-2 text-[13px]"><span class="text-[#777]">Betreff: </span><span class="font-medium text-[#1c1c1c]">{{ vorschau.betreff }}</span></div>
        <MailHtml :html="vorschau.html" />
      </template>
      <p v-else class="text-sm text-[#777]">{{ positionen.length ? 'Vorschau wird erstellt …' : leerText }}</p>
    </div>
  </div>
</template>
