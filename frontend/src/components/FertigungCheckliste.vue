<script setup>
// Checkliste vor dem Fertigungsstart je Fertigungsbauteil: feste Punkte aus den Stammdaten (Material, Werkzeug,
// Messmittel …) abhaken, mit Notiz; eigene Punkte nur für dieses Bauteil. Pflichtpunkte müssen vor dem Start erledigt sein.
import { ref, computed } from 'vue';
import { ListChecks, Check, Plus, Trash2, AlertTriangle, Settings2, StickyNote } from '@lucide/vue';
import Toggle from './Toggle.vue';
import { useFertigung } from '../stores/fertigung.js';
import { checkOffen, checkStand } from '../lib/fertigung.js';

const props = defineProps({
  fb: { type: Object, required: true },
  kompakt: Boolean, // im Start-Dialog: ohne Kopf und ohne eigene Punkte
});
const f = useFertigung();
const offen = computed(() => checkOffen(props.fb));
const stand = computed(() => checkStand(props.fb));
const notizOffen = ref({});
const neu = ref('');
const neuPflicht = ref(true);
const arbeitet = ref('');

async function umschalten(p) {
  arbeitet.value = p.id;
  await f.checkSetzen(props.fb.id, p.id, { erledigt: p.erledigt ? 0 : 1 });
  arbeitet.value = '';
}
function notizSpeichern(p, wert) {
  if ((wert ?? '') !== (p.notiz ?? '')) f.checkSetzen(props.fb.id, p.id, { notiz: wert });
}
async function eigenDazu() {
  if (!neu.value.trim()) return;
  await f.checkEigen(props.fb.id, neu.value.trim(), neuPflicht.value);
  neu.value = '';
}
const wann = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');
</script>

<template>
  <section :class="kompakt ? '' : 'card p-5'">
    <div v-if="!kompakt" class="mb-3 flex items-center gap-2">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><ListChecks :size="16" class="text-accent" /> Checkliste vor dem Start</h3>
      <span class="ml-auto rounded-full px-2 py-0.5 text-xs font-medium tnum" :class="offen.length ? 'bg-warn/10 text-warn' : 'bg-ok/10 text-ok'">{{ stand.erledigt }} / {{ stand.alle }}</span>
      <RouterLink to="/stammdaten/checkliste" class="text-mute hover:text-accent" title="Feste Punkte in den Stammdaten ändern"><Settings2 :size="14" /></RouterLink>
    </div>
    <p v-if="!kompakt && fb.checklisteTrotzdem" class="mb-3 flex items-start gap-1.5 rounded-lg bg-warn/10 px-2.5 py-1.5 text-xs text-warn"><AlertTriangle :size="13" class="mt-0.5 shrink-0" /> Ohne vollständige Checkliste gestartet: {{ fb.checklisteTrotzdem }}</p>

    <ul class="space-y-1.5">
      <li v-for="p in fb.checkliste" :key="p.id" class="rounded-xl border px-3 py-2 transition" :class="p.erledigt ? 'border-ok/30 bg-ok/5' : p.pflicht ? 'border-line' : 'border-line/60'">
        <div class="flex items-start gap-2.5">
          <button type="button" class="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md border-2 transition" :class="p.erledigt ? 'border-ok bg-ok text-white' : 'border-line hover:border-accent'" :disabled="arbeitet === p.id" :aria-checked="p.erledigt" role="checkbox" :title="p.erledigt ? 'Wieder öffnen' : 'Abhaken'" @click="umschalten(p)">
            <Check v-if="p.erledigt" :size="13" :stroke-width="3" />
          </button>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-x-2 text-sm">
              <span class="font-medium" :class="p.erledigt ? 'text-mute line-through decoration-1' : ''">{{ p.text }}</span>
              <span v-if="p.pflicht && !p.erledigt" class="rounded-full bg-accent-soft px-1.5 text-[10px] font-medium text-accent">Pflicht</span>
              <span v-if="p.eigen" class="rounded-full bg-surface2 px-1.5 text-[10px] text-mute">nur hier</span>
            </div>
            <div v-if="p.hinweis && !p.erledigt" class="text-xs text-mute">{{ p.hinweis }}</div>
            <div v-if="p.erledigt" class="text-[11px] text-mute">{{ p.von }} · {{ wann(p.am) }}</div>
            <div v-if="p.notiz && !notizOffen[p.id]" class="mt-0.5 text-xs">{{ p.notiz }}</div>
            <input v-if="notizOffen[p.id]" :value="p.notiz" class="field mt-1 !py-1 text-xs" placeholder="Notiz, z. B. Charge, Werkzeug-Nr., Lagerplatz" autofocus @blur="notizSpeichern(p, $event.target.value); notizOffen[p.id] = false" @keydown.enter="$event.target.blur()" />
          </div>
          <button type="button" class="text-mute hover:text-accent" title="Notiz" @click="notizOffen[p.id] = true"><StickyNote :size="14" /></button>
          <button v-if="p.eigen && !kompakt" type="button" class="text-mute hover:text-accent" title="Punkt entfernen" @click="f.checkWeg(fb.id, p.id)"><Trash2 :size="14" /></button>
        </div>
      </li>
    </ul>
    <p v-if="!fb.checkliste?.length" class="py-2 text-center text-xs text-mute">Keine Punkte. Feste Punkte legen Sie in den Stammdaten an.</p>

    <form v-if="!kompakt" class="mt-3 flex flex-wrap items-center gap-2" @submit.prevent="eigenDazu">
      <input v-model="neu" class="field min-w-0 basis-full !py-1.5 text-sm" placeholder="Eigener Punkt, z. B. Prüfvorrichtung vom Kunden" />
      <Toggle v-model="neuPflicht" klein label="Pflicht" />
      <button class="btn ml-auto !py-1.5 text-sm" :disabled="!neu.trim()"><Plus :size="14" /> Dazu</button>
    </form>
  </section>
</template>
