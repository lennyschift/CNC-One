<script>
// Gepflegte ISO-Gruppen der Rohmaterialien, einmal für alle Bilder geholt
import { ref as modulRef } from 'vue';
import { repo } from '../data/repo.js';

const stamm = modulRef(null);
function gepflegteGruppe(name) {
  if (!name) return '';
  if (stamm.value === null) {
    stamm.value = [];
    repo.materialien.liste().then((l) => { stamm.value = l ?? []; });
  }
  return stamm.value.find((x) => x.name === name)?.isoGruppe ?? '';
}
</script>

<script setup>
// Bild eines Bauteils oder Rohmaterials. Einheitlich überall verwenden.
// Mit `iso` zeigt es oben links die ISO-Materialgruppe (P/M/K/N/S/H, farbig) und ab 64 px unten den Werkstoff (nur Oberfläche, nicht PDF).
// Solange es keine echte Vorschau aus der STEP-Datei gibt, zeigt die Komponente
// eine schematische Darstellung, die je nach Teil (Name/Nummer) unterschiedlich ausfällt.
import { computed } from 'vue';
import { isoGruppe } from '../lib/iso.js';

const props = defineProps({
  teil: { type: Object, default: null },
  art: { type: String, default: 'teil' },
  bild: { type: String, default: '' },
  groesse: { type: Number, default: 44 },
  iso: { type: Boolean, default: false },
});

const bildUrl = computed(() => props.bild || props.teil?.vorschaubild || '');
const form = computed(() => {
  const s = `${props.teil?.teilenummer ?? ''}${props.teil?.name ?? ''}`;
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 4;
});
const uid = Math.random().toString(36).slice(2, 7);
const werkstoff = computed(() => (props.iso ? props.teil?.material ?? '' : ''));
const gruppe = computed(() => (werkstoff.value ? isoGruppe(werkstoff.value, gepflegteGruppe(werkstoff.value)) : null));
// klein und bündig in der Ecke, damit es das Teil nicht verdeckt
const marke = computed(() => Math.round(Math.min(16, Math.max(11, props.groesse * 0.14))));
const titel = computed(() => (gruppe.value ? `ISO ${gruppe.value.code} · ${gruppe.value.name} · ${werkstoff.value}` : werkstoff.value || undefined));
</script>

<template>
  <div class="relative shrink-0 overflow-hidden rounded-xl border border-line bg-surface2" :style="{ width: groesse + 'px', height: groesse + 'px' }" :title="titel">
    <img v-if="bildUrl" :src="bildUrl" alt="" class="h-full w-full object-contain" />
    <svg v-else viewBox="0 0 64 64" class="h-full w-full">
      <defs>
        <linearGradient :id="'m' + uid" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="var(--mute)" stop-opacity="0.55" />
          <stop offset="1" stop-color="var(--mute)" stop-opacity="0.2" />
        </linearGradient>
      </defs>
      <!-- Rohmaterial: Rundstab -->
      <g v-if="art === 'material'">
        <rect x="8" y="24" width="42" height="16" :fill="`url(#m${uid})`" />
        <ellipse cx="50" cy="32" rx="5" ry="8" fill="var(--mute)" fill-opacity="0.45" stroke="var(--accent)" stroke-width="1.2" />
        <ellipse cx="8" cy="32" rx="5" ry="8" fill="var(--mute)" fill-opacity="0.3" />
        <line x1="12" y1="27" x2="46" y2="27" stroke="var(--surface)" stroke-opacity="0.6" stroke-width="1.5" />
      </g>
      <!-- Welle / Bolzen -->
      <g v-else-if="form === 0">
        <rect x="12" y="22" width="40" height="20" :fill="`url(#m${uid})`" />
        <rect x="12" y="25" width="10" height="14" fill="var(--mute)" fill-opacity="0.25" />
        <ellipse cx="52" cy="32" rx="4.5" ry="10" fill="var(--mute)" fill-opacity="0.5" stroke="var(--accent)" stroke-width="1.2" />
        <ellipse cx="12" cy="32" rx="4.5" ry="10" fill="var(--mute)" fill-opacity="0.3" />
      </g>
      <!-- Flansch -->
      <g v-else-if="form === 1">
        <ellipse cx="32" cy="38" rx="24" ry="9" fill="var(--mute)" fill-opacity="0.3" />
        <rect x="8" y="26" width="48" height="12" :fill="`url(#m${uid})`" />
        <ellipse cx="32" cy="26" rx="24" ry="9" fill="var(--mute)" fill-opacity="0.45" stroke="var(--accent)" stroke-width="1.2" />
        <ellipse cx="32" cy="26" rx="9" ry="3.6" fill="var(--surface-2)" stroke="var(--mute)" stroke-opacity="0.6" />
        <circle cx="17" cy="26" r="1.6" fill="var(--surface-2)" /><circle cx="47" cy="26" r="1.6" fill="var(--surface-2)" /><circle cx="32" cy="21" r="1.4" fill="var(--surface-2)" /><circle cx="32" cy="31" r="1.4" fill="var(--surface-2)" />
      </g>
      <!-- Block -->
      <g v-else-if="form === 2">
        <polygon points="32,12 54,24 32,36 10,24" fill="var(--mute)" fill-opacity="0.45" stroke="var(--accent)" stroke-width="1.2" stroke-linejoin="round" />
        <polygon points="10,24 32,36 32,56 10,44" fill="var(--mute)" fill-opacity="0.28" />
        <polygon points="54,24 32,36 32,56 54,44" fill="var(--mute)" fill-opacity="0.18" />
      </g>
      <!-- Hülse -->
      <g v-else>
        <rect x="18" y="16" width="28" height="34" :fill="`url(#m${uid})`" />
        <ellipse cx="32" cy="50" rx="14" ry="5" fill="var(--mute)" fill-opacity="0.35" />
        <ellipse cx="32" cy="16" rx="14" ry="5" fill="var(--mute)" fill-opacity="0.45" stroke="var(--accent)" stroke-width="1.2" />
        <ellipse cx="32" cy="16" rx="7" ry="2.6" fill="var(--surface-2)" />
      </g>
    </svg>
    <span
      v-if="gruppe" class="absolute left-0 top-0 grid place-items-center rounded-br-[5px] font-bold leading-none"
      :style="{ width: marke + 'px', height: marke + 'px', fontSize: Math.round(marke * 0.66) + 'px', background: gruppe.farbe, color: gruppe.schrift }"
    >{{ gruppe.code }}</span>
    <span
      v-if="werkstoff && groesse >= 64" class="absolute inset-x-0 bottom-0 truncate bg-surface/85 px-1 py-0.5 text-center font-medium leading-tight text-ink"
      :style="{ fontSize: groesse >= 100 ? '11px' : '9.5px' }"
    >{{ werkstoff }}</span>
  </div>
</template>
