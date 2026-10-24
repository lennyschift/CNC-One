<script setup>
// Rechnung als Dokument (Papier). Zeigt je Bauteil, mit welchen Lieferscheinen es geliefert wurde. Wird später durch das
// serverseitige Druckformat mit E-Rechnung (ZUGFeRD/XRechnung) ersetzt.
import { computed } from 'vue';
import BelegKopf from './BelegKopf.vue';
import BelegFuss from './BelegFuss.vue';
import PartImage from './PartImage.vue';
import { eur } from '../lib/format.js';
import { useFirma } from '../stores/firma.js';

const props = defineProps({ rechnung: { type: Object, required: true } });
const aktuelleFirma = useFirma();
// Festgeschriebene Rechnungen zeigen die Firmendaten von damals, Entwürfe die aktuellen
const firma = computed(() => props.rechnung.firma ?? aktuelleFirma.firma);
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const storno = computed(() => props.rechnung.art === 'Storno');
const leistung = computed(() => {
  const { leistungVon: v, leistungBis: b } = props.rechnung;
  if (!v) return '';
  return v === b ? de(v) : `${de(v)} bis ${de(b)}`;
});
</script>

<template>
  <article class="paper relative mx-auto w-full max-w-[820px] px-12 py-10 text-[13px] leading-relaxed">
    <div v-if="rechnung.status === 'Entwurf'" class="pointer-events-none absolute right-10 top-24 rotate-[-8deg] rounded-lg border-2 border-neutral-300 px-4 py-1 text-3xl font-bold tracking-widest text-neutral-300">ENTWURF</div>
    <div v-else-if="rechnung.status === 'Storniert'" class="pointer-events-none absolute right-10 top-24 rotate-[-8deg] rounded-lg border-2 px-4 py-1 text-3xl font-bold tracking-widest" style="border-color: #d4242a55; color: #d4242a55">STORNIERT</div>

    <BelegKopf :firma="firma" />

    <section class="mt-8 flex justify-between gap-8">
      <div>
        <div class="mb-1 text-[10px] uppercase tracking-wider text-neutral-400">Rechnungsempfänger</div>
        <div v-for="(z, i) in rechnung.adresse" :key="z" :class="i === 0 ? 'font-semibold' : ''">{{ z }}</div>
        <div v-if="rechnung.kundeUstId" class="mt-1 text-neutral-500">USt-IdNr. {{ rechnung.kundeUstId }}</div>
        <div v-if="rechnung.leitwegId" class="text-neutral-500">Leitweg-ID {{ rechnung.leitwegId }}</div>
      </div>
      <dl class="grid grid-cols-[auto_auto] gap-x-6 gap-y-0.5 self-start text-right">
        <dt class="text-neutral-500">{{ storno ? 'Stornorechnung' : 'Rechnung' }}</dt><dd class="font-semibold">{{ rechnung.nummer || 'Entwurf' }}</dd>
        <dt class="text-neutral-500">Datum</dt><dd>{{ de(rechnung.rechnungsdatum) }}</dd>
        <template v-if="leistung"><dt class="text-neutral-500">Leistungsdatum</dt><dd>{{ leistung }}</dd></template>
        <template v-if="!storno"><dt class="text-neutral-500">Fällig am</dt><dd>{{ de(rechnung.faelligAm) }}</dd></template>
        <template v-if="rechnung.kundenbestellnr"><dt class="text-neutral-500">Ihre Bestellung</dt><dd>{{ rechnung.kundenbestellnr }}</dd></template>
        <dt class="text-neutral-500">Unser Auftrag</dt><dd>{{ rechnung.auftragId }}</dd>
        <template v-if="storno"><dt class="text-neutral-500">Storno zu</dt><dd>{{ rechnung.stornoZu }}</dd></template>
      </dl>
    </section>

    <h2 class="mb-1 mt-8 text-lg font-semibold">{{ storno ? 'Stornorechnung' : 'Rechnung' }}<span v-if="rechnung.art === 'Teilrechnung'" class="ml-2 text-sm font-normal text-neutral-500">(Teilrechnung)</span></h2>
    <p v-if="rechnung.einleitung" class="mb-5 whitespace-pre-line text-neutral-600">{{ rechnung.einleitung }}</p>

    <table class="w-full text-left">
      <thead>
        <tr class="border-b border-neutral-300 text-[11px] uppercase tracking-wider text-neutral-400">
          <th class="w-10 py-1.5 font-medium">Pos.</th><th class="py-1.5 font-medium">Beschreibung</th><th class="w-24 py-1.5 text-right font-medium">Menge</th><th class="w-24 py-1.5 text-right font-medium">Einzelpreis</th><th class="w-28 py-1.5 text-right font-medium">Betrag</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in rechnung.positionen" :key="p.zeile" class="break-inside-avoid border-b border-neutral-100 align-top" :class="p.art === 'Sonderkosten' ? 'text-neutral-600' : ''">
          <td class="py-2.5 text-neutral-400 tnum">{{ p.zeile }}</td>
          <td class="py-2.5 pr-3">
            <div class="flex gap-3">
              <PartImage v-if="p.art === 'Bauteil'" :teil="p.teil" :groesse="40" />
              <div class="min-w-0" :class="p.art === 'Sonderkosten' ? 'pl-3' : ''">
                <div :class="p.art === 'Bauteil' ? 'font-semibold' : ''">{{ p.bezeichnung }}</div>
                <div v-if="p.teil.teilenummer || p.teil.zeichnungsnr" class="text-[12px] text-neutral-500"><span v-if="p.teil.teilenummer">Teilenummer {{ p.teil.teilenummer }}</span><span v-if="p.teil.zeichnungsnr"> · Zeichnung {{ p.teil.zeichnungsnr }}</span></div>
                <div v-if="p.lieferungenText" class="text-[12px] text-neutral-500">{{ p.lieferungenText }}</div>
                <div v-if="p.serienText" class="text-[12px] text-neutral-500">Seriennummern <span class="tnum">{{ p.serienText }}</span></div>
              </div>
            </div>
          </td>
          <td class="whitespace-nowrap py-2.5 text-right tnum">{{ p.art === 'Bauteil' ? `${p.menge} ${p.einheit}` : '' }}</td>
          <td class="whitespace-nowrap py-2.5 text-right tnum">{{ p.art === 'Bauteil' ? eur(p.einzelpreis) : '' }}</td>
          <td class="whitespace-nowrap py-2.5 text-right font-medium tnum">{{ eur(p.netto) }}</td>
        </tr>
      </tbody>
    </table>

    <div class="mt-4 flex justify-end">
      <dl class="grid w-72 grid-cols-[1fr_auto] gap-x-6 gap-y-0.5 text-right">
        <dt class="text-neutral-500">Summe netto</dt><dd class="tnum">{{ eur(rechnung.netto) }}</dd>
        <dt class="text-neutral-500">zzgl. {{ rechnung.steuersatz }} % Umsatzsteuer</dt><dd class="tnum">{{ eur(rechnung.steuerbetrag) }}</dd>
        <dt class="mt-1 border-t border-neutral-300 pt-1 font-semibold">Rechnungsbetrag</dt><dd class="mt-1 border-t border-neutral-300 pt-1 text-base font-bold tnum">{{ eur(rechnung.brutto) }}</dd>
      </dl>
    </div>

    <section v-if="!storno && rechnung.zahlungshinweis" class="mt-8 break-inside-avoid text-neutral-600">
      <p class="font-medium text-neutral-800">Zahlbar bis {{ de(rechnung.faelligAm) }} ohne Abzug.</p>
      <p class="mt-1 whitespace-pre-line text-[12px]">{{ rechnung.zahlungshinweis }}</p>
    </section>
    <p v-if="rechnung.bemerkung" class="mt-4 whitespace-pre-line text-neutral-600">{{ rechnung.bemerkung }}</p>
    <p v-if="rechnung.fusstext" class="mt-4 text-[12px] text-neutral-500">{{ rechnung.fusstext }}</p>

    <BelegFuss :firma="firma" />
  </article>
</template>
