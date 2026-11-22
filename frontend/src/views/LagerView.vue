<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed, onMounted } from 'vue';
import { Search, Package, Layers, ArrowDownToLine, ArrowUpFromLine, RotateCcw, SlidersHorizontal } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import RohmaterialLager from '../components/RohmaterialLager.vue';
import StammDialog from '../components/StammDialog.vue';
import NumField from '../components/NumField.vue';
import { useLieferung } from '../stores/lieferung.js';

const l = useLieferung();
const gruppe = ref('fertig');
const suche = ref('');
const nurMinus = ref(false);
onMounted(() => l.lagerLaden().catch(() => {}));

// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'kundeName': 'Kunde', 'bestand': 'Bestand', 'teil.name': 'Bauteil', 'teil.material': 'Werkstoff'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return l.lager.filter((x) => (!nurMinus.value || x.bestand < 0)
    && (!q || `${x.teil.name} ${x.teil.teilenummer} ${x.kundeName}`.toLowerCase().includes(q)));
});
const summe = computed(() => l.lager.reduce((n, x) => n + Math.max(0, x.bestand), 0));
const minus = computed(() => l.lager.filter((x) => x.bestand < 0).length);

// ---- Verlauf und Korrektur eines Bauteils
const gewaehlt = ref(null);
const verlauf = ref([]);
const korrektur = ref({ menge: 0, grund: '' });
const speichert = ref(false);
async function oeffnen(x) {
  gewaehlt.value = x;
  korrektur.value = { menge: 0, grund: '' };
  verlauf.value = (await l.buchungen(x.bauteilId)) ?? [];
}
async function korrigieren() {
  speichert.value = true;
  const r = await l.korrigieren(gewaehlt.value.bauteilId, Math.round(korrektur.value.menge), korrektur.value.grund);
  speichert.value = false;
  if (r) { gewaehlt.value = l.lager.find((x) => x.bauteilId === gewaehlt.value.bauteilId) ?? gewaehlt.value; korrektur.value = { menge: 0, grund: '' }; verlauf.value = (await l.buchungen(gewaehlt.value.bauteilId)) ?? []; }
}
const artIcon = { Fertigung: ArrowDownToLine, Lieferschein: ArrowUpFromLine, 'Storno Lieferschein': RotateCcw, Korrektur: SlidersHorizontal };
const zeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const SPALTEN = [
  { key: 'bauteil', label: 'Bauteil', wert: (x) => x.teil.name },
  { key: 'teilenummer', label: 'Teilenummer', wert: (x) => x.teil.teilenummer },
  { key: 'zeichnungsnr', label: 'Zeichnung', wert: (x) => x.teil.zeichnungsnr },
  { key: 'kundeName', label: 'Kunde' },
  { key: 'bestand', label: 'Bestand', rechts: true },
];
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="gruppe === 'fertig' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="gruppe = 'fertig'"><Package :size="15" /> Fertigbauteil Lager</button>
        <button class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition" :class="gruppe === 'roh' ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="gruppe = 'roh'"><Layers :size="15" /> Rohmaterial Lager</button>
      </div>
    </div>

    <template v-if="gruppe === 'fertig'">
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <div class="rounded-2xl bg-surface2 px-4 py-2.5"><div class="label">Auf Lager</div><div class="text-xl font-semibold tnum">{{ summe }} Stk</div></div>
        <div v-if="minus" class="rounded-2xl bg-accent-soft px-4 py-2.5 text-accent"><div class="label !text-accent">Im Minus</div><div class="text-xl font-semibold tnum">{{ minus }} Bauteil{{ minus === 1 ? '' : 'e' }}</div></div>
        <label class="relative ml-auto">
          <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
          <input v-model="suche" class="field !w-60 !pl-9" placeholder="Bauteil oder Kunde …" />
        </label>
        <label class="flex cursor-pointer items-center gap-2 text-xs text-mute"><input v-model="nurMinus" type="checkbox" class="accent-[var(--accent)]" /> nur Minusbestand</label>
      </div>

      <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="lager" :beschriftungen="beschriftungen" :standard-angeheftet="[]" />
      <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" zeilen-key="bauteilId" min-breite="800px" @oeffnen="oeffnen">
        <template #bauteil="{ x }"><div class="flex items-center gap-3"><PartImage :teil="x.teil" :groesse="36" /><div class="min-w-0"><div class="truncate font-medium">{{ x.teil.name || 'Ohne Bezeichnung' }}</div><div v-if="x.teil.material" class="truncate text-xs text-mute">{{ x.teil.material }}</div></div></div></template>
        <template #teilenummer="{ x }"><span class="tnum">{{ x.teil.teilenummer || '–' }}</span></template>
        <template #zeichnungsnr="{ x }"><span class="tnum">{{ x.teil.zeichnungsnr || '–' }}</span></template>
        <template #bestand="{ x }"><span class="text-base font-semibold" :class="x.bestand < 0 ? 'text-accent' : x.bestand === 0 ? 'text-mute' : ''">{{ x.bestand }} Stk</span><div v-if="x.bestand < 0" class="text-[11px] text-accent">Lieferschein vor Fertigung</div></template>
        <template #leer>
          <div class="grid place-items-center px-6 py-16 text-center">
            <Package :size="36" class="text-mute" :stroke-width="1.4" />
            <p class="mt-3 text-sm font-medium">{{ l.lager.length ? 'Keine Treffer' : 'Noch nichts im Fertigbauteil Lager' }}</p>
            <p class="mt-1 max-w-md text-xs text-mute">Gefertigte Bauteile kommen automatisch hierher, auch Überproduktion. Ein Lieferschein bucht sie wieder ab; wird er vor der Fertigung angelegt, steht der Bestand im Minus, bis die Fertigung einbucht.</p>
          </div>
        </template>
      </ListenTabelle>
    </template>

    <RohmaterialLager v-else />

    <StammDialog v-if="gewaehlt" :titel="gewaehlt.teil.name || gewaehlt.teil.teilenummer" :untertitel="`Fertigbauteil Lager · Bestand ${gewaehlt.bestand} Stk`" breite="680px" neu speichern-text="Korrektur buchen" :speichert="speichert" :gueltig="!!Math.round(korrektur.menge) && !!korrektur.grund.trim()" @schliessen="gewaehlt = null" @speichern="korrigieren">
      <section>
        <h3 class="mb-2 text-sm font-semibold">Buchungen</h3>
        <ul class="space-y-1">
          <li v-for="b in verlauf" :key="b.id" class="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-surface2">
            <component :is="artIcon[b.art] ?? SlidersHorizontal" :size="14" class="shrink-0 text-mute" />
            <span class="w-24 shrink-0 text-xs text-mute tnum">{{ zeit(b.zeit) }}</span>
            <span class="min-w-0 flex-1 truncate">{{ b.art }}
              <RouterLink v-if="b.lieferschein" :to="`/lieferscheine/${b.lieferschein}`" class="ml-1 text-accent hover:underline tnum">{{ b.lieferschein }}</RouterLink>
              <RouterLink v-else-if="b.fertigungsbauteil" :to="`/fertigung/${b.fertigungsbauteil}`" class="ml-1 text-accent hover:underline tnum">{{ b.fertigungsbauteil }}</RouterLink>
              <span v-if="b.bemerkung" class="ml-1 text-xs text-mute">{{ b.bemerkung }}</span>
            </span>
            <span class="font-semibold tnum" :class="b.menge < 0 ? 'text-accent' : 'text-ok'">{{ b.menge > 0 ? '+' : '' }}{{ b.menge }}</span>
          </li>
          <li v-if="!verlauf.length" class="px-2 py-4 text-center text-xs text-mute">Noch keine Buchungen.</li>
        </ul>
      </section>
      <section class="rounded-xl border border-line p-3">
        <h3 class="mb-2 text-sm font-semibold">Bestand korrigieren</h3>
        <div class="grid gap-3 sm:grid-cols-[160px_1fr]">
          <NumField v-model="korrektur.menge" label="Menge (minus = weniger)" unit="Stk" :decimals="0" :min="-100000" />
          <label class="block"><span class="label mb-1 block">Grund (Pflicht)</span><input v-model="korrektur.grund" class="field" placeholder="z. B. Inventur, Ausschuss, Muster entnommen" /></label>
        </div>
      </section>
    </StammDialog>
  </div>
</template>
