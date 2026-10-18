<script setup>
// Lieferschein als Dokument (Papier). Bewusst ohne Preise und Kosten. Wird später durch das Druckformat in Frappe ersetzt.
import PartImage from './PartImage.vue';
import { bereichText } from '../lib/serien.js';

defineProps({ lieferschein: { type: Object, required: true } });
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
</script>

<template>
  <article class="paper mx-auto w-full max-w-[820px] px-12 py-10 text-[13px] leading-relaxed">
    <header class="flex items-start justify-between border-b-2 pb-5" style="border-color: #d4242a">
      <div>
        <div class="text-2xl font-bold tracking-wide" style="color: #d4242a">HOHENSTEIN</div>
        <div class="text-[11px] uppercase tracking-[0.2em] text-neutral-500">CNC-Fertigung</div>
      </div>
      <div class="text-right text-[11px] text-neutral-500">
        <div>Hohenstein GmbH</div>
        <div>Musterstraße 1 · 72000 Beispielstadt</div>
      </div>
    </header>

    <section class="mt-8 flex justify-between gap-8">
      <div>
        <div class="mb-1 text-[10px] uppercase tracking-wider text-neutral-400">Lieferanschrift</div>
        <div v-for="(z, i) in lieferschein.adresse" :key="z" :class="i === 0 ? 'font-semibold' : ''">{{ z }}</div>
      </div>
      <dl class="grid grid-cols-[auto_auto] gap-x-6 gap-y-0.5 self-start text-right">
        <dt class="text-neutral-500">Lieferschein</dt><dd class="font-semibold">{{ lieferschein.id }}</dd>
        <dt class="text-neutral-500">Datum</dt><dd>{{ de(lieferschein.gelieferAm || lieferschein.lieferdatum || lieferschein.erstellt) }}</dd>
        <template v-if="lieferschein.kundenbestellnr"><dt class="text-neutral-500">Ihre Bestellung</dt><dd>{{ lieferschein.kundenbestellnr }}</dd></template>
      </dl>
    </section>

    <h2 class="mb-1 mt-8 text-lg font-semibold">Lieferschein</h2>
    <p class="mb-5 text-neutral-600">Wir liefern Ihnen folgende Bauteile:</p>

    <div v-for="(p, i) in lieferschein.positionen" :key="i" class="break-inside-avoid border-t border-neutral-200 py-4">
      <div class="flex gap-4">
        <PartImage :teil="p.teil" :groesse="56" />
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline justify-between gap-4">
            <div><span class="mr-2 text-neutral-400">{{ i + 1 }}</span><span class="font-semibold">{{ p.teil.name }}</span></div>
            <div class="whitespace-nowrap font-semibold">{{ p.menge }} Stk</div>
          </div>
          <div class="mt-0.5 text-neutral-500">
            <span v-if="p.teil.teilenummer">Teilenummer {{ p.teil.teilenummer }}</span><span v-if="p.teil.zeichnungsnr"> · Zeichnung {{ p.teil.zeichnungsnr }}</span><span v-if="p.auftragId"> · Auftrag {{ p.auftragId }}</span>
          </div>
          <div v-if="p.serienVon" class="mt-0.5">Seriennummern <span class="font-semibold tnum">{{ bereichText(p.serienVon, p.serienBis, p.serienStellen) }}</span></div>
        </div>
      </div>
    </div>

    <p v-if="lieferschein.bemerkung" class="mt-6 border-t border-neutral-200 pt-4 text-neutral-600">{{ lieferschein.bemerkung }}</p>
    <footer class="mt-12 grid grid-cols-2 gap-10 text-[11px] text-neutral-500">
      <div class="border-t border-neutral-300 pt-1">Datum, Unterschrift Warenausgang</div>
      <div class="border-t border-neutral-300 pt-1">Datum, Unterschrift Empfänger</div>
    </footer>
  </article>
</template>
