<script setup>
// Passende Chargen im Rohmaterial-Lager zum Auswählen (Workbench, Fertigung, Entnahme). Oben das gesuchte Material,
// darunter je Charge die Eigenschaften (Zeugnis, Prüfungen) und ihre Posten mit Maßen untereinander, z. B. volle Stangen
// und Reststücke. Der Lieferant steht nur als Kürzel dabei. Ein Klick auf einen Posten wählt ihn.
import { computed } from 'vue';
import { Check, FileBadge, ShieldCheck, Warehouse, Scissors, AlertTriangle } from '@lucide/vue';
import { chargenBuendeln, zeugnisKurz } from '../lib/werkstoffbaum.js';
import { zahl } from '../lib/format.js';

const props = defineProps({
  chargen: { type: Array, default: () => [] }, // Posten mit id, interneNr, chargennr, form, laenge, breite, stueck, zeugnis, pruefungen, lagerplatz, rest, reicht, ok, fehlt
  gewaehlt: { type: String, default: '' },
  titel: { type: String, default: '' }, // gesuchtes Material, z. B. EN AW-7075 T651 · Rund Ø60
  bedarf: { type: Number, default: 0 }, // Stück, für „reicht“
  deaktiviert: { type: Boolean, default: false },
  leer: { type: String, default: 'Keine passende Charge im Lager.' },
});
const emit = defineEmits(['waehlen']);

const gruppen = computed(() => chargenBuendeln(props.chargen));
const summe = computed(() => {
  const g = gruppen.value;
  const stk = g.reduce((s, x) => s + x.stueck, 0);
  const platte = props.chargen.some((c) => c.form === 'Platte');
  const menge = platte ? `${zahl(g.reduce((s, x) => s + x.qm, 0), 2)} m²` : `${zahl(g.reduce((s, x) => s + x.meter, 0), 2)} m`;
  return `${stk} ${platte ? (stk === 1 ? 'Platte' : 'Platten') : (stk === 1 ? 'Stange' : 'Stangen')} · ${menge} · ${g.length} ${g.length === 1 ? 'Charge' : 'Chargen'}`;
});
const mass = (c) => (c.form === 'Platte' ? `${zahl(c.breite, 0)} × ${zahl(c.laenge, 0)}` : zahl(c.laenge, 0));
const monat = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString('de-DE', { month: '2-digit', year: '2-digit' }) : '');
const reichtKlasse = (c) => (c.reicht == null ? 'text-mute' : props.bedarf && c.reicht >= props.bedarf ? 'text-ok' : c.reicht > 0 ? 'text-warn' : 'text-mute');
</script>

<template>
  <div>
    <div class="mb-2">
      <div class="label flex items-center gap-1.5"><Warehouse :size="12" /> Im Lager</div>
      <div v-if="titel" class="text-sm font-semibold leading-snug">{{ titel }}</div>
      <div v-if="chargen.length" class="text-[11px] text-mute tnum">{{ summe }}</div>
    </div>

    <div v-if="gruppen.length" class="space-y-2">
      <div v-for="g in gruppen" :key="g.key" class="overflow-hidden rounded-xl border" :class="g.posten.some((c) => c.id === gewaehlt) ? 'border-accent' : g.ok ? 'border-line' : 'border-warn/50'">
        <!-- Charge: Nummer und Eigenschaften -->
        <div class="flex flex-wrap items-center gap-x-1.5 gap-y-1 bg-surface2/70 px-3 py-1.5">
          <FileBadge :size="13" :class="g.zeugnisDatei ? 'text-accent' : 'text-mute'" />
          <span class="text-sm font-semibold tnum">{{ g.nr }}</span>
          <span class="rounded-md px-1.5 py-px text-[10.5px] font-medium" :class="g.zeugnis ? 'bg-surface text-ink' : 'bg-surface text-mute'">Zeugnis {{ zeugnisKurz(g.zeugnis) }}</span>
          <span v-for="p in g.pruefungen" :key="p" class="inline-flex items-center gap-0.5 rounded-md bg-surface px-1.5 py-px text-[10.5px] text-ok"><ShieldCheck :size="10" /> {{ p }}</span>
          <span class="ml-auto text-[10.5px] text-mute" :title="[g.lieferant, g.chargennr && `Charge ${g.chargennr}`, g.eingang && `Eingang ${g.eingang}`].filter(Boolean).join(' · ')">{{ [g.lieferantKurz || g.lieferant.split(' ')[0], monat(g.eingang)].filter(Boolean).join(' · ') }}</span>
        </div>
        <div v-if="!g.ok" class="flex items-center gap-1 px-3 pt-1 text-[11px] text-warn"><AlertTriangle :size="11" /> fehlt: {{ g.fehlt.join(', ') }}</div>
        <!-- Posten: Maße untereinander -->
        <div class="divide-y divide-line/70">
          <button v-for="c in g.posten" :key="c.id" type="button" class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition disabled:cursor-default" :class="c.id === gewaehlt ? 'bg-accent-soft/60' : 'hover:bg-surface2'" :disabled="deaktiviert" @click="emit('waehlen', c)">
            <span class="w-6 shrink-0 text-right text-sm font-semibold tnum">{{ c.stueck }}×</span>
            <span class="text-[15px] font-semibold tnum">{{ mass(c) }}<span class="text-xs font-normal text-mute"> mm</span></span>
            <span v-if="c.rest" class="inline-flex items-center gap-0.5 rounded-md bg-surface2 px-1.5 py-px text-[10px] text-mute"><Scissors :size="10" /> Rest</span>
            <span v-if="c.lagerplatz" class="truncate text-[11px] text-mute">{{ c.lagerplatz }}</span>
            <span v-if="c.reicht != null" class="ml-auto shrink-0 text-[11px] tnum" :class="reichtKlasse(c)">reicht für {{ c.reicht }}</span>
            <span v-else class="ml-auto" />
            <Check v-if="c.id === gewaehlt" :size="14" class="shrink-0 text-accent" />
          </button>
        </div>
      </div>
    </div>
    <p v-else class="rounded-xl bg-surface2 px-3 py-2.5 text-xs text-mute">{{ leer }}</p>
  </div>
</template>
