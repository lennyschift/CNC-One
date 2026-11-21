<script setup>
// Auswertung der zurückgemeldeten Zeiten: Soll (aus dem Arbeitsplan) gegen Ist je Maschine, Arbeitsgang oder Bauteil.
// Grundlage für Erfahrungswerte und Nachkalkulation. Darunter die abgeschlossenen Arbeitsgänge, denen Zeiten fehlen.
import { ref, computed } from 'vue';
import { BarChart3, ChevronRight, AlertTriangle } from '@lucide/vue';
import { sollIst, zeitenFehlen } from '../lib/fertigung.js';
import { useFertigung } from '../stores/fertigung.js';
import { zahl } from '../lib/format.js';

const props = defineProps({ liste: { type: Array, required: true } });
const f = useFertigung();
const nach = ref('maschine');
const offen = ref({});
const gruppen = computed(() => sollIst(props.liste, nach.value));
const summe = computed(() => gruppen.value.reduce((s, g) => ({ soll: s.soll + g.soll, ist: s.ist + g.ist, anzahl: s.anzahl + g.anzahl }), { soll: 0, ist: 0, anzahl: 0 }));
const fehlend = computed(() => props.liste.flatMap((fb) => zeitenFehlen(fb).map((ag) => ({ fb, ag }))));
const h = (min) => zahl(min / 60, 1);
const prozent = (soll, ist) => (soll > 0 ? Math.round((ist / soll - 1) * 100) : null);
const farbe = (p) => (p === null ? 'text-mute' : p > 10 ? 'text-accent' : p < -10 ? 'text-ok' : 'text-mute');
const text = (p) => (p === null ? '–' : `${p > 0 ? '+' : ''}${p} %`);
</script>

<template>
  <div class="space-y-4">
    <section class="card overflow-hidden">
      <header class="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <BarChart3 :size="16" class="text-accent" /><span class="text-sm font-semibold">Soll und Ist</span>
        <span class="text-xs text-mute">{{ summe.anzahl }} abgeschlossene Arbeitsgänge mit Zeiten · Soll {{ h(summe.soll) }} h · Ist {{ h(summe.ist) }} h · <span :class="farbe(prozent(summe.soll, summe.ist))">{{ text(prozent(summe.soll, summe.ist)) }}</span></span>
        <span class="ml-auto flex gap-0.5 rounded-lg border border-line bg-surface2 p-0.5 text-xs" role="radiogroup" aria-label="Gruppieren nach">
          <button v-for="[k, l] in [['maschine', 'Maschine'], ['art', 'Arbeitsgang'], ['bauteil', 'Bauteil']]" :key="k" class="rounded-md px-2 py-0.5" :class="nach === k ? 'bg-surface font-medium text-accent shadow-sm' : 'text-mute'" @click="nach = k; offen = {}">{{ l }}</button>
        </span>
      </header>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[760px] text-sm">
          <thead>
            <tr class="text-left text-[11px] uppercase tracking-wide text-mute">
              <th class="px-4 py-2 font-semibold">{{ { maschine: 'Maschine', art: 'Arbeitsgang', bauteil: 'Bauteil' }[nach] }}</th>
              <th class="px-2 py-2 text-right font-semibold">Anzahl</th>
              <th class="px-2 py-2 text-right font-semibold">Rüsten Soll / Ist</th>
              <th class="px-2 py-2 text-right font-semibold">Bearbeiten Soll / Ist</th>
              <th class="px-2 py-2 text-right font-semibold">Gesamt Soll / Ist</th>
              <th class="px-4 py-2 text-right font-semibold">Abweichung</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="g in gruppen" :key="g.name">
              <tr class="cursor-pointer border-t border-line hover:bg-surface2" @click="offen[g.name] = !offen[g.name]">
                <td class="px-4 py-2.5 font-medium"><span class="inline-flex items-center gap-1"><ChevronRight :size="14" class="text-mute transition" :class="offen[g.name] ? 'rotate-90' : ''" />{{ g.name }}</span></td>
                <td class="px-2 py-2.5 text-right tnum">{{ g.anzahl }}</td>
                <td class="px-2 py-2.5 text-right tnum">{{ h(g.sollRuest) }} / {{ h(g.istRuest) }} h</td>
                <td class="px-2 py-2.5 text-right tnum">{{ h(g.sollBearb) }} / {{ h(g.istBearb) }} h</td>
                <td class="px-2 py-2.5 text-right font-medium tnum">{{ h(g.soll) }} / {{ h(g.ist) }} h</td>
                <td class="px-4 py-2.5 text-right font-semibold tnum" :class="farbe(prozent(g.soll, g.ist))">{{ text(prozent(g.soll, g.ist)) }}</td>
              </tr>
              <template v-if="offen[g.name]">
                <tr v-for="e in g.eintraege" :key="e.ag.id" class="bg-surface2/50 text-xs">
                  <td class="py-2 pl-10 pr-4"><RouterLink :to="`/fertigung/${e.fb.id}`" class="text-accent hover:underline">{{ e.fb.teil.name }}</RouterLink> <span class="text-mute">· {{ e.ag.name }} · {{ e.ag.maschine || 'ohne Maschine' }} · {{ e.fb.auftragId }}</span></td>
                  <td class="px-2 py-2 text-right tnum">{{ e.menge }} Stk</td>
                  <td class="px-2 py-2 text-right tnum">{{ h(e.ag.ruestMin) }} / {{ h(e.ag.istRuestMin) }} h</td>
                  <td class="px-2 py-2 text-right tnum">{{ h(e.ag.stueckMin * e.menge) }} / {{ h(e.ag.istBearbMin) }} h</td>
                  <td class="px-2 py-2 text-right tnum" :title="`Ist je Stück ${zahl(e.ag.istBearbMin / Math.max(e.menge, 1), 2)} min, geplant ${zahl(e.ag.stueckMin, 2)} min`">{{ zahl(e.ag.istBearbMin / Math.max(e.menge, 1), 1) }} min/Stk</td>
                  <td class="px-4 py-2 text-right tnum" :class="farbe(prozent(e.ag.ruestMin + e.ag.stueckMin * e.menge, e.ag.istRuestMin + e.ag.istBearbMin))">{{ text(prozent(e.ag.ruestMin + e.ag.stueckMin * e.menge, e.ag.istRuestMin + e.ag.istBearbMin)) }}</td>
                </tr>
              </template>
            </template>
          </tbody>
        </table>
        <p v-if="!gruppen.length" class="px-6 py-12 text-center text-sm text-mute">Noch keine zurückgemeldeten Zeiten. Sie entstehen beim Abschließen eines Arbeitsgangs in der Fertigung.</p>
      </div>
    </section>

    <section v-if="fehlend.length" class="card p-5">
      <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><AlertTriangle :size="16" class="text-warn" /> Abgeschlossen, aber ohne Zeiten <span class="rounded-full bg-surface2 px-2 py-0.5 text-xs font-normal text-mute tnum">{{ fehlend.length }}</span></h3>
      <div class="space-y-1.5">
        <div v-for="e in fehlend" :key="e.ag.id" class="flex items-center gap-3 rounded-lg bg-surface2 px-3 py-2 text-sm">
          <RouterLink :to="`/fertigung/${e.fb.id}`" class="min-w-0 flex-1 truncate hover:text-accent">{{ e.fb.teil.name }} <span class="text-xs text-mute">· {{ e.ag.name }} · {{ e.fb.auftragId }}</span></RouterLink>
          <button class="btn !py-0.5 !text-xs" @click="f.zeitenMelden(e.fb.id, [e.ag.id])">Zeiten nachtragen</button>
        </div>
      </div>
    </section>
  </div>
</template>
