<script setup>
// Zeichnung und 3D-Modell eines Bauteils in der Revision eines Belegs (z. B. der bestellten), nur zum Ansehen und Messen.
// Ist am Bauteil inzwischen eine neuere Revision aktuell, steht ein Hinweis darüber.
import { computed, defineAsyncComponent } from 'vue';
import { Box, AlertTriangle } from '@lucide/vue';

const ModelViewer = defineAsyncComponent(() => import('./ModelViewer.vue'));
const DrawingViewer = defineAsyncComponent(() => import('./DrawingViewer.vue'));

const props = defineProps({ teil: { type: Object, required: true } });
const dateiname = (url) => decodeURIComponent((url || '').split('/').pop() || '');
const andere = computed(() => {
  const t = props.teil;
  return t.revision && t.aktuelleRevision && t.revision.toLowerCase() !== t.aktuelleRevision.toLowerCase();
});
</script>

<template>
  <section class="card p-5">
    <h3 class="mb-3 flex flex-wrap items-center gap-2 text-sm font-semibold">
      <Box :size="16" class="text-accent" /> Zeichnung und 3D-Modell
      <span v-if="teil.revision" class="rounded-full bg-surface2 px-2 py-0.5 text-xs font-medium text-mute">Rev. {{ teil.revision }}</span>
    </h3>
    <p v-if="andere" class="mb-3 flex items-start gap-1.5 rounded-xl bg-warn/10 px-3 py-2 text-xs text-warn">
      <AlertTriangle :size="14" class="mt-0.5 shrink-0" />
      <span>Bestellt ist Revision <strong>{{ teil.revision }}</strong>, gezeigt werden deren Dateien. Am Bauteil ist inzwischen Revision <strong>{{ teil.aktuelleRevision }}</strong> aktuell.</span>
    </p>
    <div v-if="teil.zeichnung || teil.stepDatei" class="grid gap-4 xl:grid-cols-2">
      <div class="h-[460px] min-w-0">
        <DrawingViewer v-if="teil.zeichnung" :key="teil.zeichnung" :url="teil.zeichnung" :name="dateiname(teil.zeichnung)" />
        <div v-else class="leer">Keine Zeichnung zu dieser Revision</div>
      </div>
      <div class="h-[460px] min-w-0">
        <ModelViewer v-if="teil.stepDatei" :key="teil.stepDatei" :url="teil.stepDatei" :name="dateiname(teil.stepDatei)" nur-ansehen />
        <div v-else class="leer">Kein 3D-Modell zu dieser Revision</div>
      </div>
    </div>
    <p v-else class="text-sm text-mute">Zu diesem Bauteil sind noch keine Zeichnung und kein 3D-Modell abgelegt.</p>
  </section>
</template>

<style scoped>
.leer { display: flex; height: 100%; align-items: center; justify-content: center; border-radius: 1rem; border: 2px dashed var(--line); font-size: 0.875rem; color: var(--mute); }
</style>
