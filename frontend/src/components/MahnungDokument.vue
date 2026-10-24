<script setup>
// Mahnung als Dokument (Papier): Zahlungserinnerung, 1. Mahnung, 2. Mahnung.
import BelegKopf from './BelegKopf.vue';
import BelegFuss from './BelegFuss.vue';
import { eur } from '../lib/format.js';

defineProps({ mahnung: { type: Object, required: true } });
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
</script>

<template>
  <article class="paper relative mx-auto w-full max-w-[820px] px-12 py-10 text-[13px] leading-relaxed">
    <div v-if="mahnung.status === 'Zurückgezogen'" class="pointer-events-none absolute right-10 top-24 rotate-[-8deg] rounded-lg border-2 border-neutral-300 px-4 py-1 text-3xl font-bold tracking-widest text-neutral-300">ZURÜCKGEZOGEN</div>
    <BelegKopf :firma="mahnung.firma" />

    <section class="mt-8 flex justify-between gap-8">
      <div>
        <div class="mb-1 text-[10px] uppercase tracking-wider text-neutral-400">Empfänger</div>
        <div v-for="(z, i) in mahnung.adresse" :key="z" :class="i === 0 ? 'font-semibold' : ''">{{ z }}</div>
      </div>
      <dl class="grid grid-cols-[auto_auto] gap-x-6 gap-y-0.5 self-start text-right">
        <dt class="text-neutral-500">Datum</dt><dd>{{ de(mahnung.datum) }}</dd>
        <dt class="text-neutral-500">Rechnung</dt><dd class="font-semibold">{{ mahnung.rechnungNummer }}</dd>
        <dt class="text-neutral-500">Rechnungsdatum</dt><dd>{{ de(mahnung.rechnungsdatum) }}</dd>
        <dt class="text-neutral-500">Zahlen bis</dt><dd class="font-semibold">{{ de(mahnung.fristBis) }}</dd>
      </dl>
    </section>

    <h2 class="mb-4 mt-8 text-lg font-semibold">{{ mahnung.stufe }} zur Rechnung {{ mahnung.rechnungNummer }}</h2>
    <p class="whitespace-pre-line text-neutral-700">{{ mahnung.text }}</p>

    <table class="mt-6 w-full max-w-md text-left">
      <tbody>
        <tr class="border-b border-neutral-200"><td class="py-1.5 text-neutral-500">Offener Rechnungsbetrag</td><td class="py-1.5 text-right tnum">{{ eur(mahnung.offenerBetrag) }}</td></tr>
        <tr v-if="mahnung.gebuehr" class="border-b border-neutral-200"><td class="py-1.5 text-neutral-500">Mahngebühr</td><td class="py-1.5 text-right tnum">{{ eur(mahnung.gebuehr) }}</td></tr>
        <tr><td class="pt-2 font-semibold">Zu zahlen bis {{ de(mahnung.fristBis) }}</td><td class="pt-2 text-right text-base font-bold tnum">{{ eur(mahnung.offenerBetrag + mahnung.gebuehr) }}</td></tr>
      </tbody>
    </table>

    <section v-if="mahnung.firma?.banken?.length" class="mt-8 text-[12px] text-neutral-600">
      <p class="font-medium text-neutral-800">Bitte überweisen Sie unter Angabe der Rechnungsnummer {{ mahnung.rechnungNummer }} auf eines unserer Konten:</p>
      <p v-for="b in mahnung.firma.banken" :key="b.iban">{{ b.bezeichnung }}: IBAN {{ b.iban }}<template v-if="b.bic">, BIC {{ b.bic }}</template></p>
    </section>
    <p class="mt-6 text-neutral-600">Mit freundlichen Grüßen<br />{{ mahnung.firma?.firmenname }}</p>
    <BelegFuss :firma="mahnung.firma" />
  </article>
</template>
