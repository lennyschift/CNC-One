<script setup>
// Ähnliche Bauteile zu einem Bauteil oder zu einem Workbench-Bauteil (auch ohne gespeichertes Bauteil): über Teilenummer
// (Index, Baustufe), Zeichnung, Bezeichnung, Werkstoff und Rohteil sowie die Geometrie aus dem STEP-Modell.
// Bewertet wird auf dem Server (api/aehnlich.py). In der Workbench lässt sich die Kalkulation übernehmen und eine
// Teilefamilie bilden.
import { ref, computed, watch } from 'vue';
import { Sparkles, ChevronDown, Copy, Network, Box } from '@lucide/vue';
import PartImage from './PartImage.vue';
import TeilefamilieDialog from './TeilefamilieDialog.vue';
import { call } from '../data/api.js';
import { eur } from '../lib/format.js';
import { preisText } from '../lib/historie.js';

const props = defineProps({
  bauteilId: { type: String, default: '' },
  kundeId: { type: String, default: '' },
  teil: { type: Object, default: null }, // Workbench-Bauteil: { teilenummer, name, zeichnungsnr, material, roh, geo }
  aktionen: { type: Boolean, default: false },
  offen: { type: Boolean, default: false },
});
const emit = defineEmits(['kalkulation', 'familie']);

const daten = ref(null);
const laedt = ref(false);
const aufgeklappt = ref(props.offen);
let zaehler = 0;
let warten = null;
const anfrage = computed(() => {
  const t = props.teil ?? {};
  return {
    bauteil: props.bauteilId, kunde: props.kundeId, teilenummer: t.teilenummer ?? '', bezeichnung: t.name ?? '', zeichnungsnr: t.zeichnungsnr ?? '',
    material: t.material ?? '', roh: t.roh ?? null, geo: t.geo ?? null,
  };
});
// neu laden, wenn sich etwas Vergleichbares ändert (nicht bei jeder Zeitänderung der Kalkulation)
const schluessel = computed(() => { const a = anfrage.value; return JSON.stringify([a.bauteil, a.kunde, a.teilenummer, a.bezeichnung, a.zeichnungsnr, a.material, a.roh?.form, a.roh?.durchmesser, a.roh?.laenge, a.roh?.breite, a.roh?.hoehe, a.geo?.url ?? a.geo?.volumen]); });
async function laden() {
  const a = anfrage.value;
  if (!a.bauteil && !a.teilenummer.trim() && !a.zeichnungsnr.trim() && !a.geo) { daten.value = null; return; }
  const nr = ++zaehler;
  laedt.value = true;
  try {
    const d = await call('cnc_one.api.aehnlich.aehnliche', JSON.parse(JSON.stringify(a)));
    if (nr === zaehler) daten.value = d;
  } catch { if (nr === zaehler) daten.value = null; } finally { if (nr === zaehler) laedt.value = false; }
}
watch(schluessel, () => { clearTimeout(warten); warten = setTimeout(laden, 600); }, { immediate: true });
defineExpose({ laden });

const liste = computed(() => daten.value?.treffer ?? []);
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const prozent = (p) => `${Math.round(p * 100)} %`;
const farbe = (g) => (/geometrie|form/i.test(g) ? 'bg-[#7c3aed]/10 text-[#7c3aed]' : /index|baustufe|zeichnung|gleiche teilenummer|stelle/i.test(g) ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute');

// Familie bilden: dieses Bauteil und das ähnliche (ist eines schon in einer Familie, kommt das andere dazu)
const familieDialog = ref(null);
async function familieBilden(x) {
  if (x.familie) {
    const f = await call('cnc_one.api.teilefamilie.fuer_bauteil', { bauteil: x.id });
    if (f) { familieDialog.value = { familie: { ...f, varianten: [...f.varianten, { id: props.bauteilId, teilenummer: props.teil?.teilenummer ?? '', name: props.teil?.name ?? '', variante: '' }] } }; return; }
  }
  familieDialog.value = { vorschlag: { bezeichnung: props.teil?.name || x.name || '', zeichnungsnr: props.teil?.zeichnungsnr || '', bauteile: [
    { id: props.bauteilId, teilenummer: props.teil?.teilenummer ?? '', name: props.teil?.name ?? '', vorschaubild: props.teil?.vorschaubild ?? '', variante: '' },
    { id: x.id, teilenummer: x.teilenummer, name: x.name, vorschaubild: x.vorschaubild, variante: '' },
  ] } };
}
function gespeichert() { familieDialog.value = null; laden(); emit('familie'); }
</script>

<template>
  <section v-if="daten || laedt" class="rounded-2xl border border-line">
    <button type="button" class="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-left" @click="aufgeklappt = !aufgeklappt">
      <Sparkles :size="16" class="text-accent" />
      <span class="text-sm font-semibold">Ähnliche Bauteile</span>
      <span v-if="laedt && !daten" class="text-xs text-mute">suche …</span>
      <span v-else-if="!liste.length" class="text-xs text-mute">keine gefunden<template v-if="daten"> ({{ daten.verglichen }} Bauteile verglichen{{ daten.mitGeometrie ? ', mit Geometrie' : '' }})</template></span>
      <span v-else class="text-xs text-mute">{{ liste.length }} Treffer · am ähnlichsten <strong class="text-ink tnum">{{ liste[0].teilenummer }}</strong> ({{ liste[0].gruende[0] }})</span>
      <span v-if="daten && !daten.mitGeometrie" class="text-[11px] text-mute" title="Mit einem STEP-Modell wird auch die Geometrie verglichen">· ohne 3D-Vergleich</span>
      <ChevronDown :size="15" class="ml-auto text-mute transition" :class="aufgeklappt ? 'rotate-180' : ''" />
    </button>
    <div v-if="aufgeklappt && liste.length" class="divide-y divide-line border-t border-line px-4">
      <div v-for="x in liste" :key="x.id" class="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-2.5">
        <PartImage :teil="x" :groesse="44" />
        <div class="min-w-[180px] flex-1">
          <div class="flex flex-wrap items-center gap-2"><span class="font-medium tnum">{{ x.teilenummer }}</span><span class="truncate text-sm">{{ x.name }}</span><span class="rounded-full bg-surface2 px-2 py-0.5 text-[11px] tnum text-mute" title="Ähnlichkeit">{{ prozent(x.punkte) }}</span></div>
          <div class="text-xs text-mute">{{ x.kundeName }}<template v-if="x.material"> · {{ x.material }}</template><template v-if="x.zeichnungsnr"> · Zeichnung {{ x.zeichnungsnr }}</template></div>
          <div class="mt-1 flex flex-wrap gap-1">
            <span v-for="g in x.gruende" :key="g" class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]" :class="farbe(g)"><Box v-if="/geometrie|form/i.test(g)" :size="10" />{{ g }}</span>
            <span v-if="x.familie" class="inline-flex items-center gap-1 rounded-full bg-ok/10 px-2 py-0.5 text-[11px] text-ok"><Network :size="10" /> {{ x.familieName }}<template v-if="x.variante"> · {{ x.variante }}</template></span>
          </div>
        </div>
        <div class="text-right text-xs">
          <div v-if="x.letzterAuftrag" class="tnum"><RouterLink :to="`/auftraege/${x.letzterAuftrag.auftrag}`" class="text-accent hover:underline">{{ x.letzterAuftrag.auftrag }}</RouterLink> · <strong>{{ eur(x.letzterAuftrag.jeStueck) }}</strong> je Stk ({{ x.letzterAuftrag.menge }} Stk, {{ de(x.letzterAuftrag.datum) }})</div>
          <div v-if="x.letztesAngebot" class="tnum text-mute"><RouterLink :to="`/angebote/${x.letztesAngebot.angebot}`" class="hover:underline">{{ x.letztesAngebot.angebot }}</RouterLink> · {{ preisText(x.letztesAngebot, eur) }}</div>
          <div v-if="!x.letzterAuftrag && !x.letztesAngebot" class="text-mute">noch kein Preis</div>
        </div>
        <div v-if="aktionen" class="flex gap-1.5">
          <button v-if="x.letztesAngebot" type="button" class="btn !px-2.5 !py-1 text-xs" title="Zeiten, Maschinen, Material, Kosten, Staffeln und Arbeitsgänge aus dem letzten Angebot dieses Bauteils übernehmen" @click="emit('kalkulation', x.letztesAngebot)"><Copy :size="13" /> Kalkulation</button>
          <button type="button" class="btn !px-2.5 !py-1 text-xs" :disabled="!bauteilId" :title="bauteilId ? 'Als Varianten in einer Teilefamilie verknüpfen' : 'Erst das Angebot speichern, dann gibt es das Bauteil'" @click="familieBilden(x)"><Network :size="13" /> Familie</button>
        </div>
      </div>
    </div>
    <TeilefamilieDialog v-if="familieDialog" :familie="familieDialog.familie ?? null" :vorschlag="familieDialog.vorschlag ?? null" @schliessen="familieDialog = null" @gespeichert="gespeichert" />
  </section>
</template>
