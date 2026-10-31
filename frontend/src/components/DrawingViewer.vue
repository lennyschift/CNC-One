<script setup>
// Zeichnung (PDF) ansehen: scharf gerendert mit pdf.js, zoomen (Knöpfe oder Strg + Rad), verschieben mit gedrückter Maus,
// im Textmodus Werte markieren und kopieren. Wird nur geladen, wenn eine Zeichnung da ist (pdf.js ist groß).
import { ref, shallowRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { pdfjs } from '../lib/pdf.js';
import { useEventListener } from '@vueuse/core';
import { Maximize2, Minimize2, ZoomIn, ZoomOut, MoveHorizontal, Hand, TextCursor, ExternalLink, Loader, AlertTriangle } from '@lucide/vue';

const props = defineProps({
  url: { type: String, required: true },
  name: { type: String, default: '' },
  markierung: { type: Object, default: null }, // { x, y, b, h } auf Seite 1, 0 bis 1
  anlernen: { type: Boolean, default: false }, // Klick auf Seite 1 meldet die Stelle (Wert anlernen)
  fokus: { type: Object, default: null }, // { lage } auf Seite 1: nah heranzoomen und mittig zeigen
});
const emit = defineEmits(['punkt']);

const flaeche = ref(null);
const seitenEl = ref([]);
const dokument = shallowRef(null);
const seiten = ref(0);
const zoom = ref(1); // 1 = Seitenbreite
const modus = ref('hand'); // 'hand' | 'text'
const stand = ref('laedt');
const fehler = ref('');
const vollbild = ref(false);

let lauf = 0;
let aufgaben = [];
let ladeAufgabe = null;
let zoomTimer = 0;

function abbrechen() {
  aufgaben.forEach((t) => t.cancel?.());
  aufgaben = [];
}

async function rendern() {
  const doc = dokument.value;
  const el = flaeche.value;
  if (!doc || !el) return;
  const meinLauf = ++lauf;
  abbrechen();
  const breite = Math.max(el.clientWidth - 32, 200);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  for (let i = 1; i <= doc.numPages; i++) {
    const seite = await doc.getPage(i);
    if (meinLauf !== lauf) return;
    const basis = seite.getViewport({ scale: 1 });
    const scale = (breite / basis.width) * zoom.value;
    const viewport = seite.getViewport({ scale });
    const huelle = seitenEl.value[i - 1];
    if (!huelle) return;
    huelle.style.width = `${Math.floor(viewport.width)}px`;
    huelle.style.height = `${Math.floor(viewport.height)}px`;
    huelle.style.setProperty('--total-scale-factor', String(scale));
    const canvas = huelle.querySelector('canvas');
    canvas.width = Math.floor(viewport.width * dpr);
    canvas.height = Math.floor(viewport.height * dpr);
    canvas.style.width = `${Math.floor(viewport.width)}px`;
    canvas.style.height = `${Math.floor(viewport.height)}px`;
    const aufgabe = seite.render({ canvas, canvasContext: canvas.getContext('2d'), viewport, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined });
    aufgaben.push(aufgabe);
    const text = huelle.querySelector('.textLayer');
    text.replaceChildren();
    const textLage = new pdfjs.TextLayer({ textContentSource: seite.streamTextContent(), container: text, viewport });
    aufgaben.push(textLage);
    try {
      await Promise.all([aufgabe.promise, textLage.render()]);
    } catch (e) {
      if (e?.name !== 'RenderingCancelledException' && e?.name !== 'AbortException') throw e;
      return;
    }
  }
}

async function laden() {
  stand.value = 'laedt';
  fehler.value = '';
  abbrechen();
  ladeAufgabe?.destroy();
  dokument.value = null;
  try {
    ladeAufgabe = pdfjs.getDocument({ url: props.url, withCredentials: true });
    const doc = await ladeAufgabe.promise;
    dokument.value = doc;
    seiten.value = doc.numPages;
    stand.value = 'bereit';
    await nextTick();
    await rendern();
  } catch (e) {
    if (e?.name === 'AbortException') return;
    stand.value = 'fehler';
    fehler.value = 'Die Zeichnung ließ sich nicht öffnen.';
  }
}

function zoomen(faktor) {
  zoom.value = Math.min(6, Math.max(0.3, zoom.value * faktor));
}

watch(zoom, () => { clearTimeout(zoomTimer); zoomTimer = setTimeout(rendern, 90); });
watch(() => props.url, laden);
watch(vollbild, async () => { await nextTick(); rendern(); });

// Strg + Mausrad zoomt die Zeichnung, nicht die Seite
useEventListener(flaeche, 'wheel', (e) => {
  if (!e.ctrlKey) return;
  e.preventDefault();
  zoomen(e.deltaY < 0 ? 1.12 : 1 / 1.12);
}, { passive: false });

// Verschieben mit gedrückter Maus (Handmodus)
let ziehen = null;
function runter(e) {
  if (props.anlernen || modus.value !== 'hand' || e.button !== 0) return;
  ziehen = { x: e.clientX, y: e.clientY, l: flaeche.value.scrollLeft, t: flaeche.value.scrollTop };
  flaeche.value.setPointerCapture(e.pointerId);
}
function bewegen(e) {
  if (!ziehen) return;
  flaeche.value.scrollLeft = ziehen.l - (e.clientX - ziehen.x);
  flaeche.value.scrollTop = ziehen.t - (e.clientY - ziehen.y);
}
function hoch() { ziehen = null; }

// Beim Anlernen: Stelle des Klicks auf Seite 1 als Anteil der Seite melden
function klick(e, n) {
  if (!props.anlernen || n !== 1) return;
  const r = e.currentTarget.getBoundingClientRect();
  emit('punkt', { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
}

// Zur Stelle zoomen: so nah, dass der Wert gut ein Drittel der Ansicht breit ist, und ihn mittig zeigen.
// Gescrollt wird nur in der Ansicht selbst, die Workbench drumherum bleibt stehen.
watch(() => props.fokus, async (f) => {
  const el = flaeche.value;
  const seite = seitenEl.value[0];
  if (!f?.lage || !el || !seite || !dokument.value) return;
  const breiteBeiZoom1 = seite.offsetWidth / zoom.value;
  zoom.value = Math.min(6, Math.max(1.5, (el.clientWidth * 0.35) / Math.max(f.lage.b * breiteBeiZoom1, 1)));
  clearTimeout(zoomTimer);
  await nextTick();
  clearTimeout(zoomTimer);
  await rendern();
  el.scrollLeft = seite.offsetLeft + (f.lage.x + f.lage.b / 2) * seite.offsetWidth - el.clientWidth / 2;
  el.scrollTop = seite.offsetTop + (f.lage.y + f.lage.h / 2) * seite.offsetHeight - el.clientHeight / 2;
});

useEventListener(window, 'keydown', (e) => { if (e.key === 'Escape' && vollbild.value) vollbild.value = false; });
let groesse = null;
onMounted(() => {
  laden();
  let letzteBreite = 0;
  groesse = new ResizeObserver(() => {
    const b = flaeche.value?.clientWidth ?? 0;
    if (Math.abs(b - letzteBreite) > 8) { letzteBreite = b; clearTimeout(zoomTimer); zoomTimer = setTimeout(rendern, 120); }
  });
  groesse.observe(flaeche.value);
});
onBeforeUnmount(() => {
  lauf++;
  groesse?.disconnect();
  abbrechen();
  ladeAufgabe?.destroy();
});
</script>

<template>
  <div class="h-full">
    <Teleport to="body" :disabled="!vollbild">
      <div class="zeichnung-flaeche flex flex-col overflow-hidden border border-line" :class="vollbild ? 'fixed inset-3 z-50 rounded-3xl shadow-2xl' : 'relative h-full rounded-2xl'">
        <div class="flex shrink-0 items-center gap-1 border-b border-line bg-surface px-2 py-1.5">
          <button class="knopf" title="Verkleinern" @click="zoomen(1 / 1.25)"><ZoomOut :size="15" /></button>
          <span class="w-12 text-center text-xs text-mute tnum">{{ Math.round(zoom * 100) }} %</span>
          <button class="knopf" title="Vergrößern" @click="zoomen(1.25)"><ZoomIn :size="15" /></button>
          <button class="knopf" title="Auf Breite einpassen" @click="zoom = 1"><MoveHorizontal :size="15" /></button>
          <span class="mx-1 h-5 w-px bg-line" />
          <button class="knopf" :class="modus === 'hand' ? 'bg-accent-soft !text-accent' : ''" title="Verschieben" @click="modus = 'hand'"><Hand :size="15" /></button>
          <button class="knopf" :class="modus === 'text' ? 'bg-accent-soft !text-accent' : ''" title="Text markieren und kopieren" @click="modus = 'text'"><TextCursor :size="15" /></button>
          <span v-if="seiten > 1" class="ml-1 text-xs text-mute">{{ seiten }} Seiten</span>
          <span class="flex-1" />
          <a class="knopf" :href="url" target="_blank" rel="noopener" title="In neuem Tab öffnen"><ExternalLink :size="15" /></a>
          <button class="knopf" :title="vollbild ? 'Vollbild verlassen (Esc)' : 'Vollbild'" @click="vollbild = !vollbild"><Minimize2 v-if="vollbild" :size="15" /><Maximize2 v-else :size="15" /></button>
        </div>
        <div
          ref="flaeche"
          class="relative min-h-0 flex-1 overflow-auto p-4"
          :class="[anlernen ? 'modus-anlernen cursor-crosshair select-none' : modus === 'hand' ? 'cursor-grab active:cursor-grabbing select-none' : '', anlernen ? '' : `modus-${modus}`]"
          @pointerdown="runter" @pointermove="bewegen" @pointerup="hoch" @pointercancel="hoch"
        >
          <div v-for="n in seiten" :key="n" :ref="(el) => { if (el) seitenEl[n - 1] = el; }" class="seite relative mx-auto mb-4 bg-white shadow-md" @click="klick($event, n)">
            <canvas class="block" />
            <div class="textLayer" />
            <div
              v-if="n === 1 && markierung" class="markierung pointer-events-none absolute rounded-sm"
              :style="{ left: `${(markierung.x - 0.004) * 100}%`, top: `${(markierung.y - 0.004) * 100}%`, width: `${(markierung.b + 0.008) * 100}%`, height: `${(markierung.h + 0.008) * 100}%` }"
            />
          </div>
          <div v-if="stand === 'laedt'" class="absolute inset-0 grid place-items-center">
            <div class="flex items-center gap-2 rounded-xl bg-surface/85 px-3.5 py-2 text-sm text-mute shadow-sm"><Loader :size="15" class="animate-spin" /> Zeichnung wird geladen …</div>
          </div>
          <div v-else-if="stand === 'fehler'" class="absolute inset-0 grid place-items-center p-6 text-center">
            <div><AlertTriangle :size="22" class="mx-auto text-accent" /><p class="mt-2 text-sm">{{ fehler }}</p></div>
          </div>
        </div>
      </div>
    </Teleport>
    <div v-if="vollbild" class="grid h-full place-items-center rounded-2xl border border-dashed border-line text-xs text-mute">Im Vollbild geöffnet</div>
  </div>
</template>

<style scoped>
.zeichnung-flaeche { background: var(--surface-2); }
.knopf { display: grid; place-items: center; height: 1.85rem; min-width: 1.85rem; padding: 0 0.45rem; border-radius: 0.6rem; font-size: 0.72rem; color: var(--mute); }
.knopf:hover { background: var(--surface-2); color: var(--ink); }
.modus-hand :deep(.textLayer) { pointer-events: none; }
.modus-anlernen :deep(.textLayer span) { cursor: crosshair; border-radius: 2px; }
.modus-anlernen :deep(.textLayer span:hover) { background: color-mix(in srgb, var(--accent) 22%, transparent); outline: 1px solid var(--accent); }
.markierung { outline: 2px solid var(--accent); background: color-mix(in srgb, var(--accent) 14%, transparent); animation: markieren 1.4s ease-out 2; }
@keyframes markieren { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 55%, transparent); } 100% { box-shadow: 0 0 0 10px transparent; } }

/* Textebene von pdf.js (Auszug aus pdf_viewer.css): unsichtbarer Text über dem Bild, damit er sich markieren lässt */
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
