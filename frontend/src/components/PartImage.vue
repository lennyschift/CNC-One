<script setup>
// Bild eines Bauteils oder Rohmaterials. Einheitlich überall verwenden.
// Solange es keine echte Vorschau aus der STEP-Datei gibt, zeigt die Komponente
// eine schematische Darstellung, die je nach Teil (Name/Nummer) unterschiedlich ausfällt.
import { computed } from 'vue';

const props = defineProps({
  teil: { type: Object, default: null },
  art: { type: String, default: 'teil' },
  bild: { type: String, default: '' },
  groesse: { type: Number, default: 44 },
});

const bildUrl = computed(() => props.bild || props.teil?.vorschaubild || '');
const form = computed(() => {
  const s = `${props.teil?.teilenummer ?? ''}${props.teil?.name ?? ''}`;
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 4;
});
const uid = Math.random().toString(36).slice(2, 7);
</script>

<template>
  <div class="relative shrink-0 overflow-hidden rounded-xl border border-line bg-surface2" :style="{ width: groesse + 'px', height: groesse + 'px' }">
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
  </div>
</template>
