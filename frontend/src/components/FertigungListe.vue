<script setup>
// Fertigung als Liste: ein Fertigungsbauteil je Zeile mit dem aktuellen Arbeitsgang, Maschine, Plan- und Liefertermin.
import { Flame, AlertTriangle, Truck } from '@lucide/vue';
import PartImage from './PartImage.vue';
import StatusBadge from './StatusBadge.vue';
import { produziert, tageBis, zeitenFehlen } from '../lib/fertigung.js';

defineProps({ liste: { type: Array, required: true } });
const aktuell = (fb) => fb.arbeitsgaenge.find((a) => a.gebucht < fb.menge) ?? null;
const tag = (d) => (d ? new Date(d).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '–');
const terminFarbe = (fb) => {
  const t = tageBis(fb.termin);
  if (fb.status === 'Fertig' || t === null) return 'text-mute';
  return t < 0 ? 'font-semibold text-accent' : t <= 3 ? 'text-warn' : '';
};
</script>

<template>
  <section class="card overflow-x-auto">
    <table class="w-full min-w-[980px] text-sm">
      <thead>
        <tr class="text-left text-[11px] uppercase tracking-wide text-mute">
          <th class="px-4 py-2.5 font-semibold">Bauteil</th>
          <th class="px-2 py-2.5 font-semibold">Auftrag · Kunde</th>
          <th class="px-2 py-2.5 text-right font-semibold">Fortschritt</th>
          <th class="px-2 py-2.5 font-semibold">Aktueller Arbeitsgang</th>
          <th class="px-2 py-2.5 font-semibold">Geplant</th>
          <th class="px-2 py-2.5 font-semibold">Liefertermin</th>
          <th class="px-4 py-2.5 font-semibold">Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="fb in liste" :key="fb.id" class="cursor-pointer border-t border-line transition hover:bg-surface2" @click="$router.push(`/fertigung/${fb.id}`)">
          <td class="px-4 py-2">
            <div class="flex items-center gap-3">
              <PartImage iso :teil="fb.teil" :groesse="36" />
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 truncate font-medium"><Flame v-if="fb.prioritaet !== 'Normal'" :size="12" class="shrink-0 text-accent" :title="fb.prioritaet" />{{ fb.teil.name }}</div>
                <div class="truncate text-xs text-mute">{{ fb.teil.teilenummer || 'ohne Teilenummer' }}</div>
              </div>
            </div>
          </td>
          <td class="px-2 py-2"><div class="tnum">{{ fb.auftragId }}</div><div class="truncate text-xs text-mute">{{ fb.kundeName }}</div></td>
          <td class="px-2 py-2 text-right tnum">{{ produziert(fb) }} / {{ fb.menge }}</td>
          <td class="px-2 py-2">
            <template v-if="aktuell(fb)">
              <div class="flex items-center gap-1"><Truck v-if="aktuell(fb).typ === 'fremd'" :size="12" class="text-mute" />{{ aktuell(fb).name || 'ohne Namen' }}</div>
              <div class="text-xs" :class="aktuell(fb).typ === 'intern' && !aktuell(fb).maschine ? 'text-warn' : 'text-mute'">{{ aktuell(fb).typ === 'fremd' ? (aktuell(fb).lieferant || 'Lieferant offen') : (aktuell(fb).maschine || 'Maschine offen') }}</div>
            </template>
            <span v-else-if="!fb.arbeitsgaenge.length" class="text-xs text-accent">keine Arbeitsgänge</span>
            <span v-else class="text-xs text-mute">alle erledigt</span>
            <div v-if="zeitenFehlen(fb).length" class="mt-0.5 inline-flex items-center gap-1 text-[11px] text-warn"><AlertTriangle :size="11" /> Zeiten fehlen</div>
          </td>
          <td class="px-2 py-2 tnum">{{ tag(aktuell(fb)?.geplantAm) }}</td>
          <td class="px-2 py-2 tnum" :class="terminFarbe(fb)">{{ tag(fb.termin) }}</td>
          <td class="px-4 py-2"><StatusBadge :status="fb.status" /></td>
        </tr>
      </tbody>
    </table>
    <p v-if="!liste.length" class="px-6 py-12 text-center text-sm text-mute">Keine Fertigungsbauteile für diesen Filter.</p>
  </section>
</template>
