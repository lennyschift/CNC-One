<script setup>
// 3D-Ansicht eines STEP-Modells: drehen (linke Maustaste), verschieben (rechte), zoomen (Rad), feste Ansichten, Kanten,
// Abmessungen und „aktuelle Ansicht als Vorschaubild“. Wird nur geladen, wenn ein Modell da ist (Three.js ist groß).
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { useEventListener } from '@vueuse/core';
import { Maximize2, Minimize2, Scan, ImagePlus, Loader, AlertTriangle, Spline, Download } from '@lucide/vue';
import { stepNetze } from '../lib/step.js';
import { ANSICHTEN, modellGruppe, abmessungen, kameraAusrichten, lichter } from '../lib/modell3d.js';
import { zahl } from '../lib/format.js';

const props = defineProps({ url: { type: String, required: true }, name: { type: String, default: '' } });
const emit = defineEmits(['geladen', 'vorschau']);

const huelle = ref(null);
const stand = ref('laedt'); // 'laedt' | 'bereit' | 'fehler'
const fehler = ref('');
const masse = ref(null);
const kantenAn = ref(true);
const ansicht = ref('iso');
const vollbild = ref(false);

let renderer = null;
let szene = null;
let kamera = null;
let steuerung = null;
let modell = null;
let beobachter = null;
let aktiv = true;

const zeichnen = () => renderer?.render(szene, kamera);

function groesseAnpassen() {
  const el = huelle.value;
  if (!el || !renderer) return;
  const w = Math.max(el.clientWidth, 1);
  const h = Math.max(el.clientHeight, 1);
  renderer.setSize(w, h, false);
  kamera.aspect = w / h;
  kamera.updateProjectionMatrix();
  zeichnen();
}

function zeigen(name) {
  if (!modell) return;
  ansicht.value = name;
  kameraAusrichten(kamera, steuerung.target, modell.gruppe, ANSICHTEN[name].richtung);
  steuerung.update();
  zeichnen();
}

function modellEntfernen() {
  if (!modell) return;
  szene.remove(modell.gruppe);
  modell.entsorgen();
  modell = null;
}

async function laden() {
  stand.value = 'laedt';
  fehler.value = '';
  masse.value = null;
  modellEntfernen();
  zeichnen();
  const url = props.url;
  try {
    const netze = await stepNetze(url);
    if (!aktiv || url !== props.url) return;
    modell = modellGruppe(netze);
    modell.kanten.visible = kantenAn.value;
    szene.add(modell.gruppe);
    masse.value = abmessungen(netze);
    stand.value = 'bereit';
    await nextTick();
    groesseAnpassen();
    zeigen('iso');
    emit('geladen', netze);
  } catch (e) {
    if (!aktiv) return;
    stand.value = 'fehler';
    fehler.value = e.message;
  }
}

function alsVorschau() {
  if (!modell) return;
  zeichnen();
  renderer.domElement.toBlob((blob) => blob && emit('vorschau', blob), 'image/png');
}

onMounted(() => {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.domElement.className = 'block h-full w-full';
  huelle.value.appendChild(renderer.domElement);
  szene = new THREE.Scene();
  lichter(szene);
  kamera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
  steuerung = new OrbitControls(kamera, renderer.domElement);
  steuerung.addEventListener('change', zeichnen);
  beobachter = new ResizeObserver(groesseAnpassen);
  beobachter.observe(huelle.value);
  laden();
});

onBeforeUnmount(() => {
  aktiv = false;
  beobachter?.disconnect();
  steuerung?.dispose();
  modellEntfernen();
  renderer?.dispose();
  renderer?.forceContextLoss();
  renderer = null;
});

watch(() => props.url, laden);
watch(kantenAn, (an) => { if (modell) { modell.kanten.visible = an; zeichnen(); } });
watch(vollbild, () => nextTick(groesseAnpassen));
useEventListener(window, 'keydown', (e) => { if (e.key === 'Escape' && vollbild.value) vollbild.value = false; });

const mm = (v) => zahl(v, v < 10 ? 2 : 1);
</script>

<template>
  <div class="h-full">
    <Teleport to="body" :disabled="!vollbild">
      <div class="modell-flaeche overflow-hidden border border-line" :class="vollbild ? 'fixed inset-3 z-50 rounded-3xl shadow-2xl' : 'relative h-full rounded-2xl'">
        <div ref="huelle" class="absolute inset-0" />

        <div v-if="stand === 'bereit'" class="werkzeug left-3 top-3">
          <button v-for="(a, k) in ANSICHTEN" :key="k" class="knopf" :class="ansicht === k ? 'bg-accent-soft !text-accent' : ''" @click="zeigen(k)">{{ a.label }}</button>
          <span class="mx-0.5 w-px self-stretch bg-line" />
          <button class="knopf" :class="kantenAn ? 'bg-accent-soft !text-accent' : ''" title="Kanten ein-/ausblenden" @click="kantenAn = !kantenAn"><Spline :size="15" /></button>
          <button class="knopf" title="Modell einpassen" @click="zeigen(ansicht)"><Scan :size="15" /></button>
        </div>
        <div class="werkzeug right-3 top-3">
          <button v-if="stand === 'bereit'" class="knopf" title="Aktuelle Ansicht als Vorschaubild des Bauteils übernehmen" @click="alsVorschau"><ImagePlus :size="15" /></button>
          <a class="knopf" :href="url" :download="name || true" title="STEP-Datei herunterladen"><Download :size="15" /></a>
          <button class="knopf" :title="vollbild ? 'Vollbild verlassen (Esc)' : 'Vollbild'" @click="vollbild = !vollbild"><Minimize2 v-if="vollbild" :size="15" /><Maximize2 v-else :size="15" /></button>
        </div>

        <div v-if="masse" class="absolute bottom-3 left-3 rounded-lg bg-surface/85 px-2.5 py-1 text-xs shadow-sm backdrop-blur tnum" title="Größe des umschließenden Quaders (X × Y × Z)">
          {{ mm(masse.x) }} × {{ mm(masse.y) }} × {{ mm(masse.z) }} mm
        </div>
        <div v-if="stand === 'bereit'" class="pointer-events-none absolute bottom-3 right-3 hidden text-[10px] text-mute sm:block">Drehen: linke Taste · Verschieben: rechte Taste · Zoom: Rad</div>

        <div v-if="stand === 'laedt'" class="absolute inset-0 grid place-items-center">
          <div class="flex items-center gap-2 rounded-xl bg-surface/85 px-3.5 py-2 text-sm text-mute shadow-sm backdrop-blur"><Loader :size="15" class="animate-spin" /> 3D-Modell wird gelesen …</div>
        </div>
        <div v-else-if="stand === 'fehler'" class="absolute inset-0 grid place-items-center p-6 text-center">
          <div><AlertTriangle :size="22" class="mx-auto text-accent" /><p class="mt-2 text-sm">{{ fehler }}</p></div>
        </div>
      </div>
    </Teleport>
    <div v-if="vollbild" class="grid h-full place-items-center rounded-2xl border border-dashed border-line text-xs text-mute">Im Vollbild geöffnet</div>
  </div>
</template>

<style scoped>
.modell-flaeche { background: radial-gradient(ellipse at 30% 15%, var(--surface), var(--surface-2) 70%); }
.werkzeug { position: absolute; display: flex; gap: 0.15rem; border-radius: 0.8rem; padding: 0.2rem; background: color-mix(in srgb, var(--surface) 85%, transparent); box-shadow: 0 1px 3px rgb(0 0 0 / 0.08); backdrop-filter: blur(6px); }
.knopf { display: grid; place-items: center; height: 1.85rem; min-width: 1.85rem; padding: 0 0.5rem; border-radius: 0.6rem; font-size: 0.72rem; color: var(--mute); }
.knopf:hover { background: var(--surface-2); color: var(--ink); }
</style>
