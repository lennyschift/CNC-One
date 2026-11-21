<script setup>
// Auslastung je Maschine und Woche: eingeplante offene Stunden gegen die verfügbaren Stunden (Stunden je Tag × Arbeitstage),
// dazu was noch nicht eingeplant ist. Darunter der offene Bedarf je Arbeitsgang (auch ohne Maschine).
import { ref, computed } from 'vue';
import { Gauge, Layers } from '@lucide/vue';
import { auslastung, alleArbeitsgaenge, restMinuten, tagIso, wocheVon, tageAb, kw } from '../lib/fertigung.js';
import { zahl } from '../lib/format.js';

const props = defineProps({
  liste: { type: Array, required: true },
  maschinen: { type: Array, required: true },
});
const arbeitstage = ref(5);
const wochen = computed(() => Array.from({ length: 6 }, (_x, i) => {
  const s = wocheVon(new Date());
  s.setDate(s.getDate() + 7 * i);
  return { start: s, tage: tageAb(s, 7).map(tagIso) };
}));
const l = computed(() => auslastung(props.liste));
const zeilen = computed(() => {
  const namen = props.maschinen.map((m) => m.name);
  const extra = Object.keys({ ...l.value.plan, ...l.value.ungeplant }).filter((m) => !namen.includes(m));
  return [...props.maschinen, ...extra.map((name) => ({ name, stundenTag: 0 }))];
});
const minutenWoche = (m, w) => w.tage.reduce((s, t) => s + (l.value.plan[m.name]?.[t] ?? 0), 0);
const vorher = (m) => Object.entries(l.value.plan[m.name] ?? {}).filter(([t]) => t < wochen.value[0].tage[0]).reduce((s, [, v]) => s + v, 0);
const kapazitaet = (m) => (m.stundenTag || 0) * arbeitstage.value * 60;
const anteil = (m, w) => (kapazitaet(m) ? minutenWoche(m, w) / kapazitaet(m) : 0);
const h = (min) => zahl(min / 60, 1);

// offener Bedarf je Arbeitsgang
const jeArt = computed(() => {
  const g = new Map();
  for (const { fb, ag } of alleArbeitsgaenge(props.liste)) {
    if (ag.typ === 'fremd' || fb.status === 'Fertig' || ag.gebucht >= fb.menge) continue;
    const x = g.get(ag.name || 'ohne Namen') ?? { name: ag.name || 'ohne Namen', minuten: 0, anzahl: 0, ohneMaschine: 0 };
    x.minuten += restMinuten(ag, fb.menge);
    x.anzahl += 1;
    if (!ag.maschine) x.ohneMaschine += 1;
    g.set(x.name, x);
  }
  return [...g.values()].sort((a, b) => b.minuten - a.minuten);
});
const maxArt = computed(() => Math.max(1, ...jeArt.value.map((x) => x.minuten)));
</script>

<template>
  <div class="space-y-4">
    <section class="card overflow-hidden">
      <header class="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <Gauge :size="16" class="text-accent" /><span class="text-sm font-semibold">Auslastung je Maschine</span>
        <span class="text-xs text-mute">eingeplante offene Stunden gegen verfügbare Stunden</span>
        <span class="ml-auto flex gap-0.5 rounded-lg border border-line bg-surface2 p-0.5 text-xs" role="radiogroup" aria-label="Arbeitstage je Woche">
          <button v-for="n in [5, 6, 7]" :key="n" class="rounded-md px-2 py-0.5" :class="arbeitstage === n ? 'bg-surface font-medium text-accent shadow-sm' : 'text-mute'" @click="arbeitstage = n">{{ n }} Tage</button>
        </span>
      </header>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[820px] text-sm">
          <thead>
            <tr class="text-left text-[11px] uppercase tracking-wide text-mute">
              <th class="px-4 py-2 font-semibold">Maschine</th>
              <th class="px-2 py-2 text-right font-semibold">Überfällig</th>
              <th v-for="w in wochen" :key="w.tage[0]" class="px-2 py-2 font-semibold">KW {{ kw(w.start) }}</th>
              <th class="px-4 py-2 text-right font-semibold">Nicht eingeplant</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in zeilen" :key="m.name || '-'" class="border-t border-line">
              <td class="px-4 py-2.5"><div class="font-medium">{{ m.name || 'Ohne Maschine' }}</div><div v-if="m.stundenTag" class="text-[11px] text-mute">{{ zahl(kapazitaet(m) / 60, 0) }} h/Woche</div></td>
              <td class="px-2 py-2.5 text-right tnum" :class="vorher(m) ? 'text-accent' : 'text-mute'">{{ vorher(m) ? h(vorher(m)) + ' h' : '–' }}</td>
              <td v-for="w in wochen" :key="w.tage[0]" class="px-2 py-2.5">
                <div class="flex items-center gap-2">
                  <div class="h-2 flex-1 overflow-hidden rounded-full bg-line"><div class="h-full rounded-full" :class="anteil(m, w) > 1 ? 'bg-accent' : anteil(m, w) > 0.85 ? 'bg-warn' : 'bg-ok'" :style="{ width: Math.min(100, anteil(m, w) * 100) + '%' }" /></div>
                  <span class="w-16 text-right text-xs tnum" :class="anteil(m, w) > 1 ? 'font-semibold text-accent' : 'text-mute'">{{ minutenWoche(m, w) ? h(minutenWoche(m, w)) + ' h' : '–' }}<template v-if="kapazitaet(m) && minutenWoche(m, w)"> · {{ Math.round(anteil(m, w) * 100) }} %</template></span>
                </div>
              </td>
              <td class="px-4 py-2.5 text-right tnum" :class="l.ungeplant[m.name] ? 'text-warn' : 'text-mute'">{{ l.ungeplant[m.name] ? h(l.ungeplant[m.name]) + ' h' : '–' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card p-5">
      <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><Layers :size="16" class="text-accent" /> Offener Bedarf je Arbeitsgang</h3>
      <div class="space-y-2">
        <div v-for="x in jeArt" :key="x.name" class="grid grid-cols-[160px_minmax(0,1fr)_auto] items-center gap-3 text-sm">
          <span class="truncate font-medium">{{ x.name }}</span>
          <div class="h-2 overflow-hidden rounded-full bg-line"><div class="h-full rounded-full bg-accent" :style="{ width: (x.minuten / maxArt) * 100 + '%' }" /></div>
          <span class="text-xs text-mute tnum">{{ h(x.minuten) }} h · {{ x.anzahl }} AG<template v-if="x.ohneMaschine"> · <span class="text-warn">{{ x.ohneMaschine }} ohne Maschine</span></template></span>
        </div>
        <p v-if="!jeArt.length" class="py-6 text-center text-xs text-mute">Keine offenen internen Arbeitsgänge.</p>
      </div>
    </section>
  </div>
</template>
