<script setup>
// Teilefamilie eines Bauteils: die anderen Varianten mit ihrem Unterschied. In der Workbench (`teileImAngebot`) lässt
// sich die Kalkulation dieses Bauteils auf die anderen Varianten im selben Angebot übertragen.
import { ref, computed, watch } from 'vue';
import { Network, Pencil, Copy } from '@lucide/vue';
import PartImage from './PartImage.vue';
import TeilefamilieDialog from './TeilefamilieDialog.vue';
import { call } from '../data/api.js';

const props = defineProps({
  bauteilId: { type: String, required: true },
  teileImAngebot: { type: Array, default: null }, // [{ teil, bauteilId }] der anderen Positionen (Workbench)
  aktionen: { type: Boolean, default: true },
});
const emit = defineEmits(['uebertragen', 'geaendert']);
const familie = ref(null);
const bearbeiten = ref(false);
async function laden() {
  try { familie.value = props.bauteilId ? await call('cnc_one.api.teilefamilie.fuer_bauteil', { bauteil: props.bauteilId }) : null; } catch { familie.value = null; }
}
watch(() => props.bauteilId, laden, { immediate: true });
defineExpose({ laden });

const selbst = computed(() => familie.value?.varianten.find((v) => v.id === props.bauteilId) ?? null);
// andere Varianten dieser Familie, die im selben Angebot stehen
const imAngebot = computed(() => {
  if (!familie.value || !props.teileImAngebot) return [];
  const ids = new Set(familie.value.varianten.map((v) => v.id).filter((id) => id !== props.bauteilId));
  return props.teileImAngebot.filter((x) => ids.has(x.bauteilId));
});
function gespeichert() { bearbeiten.value = false; laden(); emit('geaendert'); }
</script>

<template>
  <section v-if="familie" class="rounded-2xl border border-line p-4">
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
      <Network :size="16" class="text-accent" />
      <span class="text-sm font-semibold">Teilefamilie: {{ familie.bezeichnung }}</span>
      <span class="text-xs text-mute">{{ familie.varianten.length }} Varianten<template v-if="familie.merkmal"> · unterscheiden sich in: {{ familie.merkmal }}</template><template v-if="selbst?.variante"> · dieses: <strong class="text-ink">{{ selbst.variante }}</strong></template></span>
      <button v-if="aktionen" type="button" class="btn ml-auto !px-2.5 !py-1 text-xs" @click="bearbeiten = true"><Pencil :size="13" /> Bearbeiten</button>
    </div>
    <div class="mt-3 flex flex-wrap gap-2">
      <div v-for="v in familie.varianten" :key="v.id" class="flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-xs" :class="v.id === bauteilId ? 'border-accent bg-accent-soft' : 'border-line'">
        <PartImage :teil="v" :groesse="28" />
        <div><div class="font-medium tnum">{{ v.teilenummer }}</div><div class="text-mute">{{ v.variante || v.name || '–' }}</div></div>
      </div>
    </div>
    <div v-if="aktionen && imAngebot.length" class="mt-3 flex flex-wrap items-center gap-2 rounded-xl bg-surface2 px-3 py-2 text-xs">
      <span>{{ imAngebot.length }} weitere Variante{{ imAngebot.length === 1 ? '' : 'n' }} in diesem Angebot.</span>
      <button type="button" class="btn !px-2.5 !py-1 text-xs" title="Zeiten, Material, Kosten, Staffeln und Arbeitsgänge dieses Bauteils auf die anderen Varianten im Angebot übertragen" @click="emit('uebertragen', imAngebot)"><Copy :size="13" /> Kalkulation auf {{ imAngebot.length === 1 ? 'sie' : 'alle' }} übertragen</button>
    </div>
    <TeilefamilieDialog v-if="bearbeiten" :familie="familie" @schliessen="bearbeiten = false" @gespeichert="gespeichert" />
  </section>
</template>
