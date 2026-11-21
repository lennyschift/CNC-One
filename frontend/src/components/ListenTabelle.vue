<script setup>
// Listenansicht als Tabelle mit festen Spalten (wie die Fertigungsliste): Kopf mit Sortierung per Klick, ganze Zeile
// anklickbar. Zellen über Slots `#<key>="{ x }"`, sonst der Wert `wert(x)` bzw. x[key].
// spalten: [{ key, label, rechts?, breite?, wert?: (x) => sortier-/anzeigewert, sortierbar?: false, klasse? }]
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ChevronUp, ChevronDown } from '@lucide/vue';

const props = defineProps({
  spalten: { type: Array, required: true },
  zeilen: { type: Array, required: true },
  link: { type: Function, default: null }, // (x) => Pfad der Detailseite
  zeilenKey: { type: String, default: 'id' },
  minBreite: { type: String, default: '900px' },
  leerText: { type: String, default: 'Keine Einträge für diesen Filter.' },
});
const emit = defineEmits(['oeffnen']); // ohne `link`: Klick auf die Zeile (z. B. Dialog öffnen)
const router = useRouter();

// Sortierung per Spaltenkopf; ohne Wahl bleibt die Reihenfolge der Filterleiste
const sortKey = ref('');
const richtung = ref(1);
function sortieren(sp) {
  if (sp.sortierbar === false) return;
  if (sortKey.value !== sp.key) { sortKey.value = sp.key; richtung.value = 1; }
  else if (richtung.value === 1) richtung.value = -1;
  else sortKey.value = '';
}
const wert = (sp, x) => (sp.wert ? sp.wert(x) : x[sp.key]);
const sortiert = computed(() => {
  const sp = props.spalten.find((s) => s.key === sortKey.value);
  if (!sp) return props.zeilen;
  const leer = (v) => v === null || v === undefined || v === '';
  return [...props.zeilen].sort((a, b) => {
    const va = wert(sp, a);
    const vb = wert(sp, b);
    if (leer(va) || leer(vb)) return leer(va) - leer(vb);
    const c = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), 'de', { numeric: true });
    return c * richtung.value;
  });
});
function oeffnen(x, e) {
  if (e.target.closest('a, button, input, select, label')) return;
  if (!props.link) { emit('oeffnen', x); return; }
  const ziel = props.link(x);
  if (e.ctrlKey || e.metaKey) window.open(router.resolve(ziel).href, '_blank');
  else router.push(ziel);
}
</script>

<template>
  <section class="card overflow-x-auto">
    <table class="w-full text-sm" :style="{ minWidth: minBreite }">
      <thead>
        <tr class="text-left text-[11px] uppercase tracking-wide text-mute">
          <th v-for="(sp, i) in spalten" :key="sp.key" class="whitespace-nowrap py-2.5 font-semibold" :class="[i === 0 ? 'pl-4 pr-2' : i === spalten.length - 1 ? 'pl-2 pr-4' : 'px-2', sp.rechts ? 'text-right' : '']" :style="sp.breite ? { width: sp.breite } : null">
            <button v-if="sp.sortierbar !== false && sp.label" type="button" class="inline-flex items-center gap-0.5 uppercase tracking-wide hover:text-ink" :class="sortKey === sp.key ? 'text-accent' : ''" @click="sortieren(sp)">
              {{ sp.label }}<ChevronUp v-if="sortKey === sp.key && richtung === 1" :size="12" /><ChevronDown v-else-if="sortKey === sp.key" :size="12" />
            </button>
            <template v-else>{{ sp.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="x in sortiert" :key="x[zeilenKey]" class="cursor-pointer border-t border-line transition hover:bg-surface2" @click="oeffnen(x, $event)">
          <td v-for="(sp, i) in spalten" :key="sp.key" class="py-2" :class="[i === 0 ? 'whitespace-nowrap pl-4 pr-2' : i === spalten.length - 1 ? 'whitespace-nowrap pl-2 pr-4' : 'px-2', sp.rechts ? 'whitespace-nowrap text-right tnum' : '', sp.klasse ?? '']">
            <slot :name="sp.key" :x="x">{{ wert(sp, x) ?? '–' }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
    <slot v-if="!zeilen.length" name="leer"><p class="px-6 py-12 text-center text-sm text-mute">{{ leerText }}</p></slot>
  </section>
</template>
