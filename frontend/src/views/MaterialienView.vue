<script setup>
import { Layers } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';

const felder = [
  { key: 'preisKg', label: 'Preis je Kilogramm', typ: 'euro', suffix: '€/kg' },
  { key: 'dichte', label: 'Dichte', typ: 'zahl', suffix: 'g/cm³', decimals: 2 },
];
</script>

<template>
  <StammListe art="material" einzahl="Material" :icon="Layers" beschreibung="Werkstoffe mit Preis je Kilogramm, aus denen die Materialkosten im Angebot entstehen." :felder="felder" :spalten="['preisKg', 'dichte']" />
</template>
