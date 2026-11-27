<script setup>
// Seriennummern eines Fertigungsbauteils: was im Auftrag steht (wird gefertigt) und was die Bestellung des Kunden nennt
// (aus dem Bestell-PDF, z. B. „8F8115283G/0081“). Weichen sie ab, steht das deutlich da; die Liste lässt sich aufklappen.
import { ref, computed } from 'vue';
import { Hash, CheckCircle2, AlertTriangle, ChevronDown } from '@lucide/vue';
import { bereichText, formatNr } from '../lib/serien.js';

const props = defineProps({ fb: { type: Object, required: true } });
const offen = ref(false);
const b = computed(() => props.fb.serienBestellung ?? null);
const system = computed(() => (props.fb.serienVon ? { von: props.fb.serienVon, bis: props.fb.serienBis, stellen: props.fb.serienStellen } : null));
const passt = computed(() => !!b.value && !!system.value && b.value.von === system.value.von && b.value.bis === system.value.bis);
const nummern = computed(() => {
  if (b.value?.nummern?.length) return b.value.nummern.map((n) => `${b.value.praefix ? `${b.value.praefix}/` : ''}${formatNr(n, b.value.stellen)}`);
  if (system.value) return Array.from({ length: system.value.bis - system.value.von + 1 }, (_, i) => formatNr(system.value.von + i, system.value.stellen));
  return [];
});
</script>

<template>
  <section v-if="system || b" class="card p-5">
    <div class="mb-3 flex items-center gap-2">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><Hash :size="16" class="text-accent" /> Seriennummern</h3>
      <span v-if="passt" class="ml-auto inline-flex items-center gap-1 rounded-full bg-ok/10 px-2 py-0.5 text-xs text-ok"><CheckCircle2 :size="12" /> wie bestellt</span>
      <span v-else-if="b" class="ml-auto inline-flex items-center gap-1 rounded-full bg-warn/10 px-2 py-0.5 text-xs text-warn"><AlertTriangle :size="12" /> {{ system ? 'weicht ab' : 'nicht im Auftrag' }}</span>
    </div>
    <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      <dt class="text-mute">Im Auftrag</dt>
      <dd class="font-semibold tnum">{{ system ? bereichText(system.von, system.bis, system.stellen) : '–' }}<span v-if="system" class="ml-1 font-normal text-mute">({{ system.bis - system.von + 1 }} Stk)</span></dd>
      <template v-if="b">
        <dt class="text-mute">Bestellung</dt>
        <dd class="tnum"><span class="font-semibold">{{ b.praefix ? `${b.praefix}/` : '' }}{{ bereichText(b.von, b.bis, b.stellen) }}</span> <span class="text-mute">({{ b.anzahl }} Stk<template v-if="b.luecken">, mit Lücken</template>)</span></dd>
      </template>
    </dl>
    <p v-if="b && !passt" class="mt-2 rounded-lg bg-warn/10 px-2.5 py-1.5 text-xs text-warn">{{ system ? 'Die Seriennummern im Auftrag weichen von der Bestellung ab. Bitte vor dem Anbringen klären.' : 'Die Bestellung nennt Seriennummern, im Auftrag sind keine eingetragen.' }}</p>
    <p v-if="b && b.anzahl !== fb.menge" class="mt-2 text-xs text-warn">Die Bestellung nennt {{ b.anzahl }} Nummern für {{ fb.menge }} Stück.</p>
    <button v-if="nummern.length" type="button" class="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline" @click="offen = !offen"><ChevronDown :size="13" class="transition" :class="offen ? 'rotate-180' : ''" /> {{ offen ? 'Liste ausblenden' : `Alle ${nummern.length} Nummern zeigen` }}</button>
    <ol v-if="offen" class="mt-2 grid max-h-64 grid-cols-2 gap-x-4 gap-y-0.5 overflow-auto rounded-lg bg-surface2 px-3 py-2 font-mono text-xs">
      <li v-for="n in nummern" :key="n">{{ n }}</li>
    </ol>
  </section>
</template>
