<script setup>
// Alles, was ein Lieferant zu einer Position anbietet, kompakt in einer Vergleichszelle: Werkstoff und Zustand, Form und
// Maße, Herstellung/Oberfläche (gewalzt, Gussplatte, beidseitig plangefräst …), Toleranzen, Stück/kg/m, Preis mit
// Preiseinheit (und umgerechnet je kg bzw. je Stück, damit sich Angebote vergleichen lassen) und Liefertermin.
// Was von der Anfrage bzw. der Vergleichszeile abweicht (`abw`: [{ feld, angeboten, erwartet }]), ist orange markiert.
import { computed } from 'vue';
import { AlertTriangle, Truck, Ruler } from '@lucide/vue';
import { eur, zahl } from '../lib/format.js';

const props = defineProps({
  o: { type: Object, required: true },
  abw: { type: Array, default: () => [] },
  termin: { type: Boolean, default: true },
  schnell: { type: Boolean, default: false }, // frühester Liefertermin der Zeile: grün
});
const terminText = computed(() => (props.o.lieferdatum ? new Date(props.o.lieferdatum).toLocaleDateString('de-DE') : String(props.o.liefertermin ?? '').slice(0, 30)));
const anders = (feld) => props.abw.find((a) => a.feld === feld) ?? null;
const titel = (feld) => { const a = anders(feld); return a ? `${feld} weicht ab: angeboten ${a.angeboten}, erwartet ${a.erwartet}` : ''; };
const material = computed(() => [props.o.werkstoff, props.o.zustand].filter(Boolean).join(' '));
const masse = computed(() => {
  const m = (props.o.masse ?? []).map((x) => zahl(x, x % 1 ? 1 : 0));
  if (!m.length) return props.o.abmessung || '';
  return props.o.form === 'Rund' ? `Ø${m[0]}${m.length > 1 ? ` × ${m.slice(1).join(' × ')}` : ''} mm` : `${m.join(' × ')} mm`;
});
const mengen = computed(() => [props.o.stueck != null && `${zahl(props.o.stueck, 0)} Stk`, props.o.kg != null && `${zahl(props.o.kg, 2)} kg`, props.o.meter != null && `${zahl(props.o.meter, 2)} m`].filter(Boolean).join(' · '));
// Preis wie angeboten, dazu umgerechnet: bei Preis je kg der Stückpreis, bei Preis je Stück der kg-Preis
const preis = computed(() => {
  const o = props.o;
  const b = Number(o.betrag) || 0;
  const teile = [];
  if (o.preis) teile.push(`${eur(o.preis)}/${o.preisJe || 'Stk'}`);
  if (b && o.preisJe !== 'kg' && Number(o.kg) > 0) teile.push(`≈ ${eur(b / o.kg)}/kg`);
  if (b && o.preisJe !== 'Stk' && Number(o.stueck) > 0) teile.push(`≈ ${eur(b / o.stueck)}/Stk`);
  return teile.join(' · ');
});
</script>

<template>
  <div class="space-y-0.5 text-[11px] leading-snug">
    <div v-if="material" :class="anders('Werkstoff') || anders('Zustand') ? 'font-semibold text-warn' : 'text-mute'" :title="titel('Werkstoff') || titel('Zustand')">
      <AlertTriangle v-if="anders('Werkstoff') || anders('Zustand')" :size="10" class="mr-0.5 inline" />{{ material }}
    </div>
    <div v-if="o.form || masse" :class="anders('Form') || anders('Maße') ? 'font-semibold text-warn' : 'text-mute'" :title="titel('Form') || titel('Maße')">
      <AlertTriangle v-if="anders('Form') || anders('Maße')" :size="10" class="mr-0.5 inline" />{{ [o.form, masse].filter(Boolean).join(' ') }}
    </div>
    <div v-if="o.merkmale?.length" class="flex flex-wrap justify-end gap-0.5">
      <span v-for="m in o.merkmale" :key="m" class="rounded bg-surface2 px-1 text-[10px] text-ink">{{ m }}</span>
    </div>
    <div v-for="t in o.toleranzen ?? []" :key="t" class="text-[10px] text-mute" :title="t"><Ruler :size="9" class="mr-0.5 inline" />{{ t.length > 42 ? `${t.slice(0, 40)}…` : t }}</div>
    <div v-if="mengen" class="text-mute tnum">{{ mengen }}</div>
    <div v-if="preis" class="text-mute tnum">{{ preis }}</div>
    <div v-if="termin && o.liefertermin" class="pt-0.5"><span class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold" :class="schnell ? 'bg-ok/15 text-ok' : 'bg-surface2 text-ink'" :title="`Liefertermin laut Angebot: ${o.liefertermin}${schnell ? ' (schnellster)' : ''}`"><Truck :size="12" /> {{ terminText }}</span></div>
  </div>
</template>
