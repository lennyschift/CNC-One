<script setup>
// Zeiten beim Abschließen eines Arbeitsgangs (Pflicht): Maschine, Rüstzeit und Bearbeitungszeit für die ganze Menge.
// Daneben steht die geplante Zeit, damit Abweichungen gleich auffallen. Offen hält ihn der Fertigungs-Store.
import { ref, computed, watch } from 'vue';
import { Clock, Cog } from '@lucide/vue';
import StammDialog from './StammDialog.vue';
import { repo } from '../data/repo.js';
import { useFertigung } from '../stores/fertigung.js';
import { maschinenFuer, sollMinuten } from '../lib/fertigung.js';
import { zahl, parseDe } from '../lib/format.js';

const f = useFertigung();
const maschinen = ref([]);
repo.maschinen.liste().then((m) => { maschinen.value = m; });

// je Arbeitsgang: Eingaben als Text (Stunden oder Minuten)
const zeilen = ref([]);
const einheit = ref('min');
watch(() => f.zeitenAnfrage, (a) => {
  if (!a) return;
  zeilen.value = a.ags.map((ag) => ({
    ag, maschine: ag.maschine || '',
    ruest: ag.istAm ? wert(ag.istRuestMin) : '', bearb: ag.istAm ? wert(ag.istBearbMin) : '',
  }));
}, { immediate: true });
const faktor = computed(() => (einheit.value === 'h' ? 60 : 1));
const wert = (min) => zahl((min || 0) / faktor.value, 2);
watch(einheit, (neu, alt) => {
  const k = neu === alt ? 1 : neu === 'h' ? 1 / 60 : 60;
  for (const z of zeilen.value) for (const feld of ['ruest', 'bearb']) {
    const n = parseDe(z[feld]);
    if (z[feld] !== '' && Number.isFinite(n)) z[feld] = zahl(n * k, 2);
  }
});
const ok = (t) => t !== '' && Number.isFinite(parseDe(t)) && parseDe(t) >= 0;
const gueltig = computed(() => zeilen.value.every((z) => ok(z.ruest) && ok(z.bearb)));
const versucht = ref(false);
const menge = computed(() => f.zeitenAnfrage?.fb.menge ?? 0);
const soll = (ag) => `Rüsten ${wert(ag.ruestMin)} · Bearbeiten ${wert(sollMinuten({ ...ag, ruestMin: 0 }, menge.value))} ${einheit.value}`;

function speichern() {
  versucht.value = true;
  if (!gueltig.value) return;
  f.zeitenAntwort(zeilen.value.map((z) => ({ agId: z.ag.id, maschine: z.maschine, ruestMin: parseDe(z.ruest) * faktor.value, bearbMin: parseDe(z.bearb) * faktor.value })));
  versucht.value = false;
}
function abbrechen() {
  versucht.value = false;
  f.zeitenAntwort(null);
}
</script>

<template>
  <StammDialog v-if="f.zeitenAnfrage" :titel="f.zeitenAnfrage.titel" :untertitel="`${f.zeitenAnfrage.fb.teil.name} · ${menge} Stk · Zeiten sind beim Abschließen Pflicht`" neu breite="720px" :speichern-text="f.zeitenAnfrage.titel === 'Zeiten melden' ? 'Zeiten speichern' : 'Zeiten speichern und abschließen'" @speichern="speichern" @schliessen="abbrechen">
    <div class="flex items-center justify-between gap-3">
      <p class="text-xs text-mute">Tatsächliche Zeiten für die ganze Menge. Sie fließen in die Auswertung und die Nachkalkulation.</p>
      <span class="flex shrink-0 rounded-lg border border-line bg-surface p-0.5 text-xs" role="radiogroup" aria-label="Einheit">
        <button v-for="e in ['min', 'h']" :key="e" type="button" class="rounded-md px-2 py-0.5" :class="einheit === e ? 'bg-accent-soft font-medium text-accent' : 'text-mute'" @click="einheit = e">{{ e === 'min' ? 'Minuten' : 'Stunden' }}</button>
      </span>
    </div>
    <div v-for="z in zeilen" :key="z.ag.id" class="rounded-xl border border-line bg-surface2 p-3.5">
      <div class="mb-2.5 flex items-center gap-2 text-sm font-semibold"><Cog :size="15" class="text-accent" /> {{ z.ag.name || 'Arbeitsgang' }}
        <span class="ml-auto inline-flex items-center gap-1 text-[11px] font-normal text-mute"><Clock :size="12" /> geplant: {{ soll(z.ag) }}</span>
      </div>
      <div class="grid gap-3 sm:grid-cols-3">
        <label class="block"><span class="label mb-1 block">Maschine</span>
          <select v-model="z.maschine" class="field"><option value="">– ohne –</option><option v-for="m in maschinenFuer(maschinen, z.ag.name)" :key="m.name" :value="m.name">{{ m.name }}</option></select>
        </label>
        <label class="block"><span class="label mb-1 block">Rüstzeit ({{ einheit }})</span>
          <input v-model="z.ruest" inputmode="decimal" class="field text-right tnum" :class="versucht && !ok(z.ruest) ? '!border-accent' : ''" placeholder="0" />
        </label>
        <label class="block"><span class="label mb-1 block">Bearbeitungszeit gesamt ({{ einheit }})</span>
          <input v-model="z.bearb" inputmode="decimal" class="field text-right tnum" :class="versucht && !ok(z.bearb) ? '!border-accent' : ''" />
        </label>
      </div>
    </div>
    <p v-if="versucht && !gueltig" class="text-xs text-accent">Bitte für jeden Arbeitsgang Rüst- und Bearbeitungszeit eintragen (0 ist erlaubt).</p>
  </StammDialog>
</template>
