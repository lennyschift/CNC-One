<script setup>
import { Layers } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';

const felder = [
  { key: 'preisKg', label: 'Preis je Kilogramm', typ: 'euro', suffix: '€/kg' },
  { key: 'dichte', label: 'Dichte', typ: 'zahl', suffix: 'g/cm³', decimals: 2 },
];
</script>

<template>
  <StammListe art="material" einzahl="Rohmaterial" :icon="Layers" beschreibung="Rohmaterial mit Preis je Kilogramm, aus dem die Materialkosten im Angebot entstehen." :felder="felder" :spalten="['preisKg', 'dichte']" />
</template>
