<script setup>
import { ref } from 'vue';
import { useEventListener } from '@vueuse/core';
import { UploadCloud } from '@lucide/vue';

const emit = defineEmits(['dateien']);
const aktiv = ref(false);
let zaehler = 0;

const hatDateien = (e) => Array.from(e.dataTransfer?.types ?? []).includes('Files');

useEventListener(window, 'dragenter', (e) => {
  if (!hatDateien(e)) return;
  zaehler++;
  aktiv.value = true;
});
useEventListener(window, 'dragleave', (e) => {
  if (!hatDateien(e)) return;
  zaehler = Math.max(0, zaehler - 1);
  if (!zaehler) aktiv.value = false;
});
useEventListener(window, 'dragover', (e) => { if (hatDateien(e)) e.preventDefault(); });
useEventListener(window, 'drop', (e) => {
  if (!hatDateien(e)) return;
  e.preventDefault();
  zaehler = 0;
  aktiv.value = false;
  const files = Array.from(e.dataTransfer.files);
  if (files.length) emit('dateien', files);
});
</script>

<template>
  <Transition name="fade">
    <div v-if="aktiv" class="pointer-events-none fixed inset-0 z-40 grid place-items-center bg-accent/10 backdrop-blur-[3px]">
      <div class="m-8 grid h-[min(70vh,520px)] w-[min(90vw,760px)] place-items-center rounded-3xl border-2 border-dashed border-accent bg-surface/80">
        <div class="text-center">
          <UploadCloud :size="48" class="mx-auto text-accent" :stroke-width="1.5" />
          <p class="mt-4 text-lg font-medium">Dateien hier ablegen</p>
          <p class="mt-1 text-sm text-mute">STEP und PDF mit gleichem Namen werden zu einem Bauteil</p>
        </div>
      </div>
    </div>
  </Transition>
</template>
