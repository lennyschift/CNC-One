<script setup>
import { Layers } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';
import { ISO_GRUPPEN, isoAusName } from '../lib/iso.js';

const felder = [
  { key: 'preisKg', label: 'Preis je Kilogramm', typ: 'euro', suffix: '€/kg' },
  { key: 'dichte', label: 'Dichte', typ: 'zahl', suffix: 'g/cm³', decimals: 2 },
  {
    key: 'isoGruppe', label: 'ISO-Gruppe (Zerspanung)', typ: 'auswahl',
    optionen: [{ wert: '', label: 'Automatisch aus dem Namen' }, ...Object.values(ISO_GRUPPEN).map((g) => ({ wert: g.code, label: `${g.code} · ${g.name}` }))],
    leer: (x) => (isoAusName(x.name) ? `${isoAusName(x.name)} (automatisch)` : '–'),
  },
  { key: 'schreibweisen', label: 'Schreibweisen auf Zeichnungen (eine je Zeile, z. B. X5CrNi18-10)', typ: 'text-lang' },
];
</script>

<template>
  <StammListe art="material" einzahl="Rohmaterial" :icon="Layers" beschreibung="Rohmaterial mit Preis je Kilogramm, aus dem die Materialkosten im Angebot entstehen." :felder="felder" :spalten="['preisKg', 'dichte', 'isoGruppe']" />
</template>
