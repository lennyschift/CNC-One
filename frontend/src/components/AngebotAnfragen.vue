<script setup>
// Lieferantenanfragen zu einem Angebot oder Entwurf. Als Leiste in der Workbench und als Karte im Angebot.
import { computed } from 'vue';
import { Send, ArrowRight } from '@lucide/vue';
import StatusBadge from './StatusBadge.vue';
import PartImage from './PartImage.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { zusammenfassung, zusammenfassungText } from '../lib/anfrage.js';

const props = defineProps({
  ziel: { type: Object, required: true },
  // 'leiste': eine Zeile mit Chips, 'karte': Liste mit Positionen
  variante: { type: String, default: 'karte' },
});
const store = useAnfragen();
const liste = computed(() => store.fuerAngebot(props.ziel));
const text = computed(() => zusammenfassungText(zusammenfassung(liste.value)));
const alleLink = computed(() => (props.ziel.angebotId ? `/anfragen?angebot=${props.ziel.angebotId}` : `/anfragen?entwurf=${props.ziel.entwurfId}`));
const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
const farbe = { Gesendet: 'text-warn', 'Angebot erhalten': 'text-ok', Abgesagt: 'text-mute' };
</script>

<template>
  <!-- Leiste -->
  <section v-if="variante === 'leiste' && liste.length" class="card flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
    <div class="flex items-center gap-2 text-sm font-semibold"><Send :size="15" class="text-accent" /> Lieferantenanfragen</div>
    <span class="text-xs text-mute">{{ text }}</span>
    <div class="flex flex-wrap gap-2">
      <RouterLink v-for="a in liste" :key="a.id" :to="`/anfragen/${a.id}`" class="inline-flex items-center gap-2 rounded-full border border-line bg-surface2 px-3 py-1 text-xs transition hover:border-accent/50">
        <span class="font-semibold tnum">{{ a.id }}</span><span class="text-mute">{{ a.lieferantName }}</span><span class="text-mute">{{ a.positionen.length }} Pos.</span><span :class="farbe[a.status]">{{ a.status }}</span>
      </RouterLink>
    </div>
    <RouterLink :to="alleLink" class="ml-auto inline-flex items-center gap-1 text-xs text-accent hover:underline">Alle anzeigen <ArrowRight :size="12" /></RouterLink>
  </section>

  <!-- Karte -->
  <section v-else-if="variante === 'karte'" class="card p-5">
    <div class="mb-3 flex items-center justify-between">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><Send :size="15" class="text-accent" /> Lieferantenanfragen</h3>
      <RouterLink v-if="liste.length" :to="alleLink" class="inline-flex items-center gap-1 text-xs text-accent hover:underline">Alle anzeigen <ArrowRight :size="12" /></RouterLink>
    </div>
    <ul v-if="liste.length" class="space-y-2.5">
      <li v-for="a in liste" :key="a.id">
        <RouterLink :to="`/anfragen/${a.id}`" class="block rounded-xl border border-line p-3 transition hover:border-accent/50">
          <div class="flex items-center justify-between gap-2"><span class="text-sm font-semibold tnum">{{ a.id }}</span><StatusBadge :status="a.status" /></div>
          <div class="mt-0.5 text-xs text-mute">{{ a.lieferantName }} · {{ de(a.erstellt) }}</div>
          <div class="mt-2 flex items-center gap-2">
            <div class="flex -space-x-2"><PartImage v-for="p in a.positionen.slice(0, 4)" :key="p.key" :teil="p.teil" :groesse="26" class="ring-2 ring-surface" /></div>
            <span class="truncate text-xs text-mute">{{ a.positionen.map((p) => p.agName || 'Fremdvergabe').join(', ') }}</span>
          </div>
        </RouterLink>
      </li>
    </ul>
    <p v-else class="text-xs text-mute">Zu diesem Angebot wurde noch nichts an Lieferanten geschickt.</p>
    <p v-if="liste.length" class="mt-3 text-xs text-mute">{{ text }}</p>
  </section>
</template>
