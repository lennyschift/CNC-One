<script setup>
// Rohmaterial auswählen (ohne Bauteil), z. B. für eine Materialanfrage: Auswahl in Stufen (RohmaterialWahl, mit „+ Neu“)
// und Anforderungen (Werkszeugnis, Prüfungen). „Übernehmen“ liefert { werkstoff, zustand, form, ausfuehrung, abmessungId,
// abmessung, anforderungen: { zeugnis, pruefungen }, artikel }.
import { reactive, computed } from 'vue';
import { X, Check, ShieldCheck } from '@lucide/vue';
import RohmaterialWahl from './RohmaterialWahl.vue';
import { ZEUGNISSE, STANDARD_ZEUGNIS, zeugnisKurz, artikelText } from '../lib/werkstoffbaum.js';
import { useWerkstoff } from '../stores/werkstoff.js';

const props = defineProps({ wert: { type: Object, default: null } });
const emit = defineEmits(['uebernehmen', 'schliessen']);
const ws = useWerkstoff();

const w = props.wert ?? {};
const wahl = reactive({ werkstoff: w.werkstoff || '', zustand: w.zustand || '', form: w.form || 'Rund', ausfuehrung: w.ausfuehrung || '', abmessungId: w.abmessungId || '' });
const anf = reactive({ zeugnis: w.anforderungen ? w.anforderungen.zeugnis || '' : STANDARD_ZEUGNIS, pruefungen: [...(w.anforderungen?.pruefungen ?? [])] });
const abm = computed(() => ws.baum.abmessungen.find((a) => a.id === wahl.abmessungId) ?? null);
const artikel = computed(() => artikelText(wahl.werkstoff, { ...wahl, abmessung: abm.value?.text ?? '' }));
const pruefung = (p) => { anf.pruefungen = anf.pruefungen.includes(p) ? anf.pruefungen.filter((x) => x !== p) : [...anf.pruefungen, p]; };
function uebernehmen() {
  emit('uebernehmen', { ...wahl, abmessung: abm.value?.text ?? '', anforderungen: { zeugnis: anf.zeugnis, pruefungen: [...anf.pruefungen] }, artikel: artikel.value });
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')" @keydown.esc="emit('schliessen')">
      <div class="card flex max-h-[94vh] w-[min(1100px,97vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center gap-3 border-b border-line px-6 py-3.5">
          <div class="min-w-0"><h2 class="truncate text-base font-semibold">{{ artikel || 'Rohmaterial wählen' }}</h2><p class="text-xs text-mute">Werkstoff, Zustand, Form, Ausführung und Abmessung aus den Stammdaten</p></div>
          <button type="button" class="ml-auto grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" title="Schließen" @click="emit('schliessen')"><X :size="18" /></button>
        </header>
        <div class="min-h-0 flex-1 space-y-5 overflow-auto p-5">
          <RohmaterialWahl :wahl="wahl" />
          <section class="flex flex-wrap items-start gap-5 border-t border-line pt-4">
            <div><div class="label mb-1">Werkszeugnis (EN 10204)</div>
              <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1 text-xs">
                <button v-for="z in ZEUGNISSE" :key="z" type="button" class="rounded-lg px-3 py-1.5" :class="anf.zeugnis === z ? 'bg-surface font-medium shadow-sm' : 'text-mute hover:text-ink'" @click="anf.zeugnis = z">{{ zeugnisKurz(z) }}</button>
              </div>
            </div>
            <div class="min-w-0 flex-1"><div class="label mb-1">Prüfungen und Nachweise</div>
              <div class="flex flex-wrap gap-1.5">
                <button v-for="a in ws.baum.anforderungen" :key="a.name" type="button" class="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition" :class="anf.pruefungen.includes(a.name) ? 'border-accent bg-accent-soft text-accent' : 'border-line text-mute hover:text-ink'" @click="pruefung(a.name)"><ShieldCheck v-if="anf.pruefungen.includes(a.name)" :size="11" /> {{ a.name }}</button>
              </div>
            </div>
          </section>
        </div>
        <footer class="flex items-center gap-2 border-t border-line bg-surface2 px-6 py-3">
          <span v-if="!abm" class="text-xs text-mute">Bitte bis zur Abmessung auswählen.</span>
          <button type="button" class="btn ml-auto" @click="emit('schliessen')">Abbrechen</button>
          <button type="button" class="btn btn-primary" :disabled="!wahl.werkstoff || !abm" @click="uebernehmen"><Check :size="15" /> Übernehmen</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
