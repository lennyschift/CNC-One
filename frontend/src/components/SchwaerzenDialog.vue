<script setup>
// Gegenprüfung einer geschwärzten Zeichnung, bevor sie an Partner geht (oder in die Fertigung).
// „Bearbeiten“: das Original mit den Bereichen (farbig markiert, die Schrift darunter bleibt lesbar) — aufziehen,
// verschieben, Größe ändern, löschen, neu erkennen. „Ergebnis“: die geschwärzte Datei, so wie sie verschickt wird
// (weiß übermalt, nur Bilder). Freigeben geht erst, wenn das Ergebnis angesehen, die Prüfung bestanden und bestätigt ist.
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { X, ShieldCheck, ShieldAlert, Eye, PencilLine, Wand2, Trash2, Loader, Check, AlertTriangle, CircleCheck, CircleAlert, CircleX, RotateCcw, Square, SquareDashed, Hand, ZoomIn, ZoomOut, MoveHorizontal, Maximize } from '@lucide/vue';
import { useSchwaerzen } from '../stores/schwaerzen.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ eintrag: { type: Object, required: true } }); // { url, bauteil, kunde, revision, teilenummer, name, dateiname }
const emit = defineEmits(['schliessen', 'freigegeben']);
const sw = useSchwaerzen();
const ui = useUi();
const s = computed(() => sw.stand[props.eintrag.url] ?? null);

const ansicht = ref('bearbeiten'); // 'bearbeiten' | 'ergebnis'
const ergebnisGesehen = ref(false);
const bestaetigt = ref(false);
const laedt = ref(true);
const arbeitet = ref('');
const geaendert = ref(false);
const bereiche = ref([]);
const auswahl = ref(null);
const hinweise = ref([]);
let k = null;
let original = null;
let ergebnis = null;
const seiten = ref([]); // [{ nr, w, h }] (pt) des Originals
const ergSeiten = ref([]);
const leinwand = reactive({}); // 'o3' / 'e3' → canvas

// ---- Ansicht wie im PDF-Programm: Zoom (100 % = Seitenbreite), Verschieben mit Hand-Werkzeug, mittlerer Maustaste oder Leertaste
const flaeche = ref(null); // Scroll-Bereich der Seiten
const basis = ref(900); // Seitenbreite bei 100 % (Breite des Bereichs)
const zoom = ref(1);
const werkzeug = ref('rahmen'); // 'rahmen' | 'hand'
const leertaste = ref(false);
const ZOOM_MIN = 0.25, ZOOM_MAX = 8;
const seitenBreite = computed(() => Math.round(basis.value * zoom.value));
const zoomText = computed(() => `${Math.round(zoom.value * 100)} %`);
function basisMessen() { if (flaeche.value) basis.value = Math.max(400, flaeche.value.clientWidth - 40); }

let zeichnet = 0;
async function seitenZeichnen(doc, praefix, liste) {
  const lauf = ++zeichnet; // ein neuer Zoom bricht das alte Zeichnen ab
  const dpr = window.devicePixelRatio || 1;
  for (const sz of liste) {
    if (lauf !== zeichnet) return;
    const c = leinwand[`${praefix}${sz.nr}`];
    if (!c) continue;
    const page = await doc.getPage(sz.nr);
    // scharf in jeder Vergrößerung, aber höchstens ~10.000 Pixel breit (Speicher)
    const vp = page.getViewport({ scale: Math.min(seitenBreite.value * dpr, 10000) / sz.w });
    const neu = document.createElement('canvas');
    neu.width = Math.ceil(vp.width);
    neu.height = Math.ceil(vp.height);
    await page.render({ canvas: neu, viewport: vp }).promise;
    if (lauf !== zeichnet) return;
    // erst fertig zeichnen, dann tauschen: kein Flackern beim Zoomen
    c.width = neu.width;
    c.height = neu.height;
    c.getContext('2d').drawImage(neu, 0, 0);
  }
}
const aktuelleSeiten = () => (ansicht.value === 'ergebnis' ? [ergebnis, 'e', ergSeiten.value] : [original, 'o', seiten.value]);
let zoomTimer = null;
function neuZeichnenSpaeter() {
  clearTimeout(zoomTimer);
  zoomTimer = setTimeout(() => { const [d, p, l] = aktuelleSeiten(); if (d) seitenZeichnen(d, p, l); }, 180);
}
// Zoom um einen Punkt (Mausposition), sonst um die Mitte des Bereichs
async function zoomAuf(z, um = null) {
  const el = flaeche.value;
  const neu = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  if (!el || neu === zoom.value) return;
  const r = el.getBoundingClientRect();
  const px = um ? um.x - r.left : el.clientWidth / 2;
  const py = um ? um.y - r.top : el.clientHeight / 2;
  const f = neu / zoom.value;
  const sx = (el.scrollLeft + px) * f - px;
  const sy = (el.scrollTop + py) * f - py;
  zoom.value = neu;
  await nextTick();
  el.scrollLeft = sx;
  el.scrollTop = sy;
  neuZeichnenSpaeter();
}
const zoomRein = () => zoomAuf(zoom.value * 1.25);
const zoomRaus = () => zoomAuf(zoom.value / 1.25);
const breiteAnpassen = () => zoomAuf(1);
function seiteAnpassen() {
  const el = flaeche.value;
  const sz = (ansicht.value === 'ergebnis' ? ergSeiten.value : seiten.value)[0];
  if (el && sz) zoomAuf(Math.min(1, (el.clientHeight - 50) / ((basis.value * sz.h) / sz.w)));
}
function rad(e) {
  if (!e.ctrlKey && !e.metaKey) return;
  e.preventDefault();
  zoomAuf(zoom.value * (e.deltaY < 0 ? 1.15 : 1 / 1.15), { x: e.clientX, y: e.clientY });
}
// Verschieben: Hand-Werkzeug, mittlere Maustaste oder Leertaste gedrückt halten
let pan = null;
const schiebt = ref(false);
function panStart(e) {
  const el = flaeche.value;
  if (!el || !(e.button === 1 || (e.button === 0 && (werkzeug.value === 'hand' || leertaste.value || ansicht.value === 'ergebnis')))) return false;
  e.preventDefault();
  pan = { x: e.clientX, y: e.clientY, sl: el.scrollLeft, st: el.scrollTop, id: e.pointerId };
  schiebt.value = true;
  el.setPointerCapture(e.pointerId);
  return true;
}
function panBewegen(e) {
  if (!pan || e.pointerId !== pan.id) return;
  flaeche.value.scrollLeft = pan.sl - (e.clientX - pan.x);
  flaeche.value.scrollTop = pan.st - (e.clientY - pan.y);
}
function panEnde(e) {
  if (!pan || e.pointerId !== pan.id) return;
  pan = null;
  schiebt.value = false;
}
const cursor = computed(() => (schiebt.value ? 'grabbing' : werkzeug.value === 'hand' || leertaste.value || ansicht.value === 'ergebnis' ? 'grab' : 'crosshair'));
async function seitenListe(doc) {
  const out = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const vp = (await doc.getPage(i)).getViewport({ scale: 1 });
    out.push({ nr: i, w: vp.width, h: vp.height });
  }
  return out;
}

async function ergebnisLaden() {
  if (!s.value?.ergebnisUrl) return;
  const r = await fetch(s.value.ergebnisUrl, { credentials: 'same-origin' });
  ergebnis?.destroy?.();
  ergebnis = await k.pdfOeffnen(new Uint8Array(await r.arrayBuffer()));
  ergSeiten.value = await seitenListe(ergebnis);
  await nextTick();
  if (ansicht.value === 'ergebnis') await seitenZeichnen(ergebnis, 'e', ergSeiten.value);
}

onMounted(async () => {
  try {
    k = await import('../lib/schwaerzen/cncone.js');
    await sw.statusLaden([props.eintrag.url]);
    original = (await k.pdfLaden(props.eintrag.url)).doc;
    seiten.value = await seitenListe(original);
    if (s.value?.bereiche?.length || s.value) {
      bereiche.value = (s.value?.bereiche ?? []).map((b) => ({ ...b, id: k.neueId() }));
      hinweise.value = s.value?.protokoll?.hinweise ?? [];
    } else {
      await neuErkennen();
    }
    // erst die Seiten anzeigen (die Leinwände entstehen mit laedt = false), dann zeichnen
    laedt.value = false;
    await nextTick();
    basisMessen();
    await nextTick();
    await seitenZeichnen(original, 'o', seiten.value);
    await ergebnisLaden();
  } catch (e) {
    ui.toast(`Zeichnung: ${e.message}`, 'warn');
  } finally {
    laedt.value = false;
  }
});
onBeforeUnmount(() => { clearTimeout(zoomTimer); original?.destroy?.(); ergebnis?.destroy?.(); });

watch(ansicht, async (a) => {
  await nextTick();
  if (a === 'ergebnis') { ergebnisGesehen.value = true; if (ergebnis) await seitenZeichnen(ergebnis, 'e', ergSeiten.value); }
  else if (original) await seitenZeichnen(original, 'o', seiten.value);
});

async function neuErkennen() {
  arbeitet.value = 'Erkennung läuft …';
  try {
    const regeln = k.regelnMitKunde(await sw.regelnFuer(props.eintrag.kunde));
    const r = await k.erkennen(original, regeln);
    // von Hand gesetzte Bereiche bleiben, automatische werden ersetzt
    bereiche.value = [...bereiche.value.filter((b) => b.source === 'manual'), ...r.bereiche];
    hinweise.value = r.hinweise;
    geaendert.value = true;
  } finally { arbeitet.value = ''; }
}

// ---- Bereiche mit der linken Maustaste: aufziehen (leere Stelle), verschieben (Bereich), Größe (Ecke unten rechts).
// Die Seite hält den Zeiger fest (Pointer Capture): das Ziehen reißt auch über Rahmen, Rand oder Fensterkante nicht ab.
let zug = null;
const MIN = 0.003;
function punkt(e, el) {
  const r = el.getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
}
function runter(e, nr, b = null, ecke = false) {
  if (panStart(e)) return;
  if (e.button !== 0 || zug) return;
  const el = e.currentTarget.closest('[data-seite]');
  const p = punkt(e, el);
  e.preventDefault();
  e.stopPropagation();
  if (b) {
    auswahl.value = b.id;
    zug = { art: ecke ? 'groesse' : 'schieben', b, start: p, alt: { ...b }, el, id: e.pointerId };
  } else {
    const neu = { id: k.neueId(), page: nr, x0: p.x, y0: p.y, x1: p.x, y1: p.y, source: 'manual', kind: 'manual', reason: 'von Hand' };
    bereiche.value.push(neu);
    zug = { art: 'neu', b: bereiche.value.at(-1), start: p, el, id: e.pointerId };
    auswahl.value = neu.id;
  }
  el.setPointerCapture(e.pointerId);
  el.addEventListener('pointermove', bewegen);
  el.addEventListener('pointerup', los);
  el.addEventListener('pointercancel', los);
}
function bewegen(e) {
  if (!zug || e.pointerId !== zug.id) return;
  const p = punkt(e, zug.el);
  const b = zug.b;
  if (zug.art === 'neu') {
    Object.assign(b, { x0: Math.min(zug.start.x, p.x), y0: Math.min(zug.start.y, p.y), x1: Math.max(zug.start.x, p.x), y1: Math.max(zug.start.y, p.y) });
  } else if (zug.art === 'schieben') {
    const dx = Math.min(1 - zug.alt.x1, Math.max(-zug.alt.x0, p.x - zug.start.x));
    const dy = Math.min(1 - zug.alt.y1, Math.max(-zug.alt.y0, p.y - zug.start.y));
    Object.assign(b, { x0: zug.alt.x0 + dx, x1: zug.alt.x1 + dx, y0: zug.alt.y0 + dy, y1: zug.alt.y1 + dy });
  } else {
    Object.assign(b, { x1: Math.max(b.x0 + MIN, p.x), y1: Math.max(b.y0 + MIN, p.y) });
  }
  if (zug.art !== 'neu') b.source = 'manual';
  geaendert.value = true;
}
function los(e) {
  if (!zug || (e && e.pointerId !== zug.id)) return;
  const el = zug.el;
  el.removeEventListener('pointermove', bewegen);
  el.removeEventListener('pointerup', los);
  el.removeEventListener('pointercancel', los);
  if (el.hasPointerCapture?.(zug.id)) el.releasePointerCapture(zug.id);
  // nur ein Klick ohne Ziehen: kein Bereich
  if (zug.art === 'neu' && (zug.b.x1 - zug.b.x0 < MIN || zug.b.y1 - zug.b.y0 < MIN)) {
    const weg = zug.b.id;
    bereiche.value = bereiche.value.filter((b) => b.id !== weg);
    if (auswahl.value === weg) auswahl.value = null;
  }
  zug = null;
}
function loeschen(id) { bereiche.value = bereiche.value.filter((b) => b.id !== id); geaendert.value = true; if (auswahl.value === id) auswahl.value = null; }
const eingabe = (e) => /input|textarea|select/i.test(e.target.tagName);
function taste(e) {
  if (eingabe(e)) return;
  if ((e.key === 'Delete' || e.key === 'Backspace') && auswahl.value) loeschen(auswahl.value);
  else if (e.key === 'Escape') emit('schliessen');
  else if (e.key === ' ') { e.preventDefault(); leertaste.value = true; }
  else if (e.key === '+' || e.key === '=') zoomRein();
  else if (e.key === '-') zoomRaus();
  else if (e.key === '0') breiteAnpassen();
  else if (e.key === 'h' || e.key === 'H') werkzeug.value = werkzeug.value === 'hand' ? 'rahmen' : 'hand';
}
function tasteLos(e) { if (e.key === ' ') leertaste.value = false; }
onMounted(() => {
  window.addEventListener('keydown', taste);
  window.addEventListener('keyup', tasteLos);
  window.addEventListener('resize', basisMessen);
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', taste);
  window.removeEventListener('keyup', tasteLos);
  window.removeEventListener('resize', basisMessen);
});
watch(flaeche, (el, alt) => {
  alt?.removeEventListener('wheel', rad);
  el?.addEventListener('wheel', rad, { passive: false });
}, { immediate: true });
watch(basis, () => neuZeichnenSpaeter());

const ART = { keyword: 'Stichwort', header: 'Kopfzeile', changeTable: 'Änderungstabelle', labelRight: 'Wert neben Beschriftung', email: 'E-Mail', phone: 'Telefon', logo: 'Logo', annotation: 'Stempel/Feld', manual: 'Von Hand' };
const farbe = (b) => (b.source === 'manual' ? '#2563eb' : b.kind === 'logo' ? '#7c3aed' : b.kind === 'annotation' ? '#d97706' : '#dc2626');

// ---- Änderungen übernehmen: neu schwärzen und prüfen (neue Fassung, die alte ungeprüfte wird verworfen)
async function uebernehmen() {
  arbeitet.value = 'Wird geschwärzt und geprüft …';
  try {
    await sw.erzeugen(props.eintrag, { bereiche: bereiche.value, onProgress: (p) => { arbeitet.value = `${{ analyse: 'Analyse', render: 'Seite wird gerastert', save: 'Speichern', verify: 'Prüfung' }[p.phase]} ${p.page}/${p.pageCount} …`; } });
    geaendert.value = false;
    bestaetigt.value = false;
    ergebnisGesehen.value = false;
    await ergebnisLaden();
    ansicht.value = 'ergebnis';
  } catch (e) {
    ui.toast(`Schwärzen: ${e.message}`, 'warn');
  } finally { arbeitet.value = ''; }
}
const kannFreigeben = computed(() => s.value?.status === 'Ungeprüft' && s.value.pruefungBestanden && !geaendert.value && ergebnisGesehen.value && bestaetigt.value && !arbeitet.value);
async function freigeben() {
  const r = await sw.freigeben(props.eintrag.url);
  if (r) emit('freigegeben', r);
}
const pruefungen = computed(() => [...(s.value?.protokoll?.checks ?? []), ...(s.value?.protokoll?.serverPruefung ? [{ id: 'server', label: 'Zweite Prüfung auf dem Server', status: s.value.protokoll.serverPruefung.bestanden ? 'ok' : 'fail', detail: s.value.protokoll.serverPruefung.fehler?.join(' · ') || 'Nur Bilder, keine Schrift, kein Text, keine Begriffe des Kunden.' }] : [])]);
const ICON = { ok: CircleCheck, warn: CircleAlert, fail: CircleX };
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const anzahlJeSeite = (nr) => bereiche.value.filter((b) => b.page === nr).length;
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[70] grid place-items-center bg-black/55 p-3 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <div class="card flex h-[96vh] w-[min(1500px,98vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
          <ShieldCheck :size="20" class="text-accent" />
          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold">Zeichnung schwärzen und prüfen: {{ eintrag.teilenummer || eintrag.dateiname }}</h2>
            <p class="truncate text-xs text-mute">{{ eintrag.dateiname }}<template v-if="eintrag.name"> · {{ eintrag.name }}</template> · an Partner geht nur die geprüfte, geschwärzte Fassung</p>
          </div>
          <div class="ml-auto flex gap-1 rounded-xl border border-line bg-surface2 p-1 text-sm">
            <button type="button" class="flex items-center gap-1.5 rounded-lg px-3 py-1.5" :class="ansicht === 'bearbeiten' ? 'bg-surface font-medium shadow-sm' : 'text-mute'" @click="ansicht = 'bearbeiten'"><PencilLine :size="14" /> Bearbeiten (Original)</button>
            <button type="button" class="flex items-center gap-1.5 rounded-lg px-3 py-1.5" :class="ansicht === 'ergebnis' ? 'bg-surface font-medium shadow-sm' : 'text-mute'" :disabled="!s?.ergebnisUrl" @click="ansicht = 'ergebnis'"><Eye :size="14" /> Ergebnis (wird verschickt)</button>
          </div>
          <button type="button" class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" title="Schließen" @click="emit('schliessen')"><X :size="18" /></button>
        </header>

        <div class="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_340px] lg:grid-rows-1">
          <!-- Seiten mit Werkzeugleiste (Zoom, Rahmen/Hand) -->
          <div class="flex min-h-0 min-w-0 flex-col bg-surface2">
            <div class="flex flex-wrap items-center gap-1 border-b border-line bg-surface px-3 py-1.5 text-sm">
              <div v-if="ansicht === 'bearbeiten'" class="mr-2 flex gap-0.5 rounded-lg border border-line p-0.5">
                <button type="button" class="flex items-center gap-1 rounded-md px-2 py-1" :class="werkzeug === 'rahmen' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" title="Rahmen aufziehen (linke Maustaste)" @click="werkzeug = 'rahmen'"><SquareDashed :size="15" /> Rahmen</button>
                <button type="button" class="flex items-center gap-1 rounded-md px-2 py-1" :class="werkzeug === 'hand' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" title="Verschieben (H) — auch mit gedrückter Leertaste oder mittlerer Maustaste" @click="werkzeug = 'hand'"><Hand :size="15" /> Verschieben</button>
              </div>
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg hover:bg-surface2" title="Verkleinern (−)" @click="zoomRaus"><ZoomOut :size="16" /></button>
              <button type="button" class="min-w-[64px] rounded-lg px-2 py-1 text-xs font-medium tnum hover:bg-surface2" title="100 % = Seitenbreite" @click="breiteAnpassen">{{ zoomText }}</button>
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg hover:bg-surface2" title="Vergrößern (+)" @click="zoomRein"><ZoomIn :size="16" /></button>
              <button type="button" class="ml-1 flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-mute hover:bg-surface2 hover:text-ink" title="Seitenbreite (0)" @click="breiteAnpassen"><MoveHorizontal :size="14" /> Breite</button>
              <button type="button" class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-mute hover:bg-surface2 hover:text-ink" title="Ganze Seite" @click="seiteAnpassen"><Maximize :size="14" /> Ganze Seite</button>
              <span class="ml-auto hidden text-[11px] text-mute xl:inline">Strg + Mausrad zoomt · Leertaste oder mittlere Maustaste halten zum Verschieben · Entf löscht den gewählten Bereich</span>
            </div>
            <div ref="flaeche" class="min-h-0 flex-1 overflow-auto p-5" :style="{ cursor }" @pointerdown="panStart" @pointermove="panBewegen" @pointerup="panEnde" @pointercancel="panEnde">
              <div v-if="laedt" class="flex items-center gap-2 p-6 text-sm text-mute"><Loader :size="16" class="animate-spin" /> Zeichnung wird geladen und erkannt …</div>
              <template v-else-if="ansicht === 'bearbeiten'">
                <div v-for="sz in seiten" :key="`o${sz.nr}`" class="mx-auto mb-5" :style="{ width: `${seitenBreite}px` }">
                  <div class="mb-1 text-xs text-mute">Seite {{ sz.nr }} · {{ anzahlJeSeite(sz.nr) }} Bereich(e) · Rahmen mit der linken Maustaste aufziehen</div>
                  <div data-seite class="relative select-none bg-white shadow" style="touch-action: none" :style="{ cursor }" @pointerdown="runter($event, sz.nr)">
                    <canvas :ref="(el) => { if (el) leinwand[`o${sz.nr}`] = el; }" class="pointer-events-none block h-auto w-full" />
                    <div v-for="b in bereiche.filter((x) => x.page === sz.nr)" :key="b.id" class="absolute border-2" :class="auswahl === b.id ? 'ring-2 ring-offset-1' : ''"
                      :style="{ left: `${b.x0 * 100}%`, top: `${b.y0 * 100}%`, width: `${(b.x1 - b.x0) * 100}%`, height: `${(b.y1 - b.y0) * 100}%`, borderColor: farbe(b), background: `${farbe(b)}33`, cursor: werkzeug === 'hand' || leertaste ? cursor : 'move' }"
                      :title="`${ART[b.kind] ?? 'Bereich'}: ${b.reason || ''}`" @pointerdown="runter($event, sz.nr, b)">
                      <span class="absolute -bottom-2 -right-2 h-4 w-4 cursor-se-resize rounded-sm border-2 border-white shadow" :style="{ background: farbe(b) }" @pointerdown="runter($event, sz.nr, b, true)" />
                    </div>
                  </div>
                </div>
              </template>
              <template v-else>
                <div v-for="sz in ergSeiten" :key="`e${sz.nr}`" class="mx-auto mb-5" :style="{ width: `${seitenBreite}px` }">
                  <div class="mb-1 text-xs text-mute">Ergebnis Seite {{ sz.nr }} von {{ ergSeiten.length }} — so bekommt es der Partner</div>
                  <canvas :ref="(el) => { if (el) leinwand[`e${sz.nr}`] = el; }" class="pointer-events-none block h-auto w-full bg-white shadow" />
                </div>
              </template>
            </div>
          </div>

          <!-- Seitenleiste -->
          <aside class="flex max-h-[45vh] min-h-0 min-w-0 flex-col border-t border-line lg:max-h-none lg:border-l lg:border-t-0">
            <div class="min-h-0 flex-1 space-y-4 overflow-auto p-4 text-sm">
              <div v-if="s" class="rounded-xl border px-3 py-2" :class="s.status === 'Freigegeben' ? 'border-ok/40 bg-ok/5' : 'border-warn/40 bg-warn/5'">
                <div class="flex items-center gap-1.5 font-medium" :class="s.status === 'Freigegeben' ? 'text-ok' : 'text-warn'">
                  <ShieldCheck v-if="s.status === 'Freigegeben'" :size="15" /><ShieldAlert v-else :size="15" />
                  {{ s.status === 'Freigegeben' ? `Freigegeben von ${s.geprueftVon}` : 'Noch nicht geprüft' }}
                </div>
                <div class="text-xs text-mute">{{ s.status === 'Freigegeben' ? zeit(s.geprueftAm) : `${s.automatisch ? 'automatisch' : 'von ' + s.erstelltVon} erstellt am ${zeit(s.erstellt)}` }}</div>
              </div>
              <p v-else-if="!laedt" class="rounded-xl bg-surface2 px-3 py-2 text-xs text-mute">Noch keine geschwärzte Fassung. Bereiche prüfen und „Schwärzen und prüfen“ drücken.</p>

              <div v-if="hinweise.length" class="space-y-1">
                <p v-for="(h, i) in hinweise" :key="i" class="flex gap-1.5 rounded-lg bg-warn/10 px-2.5 py-1.5 text-xs text-warn"><AlertTriangle :size="13" class="mt-0.5 shrink-0" />{{ h }}</p>
              </div>

              <section>
                <div class="mb-1.5 flex items-center justify-between">
                  <span class="label">Bereiche ({{ bereiche.length }})</span>
                  <button type="button" class="inline-flex items-center gap-1 text-xs text-accent hover:underline" :disabled="!!arbeitet || laedt" @click="neuErkennen"><Wand2 :size="12" /> Neu erkennen</button>
                </div>
                <div class="max-h-[260px] space-y-1 overflow-auto">
                  <div v-for="b in bereiche" :key="b.id" class="flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-1 text-xs" :class="auswahl === b.id ? 'border-accent bg-accent-soft' : 'border-line'" @click="auswahl = b.id; ansicht = 'bearbeiten'">
                    <Square :size="11" :style="{ color: farbe(b) }" />
                    <span class="min-w-0 flex-1 truncate"><span class="font-medium">{{ ART[b.kind] ?? 'Bereich' }}</span> <span class="text-mute">S. {{ b.page }} · {{ b.reason }}</span></span>
                    <button type="button" class="text-mute hover:text-accent" title="Bereich entfernen" @click.stop="loeschen(b.id)"><Trash2 :size="12" /></button>
                  </div>
                  <p v-if="!bereiche.length" class="text-xs text-mute">Keine Bereiche — die Zeichnung würde nur gerastert.</p>
                </div>
              </section>

              <section v-if="pruefungen.length">
                <div class="label mb-1.5">Prüfung der geschwärzten Datei</div>
                <div class="space-y-1">
                  <div v-for="c in pruefungen" :key="c.id" class="flex gap-1.5 text-xs" :title="c.detail">
                    <component :is="ICON[c.status]" :size="13" class="mt-0.5 shrink-0" :class="{ ok: 'text-ok', warn: 'text-warn', fail: 'text-accent' }[c.status]" />
                    <span><span class="font-medium">{{ c.label }}</span><span class="block text-mute">{{ c.detail }}</span></span>
                  </div>
                </div>
              </section>
            </div>

            <footer class="space-y-2 border-t border-line bg-surface2 p-4">
              <p v-if="arbeitet" class="flex items-center gap-2 text-xs text-mute"><Loader :size="13" class="animate-spin" /> {{ arbeitet }}</p>
              <button type="button" class="btn w-full justify-center" :class="geaendert || !s ? 'btn-primary' : ''" :disabled="!!arbeitet || laedt || (!geaendert && !!s)" @click="uebernehmen"><RotateCcw :size="15" /> {{ s ? 'Änderungen schwärzen und prüfen' : 'Schwärzen und prüfen' }}</button>
              <template v-if="s?.status === 'Ungeprüft'">
                <p v-if="!ergebnisGesehen && !geaendert" class="text-xs text-warn">Bitte das Ergebnis Seite für Seite ansehen (oben „Ergebnis“).</p>
                <label class="flex items-start gap-2 text-xs"><input v-model="bestaetigt" type="checkbox" class="mt-0.5 accent-[var(--accent)]" :disabled="!ergebnisGesehen || geaendert" /> Ich habe alle Seiten des Ergebnisses geprüft: keine Kundendaten mehr lesbar.</label>
                <button type="button" class="btn btn-primary w-full justify-center" :disabled="!kannFreigeben" :class="kannFreigeben ? '' : 'pointer-events-none opacity-40'" @click="freigeben"><Check :size="15" /> Geprüft und freigeben</button>
                <p v-if="!s.pruefungBestanden" class="text-xs text-accent">Die automatische Prüfung ist nicht bestanden — so lässt sich nicht freigeben.</p>
              </template>
            </footer>
          </aside>
        </div>
      </div>
    </div>
  </Teleport>
</template>
