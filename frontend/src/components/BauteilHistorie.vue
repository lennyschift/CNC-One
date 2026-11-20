<script setup>
// Historie eines Bauteils: frühere Angebote, Aufträge und Fertigungen. Gelesen wird bei jedem Öffnen aus den Belegen
// (api/historie.py), gespeichert wird am Bauteil nichts. Mit `aktionen` (Workbench) lassen sich frühere Preise übernehmen.
import { ref, computed, watch } from 'vue';
import { History, FileText, ClipboardList, Factory, Copy, Tag, ChevronDown } from '@lucide/vue';
import StatusBadge from './StatusBadge.vue';
import { call } from '../data/api.js';
import { eur } from '../lib/format.js';
import { preisText } from '../lib/historie.js';

const props = defineProps({
  bauteilId: { type: String, default: '' },
  kundeId: { type: String, default: '' },
  teilenummer: { type: String, default: '' },
  ohneAngebot: { type: String, default: '' },
  aktionen: { type: Boolean, default: false },
  offen: { type: Boolean, default: true },
});
const emit = defineEmits(['kalkulation', 'festpreis']);

const daten = ref(null);
const laedt = ref(false);
const reiter = ref('auftraege');
const aufgeklappt = ref(props.offen);
let zaehler = 0;
let warten = null;

async function laden() {
  if (!props.bauteilId && !(props.kundeId && props.teilenummer.trim())) { daten.value = null; return; }
  const nr = ++zaehler;
  laedt.value = true;
  try {
    const d = await call('cnc_one.api.historie.historie', { bauteil: props.bauteilId, kunde: props.kundeId, teilenummer: props.teilenummer, ohne_angebot: props.ohneAngebot });
    if (nr !== zaehler) return;
    daten.value = d;
    // der Reiter mit Inhalt zuerst
    if (!d.auftraege.length && d.angebote.length) reiter.value = 'angebote';
  } catch { if (nr === zaehler) daten.value = null; } finally { if (nr === zaehler) laedt.value = false; }
}
watch(() => [props.bauteilId, props.kundeId, props.teilenummer, props.ohneAngebot], () => { clearTimeout(warten); warten = setTimeout(laden, 400); }, { immediate: true });

const k = computed(() => daten.value?.kennzahlen ?? null);
const leer = computed(() => daten.value && !daten.value.angebote.length && !daten.value.auftraege.length && !daten.value.fertigungen.length);
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const kostenSumme = (liste) => (liste ?? []).reduce((s, x) => s + (x.betrag || 0), 0);
const minuten = (ags) => ags.filter((a) => a.ruestMin || a.stueckMin).map((a) => `${a.name || a.maschine}: ${a.ruestMin} + ${a.stueckMin} min`).join(' · ');
const reiterListe = computed(() => [
  { id: 'auftraege', label: 'Aufträge', icon: ClipboardList, n: daten.value?.auftraege.length ?? 0 },
  { id: 'angebote', label: 'Angebote', icon: FileText, n: daten.value?.angebote.length ?? 0 },
  { id: 'fertigung', label: 'Fertigung', icon: Factory, n: daten.value?.fertigungen.length ?? 0 },
]);
defineExpose({ laden });
</script>

<template>
  <section v-if="daten || laedt" class="rounded-2xl border border-line">
    <button type="button" class="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-left" @click="aufgeklappt = !aufgeklappt">
      <History :size="16" class="text-accent" />
      <span class="text-sm font-semibold">Historie</span>
      <span v-if="laedt && !daten" class="text-xs text-mute">lädt …</span>
      <span v-else-if="leer" class="text-xs text-mute">noch nichts angeboten oder bestellt</span>
      <span v-else-if="k" class="text-xs text-mute">
        {{ k.auftraege }} {{ k.auftraege === 1 ? 'Auftrag' : 'Aufträge' }} · {{ k.stueck }} Stk · {{ k.angebote }} {{ k.angebote === 1 ? 'Angebot' : 'Angebote' }}
        <template v-if="k.letzterAuftrag"> · zuletzt <strong class="text-ink">{{ eur(k.letzterAuftrag.jeStueck) }}</strong> je Stück ({{ k.letzterAuftrag.menge }} Stk, {{ de(k.letzterAuftrag.datum) }})</template>
      </span>
      <ChevronDown :size="15" class="ml-auto text-mute transition" :class="aufgeklappt ? 'rotate-180' : ''" />
    </button>

    <div v-if="aufgeklappt && daten && !leer" class="border-t border-line px-4 pb-4 pt-3">
      <div class="mb-3 flex gap-1.5">
        <button v-for="r in reiterListe" :key="r.id" type="button" class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs transition" :class="reiter === r.id ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:bg-surface2'" @click="reiter = r.id">
          <component :is="r.icon" :size="13" /> {{ r.label }} <span class="tnum opacity-70">{{ r.n }}</span>
        </button>
      </div>

      <!-- Aufträge -->
      <div v-if="reiter === 'auftraege'" class="divide-y divide-line">
        <p v-if="!daten.auftraege.length" class="py-2 text-xs text-mute">Noch kein Auftrag.</p>
        <div v-for="a in daten.auftraege" :key="a.auftrag + a.positionKey" class="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm" :class="a.status === 'Storniert' ? 'opacity-50' : ''">
          <RouterLink :to="`/auftraege/${a.auftrag}`" class="font-medium text-accent tnum hover:underline">{{ a.auftrag }}</RouterLink>
          <span class="text-xs text-mute">{{ de(a.datum) }}<template v-if="a.kundenbestellnr"> · Best. {{ a.kundenbestellnr }}</template><template v-if="a.revision"> · Rev. {{ a.revision }}</template></span>
          <StatusBadge :status="a.status" />
          <span class="tnum">{{ a.menge }} Stk × {{ eur(a.einzelpreis) }}<span v-if="a.kosten.length" class="text-mute"> + {{ eur(kostenSumme(a.kosten)) }} Kosten</span></span>
          <span v-if="a.preisform === 'Bestellung'" class="rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute" title="Der Kunde hat die Kosten auf den Stückpreis umgelegt bestellt">Preis laut Bestellung</span>
          <span class="ml-auto text-xs text-mute tnum">= {{ eur(a.jeStueck) }} je Stück</span>
          <button v-if="aktionen" type="button" class="btn !px-2.5 !py-1 text-xs" title="Diesen Stückpreis (inklusive Kosten) als festen Preis übernehmen" @click="emit('festpreis', a, true)"><Tag :size="13" /> Preis übernehmen</button>
        </div>
      </div>

      <!-- Angebote -->
      <div v-if="reiter === 'angebote'" class="divide-y divide-line">
        <p v-if="!daten.angebote.length" class="py-2 text-xs text-mute">Noch kein früheres Angebot.</p>
        <div v-for="a in daten.angebote" :key="a.angebot + a.positionKey" class="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm">
          <RouterLink :to="`/angebote/${a.angebot}`" class="font-medium text-accent tnum hover:underline">{{ a.angebot }}</RouterLink>
          <span class="text-xs text-mute">{{ de(a.datum) }}<template v-if="a.revision"> · Rev. {{ a.revision }}</template></span>
          <StatusBadge :status="a.status" />
          <span v-if="a.beauftragt" class="rounded-full bg-ok/10 px-2 py-0.5 text-[11px] font-medium text-ok">beauftragt</span>
          <span class="tnum">{{ preisText(a, eur) }}<span v-if="a.kosten.length" class="text-mute"> + {{ eur(kostenSumme(a.kosten)) }} Kosten</span></span>
          <span v-if="a.preisart === 'fest'" class="text-[11px] text-mute">fester Preis</span>
          <div v-if="aktionen" class="ml-auto flex gap-1.5">
            <button type="button" class="btn !px-2.5 !py-1 text-xs" title="Zeiten, Maschinen, Material, Kosten, Staffeln und Arbeitsgänge dieses Angebots übernehmen" @click="emit('kalkulation', a)"><Copy :size="13" /> Kalkulation übernehmen</button>
            <button type="button" class="btn !px-2.5 !py-1 text-xs" title="Die Stückpreise dieses Angebots als festen Preis übernehmen" @click="emit('festpreis', a, false)"><Tag :size="13" /> Preise übernehmen</button>
          </div>
        </div>
      </div>

      <!-- Fertigung -->
      <div v-if="reiter === 'fertigung'" class="divide-y divide-line">
        <p v-if="!daten.fertigungen.length" class="py-2 text-xs text-mute">Noch nicht gefertigt.</p>
        <div v-for="f in daten.fertigungen" :key="f.id" class="py-2 text-sm">
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
            <RouterLink :to="`/fertigung/${f.id}`" class="font-medium text-accent tnum hover:underline">{{ f.id }}</RouterLink>
            <span class="text-xs text-mute">zu {{ f.auftrag }}<template v-if="f.von"> · gebucht {{ de(f.von) }}<template v-if="de(f.bis) !== de(f.von)"> bis {{ de(f.bis) }}</template></template></span>
            <StatusBadge :status="f.status" />
            <span class="tnum">{{ f.produziert }} / {{ f.menge }} Stk<span v-if="f.ueberproduktion" class="text-mute"> (+{{ f.ueberproduktion }})</span></span>
          </div>
          <div v-if="minuten(f.arbeitsgaenge)" class="mt-0.5 text-xs text-mute">Geplant: {{ minuten(f.arbeitsgaenge) }}</div>
          <div v-if="f.rohmaterial" class="mt-0.5 text-xs text-mute">Rohmaterial: {{ f.rohmaterial }}</div>
          <div v-if="f.bemerkungen" class="mt-1 whitespace-pre-line rounded-lg bg-surface2 px-2.5 py-1.5 text-xs"><span class="font-medium">Bemerkungen:</span> {{ f.bemerkungen }}</div>
          <div v-if="f.pruefmasse" class="mt-1 whitespace-pre-line rounded-lg bg-surface2 px-2.5 py-1.5 text-xs"><span class="font-medium">Prüfmaße:</span> {{ f.pruefmasse }}</div>
        </div>
      </div>
    </div>
  </section>
</template>
