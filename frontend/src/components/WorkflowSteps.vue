<script setup>
import { Check } from '@lucide/vue';

// Ablaufleiste Angebot → … → Zahlung. `stand`: Index des aktuellen Schritts, alles davor ist erledigt.
defineProps({ stand: { type: Number, default: 0 } });
const schritte = ['Angebot', 'Auftrag', 'Fertigung', 'Lieferung', 'Rechnung', 'Zahlung'];
</script>

<template>
  <ol class="flex items-center">
    <li v-for="(s, i) in schritte" :key="s" class="flex items-center" :class="i < schritte.length - 1 ? 'flex-1' : ''">
      <div class="flex flex-col items-center gap-1.5">
        <span
          class="grid h-7 w-7 place-items-center rounded-full border text-xs font-semibold transition-colors"
          :class="i < stand ? 'border-accent bg-accent text-white' : i === stand ? 'border-accent bg-accent-soft text-accent' : 'border-line bg-surface2 text-mute'"
        >
          <Check v-if="i < stand" :size="14" :stroke-width="2.6" /><template v-else>{{ i + 1 }}</template>
        </span>
        <span class="text-[11px]" :class="i === stand ? 'font-semibold text-ink' : 'text-mute'">{{ s }}</span>
      </div>
      <span v-if="i < schritte.length - 1" class="mx-1 mb-5 h-px flex-1" :class="i < stand ? 'bg-accent' : 'bg-line'" />
    </li>
  </ol>
</template>
