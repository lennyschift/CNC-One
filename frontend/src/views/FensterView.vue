<script setup>
// Eigenes Fenster für Zeichnung oder 3D-Modell (z. B. auf dem zweiten Bildschirm). Zeigt, was die Workbench schickt:
// beim Wechsel des Bauteils dessen Zeichnung bzw. Modell. Ohne Seitenleiste und Kopf, nur der Betrachter.
import { ref, computed, defineAsyncComponent, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute } from 'vue-router';
import { FileText, Box, Loader } from '@lucide/vue';
import { ARTEN, fensterStarten } from '../lib/fenster.js';

const ModelViewer = defineAsyncComponent(() => import('../components/ModelViewer.vue'));
const DrawingViewer = defineAsyncComponent(() => import('../components/DrawingViewer.vue'));

const route = useRoute();
const art = computed(() => (route.params.art in ARTEN ? route.params.art : 'zeichnung'));
// { teilId, titel, url, name, dichte, dichteGeschaetzt, aufmass, nurAnsicht } oder null; undefined = noch nichts gehört
const inhalt = ref(undefined);
const aufmass = ref(0);
let verbindung = null;

function starten() {
  verbindung?.beenden();
  inhalt.value = undefined;
  verbindung = fensterStarten(art.value, (x) => {
    inhalt.value = x ?? null;
    aufmass.value = x?.aufmass ?? 0;
  });
}
onMounted(starten);
watch(art, starten);
onBeforeUnmount(() => verbindung?.beenden());

const titel = computed(() => [ARTEN[art.value], inhalt.value?.titel, inhalt.value?.name].filter(Boolean).join(' · '));
watch(titel, (t) => { document.title = `${t} – CNC One`; }, { immediate: true });

const melden = (typ, daten) => verbindung?.melden(typ, { teilId: inhalt.value?.teilId, ...daten });
// Hat das Bauteil noch kein Vorschaubild, entsteht es hier aus dem Modell (wie sonst in der Workbench)
async function modellGeladen(netze) {
  if (!inhalt.value?.vorschauFehlt) return;
  const { vorschauPng } = await import('../lib/modell3d.js');
  melden('vorschau', { blob: await vorschauPng(netze), auto: true });
}
function aufmassGeaendert(v) { aufmass.value = v; melden('aufmass', { wert: v }); }
</script>

<template>
  <div class="flex h-full flex-col bg-bg">
    <div class="flex h-10 shrink-0 items-center gap-2 border-b border-line bg-surface px-4 text-sm">
      <FileText v-if="art === 'zeichnung'" :size="15" class="text-accent" /><Box v-else :size="15" class="text-accent" />
      <span class="font-medium">{{ ARTEN[art] }}</span>
      <span v-if="inhalt?.titel" class="min-w-0 truncate text-mute">· {{ inhalt.titel }}</span>
      <span v-if="inhalt?.name" class="ml-auto min-w-0 truncate text-xs text-mute">{{ inhalt.name }}</span>
    </div>
    <div class="min-h-0 flex-1 p-3">
      <div v-if="inhalt === undefined" class="leer"><Loader :size="22" class="animate-spin" /><span class="mt-2">Warte auf die Workbench …</span></div>
      <div v-else-if="!inhalt?.url" class="leer">
        <span class="font-medium text-ink">{{ inhalt?.titel || 'Kein Bauteil gewählt' }}</span>
        <span class="mt-1">{{ art === 'zeichnung' ? 'Keine Zeichnung zu diesem Bauteil' : 'Kein 3D-Modell zu diesem Bauteil' }}</span>
      </div>
      <DrawingViewer v-else-if="art === 'zeichnung'" :key="inhalt.url" :url="inhalt.url" :name="inhalt.name" fenster="fenster" />
      <ModelViewer
        v-else :key="inhalt.url" :url="inhalt.url" :name="inhalt.name" :dichte="inhalt.dichte" :dichte-geschaetzt="inhalt.dichteGeschaetzt"
        :aufmass="aufmass" @update:aufmass="aufmassGeaendert"
        @geladen="modellGeladen" @gewicht="(kg) => melden('gewicht', { kg })" @vorschau="(blob) => melden('vorschau', { blob })"
      />
    </div>
  </div>
</template>

<style scoped>
.leer { display: flex; height: 100%; flex-direction: column; align-items: center; justify-content: center; border-radius: 1rem; border: 2px dashed var(--line); color: var(--mute); font-size: 0.875rem; }
</style>
