<script setup>
// Querschnitt-Symbol einer Rohmaterialform (Rund, Vierkant, Flach, Sechskant, Rohr, Platte), wie in Händlerkatalogen.
// farbe: Füllfarbe (z. B. ISO-Farbe), sonst currentColor.
defineProps({
  form: { type: String, required: true },
  groesse: { type: Number, default: 28 },
  farbe: { type: String, default: '' },
});
</script>

<template>
  <svg :width="groesse" :height="groesse" viewBox="0 0 32 32" fill="none" :stroke="farbe || 'currentColor'" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true">
    <g :fill="farbe || 'currentColor'" fill-opacity="0.22">
      <circle v-if="form === 'Rund'" cx="16" cy="16" r="11" />
      <rect v-else-if="form === 'Vierkant'" x="6" y="6" width="20" height="20" rx="1" />
      <rect v-else-if="form === 'Flach'" x="3" y="10" width="26" height="12" rx="1" />
      <polygon v-else-if="form === 'Sechskant'" points="16,4.5 26,10.25 26,21.75 16,27.5 6,21.75 6,10.25" />
      <path v-else-if="form === 'Rohr'" fill-rule="evenodd" d="M16 5a11 11 0 1 1 0 22a11 11 0 1 1 0-22zM16 10a6 6 0 1 0 0 12a6 6 0 1 0 0-12z" />
      <template v-else-if="form === 'Platte'">
        <polygon points="3,14 19,8 29,13 13,19" />
        <polygon points="3,14 13,19 13,23 3,18" fill-opacity="0.4" />
        <polygon points="13,19 29,13 29,17 13,23" fill-opacity="0.32" />
      </template>
      <rect v-else x="6" y="6" width="20" height="20" rx="4" stroke-dasharray="3 3" fill-opacity="0" />
    </g>
  </svg>
</template>
