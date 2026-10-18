<script setup>
import { Cog } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';

const felder = [
  { key: 'satz', label: 'Stundensatz', typ: 'euro', suffix: '€/h' },
  { key: 'bemerkung', label: 'Bemerkung', typ: 'text-lang' },
];
</script>

<template>
  <StammListe art="maschine" einzahl="Maschine" :icon="Cog" beschreibung="Maschinen mit Stundensatz. Der Satz fließt in die Kalkulation der Arbeitsgänge ein." :felder="felder" :spalten="['satz', 'bemerkung']" />
</template>
