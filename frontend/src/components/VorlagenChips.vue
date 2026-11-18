<script setup>
// Vorlagen für Lieferantenanfragen (Stammdaten → Anfragevorlagen): passt eine zum Werkstoff, zur Bezeichnung oder zum
// Arbeitsgang, werden ihre Lieferanten automatisch gewählt (einmal je Vorlage); jede Vorlage lässt sich auch anklicken.
import { computed, onMounted, ref, watch } from 'vue';
import { Sparkles, Settings2 } from '@lucide/vue';
import { useStammdaten } from '../stores/stammdaten.js';
import { passendeVorlagen } from '../lib/vergleich.js';

const props = defineProps({
  kontext: { type: Object, required: true }, // { art, texte: [Werkstoffe, Bezeichnungen, Arbeitsgänge] }
  lieferanten: { type: Array, required: true }, // [{ id, name }]
  gewaehlt: { type: Object, required: true }, // { [lieferantId]: true }
});
const notiz = defineModel('notiz', { type: String, default: '' });
const store = useStammdaten();
onMounted(() => store.laden('anfragevorlage'));

const alle = computed(() => (store.listen.anfragevorlage ?? []).filter((v) => v.aktiv && (!v.art || !props.kontext.art || v.art === props.kontext.art)));
const passend = computed(() => new Set(passendeVorlagen(alle.value, props.kontext).map((v) => v.id)));
const angewendet = ref({});

function anwenden(v) {
  for (const n of v.lieferanten) {
    const l = props.lieferanten.find((x) => x.name === n);
    if (l) props.gewaehlt[l.id] = true;
  }
  if (v.hinweis && !notiz.value.trim()) notiz.value = v.hinweis;
  angewendet.value[v.id] = true;
}

// Neu passende Vorlagen automatisch anwenden, sobald die Lieferanten geladen sind
watch([passend, () => props.lieferanten.length], () => {
  if (!props.lieferanten.length) return;
  for (const v of alle.value) if (passend.value.has(v.id) && !angewendet.value[v.id]) anwenden(v);
}, { immediate: true });
</script>

<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <span class="label mr-1">Vorlagen</span>
    <button
      v-for="v in alle" :key="v.id" type="button" class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs transition"
      :class="angewendet[v.id] ? 'border-accent bg-accent-soft text-accent' : passend.has(v.id) ? 'border-accent/60 text-accent' : 'border-line text-mute hover:border-mute hover:text-ink'"
      :title="`${v.lieferanten.join(', ') || 'keine Lieferanten'}${v.stichwoerter ? ` · passt bei: ${v.stichwoerter}` : ''}${v.isoGruppe ? ` · ISO ${v.isoGruppe}` : ''}`"
      @click="anwenden(v)"
    >
      <Sparkles v-if="passend.has(v.id)" :size="11" />{{ v.name }}
    </button>
    <span v-if="!alle.length" class="text-xs text-mute">noch keine angelegt</span>
    <RouterLink to="/stammdaten/anfragevorlagen" class="ml-1 inline-flex items-center gap-1 text-xs text-mute hover:text-ink" title="Vorlagen pflegen"><Settings2 :size="12" /> pflegen</RouterLink>
  </div>
</template>
