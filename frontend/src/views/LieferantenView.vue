<script setup>
import { Truck } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';

const felder = [
  { key: 'leistung', label: 'Leistung', hinweis: 'z. B. Härten, Eloxieren' },
  { key: 'email', label: 'E-Mail' },
  { key: 'weitereEmails', label: 'Weitere E-Mail-Adressen', typ: 'text-lang', hinweis: 'eine je Zeile, z. B. rechnung@… – Mails von dort kommen in den Posteingang' },
  { key: 'ustId', label: 'USt-IdNr.', hinweis: 'ordnet E-Rechnungen dem Lieferanten zu' },
  { key: 'telefon', label: 'Telefon' },
  { key: 'adresse', label: 'Adresse', typ: 'text-lang' },
];
</script>

<template>
  <StammListe art="lieferant" einzahl="Lieferant" :icon="Truck" beschreibung="Lieferanten für Fremdvergabe und Lieferantenanfragen." :felder="felder" :spalten="['leistung', 'email', 'telefon']" />
</template>
