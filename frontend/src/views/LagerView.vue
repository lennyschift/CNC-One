<script setup>
import { ref, computed, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Search, Package, Layers, ArrowDownToLine, ArrowUpFromLine, RotateCcw, SlidersHorizontal } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StammDialog from '../components/StammDialog.vue';
import NumField from '../components/NumField.vue';
import { useLieferung } from '../stores/lieferung.js';
import { stammdatenRoh } from '../data/repo.js';

const l = useLieferung();
const gruppe = ref('fertig');
const suche = ref('');
const nurMinus = ref(false);
onMounted(() => l.lagerLaden().catch(() => {}));

const zeilen = computed(() => {
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
const rohmaterialAnzahl = (stammdatenRoh().materialien ?? []).length;
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

      <div v-auto-animate class="space-y-2">
        <button v-for="x in zeilen" :key="x.bauteilId" class="card flex w-full items-center gap-4 p-3.5 text-left transition hover:-translate-y-px hover:border-accent/40" @click="oeffnen(x)">
          <PartImage :teil="x.teil" :groesse="48" />
          <div class="min-w-0 flex-1">
            <div class="truncate font-medium">{{ x.teil.name || 'Ohne Bezeichnung' }}</div>
            <div class="truncate text-xs text-mute">{{ x.teil.teilenummer }}<template v-if="x.teil.zeichnungsnr"> · Zeichnung {{ x.teil.zeichnungsnr }}</template> · {{ x.kundeName }}</div>
          </div>
          <div class="text-right">
            <div class="text-xl font-semibold tnum" :class="x.bestand < 0 ? 'text-accent' : x.bestand === 0 ? 'text-mute' : ''">{{ x.bestand }} <span class="text-xs font-normal text-mute">Stk</span></div>
            <div v-if="x.bestand < 0" class="text-[11px] text-accent">Lieferschein vor Fertigung</div>
          </div>
        </button>
        <div v-if="!zeilen.length" class="card grid place-items-center px-6 py-16 text-center">
          <Package :size="36" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">{{ l.lager.length ? 'Keine Treffer' : 'Noch nichts im Fertigbauteil Lager' }}</p>
          <p class="mt-1 max-w-md text-xs text-mute">Gefertigte Bauteile kommen automatisch hierher, auch Überproduktion. Ein Lieferschein bucht sie wieder ab; wird er vor der Fertigung angelegt, steht der Bestand im Minus, bis die Fertigung einbucht.</p>
        </div>
      </div>
    </template>

    <div v-else class="card grid place-items-center px-6 py-16 text-center">
      <Layers :size="36" class="text-mute" :stroke-width="1.4" />
      <p class="mt-3 text-sm font-medium">Rohmaterial Lager</p>
      <p class="mt-1 max-w-md text-xs text-mute">Hier liegt später der Bestand an Rohmaterial. Die Bestandsführung folgt; die {{ rohmaterialAnzahl }} Rohmaterialien mit Preis pflegst du unter Stammdaten.</p>
      <RouterLink to="/stammdaten/materialien" class="btn mt-4">Zu den Rohmaterialien</RouterLink>
    </div>

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
