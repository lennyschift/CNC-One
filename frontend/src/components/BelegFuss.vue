<script setup>
// Fußzeile der Belege: Steuernummer, USt-IdNr., Register, Geschäftsführer.
defineProps({ firma: { type: Object, default: null } });
</script>

<template>
  <footer v-if="firma" class="mt-10 grid gap-x-8 gap-y-1 border-t border-neutral-300 pt-3 text-[10px] leading-relaxed text-neutral-500 sm:grid-cols-3">
    <div><div class="font-semibold">{{ firma.firmenname }}<template v-if="firma.rechtsform"> {{ firma.rechtsform }}</template></div><div v-for="z in firma.adresse" :key="z">{{ z }}</div></div>
    <div>
      <div v-if="firma.steuernummer">Steuernummer {{ firma.steuernummer }}</div>
      <div v-if="firma.ustId">USt-IdNr. {{ firma.ustId }}</div>
      <div v-if="firma.handelsregister">{{ firma.handelsregister }}</div>
      <div v-if="firma.geschaeftsfuehrer">Geschäftsführer: {{ firma.geschaeftsfuehrer }}</div>
    </div>
    <div><div v-for="b in firma.banken" :key="b.iban">{{ b.bezeichnung }}: {{ b.iban }}<template v-if="b.bic"> · {{ b.bic }}</template></div></div>
  </footer>
</template>
