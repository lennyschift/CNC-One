<script setup>
// Feste Punkte der Checkliste vor dem Fertigungsstart (Material, Werkzeug, Messmittel …). Sie gelten für jedes
// Fertigungsbauteil; je Bauteil lassen sich eigene Punkte ergänzen. Pflichtpunkte müssen vor dem Start abgehakt sein.
import { ref, computed, onMounted } from 'vue';
import { Check, Plus, Trash2, ChevronUp, ChevronDown, RotateCcw, ClipboardCheck } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import Toggle from '../components/Toggle.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';
import { useFertigung } from '../stores/fertigung.js';

const ui = useUi();
const f = useFertigung();
const punkte = ref([]);
const standard = ref([]);
const darf = ref(false);
const speichert = ref(false);
const gespeichert = ref('');
const geaendert = computed(() => JSON.stringify(punkte.value) !== gespeichert.value);

function setzen(l) { punkte.value = l.map((p) => ({ ...p })); gespeichert.value = JSON.stringify(punkte.value); }
onMounted(async () => {
  try {
    const r = await call('cnc_one.api.fertigung.vorlage_checkliste');
    setzen(r.punkte);
    standard.value = r.standard;
    darf.value = r.darf;
  } catch (e) { ui.toast(e.message, 'warn'); }
});

function dazu() { punkte.value.push({ id: `p-${Date.now().toString(36)}`, text: '', hinweis: '', pflicht: true, aktiv: true }); }
function schieben(i, r) {
  const j = i + r;
  if (j < 0 || j >= punkte.value.length) return;
  const l = punkte.value;
  [l[i], l[j]] = [l[j], l[i]];
}
function standardDazu() {
  const da = new Set(punkte.value.map((p) => p.id));
  const fehlen = standard.value.filter((p) => !da.has(p.id));
  punkte.value.push(...fehlen.map((p) => ({ ...p })));
  ui.toast(fehlen.length ? `${fehlen.length} Standardpunkte ergänzt` : 'Alle Standardpunkte sind schon da');
}
async function speichern() {
  speichert.value = true;
  try {
    const r = await call('cnc_one.api.fertigung.vorlage_checkliste_speichern', { punkte: punkte.value });
    setzen(r.punkte);
    await f.neuLaden(); // die offenen Fertigungsbauteile zeigen die neuen Punkte
    ui.toast('Checkliste gespeichert', 'ok');
  } catch (e) { ui.toast(e.message, 'warn'); } finally { speichert.value = false; }
}
</script>

<template>
  <div class="mx-auto max-w-[1000px]">
    <StammNav />
    <p class="mb-4 text-sm text-mute">
      Diese Punkte stehen auf jeder Fertigungskarte. Pflichtpunkte müssen abgehakt sein, bevor ein Bauteil in Fertigung geht
      (Status, Board oder erste Buchung). Wer trotzdem startet, wird am Bauteil vermerkt. Eigene Punkte lassen sich je Bauteil ergänzen.
      Abgeschaltete Punkte verschwinden von den Karten, außer sie sind dort schon abgehakt.
    </p>
    <section class="card overflow-hidden">
      <div v-for="(p, i) in punkte" :key="p.id" class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-0" :class="p.aktiv ? '' : 'opacity-60'">
        <ClipboardCheck :size="16" class="shrink-0 text-accent" />
        <input v-model="p.text" class="field !w-52 !py-1.5 text-sm font-medium" placeholder="z. B. Werkzeug" :disabled="!darf" />
        <input v-model="p.hinweis" class="field min-w-[180px] flex-1 !py-1.5 text-xs" placeholder="Hinweis, was zu prüfen ist" :disabled="!darf" />
        <Toggle v-model="p.pflicht" klein label="Pflicht vor Start" :class="darf ? '' : 'pointer-events-none'" />
        <Toggle v-model="p.aktiv" klein label="aktiv" :class="darf ? '' : 'pointer-events-none'" />
        <div v-if="darf" class="flex">
          <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2" title="Nach oben" @click="schieben(i, -1)"><ChevronUp :size="15" /></button>
          <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2" title="Nach unten" @click="schieben(i, 1)"><ChevronDown :size="15" /></button>
          <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:text-accent" title="Punkt entfernen" @click="punkte.splice(i, 1)"><Trash2 :size="15" /></button>
        </div>
      </div>
      <p v-if="!punkte.length" class="px-4 py-8 text-center text-sm text-mute">Keine festen Punkte, die Fertigung startet ohne Checkliste.</p>
    </section>
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <template v-if="darf">
        <button class="btn" @click="dazu"><Plus :size="15" /> Punkt hinzufügen</button>
        <button class="btn" title="Material, Werkzeug, Messmittel, Spannmittel, Zeichnung, NC-Programm" @click="standardDazu"><RotateCcw :size="15" /> Standardpunkte ergänzen</button>
        <span v-if="geaendert" class="ml-auto text-xs text-warn">Nicht gespeichert</span>
        <button class="btn btn-primary" :class="geaendert ? '' : 'pointer-events-none ml-auto opacity-40'" :disabled="speichert || !geaendert" @click="speichern"><Check :size="15" /> Speichern</button>
      </template>
      <span v-else class="text-xs text-mute">Ändern dürfen Administratoren und die Fertigung.</span>
    </div>
  </div>
</template>
