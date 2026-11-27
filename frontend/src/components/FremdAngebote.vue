<script setup>
// Angebote für eine Fremdvergabe nebeneinander: aus den Lieferantenanfragen (eingelesen oder erfasst) und von Hand
// eingetragene (Telefon, Mail außerhalb). Je Angebot Preis je Stück, einmalig, Liefertermin und der Betrag für die
// Stückzahl der Kalkulation; der günstigste ist grün, der schnellste Termin auch. „Übernehmen“ setzt Lieferant und
// Preise im Arbeitsgang. Die von Hand eingetragenen Angebote werden mit dem Arbeitsgang gespeichert (ag.angebote).
import { computed } from 'vue';
import { Plus, Trash2, Check, Truck, FileText, Scale, Crown } from '@lucide/vue';
import NumField from './NumField.vue';
import { eur } from '../lib/format.js';
import { preisFuerMenge } from '../lib/anfrage.js';

const props = defineProps({
  ag: { type: Object, required: true },
  anfragen: { type: Array, default: () => [] }, // Lieferantenanfragen zu diesem Arbeitsgang
  menge: { type: Number, default: 1 },
  lieferanten: { type: Array, default: () => [] },
  nurAnsicht: { type: Boolean, default: false },
});
const emit = defineEmits(['anfrage']);

const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const zeilen = computed(() => {
  const aus = props.anfragen.filter((a) => a.antwort).map((a) => {
    const pos = a.positionen.find((x) => x.agId === props.ag.id);
    const p = preisFuerMenge(a.antwort, props.menge, pos?.key);
    const o = (a.antwort.daten?.positionen ?? []).find((x) => x.zuordnung === pos?.key);
    return {
      key: `a:${a.id}`, quelle: 'anfrage', anfrage: a, lieferant: a.lieferantName, proStk: p?.proStk ?? 0, einmalig: p?.einmalig ?? 0,
      ab: p?.menge ?? null, termin: o?.lieferdatum ? de(o.lieferdatum) : o?.liefertermin || a.antwort.lieferzeit || '', datum: o?.lieferdatum || '',
    };
  });
  const hand = (props.ag.angebote ?? []).map((m, i) => ({ key: `m:${i}`, quelle: 'hand', m, index: i, lieferant: m.lieferant, proStk: Number(m.proStk) || 0, einmalig: Number(m.einmalig) || 0, termin: m.termin ? de(m.termin) : '', datum: m.termin || '' }));
  return [...aus, ...hand].map((z) => ({ ...z, gesamt: Math.round(((z.proStk * props.menge) + z.einmalig) * 100) / 100 }));
});
const mitPreis = computed(() => zeilen.value.filter((z) => z.proStk > 0 || z.einmalig > 0));
const bester = computed(() => (mitPreis.value.length > 1 ? mitPreis.value.reduce((x, y) => (y.gesamt < x.gesamt ? y : x)).key : null));
const schnellster = computed(() => {
  const d = mitPreis.value.filter((z) => z.datum);
  if (d.length < 2 || new Set(d.map((z) => z.datum)).size < 2) return null;
  return d.reduce((x, y) => (y.datum < x.datum ? y : x)).datum;
});
const aktiv = (z) => props.ag.lieferant === z.lieferant && Number(props.ag.fremdProStk) === z.proStk && Number(props.ag.fremdEinmal || 0) === z.einmalig;

function hinzu() {
  if (!Array.isArray(props.ag.angebote)) props.ag.angebote = [];
  props.ag.angebote.push({ lieferant: '', proStk: 0, einmalig: 0, termin: '', notiz: '' });
}
function weg(i) { props.ag.angebote.splice(i, 1); }
function uebernehmen(z) {
  props.ag.lieferant = z.lieferant;
  props.ag.fremdProStk = z.proStk;
  props.ag.fremdEinmal = z.einmalig;
  props.ag.anfrageId = z.quelle === 'anfrage' ? z.anfrage.id : '';
}
</script>

<template>
  <div class="rounded-xl border border-line bg-surface2/40 p-3">
    <div class="mb-2 flex flex-wrap items-center gap-2 text-xs">
      <span class="flex items-center gap-1.5 font-semibold"><Scale :size="13" class="text-accent" /> Angebote für {{ ag.name || 'die Fremdvergabe' }}</span>
      <span class="text-mute">Betrag für {{ menge }} Stk</span>
      <span class="ml-auto flex gap-1.5">
        <button v-if="!nurAnsicht" type="button" class="mini" @click="emit('anfrage', ag)"><FileText :size="11" /> Anfrage an Lieferanten</button>
        <button v-if="!nurAnsicht" type="button" class="mini" @click="hinzu"><Plus :size="11" /> Angebot von Hand</button>
      </span>
    </div>
    <div v-if="!zeilen.length" class="text-xs text-mute">Noch keine Angebote. Anfrage verschicken (Antworten und eingelesene PDFs erscheinen hier) oder ein Angebot von Hand eintragen.</div>
    <table v-else class="w-full text-xs">
      <thead>
        <tr class="text-left text-[11px] text-mute">
          <th class="py-1 pr-2 font-medium">Lieferant</th>
          <th class="px-2 py-1 text-right font-medium">je Stk</th>
          <th class="px-2 py-1 text-right font-medium">einmalig</th>
          <th class="px-2 py-1 font-medium">Liefertermin</th>
          <th class="px-2 py-1 text-right font-medium">Betrag</th>
          <th class="w-[150px]" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="z in zeilen" :key="z.key" class="border-t border-line/60 align-middle" :class="z.key === bester ? 'bg-ok/10' : ''">
          <td class="py-1.5 pr-2">
            <template v-if="z.quelle === 'anfrage'">
              <RouterLink :to="`/anfragen/${z.anfrage.id}`" class="font-medium hover:text-accent">{{ z.lieferant }}</RouterLink>
              <span class="ml-1 text-[10px] text-mute">{{ z.anfrage.id }}{{ z.ab && z.ab !== menge ? ` · Preis ab ${z.ab} Stk` : '' }}</span>
            </template>
            <template v-else>
              <input v-model="z.m.lieferant" list="fremd-lieferanten" class="field !py-0.5 !text-xs" placeholder="Lieferant" :disabled="nurAnsicht" />
            </template>
          </td>
          <td class="px-2 py-1.5 text-right tnum">
            <NumField v-if="z.quelle === 'hand'" v-model="z.m.proStk" unit="€" class="mikro w-[96px]" />
            <template v-else>{{ eur(z.proStk) }}</template>
          </td>
          <td class="px-2 py-1.5 text-right tnum">
            <NumField v-if="z.quelle === 'hand'" v-model="z.m.einmalig" unit="€" class="mikro w-[96px]" />
            <template v-else>{{ z.einmalig ? eur(z.einmalig) : '–' }}</template>
          </td>
          <td class="px-2 py-1.5">
            <input v-if="z.quelle === 'hand'" v-model="z.m.termin" type="date" class="field !w-36 !py-0.5 !text-xs" :disabled="nurAnsicht" />
            <span v-else-if="z.termin" class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold" :class="z.datum && z.datum === schnellster ? 'bg-ok/15 text-ok' : 'bg-surface2'"><Truck :size="11" /> {{ z.termin }}</span>
            <span v-else class="text-mute">–</span>
          </td>
          <td class="px-2 py-1.5 text-right font-semibold tnum" :class="z.key === bester ? 'text-ok' : ''"><Crown v-if="z.key === bester" :size="11" class="mr-0.5 inline" />{{ z.proStk || z.einmalig ? eur(z.gesamt) : '–' }}</td>
          <td class="py-1.5 pl-2 text-right">
            <span v-if="aktiv(z)" class="inline-flex items-center gap-1 text-[11px] font-medium text-ok"><Check :size="12" /> in der Kalkulation</span>
            <button v-else-if="!nurAnsicht && (z.proStk || z.einmalig) && z.lieferant" type="button" class="mini" @click="uebernehmen(z)"><Check :size="11" /> übernehmen</button>
            <button v-if="!nurAnsicht && z.quelle === 'hand'" type="button" class="ml-1 text-mute hover:text-accent" title="Angebot entfernen" @click="weg(z.index)"><Trash2 :size="12" /></button>
          </td>
        </tr>
      </tbody>
    </table>
    <datalist id="fremd-lieferanten"><option v-for="l in lieferanten" :key="l.id" :value="l.name" /></datalist>
  </div>
</template>

<style scoped>
.mini { display: inline-flex; align-items: center; gap: 0.25rem; border-radius: 0.5rem; border: 1px solid var(--line); background: var(--surface); padding: 0.15rem 0.5rem; font-size: 0.72rem; color: var(--ink); transition: border-color 0.15s, color 0.15s; }
.mini:hover { border-color: var(--accent); color: var(--accent); }
</style>
