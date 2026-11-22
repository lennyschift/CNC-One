<script setup>
// Stammdaten Rohmaterial: der Rohmaterial-Baum. Werkstoffe (je ISO-Gruppe, mit Zuständen und Formen), Zustände, Ausführungen
// je Form, Abmessungsreihen je Form und Materialanforderungen. Alles, was hier steht, ist in der Workbench auswählbar;
// neue Einträge lassen sich auch direkt bei der Auswahl anlegen.
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Layers, FlaskConical, Wrench, Ruler, ShieldCheck } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import StammListe from '../components/StammListe.vue';
import WerkstoffbaumPflege from '../components/WerkstoffbaumPflege.vue';
import { ISO_GRUPPEN, isoAusName } from '../lib/iso.js';
import { FORM_IDS } from '../lib/werkstoffbaum.js';
import { useWerkstoff } from '../stores/werkstoff.js';
import { useStammdaten } from '../stores/stammdaten.js';

const ws = useWerkstoff();
const darf = computed(() => useStammdaten().darf('material'));
const route = useRoute();
const router = useRouter();
const REITER = [
  { id: 'werkstoffe', label: 'Werkstoffe', icon: Layers },
  { id: 'zustand', label: 'Zustände', icon: FlaskConical },
  { id: 'ausfuehrung', label: 'Ausführungen', icon: Wrench },
  { id: 'abmessung', label: 'Abmessungen', icon: Ruler },
  { id: 'anforderung', label: 'Anforderungen', icon: ShieldCheck },
];
const reiter = ref(REITER.some((r) => r.id === route.query.reiter) ? route.query.reiter : 'werkstoffe');
watch(reiter, (r) => router.replace({ query: r === 'werkstoffe' ? {} : { reiter: r } }));

const felder = computed(() => [
  {
    key: 'isoGruppe', label: 'ISO-Gruppe (Zerspanung)', typ: 'auswahl',
    optionen: [{ wert: '', label: 'Automatisch aus dem Namen' }, ...Object.values(ISO_GRUPPEN).map((g) => ({ wert: g.code, label: `${g.code} · ${g.name}` }))],
    leer: (x) => (isoAusName(x.name) ? `${isoAusName(x.name)} (automatisch)` : '–'),
  },
  { key: 'kurz', label: 'Kurzname', typ: 'text', hinweis: 'z. B. AlZn5,5MgCu' },
  { key: 'preisKg', label: 'Preis je Kilogramm', typ: 'euro', suffix: '€/kg' },
  { key: 'dichte', label: 'Dichte', typ: 'zahl', suffix: 'g/cm³', decimals: 2 },
  { key: 'zustaende', label: 'Zustände', typ: 'mehrfach', optionen: ws.baum.zustaende.map((z) => ({ wert: z.code, label: z.code })), hinweis: 'Erst unter „Zustände“ anlegen.' },
  { key: 'formen', label: 'Formen (keine gewählt = alle)', typ: 'mehrfach', optionen: FORM_IDS.map((f) => ({ wert: f, label: f })) },
  { key: 'schreibweisen', label: 'Schreibweisen auf Zeichnungen (eine je Zeile, z. B. 3.4365, AlZnMgCu1,5)', typ: 'text-lang' },
]);
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <StammNav />
    <div class="mb-4 flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
      <button v-for="r in REITER" :key="r.id" type="button" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="reiter === r.id ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="reiter = r.id">
        <component :is="r.icon" :size="15" /> {{ r.label }}
      </button>
    </div>
    <StammListe v-if="reiter === 'werkstoffe'" :nav="false" art="material" einzahl="Werkstoff" :icon="Layers" beschreibung="Werkstoffe mit Zuständen und Formen; der Preis je Kilogramm ist der Richtwert für die Kalkulation." :felder="felder" :spalten="['isoGruppe', 'kurz', 'zustaende', 'preisKg']" />
    <WerkstoffbaumPflege v-else :key="reiter" :art="reiter" :darf="darf" />
  </div>
</template>
