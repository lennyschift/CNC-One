<script setup>
// Aufmaß des Rohteils wählen: rundum, Seiten/Oben/Unten, je Richtung oder feste Größe (siehe lib/aufmass.js).
// Beim Umschalten werden die Felder aus dem bisher wirksamen Aufmaß vorbelegt.
import { computed, reactive } from 'vue';
import { AUFMASS_ARTEN, aufmassNorm, aufmassUmschalten, aufmassSpeicherform } from '../lib/aufmass.js';

const props = defineProps({
  modelValue: { type: [Number, Object], default: 0 },
  form: { type: String, default: 'Quader' }, // 'Quader' oder 'Rund'
  rohteil: { type: Object, default: null }, // aktuelles Rohteil (für die feste Größe als Vorschlag)
  gesperrt: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);
const m = computed(() => aufmassNorm(props.modelValue));
const rund = computed(() => props.form !== 'Quader');

function art(id) {
  if (props.gesperrt || id === m.value.art) return;
  emit('update:modelValue', aufmassSpeicherform(aufmassUmschalten(m.value, id, props.rohteil)));
}
// Beim Tippen sofort übernehmen (das Rohteil im 3D-Viewer wächst live mit); solange das Feld den Fokus hat, bleibt der
// getippte Text stehen (sonst würde z. B. „1,“ gleich zu „1“)
const entwurf = reactive({});
function tippen(k, text) {
  entwurf[k] = text;
  const t = String(text).trim();
  if (t === '' || !Number.isFinite(Number(t.replace(',', '.')))) return;
  setzen(k, t);
}
function fertig(k, text) {
  delete entwurf[k];
  setzen(k, text);
}
function setzen(k, text) {
  const v = Math.max(0, Number(String(text).replace(',', '.')) || 0);
  if (v === wert(k) && m.value.art !== 'fest') return;
  const neu = { ...m.value };
  // feste Größe: die angezeigten Werte (ggf. aus dem Rohteil vorbelegt) mitspeichern
  if (neu.art === 'fest') for (const [f] of felder.value) neu[f] = wert(f);
  neu[k] = v;
  emit('update:modelValue', aufmassSpeicherform(neu));
}
// Farbe je Richtung wie die Pfeile im 3D-Viewer (X rot, Y grün, Z blau; Stirn orange, Durchmesser lila)
const FARBE = { xm: '#dc2626', xp: '#dc2626', x: '#dc2626', ym: '#16a34a', yp: '#16a34a', y: '#16a34a', zm: '#2563eb', zp: '#2563eb', z: '#2563eb', oben: '#2563eb', unten: '#2563eb', l1: '#d97706', l2: '#d97706', stirn: '#d97706', radial: '#7c3aed' };
// Feld so breit wie die Zahl (mindestens 3 Stellen), damit z. B. „437,5“ ganz lesbar ist
const breite = (t) => `calc(${Math.max(3, String(t).length)}ch + 1.1rem)`;
const text = (v) => String(Math.round((v || 0) * 100) / 100).replace('.', ',');

// Felder je Art und Form: [Schlüssel, Beschriftung, Hinweis]
const felder = computed(() => {
  const a = m.value.art;
  if (a === 'gleich') return [['wert', 'je Seite', 'Aufmaß an allen Seiten']];
  if (rund.value) {
    if (a === 'seiten') return [['radial', '⌀ je Seite', 'Aufmaß am Umfang (Durchmesser wächst um das Doppelte)'], ['stirn', 'Stirnseiten', 'Aufmaß an beiden Stirnseiten']];
    if (a === 'einzeln') return [['radial', '⌀ je Seite', 'Aufmaß am Umfang (Durchmesser wächst um das Doppelte)'], ['l1', 'Stirn A', 'Stirnseite am Anfang der Achse'], ['l2', 'Stirn B', 'Stirnseite am Ende der Achse']];
    return [['d', '⌀', 'Durchmesser des Rohteils'], ['l', 'Länge', 'Länge des Rohteils']];
  }
  if (a === 'seiten') return [['seite', 'Seiten X/Y', 'Aufmaß rundherum an den Seiten (X± und Y±)'], ['oben', 'oben Z+', 'Aufmaß oben'], ['unten', 'unten Z−', 'Aufmaß unten']];
  if (a === 'einzeln') return [['xm', 'X−'], ['xp', 'X+'], ['ym', 'Y−'], ['yp', 'Y+'], ['zm', 'Z−'], ['zp', 'Z+']].map(([k, l]) => [k, l, `Aufmaß in Richtung ${l}`]);
  return [['x', 'X', 'Rohteillänge in X'], ['y', 'Y', 'Rohteillänge in Y'], ['z', 'Z', 'Rohteillänge in Z']];
});
const wert = (k) => {
  const v = m.value[k];
  if (m.value.art === 'fest' && !v && props.rohteil) {
    const r = props.rohteil;
    return Math.ceil(({ x: r.x, y: r.y, z: r.z, d: r.durchmesser, l: r.laenge })[k] || 0);
  }
  return v;
};
</script>

<template>
  <span class="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
    <span class="text-mute">Aufmaß</span>
    <span class="flex gap-0.5 rounded-lg bg-surface2 p-0.5" role="radiogroup" aria-label="Art des Aufmaßes">
      <button v-for="x in AUFMASS_ARTEN" :key="x.id" type="button" class="art" :class="m.art === x.id ? 'art-an' : ''" :title="x.titel" :disabled="gesperrt" @click="art(x.id)">{{ x.label }}</button>
    </span>
    <span class="flex flex-wrap items-center gap-x-1.5 gap-y-1">
      <label v-for="[k, l, t] in felder" :key="k" class="flex items-center gap-1" :title="t">
        <span class="text-[11px]" :class="FARBE[k] ? 'font-semibold' : 'text-mute'" :style="FARBE[k] ? { color: FARBE[k] } : {}">{{ l }}</span>
        <input :value="entwurf[k] ?? text(wert(k))" inputmode="decimal" :style="{ width: breite(entwurf[k] ?? text(wert(k))) }" class="field !px-1.5 !py-0.5 text-right text-xs tnum" :disabled="gesperrt" @input="tippen(k, $event.target.value)" @blur="fertig(k, $event.target.value)" @keydown.enter="$event.target.blur()" />
      </label>
      <span class="text-[11px] text-mute">mm</span>
    </span>
    <slot />
  </span>
</template>

<style scoped>
.art { border-radius: 0.4rem; padding: 0.1rem 0.45rem; font-size: 0.68rem; color: var(--mute); white-space: nowrap; }
.art:hover:not(:disabled) { color: var(--ink); }
.art-an { background: var(--surface); color: var(--accent); box-shadow: 0 1px 2px rgb(0 0 0 / 0.08); font-weight: 600; }
</style>
