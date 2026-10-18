<script setup>
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { CheckCircle2, Info, AlertTriangle } from '@lucide/vue';
import { useUi } from '../stores/ui.js';

const ui = useUi();
</script>

<template>
  <div v-auto-animate class="pointer-events-none fixed bottom-5 right-5 z-[60] flex flex-col items-end gap-2">
    <div
      v-for="t in ui.toasts"
      :key="t.id"
      class="card pointer-events-auto flex items-center gap-2.5 px-3.5 py-2.5 text-sm shadow-lg"
    >
      <CheckCircle2 v-if="t.art === 'ok'" :size="17" class="text-ok" />
      <AlertTriangle v-else-if="t.art === 'warn'" :size="17" class="text-warn" />
      <Info v-else :size="17" class="text-mute" />
      {{ t.text }}
    </div>
  </div>
</template>
