<script setup>
// Kalender der Fertigung: Zeilen = Maschinen, Spalten = Tage. Offene interne Arbeitsgänge werden per Drag and Drop
// auf Tag und Maschine eingeplant (nur auf Maschinen, die den Arbeitsgang können); links liegen die noch nicht eingeplanten.
// Jede Zelle zeigt die geplanten Stunden gegen die verfügbaren Stunden der Maschine.
import { ref, computed } from 'vue';
import { ChevronLeft, ChevronRight, CalendarDays, Inbox, Flame } from '@lucide/vue';
import PartImage from './PartImage.vue';
import { useFertigung } from '../stores/fertigung.js';
import { useUi } from '../stores/ui.js';
import { alleArbeitsgaenge, restMinuten, maschinenFuer, tagIso, wocheVon, tageAb, kw } from '../lib/fertigung.js';
import { zahl } from '../lib/format.js';

const props = defineProps({
  liste: { type: Array, required: true },
  maschinen: { type: Array, required: true },
});
const f = useFertigung();
const ui = useUi();

// am Wochenende zeigt der Kalender schon die nächste Woche
function aktuelleWoche() {
  const d = new Date();
  if (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 2);
  return wocheVon(d);
}
const start = ref(aktuelleWoche());
const tageAnzahl = ref(5); // 5 = Mo–Fr, 6 = Mo–Sa, 12 = zwei Wochen Mo–Sa
const tage = computed(() => {
  if (tageAnzahl.value === 12) return [...tageAb(start.value, 6), ...tageAb(new Date(start.value.getFullYear(), start.value.getMonth(), start.value.getDate() + 7), 6)];
  return tageAb(start.value, tageAnzahl.value);
});
const heute = tagIso(new Date());
function blaettern(wochen) {
  const d = new Date(start.value);
  d.setDate(d.getDate() + 7 * wochen);
  start.value = d;
}

// offene interne Arbeitsgänge
const offen = computed(() => alleArbeitsgaenge(props.liste).filter(({ fb, ag }) => ag.typ === 'intern' && fb.status !== 'Fertig' && ag.gebucht < fb.menge));
const ungeplant = computed(() => offen.value.filter((e) => !e.ag.geplantAm).sort((a, b) => (a.fb.termin || '9999').localeCompare(b.fb.termin || '9999')));
const zeilen = computed(() => {
  const namen = props.maschinen.map((m) => m.name);
  const extra = [...new Set(offen.value.map((e) => e.ag.maschine).filter((m) => m && !namen.includes(m)))];
  return [...props.maschinen, ...extra.map((name) => ({ name, stundenTag: 8 })), { name: '', stundenTag: 0 }];
});
const zelle = (maschine, tag) => offen.value.filter((e) => e.ag.geplantAm === tag && (e.ag.maschine || '') === maschine);
const minuten = (maschine, tag) => zelle(maschine, tag).reduce((s, e) => s + restMinuten(e.ag, e.fb.menge), 0);
const last = (m, tag) => (m.stundenTag ? minuten(m.name, tag) / (m.stundenTag * 60) : 0);
const stunden = (min) => zahl(min / 60, 1);
const spaet = (e) => e.fb.termin && e.ag.geplantAm && e.ag.geplantAm > e.fb.termin;

// Drag and Drop
const ziehend = ref(null);
const ziel = ref('');
function ziehen(e, eintrag) {
  ziehend.value = eintrag;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', eintrag.ag.id);
}
function ablegen(maschine, tag) {
  ziel.value = '';
  const e = ziehend.value;
  ziehend.value = null;
  if (!e) return;
  if (maschine && !maschinenFuer(props.maschinen, e.ag.name).some((m) => m.name === maschine) && props.maschinen.some((m) => m.name === maschine)) {
    ui.toast(`${maschine} kann „${e.ag.name}“ laut Stammdaten nicht`, 'warn');
    return;
  }
  const fb = f.bauteil(e.fb.id);
  const ag = fb?.arbeitsgaenge.find((a) => a.id === e.ag.id);
  if (!ag) return;
  ag.geplantAm = tag || '';
  if (tag && (ag.maschine || '') !== maschine) {
    ag.maschine = maschine;
    const m = props.maschinen.find((x) => x.name === maschine);
    if (m?.satz && !ag.satz) ag.satz = m.satz;
  }
  f.felderPlanen(fb.id);
}
const kopfTag = (d) => d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
</script>

<template>
  <div class="grid items-start gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
    <!-- noch nicht eingeplant -->
    <section class="rounded-2xl border border-dashed p-3 transition xl:sticky xl:top-4" :class="ziel === 'ablage' ? 'border-accent bg-accent-soft/50' : 'border-line bg-surface2/60'" @dragover.prevent="ziel = 'ablage'" @dragleave="ziel = ''" @drop.prevent="ablegen('', '')">
      <header class="mb-2 flex items-center gap-2 px-1 text-sm font-semibold"><Inbox :size="15" class="text-accent" /> Nicht eingeplant <span class="ml-auto rounded-full bg-surface px-2 py-0.5 text-xs font-normal text-mute tnum">{{ ungeplant.length }}</span></header>
      <div class="max-h-[70vh] space-y-1.5 overflow-auto">
        <div v-for="e in ungeplant" :key="e.ag.id" class="chip" draggable="true" @dragstart="ziehen($event, e)">
          <PartImage iso :teil="e.fb.teil" :groesse="30" />
          <div class="min-w-0 flex-1">
            <div class="truncate text-xs font-medium">{{ e.fb.teil.name }}</div>
            <div class="truncate text-[10px] text-mute">{{ e.ag.name }} · {{ e.ag.maschine || 'Maschine offen' }} · {{ stunden(restMinuten(e.ag, e.fb.menge)) }} h</div>
          </div>
          <span v-if="e.fb.termin" class="text-[10px] text-mute tnum">{{ new Date(e.fb.termin).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) }}</span>
        </div>
        <p v-if="!ungeplant.length" class="px-2 py-6 text-center text-xs text-mute">Alles eingeplant. Hierher ziehen nimmt einen Arbeitsgang wieder aus dem Plan.</p>
      </div>
    </section>

    <section class="card overflow-hidden">
      <header class="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <CalendarDays :size="16" class="text-accent" />
        <span class="text-sm font-semibold">KW {{ kw(start) }}<template v-if="tageAnzahl === 12">–{{ kw(tage[6]) }}</template></span>
        <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2" title="Zurück" @click="blaettern(-1)"><ChevronLeft :size="16" /></button>
        <button class="btn !py-0.5 text-xs" @click="start = aktuelleWoche()">Heute</button>
        <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2" title="Weiter" @click="blaettern(1)"><ChevronRight :size="16" /></button>
        <span class="ml-auto flex gap-0.5 rounded-lg border border-line bg-surface2 p-0.5 text-xs" role="radiogroup" aria-label="Zeitraum">
          <button v-for="[n, l] in [[5, 'Mo–Fr'], [6, 'Mo–Sa'], [12, '2 Wochen']]" :key="n" class="rounded-md px-2 py-0.5" :class="tageAnzahl === n ? 'bg-surface font-medium text-accent shadow-sm' : 'text-mute'" @click="tageAnzahl = n">{{ l }}</button>
        </span>
      </header>
      <div class="overflow-x-auto">
        <div class="grid min-w-[760px]" :style="{ gridTemplateColumns: `150px repeat(${tage.length}, minmax(110px, 1fr))` }">
          <div class="kopf" />
          <div v-for="d in tage" :key="tagIso(d)" class="kopf text-center" :class="tagIso(d) === heute ? '!text-accent' : ''">{{ kopfTag(d) }}</div>
          <template v-for="m in zeilen" :key="m.name || '-'">
            <div class="maschine">
              <div class="truncate text-sm font-medium">{{ m.name || 'Ohne Maschine' }}</div>
              <div v-if="m.name" class="text-[10px] text-mute">{{ zahl(m.stundenTag || 0, 1) }} h/Tag<template v-if="m.automation === true"> · Automation</template></div>
            </div>
            <div v-for="d in tage" :key="tagIso(d)" class="zelle" :class="[ziel === m.name + tagIso(d) ? 'bg-accent-soft/60' : '', tagIso(d) === heute ? 'heute' : '']" @dragover.prevent="ziel = m.name + tagIso(d)" @dragleave="ziel = ''" @drop.prevent="ablegen(m.name, tagIso(d))">
              <div v-if="m.stundenTag && minuten(m.name, tagIso(d))" class="mb-1 h-1 overflow-hidden rounded-full bg-line" :title="`${stunden(minuten(m.name, tagIso(d)))} von ${zahl(m.stundenTag, 1)} h`">
                <div class="h-full rounded-full" :class="last(m, tagIso(d)) > 1 ? 'bg-accent' : last(m, tagIso(d)) > 0.85 ? 'bg-warn' : 'bg-ok'" :style="{ width: Math.min(100, last(m, tagIso(d)) * 100) + '%' }" />
              </div>
              <RouterLink v-for="e in zelle(m.name, tagIso(d))" :key="e.ag.id" :to="`/fertigung/${e.fb.id}`" class="eintrag" :class="spaet(e) ? 'spaet' : ''" draggable="true" :title="`${e.fb.teil.name} · ${e.ag.name} · ${stunden(restMinuten(e.ag, e.fb.menge))} h${spaet(e) ? ' · nach dem Liefertermin!' : ''}`" @dragstart="ziehen($event, e)">
                <span class="flex items-center gap-1 truncate font-medium"><Flame v-if="e.fb.prioritaet !== 'Normal'" :size="10" class="shrink-0 text-accent" />{{ e.fb.teil.name }}</span>
                <span class="block truncate text-[10px] opacity-70">{{ e.ag.name }} · {{ stunden(restMinuten(e.ag, e.fb.menge)) }} h · {{ e.fb.menge - e.ag.gebucht }} Stk</span>
              </RouterLink>
              <div v-if="m.stundenTag && minuten(m.name, tagIso(d))" class="mt-0.5 text-right text-[10px] text-mute tnum">{{ stunden(minuten(m.name, tagIso(d))) }}/{{ zahl(m.stundenTag, 0) }} h</div>
            </div>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chip { display: flex; cursor: grab; align-items: center; gap: 0.5rem; border-radius: 0.65rem; border: 1px solid var(--line); background: var(--surface); padding: 0.35rem 0.5rem; }
.chip:hover { border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
.kopf { position: sticky; top: 0; border-bottom: 1px solid var(--line); background: var(--surface-2); padding: 0.45rem 0.5rem; font-size: 0.72rem; font-weight: 600; color: var(--mute); }
.maschine { border-bottom: 1px solid var(--line); border-right: 1px solid var(--line); padding: 0.5rem 0.65rem; }
.zelle { min-height: 4.5rem; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line); padding: 0.3rem; transition: background 0.15s; }
.zelle.heute { background: color-mix(in srgb, var(--accent) 4%, transparent); }
.eintrag { display: block; cursor: grab; margin-bottom: 0.25rem; border-radius: 0.5rem; border: 1px solid var(--line); background: var(--surface); padding: 0.25rem 0.4rem; font-size: 0.72rem; color: var(--ink); }
.eintrag:hover { border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
.eintrag.spaet { border-color: var(--accent); background: var(--accent-soft); }
</style>
