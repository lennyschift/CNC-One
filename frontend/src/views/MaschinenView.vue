<script setup>
import { computed } from 'vue';
import { Cog } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';
import { useStamm } from '../stores/stamm.js';

const stamm = useStamm();
// Welche Arbeitsgänge die Maschine kann: Auswahl aus den Arbeitsgangarten (leer = alle)
const felder = computed(() => [
  { key: 'arbeitsgaenge', label: 'Arbeitsgänge (keine Auswahl = alle)', typ: 'mehrfach', hinweis: 'Noch keine Arbeitsgangarten angelegt.', optionen: stamm.arten.filter((a) => a.typ === 'intern').map((a) => ({ wert: a.name, label: a.name })) },
  { key: 'satz', label: 'Stundensatz (Richtwert)', typ: 'euro', suffix: '€/h' },
  { key: 'stundenTag', label: 'Stunden je Arbeitstag', typ: 'zahl', suffix: 'h', decimals: 1 },
  { key: 'automation', label: 'Automation', typ: 'auswahl', optionen: [{ wert: 'nein', label: 'Nein' }, { wert: 'ja', label: 'Ja' }] },
  { key: 'bemerkung', label: 'Bemerkung', typ: 'text-lang' },
]);
</script>

<template>
  <StammListe art="maschine" einzahl="Maschine" :icon="Cog" beschreibung="Maschinen mit den Arbeitsgängen, die sie können. Die verfügbaren Stunden je Tag zählen für die Auslastung in der Fertigung, der Stundensatz ist ein Richtwert für die Kalkulation." :felder="felder" :spalten="['arbeitsgaenge', 'stundenTag', 'automation', 'satz']" />
</template>
