<script setup>
import { computed } from 'vue';
import { Truck, Cog, CalendarClock, Flame } from '@lucide/vue';
import PartImage from './PartImage.vue';
import { produziert, fortschritt, ueberproduktion, tageBis } from '../lib/fertigung.js';

const props = defineProps({ fb: { type: Object, required: true } });
defineEmits(['drag']);

const fertig = computed(() => produziert(props.fb));
const anteil = computed(() => fortschritt(props.fb));
const ueber = computed(() => ueberproduktion(props.fb));
const tage = computed(() => tageBis(props.fb.termin));
const terminText = computed(() => {
  if (tage.value === null) return 'kein Termin';
  if (props.fb.status === 'Fertig') return new Date(props.fb.termin).toLocaleDateString('de-DE');
  if (tage.value < 0) return `${-tage.value} Tg überfällig`;
  if (tage.value === 0) return 'heute';
  return `in ${tage.value} Tg`;
});
const terminFarbe = computed(() => {
  if (props.fb.status === 'Fertig' || tage.value === null) return 'text-mute';
  if (tage.value < 0) return 'text-accent';
  if (tage.value <= 3) return 'text-warn';
  return 'text-mute';
});
const weg = computed(() => props.fb.arbeitsgaenge.some((a) => a.typ === 'fremd' && (a.sendungen ?? []).some((s) => s.datumWeg && !s.datumZurueck)));
</script>

<template>
  <RouterLink :to="`/fertigung/${fb.id}`" class="card block cursor-grab p-3.5 transition hover:-translate-y-px hover:border-accent/40 active:cursor-grabbing" draggable="true" @dragstart="$emit('drag', fb.id)">
    <div class="flex items-start gap-3">
      <PartImage :teil="fb.teil" :groesse="52" />
      <div class="min-w-0 flex-1">
        <div class="flex items-start justify-between gap-2">
          <div class="truncate text-sm font-medium">{{ fb.teil.name }}</div>
          <span v-if="fb.prioritaet !== 'Normal'" class="inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold" :class="fb.prioritaet === 'Eilig' ? 'bg-accent-soft text-accent' : 'bg-surface2 text-warn'"><Flame :size="10" />{{ fb.prioritaet }}</span>
        </div>
        <div class="truncate text-xs text-mute">{{ fb.teil.teilenummer || 'ohne Teilenummer' }}</div>
        <div class="mt-0.5 truncate text-[11px] text-mute tnum">{{ fb.auftragId }} · {{ fb.kundeName }}</div>
      </div>
    </div>

    <div class="mt-3">
      <div class="mb-1 flex justify-between text-xs"><span class="text-mute">Fortschritt</span><span class="font-medium tnum">{{ fertig }} / {{ fb.menge }} Stk<span v-if="ueber" class="ml-1.5 rounded-md bg-surface2 px-1.5 py-0.5 text-[10px] text-ok">+{{ ueber }} fürs Lager</span></span></div>
      <div class="h-1.5 overflow-hidden rounded-full bg-line"><div class="h-full rounded-full transition-all duration-500" :class="anteil >= 1 ? 'bg-ok' : 'bg-accent'" :style="{ width: Math.max(anteil * 100, fertig ? 4 : 0) + '%' }" /></div>
    </div>

    <div class="mt-3 flex items-center justify-between gap-2">
      <div class="flex min-w-0 flex-wrap gap-1">
        <span v-if="!fb.arbeitsgaenge.length" class="inline-flex items-center gap-1 rounded-md bg-accent-soft px-1.5 py-0.5 text-[10px] text-accent">Keine Arbeitsgänge</span>
        <span v-for="a in fb.arbeitsgaenge" :key="a.id" class="inline-flex max-w-[120px] items-center gap-1 truncate rounded-md bg-surface2 px-1.5 py-0.5 text-[10px] text-mute" :class="a.status === 'Läuft' ? '!text-ink ring-1 ring-accent/50' : ''">
          <Truck v-if="a.typ === 'fremd'" :size="10" /><Cog v-else :size="10" />{{ a.typ === 'fremd' ? (a.lieferant || 'Fremd') : (a.maschine || 'Maschine?') }}
        </span>
      </div>
      <span class="inline-flex shrink-0 items-center gap-1 text-[11px]" :class="terminFarbe"><CalendarClock :size="12" />{{ terminText }}</span>
    </div>
    <div v-if="weg" class="mt-2 inline-flex items-center gap-1 rounded-md bg-surface2 px-2 py-0.5 text-[11px] text-warn"><Truck :size="11" /> Beim Lieferanten</div>
  </RouterLink>
</template>
