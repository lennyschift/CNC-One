<script setup>
// Vorlagen für Lieferantenanfragen: welche Lieferanten bei welchem Werkstoff oder welcher Leistung gefragt werden.
import { computed, onMounted } from 'vue';
import { ListChecks } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';
import { useStammdaten } from '../stores/stammdaten.js';

const store = useStammdaten();
onMounted(() => store.laden('lieferant'));
const ISO = [['', '– keine –'], ['P', 'P Stahl'], ['M', 'M Rostfreier Stahl'], ['K', 'K Guss'], ['N', 'N NE-Metalle (Alu, Messing, Kupfer)'], ['S', 'S Superlegierungen, Titan'], ['H', 'H Harte Werkstoffe'], ['O', 'O Kunststoffe']];
const felder = computed(() => [
  { key: 'stichwoerter', label: 'Passt bei (Stichwörter, mit Komma)', hinweis: 'z. B. alu, en aw, almg' },
  { key: 'isoGruppe', label: 'oder Werkstoffgruppe', typ: 'auswahl', optionen: ISO.map(([wert, label]) => ({ wert, label })) },
  { key: 'art', label: 'Art der Anfrage', typ: 'auswahl', optionen: [{ wert: '', label: 'alle' }, { wert: 'Material', label: 'Material' }, { wert: 'Fremdvergabe', label: 'Fremdvergabe' }, { wert: 'Sonstiges', label: 'Sonstiges' }] },
  { key: 'lieferanten', label: 'Diese Lieferanten anfragen', typ: 'mehrfach', hinweis: 'Noch keine Lieferanten angelegt.', optionen: (store.listen.lieferant ?? []).filter((l) => l.aktiv).map((l) => ({ wert: l.name, label: l.name })) },
  { key: 'hinweis', label: 'Hinweis an die Lieferanten (wird vorgeschlagen)', typ: 'text-lang' },
]);
</script>

<template>
  <StammListe art="anfragevorlage" einzahl="Anfragevorlage" :icon="ListChecks" beschreibung="Welche Lieferanten bei welchem Werkstoff oder welcher Leistung angefragt werden. Passt eine Vorlage, sind ihre Lieferanten in der Anfrage schon gewählt." :felder="felder" :spalten="['stichwoerter', 'lieferanten']" />
</template>
