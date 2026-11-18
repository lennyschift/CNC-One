<script setup>
// Filter für eine Liste, in der Oberfläche anpassbar: „+ Filter“ bietet jede Eigenschaft der Einträge an (aus den Daten
// abgeleitet), Felder lassen sich anheften (immer sichtbar) und Filter als Ansicht unter einem Namen speichern.
// Gemerkt wird je Benutzer und Liste auf dem Server (an jedem PC gleich); der Browser hält nur eine Kopie für den
// schnellen Start. Liefert die gefilterte Liste über v-model.
import { ref, computed, watch, onMounted } from 'vue';
import { onClickOutside, useDebounceFn } from '@vueuse/core';
import { call } from '../data/api.js';
import { ListFilter, Plus, X, Pin, PinOff, Bookmark, Trash2, Search } from '@lucide/vue';
import { felderAus, neuerFilter, anwenden, aktiv, beschreibung } from '../lib/filter.js';

const props = defineProps({
  liste: { type: Array, required: true },
  modul: { type: String, required: true }, // Schlüssel zum Merken, z. B. "auftraege"
  beschriftungen: { type: Object, default: () => ({}) }, // { pfad: 'Beschriftung' } – empfohlene Felder, zuerst angeboten
  ausblenden: { type: Array, default: () => [] },
  standardAngeheftet: { type: Array, default: () => [] }, // Felder, die anfangs angeheftet sind (änderbar)
});
const gefiltert = defineModel({ type: Array, default: () => [] });

const SPEICHER = `cnc-one-filter:${props.modul}`;
function lesen() {
  try { return JSON.parse(localStorage.getItem(SPEICHER) || 'null'); } catch { return null; }
}
const gemerkt = lesen();
const filter = ref(gemerkt?.filter ?? []);
const angeheftet = ref(gemerkt?.angeheftet ?? [...props.standardAngeheftet]);
const ansichten = ref(gemerkt?.ansichten ?? []);
const stand = () => ({ filter: filter.value, angeheftet: angeheftet.value, ansichten: ansichten.value });
const aufServer = useDebounceFn(() => call('cnc_one.api.einstellung.filter_speichern', { modul: props.modul, daten: stand() }).catch(() => {}), 700);
let geladen = false;
watch([filter, angeheftet, ansichten], () => {
  try { localStorage.setItem(SPEICHER, JSON.stringify(stand())); } catch { /* privat */ }
  if (geladen) aufServer();
}, { deep: true });
// Stand des Benutzers vom Server; gibt es dort noch nichts, wird die Kopie aus dem Browser übernommen
onMounted(async () => {
  try {
    const d = await call('cnc_one.api.einstellung.filter_holen', { modul: props.modul });
    if (d) {
      filter.value = d.filter ?? [];
      angeheftet.value = d.angeheftet ?? [];
      ansichten.value = d.ansichten ?? [];
    } else if (gemerkt) aufServer();
  } catch { /* offline: die Kopie aus dem Browser gilt */ }
  geladen = true;
});

const felder = computed(() => felderAus(props.liste, { beschriftungen: props.beschriftungen, ausblenden: props.ausblenden }));
const feld = (pfad) => felder.value.find((f) => f.pfad === pfad);
watch([() => props.liste, filter], () => { gefiltert.value = anwenden(props.liste, filter.value.filter((f) => feld(f.pfad) || !props.liste.length)); }, { deep: true, immediate: true });

// Angeheftete Felder ohne Filter erscheinen als leere Knöpfe
const knoepfe = computed(() => {
  const da = new Set(filter.value.map((f) => f.pfad));
  return [...filter.value.map((f, i) => ({ f, i })), ...angeheftet.value.filter((p) => !da.has(p) && feld(p)).map((p) => ({ f: neuerFilter(feld(p)), i: -1 }))];
});
const anzahlAktiv = computed(() => filter.value.filter(aktiv).length);

// ---- Bearbeiten eines Filters (Klappfenster)
const offen = ref(null); // { i } Index in filter
const menu = ref(false);
const suche = ref('');
const huelle = ref(null);
onClickOutside(huelle, () => { offen.value = null; menu.value = false; });

function oeffnen(k) {
  menu.value = false;
  if (k.i < 0) { filter.value.push(k.f); offen.value = filter.value.length - 1; } else offen.value = offen.value === k.i ? null : k.i;
}
function hinzufuegen(fd) {
  const i = filter.value.findIndex((f) => f.pfad === fd.pfad);
  if (i >= 0) offen.value = i;
  else { filter.value.push(neuerFilter(fd)); offen.value = filter.value.length - 1; }
  menu.value = false; suche.value = '';
}
function entfernen(i) { filter.value.splice(i, 1); offen.value = null; }
function anheften(pfad) {
  const i = angeheftet.value.indexOf(pfad);
  if (i >= 0) angeheftet.value.splice(i, 1); else angeheftet.value.push(pfad);
}
function zuruecksetzen() { filter.value = []; offen.value = null; }
const auswahlFeld = computed(() => (offen.value !== null ? feld(filter.value[offen.value]?.pfad) : null));
const angeboten = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return felder.value.filter((f) => !q || f.label.toLowerCase().includes(q));
});
// Anzahl Einträge je Auswahlwert (mit den übrigen Filtern)
function anzahl(pfad, wert) {
  const andere = filter.value.filter((f) => f.pfad !== pfad);
  return anwenden(props.liste, [...andere, { pfad, typ: 'auswahl', wert: [wert] }]).length;
}
// Nach der Wahl geht das Klappfenster gleich zu (für mehrere Werte den Knopf erneut öffnen)
function umschalten(f, w) { const i = f.wert.indexOf(w); if (i >= 0) f.wert.splice(i, 1); else f.wert.push(w); offen.value = null; }
function fertig() { offen.value = null; }

// ---- Ansichten
function ansichtSpeichern() {
  const name = (prompt('Name der Ansicht (z. B. „Offene Aufträge Alpha“):') || '').trim();
  if (!name) return;
  ansichten.value = [...ansichten.value.filter((a) => a.name !== name), { name, filter: JSON.parse(JSON.stringify(filter.value)) }];
  menu.value = false;
}
function ansichtLaden(a) { filter.value = JSON.parse(JSON.stringify(a.filter)); menu.value = false; offen.value = null; }
function ansichtLoeschen(a) { ansichten.value = ansichten.value.filter((x) => x !== a); }
</script>

<template>
  <div ref="huelle" class="relative flex flex-wrap items-center gap-1.5">
    <button type="button" class="btn !py-1.5 !text-sm" :class="menu ? 'border-accent text-accent' : ''" @click="menu = !menu; offen = null">
      <ListFilter :size="15" /> Filter<span v-if="anzahlAktiv" class="rounded-full bg-accent px-1.5 text-[11px] font-semibold text-white">{{ anzahlAktiv }}</span>
    </button>
    <button
      v-for="k in knoepfe" :key="k.f.pfad" type="button" class="inline-flex max-w-[280px] items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition"
      :class="aktiv(k.f) ? 'border-accent bg-accent-soft text-accent' : 'border-dashed border-line text-mute hover:border-mute hover:text-ink'" @click="oeffnen(k)"
    >
      <span class="truncate">{{ beschreibung(k.f, feld(k.f.pfad)) }}</span>
      <X v-if="k.i >= 0 && !angeheftet.includes(k.f.pfad)" :size="12" class="shrink-0 opacity-70 hover:opacity-100" @click.stop="entfernen(k.i)" />
    </button>
    <button v-if="anzahlAktiv" type="button" class="text-xs text-mute hover:text-ink" @click="zuruecksetzen">zurücksetzen</button>

    <!-- Menü: Feld wählen, Ansichten -->
    <div v-if="menu" class="absolute left-0 top-full z-40 mt-1.5 w-80 rounded-xl border border-line bg-surface p-2 shadow-xl">
      <label class="relative mb-1.5 block"><Search :size="14" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-mute" /><input v-model="suche" class="field !py-1.5 !pl-8 !text-sm" placeholder="Eigenschaft suchen …" autofocus /></label>
      <div class="max-h-72 overflow-auto">
        <div v-for="fd in angeboten" :key="fd.pfad" class="group flex items-center gap-1 rounded-lg hover:bg-surface2">
          <button type="button" class="min-w-0 flex-1 truncate px-2.5 py-1.5 text-left text-sm" @click="hinzufuegen(fd)">{{ fd.label }}</button>
          <button type="button" class="px-2 text-mute opacity-0 transition group-hover:opacity-100 hover:text-ink" :class="angeheftet.includes(fd.pfad) ? '!opacity-100 text-accent' : ''" :title="angeheftet.includes(fd.pfad) ? 'Nicht mehr anheften' : 'Anheften: immer als Knopf sichtbar'" @click="anheften(fd.pfad)">
            <PinOff v-if="angeheftet.includes(fd.pfad)" :size="13" /><Pin v-else :size="13" />
          </button>
        </div>
        <p v-if="!angeboten.length" class="px-2.5 py-2 text-xs text-mute">Keine passende Eigenschaft.</p>
      </div>
      <div class="mt-1.5 border-t border-line pt-1.5">
        <div class="label px-2.5 pb-1">Gespeicherte Ansichten</div>
        <div v-for="a in ansichten" :key="a.name" class="group flex items-center rounded-lg hover:bg-surface2">
          <button type="button" class="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-1.5 text-left text-sm" @click="ansichtLaden(a)"><Bookmark :size="13" class="text-mute" /><span class="truncate">{{ a.name }}</span></button>
          <button type="button" class="px-2 text-mute opacity-0 group-hover:opacity-100 hover:text-ink" title="Ansicht löschen" @click="ansichtLoeschen(a)"><Trash2 :size="13" /></button>
        </div>
        <button type="button" class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm text-accent hover:bg-surface2 disabled:opacity-40" :disabled="!anzahlAktiv" @click="ansichtSpeichern"><Plus :size="13" /> Aktuelle Filter als Ansicht speichern</button>
      </div>
    </div>

    <!-- Klappfenster: einen Filter bearbeiten -->
    <div v-if="offen !== null && filter[offen]" class="absolute left-0 top-full z-40 mt-1.5 w-80 rounded-xl border border-line bg-surface p-3 shadow-xl">
      <div class="mb-2 flex items-center gap-2">
        <span class="min-w-0 flex-1 truncate text-sm font-semibold">{{ auswahlFeld?.label ?? filter[offen].pfad }}</span>
        <button type="button" class="text-mute hover:text-ink" :title="angeheftet.includes(filter[offen].pfad) ? 'Nicht mehr anheften' : 'Anheften'" @click="anheften(filter[offen].pfad)"><PinOff v-if="angeheftet.includes(filter[offen].pfad)" :size="14" /><Pin v-else :size="14" /></button>
        <button type="button" class="text-mute hover:text-ink" title="Filter entfernen" @click="entfernen(offen)"><Trash2 :size="14" /></button>
      </div>
      <template v-if="filter[offen].typ === 'auswahl'">
        <div class="max-h-64 space-y-0.5 overflow-auto">
          <label v-for="w in auswahlFeld?.optionen ?? []" :key="String(w)" class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm hover:bg-surface2">
            <input type="checkbox" class="accent-[var(--accent)]" :checked="filter[offen].wert.includes(w)" @change="umschalten(filter[offen], w)" />
            <span class="min-w-0 flex-1 truncate">{{ w }}</span><span class="text-xs text-mute tnum">{{ anzahl(filter[offen].pfad, w) }}</span>
          </label>
        </div>
      </template>
      <template v-else-if="filter[offen].typ === 'zahl'">
        <div class="flex gap-2">
          <select v-model="filter[offen].op" class="field !w-20"><option value=">=">≥</option><option value="<=">≤</option><option value="=">=</option></select>
          <input v-model.number="filter[offen].wert" type="number" class="field" @keydown.enter="fertig" />
        </div>
      </template>
      <template v-else-if="filter[offen].typ === 'datum'">
        <div class="grid grid-cols-2 gap-2">
          <label class="block"><span class="label mb-1 block">von</span><input v-model="filter[offen].von" type="date" class="field" /></label>
          <label class="block"><span class="label mb-1 block">bis</span><input v-model="filter[offen].bis" type="date" class="field" @change="fertig" /></label>
        </div>
      </template>
      <template v-else-if="filter[offen].typ === 'janein'">
        <div class="flex gap-1 rounded-xl border border-line p-1">
          <button type="button" class="flex-1 rounded-lg py-1 text-sm" :class="filter[offen].wert ? 'bg-accent-soft font-medium text-accent' : 'text-mute'" @click="filter[offen].wert = true; fertig()">ja</button>
          <button type="button" class="flex-1 rounded-lg py-1 text-sm" :class="!filter[offen].wert ? 'bg-accent-soft font-medium text-accent' : 'text-mute'" @click="filter[offen].wert = false; fertig()">nein</button>
        </div>
      </template>
      <template v-else>
        <select v-model="filter[offen].op" class="field mb-2"><option value="enthaelt">enthält</option><option value="nicht">enthält nicht</option><option value="leer">ist leer</option><option value="nichtleer">ist nicht leer</option></select>
        <input v-if="filter[offen].op === 'enthaelt' || filter[offen].op === 'nicht'" v-model="filter[offen].wert" class="field" placeholder="Text, Enter zum Schließen" autofocus @keydown.enter="fertig" />
      </template>
    </div>
  </div>
</template>
