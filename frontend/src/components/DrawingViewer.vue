<script setup>
// Zeichnung (PDF) ansehen: scharf gerendert mit pdf.js, zoomen (Knöpfe oder Strg + Rad), verschieben mit gedrückter Maus,
// im Textmodus Werte markieren und kopieren, in 90°-Schritten drehen und wie in einem PDF-Programm markieren
// (Textmarker, Rahmen, Pfeil, Freihand, Notiz). Drehung und Markierungen werden je Datei gespeichert (eigene Ebene, die PDF
// bleibt unverändert) und sind überall zu sehen, wo die Zeichnung angezeigt wird. Ein Klick in die Zeichnung öffnet sie groß.
// Wird nur geladen, wenn eine Zeichnung da ist (pdf.js ist groß).
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { pdfjs } from '../lib/pdf.js';
import { call } from '../data/api.js';
import { useEventListener } from '@vueuse/core';
import {
  Maximize2, Minimize2, ZoomIn, ZoomOut, MoveHorizontal, Hand, TextCursor, ExternalLink, MonitorUp, Loader, AlertTriangle,
  RotateCw, RotateCcw, Highlighter, Square, MoveUpRight, PenLine, StickyNote, Eraser, Undo2, Eye, EyeOff,
} from '@lucide/vue';

const props = defineProps({
  url: { type: String, required: true },
  name: { type: String, default: '' },
  markierung: { type: Object, default: null }, // { x, y, b, h } auf Seite 1, 0 bis 1
  anlernen: { type: Boolean, default: false }, // Klick auf Seite 1 meldet die Stelle (Wert anlernen)
  fokus: { type: Object, default: null }, // { lage } auf Seite 1: nah heranzoomen und mittig zeigen
  // 'knopf': statt „In neuem Tab öffnen“ ein Knopf für das eigene Fenster (zweiter Bildschirm), meldet 'fenster';
  // 'fenster': läuft selbst im eigenen Fenster, kein Tab-Link
  fenster: { type: String, default: '' },
});
const emit = defineEmits(['punkt', 'fenster']);

const flaeche = ref(null);
const seitenEl = ref([]);
const dokument = shallowRef(null);
const seiten = ref(0);
const masse = ref([]); // je Seite { w, h } ohne eigene Drehung (Punkte)
const zoom = ref(1); // 1 = Seitenbreite
const modus = ref('hand'); // 'hand' | 'text' | Werkzeug: 'marker' | 'rahmen' | 'pfeil' | 'freihand' | 'notiz' | 'radierer'
const stand = ref('laedt');
const fehler = ref('');
const vollbild = ref(false);

// ---- Drehung und Markierungen (gespeichert je Datei)
const drehung = ref(0);
const markierungen = ref([]);
const sichtbar = ref(true);
const farbe = ref('rot');
const speicherbar = ref(false); // erst nach dem Laden, und nur wenn der Server die Markierungen kennt
const verlauf = []; // für Rückgängig: frühere Stände der Liste
const FARBEN = { rot: '#dc2626', gelb: '#facc15', gruen: '#16a34a', blau: '#2563eb' };
const WERKZEUGE = [
  { id: 'marker', titel: 'Textmarker (Fläche markieren)', icon: Highlighter },
  { id: 'rahmen', titel: 'Rahmen', icon: Square },
  { id: 'pfeil', titel: 'Pfeil', icon: MoveUpRight },
  { id: 'freihand', titel: 'Freihand zeichnen', icon: PenLine },
  { id: 'notiz', titel: 'Notiz: an die Stelle klicken und Text schreiben', icon: StickyNote },
  { id: 'radierer', titel: 'Markierung löschen: anklicken', icon: Eraser },
];
const werkzeug = computed(() => WERKZEUGE.some((w) => w.id === modus.value));

let lauf = 0;
let aufgaben = [];
let ladeAufgabe = null;
let zoomTimer = 0;
let speicherTimer = 0;

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
    const rotation = (seite.rotate + drehung.value) % 360;
    const basis = seite.getViewport({ scale: 1, rotation });
    const scale = (breite / basis.width) * zoom.value;
    const viewport = seite.getViewport({ scale, rotation });
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
  speicherbar.value = false;
  markierungen.value = [];
  verlauf.length = 0;
  drehung.value = 0;
  const gespeichert = call('cnc_one.api.zeichnung.markierungen', { datei: props.url }).catch(() => null);
  try {
    ladeAufgabe = pdfjs.getDocument({ url: props.url, withCredentials: true });
    const doc = await ladeAufgabe.promise;
    const m = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const v = (await doc.getPage(i)).getViewport({ scale: 1 });
      m.push({ w: v.width, h: v.height });
    }
    masse.value = m;
    const g = await gespeichert;
    if (g) {
      drehung.value = g.drehung || 0;
      markierungen.value = g.markierungen || [];
      speicherbar.value = true;
    }
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

// Zoomen um einen Punkt (Mauszeiger; ohne Punkt die Mitte der Ansicht): Die Stelle unter dem Zeiger bleibt stehen.
// Die Seiten werden sofort per CSS skaliert, das scharfe Rendern folgt kurz danach in derselben Größe.
function zoomen(faktor, anker = null) {
  const alt = zoom.value;
  const neu = Math.min(6, Math.max(0.3, alt * faktor));
  if (neu === alt) return;
  const el = flaeche.value;
  const huellen = seitenEl.value.filter(Boolean);
  if (!el || !huellen.length) { zoom.value = neu; return; }
  const k = neu / alt;
  // Lage der Seiten rechnerisch (Rand p-4 = 16 px, Abstand mb-4 = 16 px, waagrecht mittig, solange die Seite passt),
  // aus den gesetzten Größen: so stimmt es auch bei schnellem Drehen am Rad, bevor der Browser neu gerechnet hat.
  const RAND = 16;
  const groesse = (h) => [parseFloat(h.style.width) || h.offsetWidth, parseFloat(h.style.height) || h.offsetHeight];
  const lage = (masse) => {
    let oben = RAND;
    return masse.map(([w, h]) => {
      const l = { links: Math.max(RAND, (el.clientWidth - w) / 2), oben, w, h };
      oben += h + RAND;
      return l;
    });
  };
  const vorher = lage(huellen.map(groesse));
  const nachher = lage(huellen.map((h) => groesse(h).map((v) => Math.floor(v * k))));
  const r = el.getBoundingClientRect();
  const px = anker ? anker.x - r.left : el.clientWidth / 2;
  const py = anker ? anker.y - r.top : el.clientHeight / 2;
  const sx = scrollZiel.x ?? el.scrollLeft;
  const sy = scrollZiel.y ?? el.scrollTop;
  const cx = sx + px;
  const cy = sy + py;
  const i = Math.max(0, vorher.findIndex((s) => cy <= s.oben + s.h));
  const fx = (cx - vorher[i].links) / vorher[i].w;
  const fy = (cy - vorher[i].oben) / vorher[i].h;
  huellen.forEach((h, j) => {
    const w = `${nachher[j].w}px`;
    const hh = `${nachher[j].h}px`;
    h.style.width = w;
    h.style.height = hh;
    const c = h.querySelector('canvas');
    if (c) { c.style.width = w; c.style.height = hh; }
    h.style.setProperty('--total-scale-factor', String(parseFloat(h.style.getPropertyValue('--total-scale-factor') || '1') * k));
  });
  zoom.value = neu;
  scrollZiel.x = Math.max(0, nachher[i].links + fx * nachher[i].w - px);
  scrollZiel.y = Math.max(0, nachher[i].oben + fy * nachher[i].h - py);
  const halten = () => { el.scrollLeft = scrollZiel.x; el.scrollTop = scrollZiel.y; };
  halten();
  requestAnimationFrame(halten);
  clearTimeout(scrollZielTimer);
  scrollZielTimer = setTimeout(() => { halten(); scrollZiel.x = null; scrollZiel.y = null; }, 60);
}
// Ziel der Scrollposition beim Zoomen, bis der Browser die neue Größe übernommen hat
const scrollZiel = { x: null, y: null };
let scrollZielTimer = 0;
function drehen(grad) {
  drehung.value = (drehung.value + grad + 360) % 360;
  speichernPlanen();
}

watch(zoom, () => { clearTimeout(zoomTimer); zoomTimer = setTimeout(rendern, 90); });
watch(drehung, async () => { clearTimeout(zoomTimer); await nextTick(); rendern(); });
watch(() => props.url, laden);
watch(vollbild, async () => { await nextTick(); rendern(); });

// ---- Speichern (verzögert, damit Freihand-Striche nicht einzeln gehen)
function speichernPlanen() {
  if (!speicherbar.value) return;
  clearTimeout(speicherTimer);
  speicherTimer = setTimeout(speichernJetzt, 700);
}
async function speichernJetzt() {
  clearTimeout(speicherTimer);
  if (!speicherbar.value) return;
  try {
    await call('cnc_one.api.zeichnung.markierungen_speichern', { datei: props.url, drehung: drehung.value, markierungen: markierungen.value });
  } catch { /* nächster Versuch beim nächsten Ändern */ }
}
function aendern(neu) {
  verlauf.push(markierungen.value);
  if (verlauf.length > 100) verlauf.shift();
  markierungen.value = neu;
  speichernPlanen();
}
function rueckgaengig() {
  if (!verlauf.length) return;
  markierungen.value = verlauf.pop();
  speichernPlanen();
}

// ---- Lage auf der Seite: gespeichert ohne Drehung (Anteil 0 bis 1), angezeigt gedreht
const masseVon = (n) => masse.value[n - 1] ?? { w: 1, h: 1 };
function ansicht(n) {
  const { w, h } = masseVon(n);
  return drehung.value % 180 ? { w: h, h: w } : { w, h };
}
function drehTransform(n) {
  const { w, h } = masseVon(n);
  if (drehung.value === 90) return `translate(${h} 0) rotate(90)`;
  if (drehung.value === 180) return `translate(${w} ${h}) rotate(180)`;
  if (drehung.value === 270) return `translate(0 ${w}) rotate(270)`;
  return '';
}
// Anteil auf der ungedrehten Seite -> Anteil in der Anzeige
function angezeigt(x, y) {
  if (drehung.value === 90) return [1 - y, x];
  if (drehung.value === 180) return [1 - x, 1 - y];
  if (drehung.value === 270) return [y, 1 - x];
  return [x, y];
}
// Mausposition -> Anteil auf der ungedrehten Seite n
const gruppen = ref([]);
function aufSeite(e, n) {
  const g = gruppen.value[n - 1];
  if (!g) return null;
  const pt = g.ownerSVGElement.createSVGPoint();
  pt.x = e.clientX;
  pt.y = e.clientY;
  const p = pt.matrixTransform(g.getScreenCTM().inverse());
  const { w, h } = masseVon(n);
  return { x: Math.min(1, Math.max(0, p.x / w)), y: Math.min(1, Math.max(0, p.y / h)) };
}
const strich = (n) => Math.max(masseVon(n).w, masseVon(n).h) * 0.0024;
const schrift = (n) => Math.max(masseVon(n).w, masseVon(n).h) * 0.015;
const aufSeiteN = (n) => markierungen.value.map((m, i) => ({ m, i })).filter((x) => x.m.seite === n);
const pfad = (m, n) => m.punkte.map((p, i) => `${i ? 'L' : 'M'}${p[0] * masseVon(n).w} ${p[1] * masseVon(n).h}`).join(' ');

// ---- Zeichnen mit den Werkzeugen
const entwurf = ref(null); // Markierung, die gerade gezogen wird
const notiz = ref(null); // { seite, x, y, text, links, oben } Eingabe einer Notiz
function werkzeugRunter(e, n) {
  if (!werkzeug.value || e.button !== 0 || props.anlernen) return;
  e.stopPropagation();
  const p = aufSeite(e, n);
  if (!p) return;
  if (modus.value === 'radierer') return;
  if (modus.value === 'notiz') {
    e.preventDefault(); // sonst nimmt der Browser dem neuen Eingabefeld gleich wieder den Fokus
    notizSpeichern();
    const huelle = seitenEl.value[n - 1];
    const [ax, ay] = angezeigt(p.x, p.y);
    notiz.value = { seite: n, x: p.x, y: p.y, text: '', links: ax * huelle.offsetWidth, oben: ay * huelle.offsetHeight };
    setTimeout(() => document.querySelector('.notiz-eingabe')?.focus(), 0);
    return;
  }
  e.currentTarget.setPointerCapture(e.pointerId);
  const basis = { seite: n, farbe: farbe.value };
  if (modus.value === 'freihand') entwurf.value = { ...basis, typ: 'freihand', punkte: [[p.x, p.y]] };
  else if (modus.value === 'pfeil') entwurf.value = { ...basis, typ: 'pfeil', x1: p.x, y1: p.y, x2: p.x, y2: p.y };
  else entwurf.value = { ...basis, typ: modus.value, start: p, x: p.x, y: p.y, b: 0, h: 0 };
}
function werkzeugBewegen(e, n) {
  const d = entwurf.value;
  if (!d || d.seite !== n) return;
  const p = aufSeite(e, n);
  if (!p) return;
  if (d.typ === 'freihand') d.punkte.push([p.x, p.y]);
  else if (d.typ === 'pfeil') Object.assign(d, { x2: p.x, y2: p.y });
  else Object.assign(d, { x: Math.min(d.start.x, p.x), y: Math.min(d.start.y, p.y), b: Math.abs(p.x - d.start.x), h: Math.abs(p.y - d.start.y) });
}
function werkzeugHoch() {
  const d = entwurf.value;
  entwurf.value = null;
  if (!d) return;
  const klein = d.typ === 'freihand' ? d.punkte.length < 2 : d.typ === 'pfeil' ? Math.hypot(d.x2 - d.x1, d.y2 - d.y1) < 0.005 : d.b < 0.003 || d.h < 0.003;
  if (klein) return;
  const { start, ...fertig } = d;
  if (fertig.typ === 'freihand') fertig.punkte = fertig.punkte.filter((_, i, a) => i % 2 === 0 || i === a.length - 1); // ausdünnen
  aendern([...markierungen.value, fertig]);
}
function loeschen(i) {
  if (modus.value !== 'radierer') return;
  aendern(markierungen.value.filter((_, j) => j !== i));
}
function notizSpeichern() {
  const nz = notiz.value;
  notiz.value = null;
  if (!nz?.text.trim()) return;
  aendern([...markierungen.value, { typ: 'notiz', seite: nz.seite, x: nz.x, y: nz.y, text: nz.text.trim(), farbe: farbe.value }]);
}

// Strg + Mausrad zoomt die Zeichnung, nicht die Seite
useEventListener(flaeche, 'wheel', (e) => {
  if (!e.ctrlKey) return;
  e.preventDefault();
  zoomen(e.deltaY < 0 ? 1.12 : 1 / 1.12, { x: e.clientX, y: e.clientY });
}, { passive: false });

// Verschieben mit gedrückter Maus (Handmodus). Ein Klick ohne Verschieben öffnet die Zeichnung groß.
let ziehen = null;
function runter(e) {
  if (props.anlernen || modus.value !== 'hand' || e.button !== 0) return;
  ziehen = { x: e.clientX, y: e.clientY, l: flaeche.value.scrollLeft, t: flaeche.value.scrollTop, bewegt: false };
  flaeche.value.setPointerCapture(e.pointerId);
}
function bewegen(e) {
  if (!ziehen) return;
  if (Math.abs(e.clientX - ziehen.x) + Math.abs(e.clientY - ziehen.y) > 4) ziehen.bewegt = true;
  flaeche.value.scrollLeft = ziehen.l - (e.clientX - ziehen.x);
  flaeche.value.scrollTop = ziehen.t - (e.clientY - ziehen.y);
}
function hoch() {
  if (ziehen && !ziehen.bewegt && !vollbild.value && stand.value === 'bereit') vollbild.value = true;
  ziehen = null;
}

// Beim Anlernen: Stelle des Klicks auf Seite 1 als Anteil der (ungedrehten) Seite melden
function klick(e, n) {
  if (!props.anlernen || n !== 1) return;
  const p = aufSeite(e, n);
  if (p) emit('punkt', p);
}

// Zur Stelle zoomen: so nah, dass der Wert gut ein Drittel der Ansicht breit ist, und ihn mittig zeigen.
// Gescrollt wird nur in der Ansicht selbst, die Workbench drumherum bleibt stehen.
watch(() => props.fokus, async (f) => {
  const el = flaeche.value;
  const seite = seitenEl.value[0];
  if (!f?.lage || !el || !seite || !dokument.value) return;
  const breiteBeiZoom1 = seite.offsetWidth / zoom.value;
  const breiteWert = drehung.value % 180 ? f.lage.h : f.lage.b;
  zoom.value = Math.min(6, Math.max(1.5, (el.clientWidth * 0.35) / Math.max(breiteWert * breiteBeiZoom1, 1)));
  clearTimeout(zoomTimer);
  await nextTick();
  clearTimeout(zoomTimer);
  await rendern();
  const [mx, my] = angezeigt(f.lage.x + f.lage.b / 2, f.lage.y + f.lage.h / 2);
  el.scrollLeft = seite.offsetLeft + mx * seite.offsetWidth - el.clientWidth / 2;
  el.scrollTop = seite.offsetTop + my * seite.offsetHeight - el.clientHeight / 2;
});

useEventListener(window, 'keydown', (e) => {
  if (e.key === 'Escape') {
    if (notiz.value) { notiz.value = null; return; }
    if (werkzeug.value) { modus.value = 'hand'; return; }
    if (vollbild.value) vollbild.value = false;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'z' && vollbild.value && !notiz.value) { e.preventDefault(); rueckgaengig(); }
});
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
  if (speicherTimer) speichernJetzt();
});
</script>

<template>
  <div class="h-full">
    <Teleport to="body" :disabled="!vollbild">
      <div class="zeichnung-flaeche flex flex-col overflow-hidden border border-line" :class="vollbild ? 'fixed inset-3 z-50 rounded-3xl shadow-2xl' : 'relative h-full rounded-2xl'">
        <div class="flex shrink-0 flex-wrap items-center gap-1 border-b border-line bg-surface px-2 py-1.5">
          <button class="knopf" title="Verkleinern" @click="zoomen(1 / 1.25)"><ZoomOut :size="15" /></button>
          <span class="w-12 text-center text-xs text-mute tnum">{{ Math.round(zoom * 100) }} %</span>
          <button class="knopf" title="Vergrößern" @click="zoomen(1.25)"><ZoomIn :size="15" /></button>
          <button class="knopf" title="Auf Breite einpassen" @click="zoom = 1"><MoveHorizontal :size="15" /></button>
          <button class="knopf" title="90° nach links drehen" @click="drehen(-90)"><RotateCcw :size="15" /></button>
          <button class="knopf" title="90° nach rechts drehen" @click="drehen(90)"><RotateCw :size="15" /></button>
          <span class="mx-1 h-5 w-px bg-line" />
          <button class="knopf" :class="modus === 'hand' ? 'aktiv' : ''" title="Verschieben (Klick öffnet groß)" @click="modus = 'hand'"><Hand :size="15" /></button>
          <button class="knopf" :class="modus === 'text' ? 'aktiv' : ''" title="Text markieren und kopieren" @click="modus = 'text'"><TextCursor :size="15" /></button>
          <template v-if="speicherbar && (vollbild || !anlernen)">
            <span class="mx-1 h-5 w-px bg-line" />
            <button v-for="w in WERKZEUGE" :key="w.id" class="knopf" :class="modus === w.id ? 'aktiv' : ''" :title="w.titel" @click="modus = modus === w.id ? 'hand' : w.id; sichtbar = true"><component :is="w.icon" :size="15" /></button>
            <span v-if="werkzeug && modus !== 'radierer'" class="ml-1 flex items-center gap-1">
              <button
                v-for="(hex, f) in FARBEN" :key="f" class="h-4 w-4 rounded-full ring-offset-1 ring-offset-surface" :class="farbe === f ? 'ring-2 ring-ink' : ''"
                :style="{ background: hex }" :title="f" @click="farbe = f"
              />
            </span>
            <button class="knopf" title="Rückgängig (Strg+Z im Vollbild)" :disabled="!markierungen.length && !verlauf.length" @click="rueckgaengig"><Undo2 :size="15" /></button>
            <button v-if="markierungen.length" class="knopf" :title="sichtbar ? 'Markierungen ausblenden' : 'Markierungen einblenden'" @click="sichtbar = !sichtbar">
              <Eye v-if="sichtbar" :size="15" /><EyeOff v-else :size="15" /><span class="ml-0.5 tnum">{{ markierungen.length }}</span>
            </button>
          </template>
          <span v-if="seiten > 1" class="ml-1 text-xs text-mute">{{ seiten }} Seiten</span>
          <span class="flex-1" />
          <button v-if="fenster === 'knopf'" class="knopf" title="Im eigenen Fenster zeigen (auf den zweiten Bildschirm ziehen)" @click="emit('fenster')"><MonitorUp :size="15" /></button>
          <a v-else-if="fenster !== 'fenster'" class="knopf" :href="url" target="_blank" rel="noopener" title="In neuem Tab öffnen"><ExternalLink :size="15" /></a>
          <button class="knopf" :title="vollbild ? 'Vollbild verlassen (Esc)' : 'Groß öffnen'" @click="vollbild = !vollbild"><Minimize2 v-if="vollbild" :size="15" /><Maximize2 v-else :size="15" /></button>
        </div>
        <div
          ref="flaeche"
          class="relative min-h-0 flex-1 overflow-auto p-4 [contain:inline-size]"
          :class="[anlernen ? 'modus-anlernen cursor-crosshair select-none' : modus === 'hand' ? 'cursor-grab active:cursor-grabbing select-none' : werkzeug ? 'select-none' : '', anlernen ? '' : `modus-${werkzeug ? 'werkzeug' : modus}`]"
          @pointerdown="runter" @pointermove="bewegen" @pointerup="hoch" @pointercancel="hoch"
        >
          <div v-for="n in seiten" :key="n" :ref="(el) => { if (el) seitenEl[n - 1] = el; }" class="seite relative mx-auto mb-4 bg-white shadow-md" @click="klick($event, n)">
            <canvas class="block" />
            <div class="textLayer" />
            <!-- Markierungen und Anlern-Markierung, in Seitenpunkten ohne Drehung; die Gruppe dreht mit -->
            <svg
              class="ebene absolute inset-0 h-full w-full" :class="werkzeug && !anlernen ? 'ebene-aktiv' : ''" :style="{ cursor: modus === 'radierer' ? 'pointer' : werkzeug ? 'crosshair' : undefined }"
              :viewBox="`0 0 ${ansicht(n).w} ${ansicht(n).h}`" preserveAspectRatio="none"
              @pointerdown="werkzeugRunter($event, n)" @pointermove="werkzeugBewegen($event, n)" @pointerup="werkzeugHoch" @pointercancel="werkzeugHoch"
            >
              <defs>
                <marker v-for="(hex, f) in FARBEN" :id="`spitze-${f}`" :key="f" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                  <path d="M0 0 L10 5 L0 10 z" :fill="hex" />
                </marker>
              </defs>
              <g :ref="(el) => { if (el) gruppen[n - 1] = el; }" :transform="drehTransform(n)">
                <template v-if="sichtbar">
                  <template v-for="x in aufSeiteN(n)" :key="x.i">
                    <rect
                      v-if="x.m.typ === 'marker'" class="teil" :x="x.m.x * masseVon(n).w" :y="x.m.y * masseVon(n).h" :width="x.m.b * masseVon(n).w" :height="x.m.h * masseVon(n).h"
                      :fill="FARBEN[x.m.farbe]" fill-opacity="0.35" style="mix-blend-mode: multiply" @pointerdown="loeschen(x.i)"
                    />
                    <rect
                      v-else-if="x.m.typ === 'rahmen'" class="teil" :x="x.m.x * masseVon(n).w" :y="x.m.y * masseVon(n).h" :width="x.m.b * masseVon(n).w" :height="x.m.h * masseVon(n).h"
                      fill="transparent" :stroke="FARBEN[x.m.farbe]" :stroke-width="strich(n)" @pointerdown="loeschen(x.i)"
                    />
                    <line
                      v-else-if="x.m.typ === 'pfeil'" class="teil" :x1="x.m.x1 * masseVon(n).w" :y1="x.m.y1 * masseVon(n).h" :x2="x.m.x2 * masseVon(n).w" :y2="x.m.y2 * masseVon(n).h"
                      :stroke="FARBEN[x.m.farbe]" :stroke-width="strich(n)" stroke-linecap="round" :marker-end="`url(#spitze-${x.m.farbe})`" @pointerdown="loeschen(x.i)"
                    />
                    <path
                      v-else-if="x.m.typ === 'freihand'" class="teil" :d="pfad(x.m, n)" fill="none" :stroke="FARBEN[x.m.farbe]" :stroke-width="strich(n)"
                      stroke-linecap="round" stroke-linejoin="round" @pointerdown="loeschen(x.i)"
                    />
                    <g v-else-if="x.m.typ === 'notiz'" class="teil" @pointerdown="loeschen(x.i)">
                      <text
                        :x="x.m.x * masseVon(n).w" :y="x.m.y * masseVon(n).h" :font-size="schrift(n)" :fill="FARBEN[x.m.farbe]" font-weight="600" dominant-baseline="hanging"
                        paint-order="stroke" stroke="#fff" :stroke-width="schrift(n) * 0.28" stroke-linejoin="round"
                      ><tspan v-for="(z, k) in x.m.text.split('\n')" :key="k" :x="x.m.x * masseVon(n).w" :dy="k ? schrift(n) * 1.2 : 0">{{ z }}</tspan></text>
                    </g>
                  </template>
                </template>
                <!-- gerade gezogen -->
                <template v-if="entwurf && entwurf.seite === n">
                  <rect
                    v-if="entwurf.typ === 'marker' || entwurf.typ === 'rahmen'" :x="entwurf.x * masseVon(n).w" :y="entwurf.y * masseVon(n).h" :width="entwurf.b * masseVon(n).w" :height="entwurf.h * masseVon(n).h"
                    :fill="entwurf.typ === 'marker' ? FARBEN[entwurf.farbe] : 'transparent'" :fill-opacity="entwurf.typ === 'marker' ? 0.35 : 0" :stroke="entwurf.typ === 'rahmen' ? FARBEN[entwurf.farbe] : 'none'" :stroke-width="strich(n)"
                  />
                  <line
                    v-else-if="entwurf.typ === 'pfeil'" :x1="entwurf.x1 * masseVon(n).w" :y1="entwurf.y1 * masseVon(n).h" :x2="entwurf.x2 * masseVon(n).w" :y2="entwurf.y2 * masseVon(n).h"
                    :stroke="FARBEN[entwurf.farbe]" :stroke-width="strich(n)" stroke-linecap="round" :marker-end="`url(#spitze-${entwurf.farbe})`"
                  />
                  <path v-else-if="entwurf.typ === 'freihand'" :d="pfad(entwurf, n)" fill="none" :stroke="FARBEN[entwurf.farbe]" :stroke-width="strich(n)" stroke-linecap="round" stroke-linejoin="round" />
                </template>
                <!-- Stelle beim Anlernen -->
                <rect
                  v-if="n === 1 && markierung" class="markierung"
                  :x="(markierung.x - 0.004) * masseVon(1).w" :y="(markierung.y - 0.004) * masseVon(1).h" :width="(markierung.b + 0.008) * masseVon(1).w" :height="(markierung.h + 0.008) * masseVon(1).h"
                  rx="2" :stroke-width="strich(1)"
                />
              </g>
            </svg>
            <textarea
              v-if="notiz && notiz.seite === n" v-model="notiz.text" class="notiz-eingabe absolute z-10 w-56 rounded-lg border border-accent bg-surface p-2 text-sm text-ink shadow-lg"
              :style="{ left: `${notiz.links}px`, top: `${notiz.oben}px` }" rows="2" placeholder="Notiz, Enter speichert"
              @pointerdown.stop @keydown.enter.exact.prevent="notizSpeichern" @blur="notizSpeichern"
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
    <div v-if="vollbild" class="grid h-full place-items-center rounded-2xl border border-dashed border-line text-xs text-mute">Groß geöffnet</div>
  </div>
</template>

<style scoped>
.zeichnung-flaeche { background: var(--surface-2); }
.knopf { display: grid; grid-auto-flow: column; place-items: center; height: 1.85rem; min-width: 1.85rem; padding: 0 0.45rem; border-radius: 0.6rem; font-size: 0.72rem; color: var(--mute); }
.knopf:hover { background: var(--surface-2); color: var(--ink); }
.knopf:disabled { opacity: 0.35; pointer-events: none; }
.knopf.aktiv { background: var(--accent-soft); color: var(--accent); }
.modus-hand :deep(.textLayer), .modus-werkzeug :deep(.textLayer) { pointer-events: none; }
.modus-anlernen :deep(.textLayer span) { cursor: crosshair; border-radius: 2px; }
.modus-anlernen :deep(.textLayer span:hover) { background: color-mix(in srgb, var(--accent) 22%, transparent); outline: 1px solid var(--accent); }
/* Die Markierungsebene liegt über allem, fängt die Maus aber nur, wenn ein Werkzeug gewählt ist */
.ebene { z-index: 2; pointer-events: none; overflow: visible; }
.ebene-aktiv { pointer-events: all; touch-action: none; }
.ebene-aktiv .teil { pointer-events: visiblePainted; }
.markierung { fill: color-mix(in srgb, var(--accent) 14%, transparent); stroke: var(--accent); animation: markieren 1.4s ease-out 2; }
@keyframes markieren { 0% { opacity: 1; } 50% { opacity: 0.45; } 100% { opacity: 1; } }

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
