<script setup>
// Vorschau des Angebots als Dokument. Das Aussehen ist bewusst wie Papier und wird später
// durch das serverseitige Druckformat (PDF) in Frappe ersetzt.
import { computed } from 'vue';
import PartImage from './PartImage.vue';
import BelegKopf from './BelegKopf.vue';
import BelegFuss from './BelegFuss.vue';
import { useFirma } from '../stores/firma.js';
import { eur, zahl } from '../lib/format.js';

const props = defineProps({ angebot: { type: Object, required: true } });
const firma = useFirma();

const datum = computed(() => new Date(props.angebot.versandt ?? props.angebot.erstellt));
const gueltigBis = computed(() => {
  const d = new Date(datum.value);
  d.setDate(d.getDate() + 7 * (props.angebot.kopf.gueltigWochen || 4));
  return d;
});
const de = (d) => d.toLocaleDateString('de-DE');
const mwst = computed(() => props.angebot.netto * 0.19);
</script>

<template>
  <article class="paper mx-auto w-full max-w-[820px] px-12 py-10 text-[13px] leading-relaxed">
    <BelegKopf :firma="firma.firma" />

    <section class="mt-8 flex justify-between gap-8">
      <div>
        <div class="mb-1 text-[10px] uppercase tracking-wider text-neutral-400">Kunde</div>
        <div class="font-semibold">{{ angebot.kopf.kundeName }}</div>
        <div v-for="z in angebot.kopf.kunde.adresse" :key="z">{{ z }}</div>
        <div v-if="angebot.kopf.kunde.kontakt" class="mt-1 text-neutral-500">z. Hd. {{ angebot.kopf.kunde.kontakt.name }}</div>
      </div>
      <dl class="grid grid-cols-[auto_auto] gap-x-6 gap-y-0.5 self-start text-right">
        <dt class="text-neutral-500">Angebot</dt><dd class="font-semibold">{{ angebot.id }}</dd>
        <dt class="text-neutral-500">Datum</dt><dd>{{ de(datum) }}</dd>
        <dt class="text-neutral-500">Gültig bis</dt><dd>{{ de(gueltigBis) }}</dd>
        <template v-if="angebot.kopf.anfrageNr"><dt class="text-neutral-500">Ihre Anfrage</dt><dd>{{ angebot.kopf.anfrageNr }}</dd></template>
        <template v-if="angebot.kopf.kunde.lieferantennr"><dt class="text-neutral-500">Lieferanten-Nr.</dt><dd>{{ angebot.kopf.kunde.lieferantennr }}</dd></template>
      </dl>
    </section>

    <h2 class="mb-1 mt-8 text-lg font-semibold">Angebot</h2>
    <p class="mb-5 text-neutral-600">Vielen Dank für Ihre Anfrage. Gerne bieten wir Ihnen wie folgt an:</p>

    <div v-for="(p, i) in angebot.positionen" :key="p.key" class="break-inside-avoid border-t border-neutral-200 py-4">
      <div class="flex gap-4">
        <PartImage :teil="p.teil" :groesse="64" />
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline justify-between gap-4">
            <div><span class="mr-2 text-neutral-400">{{ i + 1 }}</span><span class="font-semibold">{{ p.teil.name }}</span></div>
            <div v-if="!p.teil.staffel.aktiv" class="whitespace-nowrap text-right">
              {{ p.ergebnis.menge }} Stk × {{ eur(p.ergebnis.zeilen[0]?.einzel) }} =
              <span class="font-semibold">{{ eur(p.ergebnis.zeilen[0]?.betrag) }}</span>
            </div>
          </div>
          <div class="text-[12px] text-neutral-500">
            <template v-if="p.teil.teilenummer">Teilenummer {{ p.teil.teilenummer }}</template>
            <template v-if="p.teil.zeichnungsnr"> · Zeichnung {{ p.teil.zeichnungsnr }}</template>
            <template v-if="p.teil.material"> · {{ p.teil.material }}</template>
          </div>

          <table v-if="p.teil.staffel.aktiv" class="mt-2 w-full max-w-sm text-[12px]">
            <thead><tr class="text-neutral-400"><th class="text-left font-normal">Menge</th><th class="text-right font-normal">Stückpreis</th><th class="text-right font-normal">Gesamt</th></tr></thead>
            <tbody>
              <tr v-for="s in p.ergebnis.stufen" :key="s.menge" class="border-t border-neutral-100">
                <td class="py-0.5">{{ s.menge }} Stk</td><td class="py-0.5 text-right">{{ eur(s.stueckpreis) }}</td><td class="py-0.5 text-right">{{ eur(s.gesamt) }}</td>
              </tr>
            </tbody>
          </table>

          <div v-for="z in p.ergebnis.zeilen.filter((x) => x.typ === 'kosten')" :key="z.label" class="mt-1 flex justify-between pl-4 text-[12px] text-neutral-600">
            <span>↳ {{ z.label }}</span><span>{{ eur(z.betrag) }}</span>
          </div>
        </div>
      </div>
    </div>

    <section class="mt-4 flex justify-end border-t-2 border-neutral-800 pt-3">
      <dl class="grid grid-cols-[auto_auto] gap-x-10 gap-y-0.5 text-right">
        <dt class="text-neutral-500">Summe netto<template v-if="angebot.positionen.some((p) => p.teil.staffel.aktiv)"> (kleinste Staffel)</template></dt><dd class="font-semibold">{{ eur(angebot.netto) }}</dd>
        <dt class="text-neutral-500">zzgl. 19 % MwSt.</dt><dd>{{ eur(mwst) }}</dd>
        <dt class="font-semibold">Gesamt</dt><dd class="font-bold">{{ eur(angebot.netto + mwst) }}</dd>
      </dl>
    </section>

    <footer class="mt-10 text-[12px] text-neutral-600">
      <p>Lieferzeit: {{ angebot.kopf.lieferzeit }}. Das Angebot ist {{ zahl(angebot.kopf.gueltigWochen, 0) }} Wochen gültig. Alle Preise netto zuzüglich gesetzlicher Mehrwertsteuer.</p>
      <p class="mt-3">Mit freundlichen Grüßen<br />{{ firma.firma.firmenname }}</p>
    </footer>
    <BelegFuss :firma="firma.firma" />
  </article>
</template>
