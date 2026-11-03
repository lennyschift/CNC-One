<script setup>
// Ein Beleg, wie er verschickt wird: die Seiten des Server-PDFs untereinander als Papierblätter, ohne Werkzeugleiste.
// Gezeichnet wird mit mehrfacher Auflösung (scharf), darüber liegt die Textebene von pdf.js (Text lässt sich markieren).
// Das PDF wird selbst geladen, damit bei einem Fehler die Meldung des Servers zu sehen ist.
import { ref, watch, nextTick, onBeforeUnmount } from 'vue';
import { useResizeObserver } from '@vueuse/core';
import { AlertTriangle, RotateCcw, Loader } from '@lucide/vue';
import { pdfLaden } from '../lib/belegpdf.js';

const props = defineProps({ url: { type: String, required: true }, name: { type: String, default: '' } });

const huelle = ref(null);
const blaetter = [];
const anzahl = ref(0);
const stand = ref('laedt'); // laedt | fertig | fehler
const fehler = ref('');
let pdfjs = null;
let dokument = null;
let lauf = 0;
let aufgaben = [];
let breite = 0;

async function laden() {
  const meiner = ++lauf;
  stand.value = 'laedt';
  fehler.value = '';
  try {
    const [modul, daten] = await Promise.all([import('../lib/pdf.js'), pdfLaden(props.url)]);
    pdfjs = modul.pdfjs;
    const doc = await pdfjs.getDocument({ data: new Uint8Array(daten) }).promise;
    if (meiner !== lauf) { doc.destroy(); return; }
    dokument?.destroy();
    dokument = doc;
    anzahl.value = doc.numPages;
    stand.value = 'fertig';
    await nextTick();
    await zeichnen();
  } catch (e) {
    if (meiner !== lauf) return;
    stand.value = 'fehler';
    fehler.value = e?.message || '';
  }
}

function abbrechen() {
  aufgaben.forEach((a) => a.cancel());
  aufgaben = [];
}

// Jede Seite in voller Breite. Der Canvas hat 2- bis 3-fache Auflösung, damit Schrift auch bei 100 % Zoom scharf ist.
async function zeichnen() {
  if (!dokument || !huelle.value) return;
  abbrechen();
  const doc = dokument;
  breite = Math.floor(huelle.value.clientWidth);
  const fein = Math.min(Math.max((window.devicePixelRatio || 1) * 2, 2), 3);
  for (let i = 1; i <= doc.numPages; i++) {
    const seite = await doc.getPage(i);
    const blatt = blaetter[i - 1];
    if (doc !== dokument || !blatt) return;
    const basis = seite.getViewport({ scale: 1 });
    const scale = breite / basis.width;
    const viewport = seite.getViewport({ scale });
    blatt.style.width = `${Math.floor(viewport.width)}px`;
    blatt.style.height = `${Math.floor(viewport.height)}px`;
    blatt.style.setProperty('--total-scale-factor', String(scale));
    const canvas = blatt.querySelector('canvas');
    canvas.width = Math.floor(viewport.width * fein);
    canvas.height = Math.floor(viewport.height * fein);
    const bild = seite.render({ canvas, canvasContext: canvas.getContext('2d'), viewport, transform: [fein, 0, 0, fein, 0, 0] });
    const textEbene = blatt.querySelector('.textLayer');
    textEbene.replaceChildren();
    const text = new pdfjs.TextLayer({ textContentSource: seite.streamTextContent(), container: textEbene, viewport });
    aufgaben.push(bild, text);
    try {
      await Promise.all([bild.promise, text.render()]);
    } catch {
      return; // abgebrochen: ein neuerer Lauf zeichnet
    }
  }
}

let warten = null;
useResizeObserver(huelle, () => {
  if (stand.value !== 'fertig' || Math.abs(Math.floor(huelle.value?.clientWidth ?? 0) - breite) < 8) return;
  clearTimeout(warten);
  warten = setTimeout(zeichnen, 200);
});

watch(() => props.url, laden, { immediate: true });
onBeforeUnmount(() => {
  lauf++;
  clearTimeout(warten);
  abbrechen();
  dokument?.destroy();
});
</script>

<template>
  <div ref="huelle" class="mx-auto w-full max-w-[820px]">
    <div v-if="stand === 'laedt'" class="paper grid aspect-[210/297] w-full place-items-center">
      <span class="flex items-center gap-2 text-sm text-neutral-400"><Loader :size="16" class="animate-spin" /> PDF wird erstellt …</span>
    </div>
    <div v-else-if="stand === 'fehler'" class="paper grid aspect-[210/297] w-full place-items-center p-10 text-center">
      <div class="max-w-sm">
        <AlertTriangle :size="24" class="mx-auto mb-2 text-accent" />
        <p class="text-sm font-semibold">Das PDF ließ sich nicht anzeigen.</p>
        <p v-if="fehler" class="mt-1 text-xs text-neutral-500">{{ fehler }}</p>
        <button class="btn mt-4" @click="laden"><RotateCcw :size="14" /> Erneut versuchen</button>
      </div>
    </div>
    <div v-show="stand === 'fertig'" class="space-y-5">
      <div v-for="i in anzahl" :key="i" :ref="(el) => (blaetter[i - 1] = el)" class="blatt paper relative overflow-hidden" :aria-label="`${name} – Seite ${i}`">
        <canvas class="block h-full w-full" />
        <div class="textLayer" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Textebene von pdf.js (Auszug aus pdf_viewer.css, wie im Zeichnungsbetrachter): unsichtbarer Text über dem Bild */
:deep(.textLayer) {
  position: absolute; inset: 0; overflow: clip; opacity: 1; line-height: 1; text-align: initial; transform-origin: 0 0; z-index: 0;
  --min-font-size: 1; --text-scale-factor: calc(var(--total-scale-factor) * var(--min-font-size)); --min-font-size-inv: calc(1 / var(--min-font-size));
}
:deep(.textLayer :is(span, br)) { color: transparent; position: absolute; white-space: pre; cursor: text; transform-origin: 0% 0%; user-select: text; }
:deep(.textLayer > :not(.markedContent)), :deep(.textLayer .markedContent span:not(.markedContent)) {
  z-index: 1; --font-height: 0; font-size: calc(var(--text-scale-factor) * var(--font-height));
  --scale-x: 1; --rotate: 0deg; transform: rotate(var(--rotate)) scaleX(var(--scale-x)) scale(var(--min-font-size-inv));
}
:deep(.textLayer .markedContent) { display: contents; }
:deep(.textLayer ::selection) { background: color-mix(in srgb, var(--accent) 30%, transparent); color: transparent; }
:deep(.textLayer .endOfContent) { display: block; position: absolute; inset: 100% 0 0; z-index: 0; cursor: default; user-select: none; }
</style>
