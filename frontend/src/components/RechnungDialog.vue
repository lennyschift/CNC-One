<script setup>
// Rechnung aus einem Auftrag: Gesamtrechnung (alles, was noch nicht berechnet ist) oder Teilrechnung (Menge je Lieferscheinposition).
// Sonderkosten werden immer in der ersten Rechnung vollständig berechnet und danach als abgerechnet markiert.
import { ref, reactive, computed, onMounted } from 'vue';
import { FileText, Layers, AlertTriangle, Check, Truck } from '@lucide/vue';
import StammDialog from './StammDialog.vue';
import PartImage from './PartImage.vue';
import NumField from './NumField.vue';
import StatusBadge from './StatusBadge.vue';
import { eur } from '../lib/format.js';
import { r2 } from '../lib/calc.js';
import { useRechnung } from '../stores/rechnung.js';

const props = defineProps({ auftragId: { type: String, required: true } });
const emit = defineEmits(['schliessen', 'angelegt']);
const store = useRechnung();

const SATZ = 19;
const daten = ref(null);
const art = ref('gesamt');
const mengen = reactive({});
const kopf = reactive({ rechnungsdatum: '', bemerkung: '' });
const speichert = ref(false);

onMounted(async () => {
  daten.value = await store.vorschlag(props.auftragId);
  for (const ls of daten.value?.lieferscheine ?? []) for (const p of ls.positionen) mengen[`${ls.id}|${p.auftragPosKey}`] = p.frei;
  // Gibt es noch nichts Geliefertes, bleibt nur die Gesamtrechnung
  if (!daten.value?.lieferscheine.some((l) => l.positionen.some((p) => p.frei > 0))) art.value = 'gesamt';
});

const positionen = computed(() => daten.value?.positionen ?? []);
const lieferscheine = computed(() => daten.value?.lieferscheine ?? []);
const teilMoeglich = computed(() => lieferscheine.value.some((l) => l.positionen.some((p) => p.frei > 0)));
const pos = (key) => positionen.value.find((p) => p.key === key);

// ---- Vorschau der Beträge
const zeilen = computed(() => {
  const out = [];
  for (const p of positionen.value) {
    const menge = art.value === 'gesamt'
      ? p.offen
      : lieferscheine.value.reduce((n, l) => n + (l.positionen.filter((x) => x.auftragPosKey === p.key).reduce((s, x) => s + (Math.min(Math.max(0, Math.floor(Number(mengen[`${l.id}|${p.key}`]) || 0)), x.frei)), 0)), 0);
    if (menge <= 0) continue;
    const kosten = p.kosten.filter((k) => !k.inRechnung);
    out.push({ p, menge, netto: r2(menge * p.einzelpreis), kosten, kostenSumme: r2(kosten.reduce((s, k) => s + k.betrag, 0)), ungeliefert: Math.max(0, menge - p.geliefert + (art.value === 'gesamt' ? p.berechnet : 0)) });
  }
  return out;
});
const netto = computed(() => r2(zeilen.value.reduce((s, z) => s + z.netto + z.kostenSumme, 0)));
const steuer = computed(() => r2(netto.value * SATZ / 100));
const brutto = computed(() => r2(netto.value + steuer.value));

const fehler = computed(() => {
  if (!zeilen.value.length) return 'Es gibt nichts zu berechnen.';
  if (art.value === 'teil') {
    for (const l of lieferscheine.value) for (const x of l.positionen) {
      const m = Math.floor(Number(mengen[`${l.id}|${x.auftragPosKey}`]) || 0);
      if (m > x.frei) return `Aus ${l.id} sind nur noch ${x.frei} Stück zu berechnen.`;
    }
  }
  return '';
});

async function anlegen() {
  speichert.value = true;
  const werte = { auftrag: props.auftragId, art: art.value === 'gesamt' ? 'Gesamtrechnung' : 'Teilrechnung', rechnungsdatum: kopf.rechnungsdatum || null, bemerkung: kopf.bemerkung };
  if (art.value === 'teil') {
    werte.mengen = lieferscheine.value.flatMap((l) => l.positionen
      .map((x) => ({ lieferschein: l.id, auftragsposition: x.auftragPosKey, menge: Math.floor(Number(mengen[`${l.id}|${x.auftragPosKey}`]) || 0) }))
      .filter((m) => m.menge > 0));
  }
  const rec = await store.anlegen(werte);
  speichert.value = false;
  if (rec) emit('angelegt', rec);
}
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
</script>

<template>
  <StammDialog :titel="`Rechnung aus ${auftragId}`" :untertitel="daten?.kundeName ?? ''" breite="920px" neu speichern-text="Entwurf anlegen" :speichert="speichert" :gueltig="!!daten && !fehler" @schliessen="emit('schliessen')" @speichern="anlegen">
    <p v-if="!daten" class="py-8 text-center text-sm text-mute">Lädt …</p>
    <template v-else>
      <div class="grid gap-3 sm:grid-cols-2">
        <button type="button" class="rounded-2xl border p-4 text-left transition" :class="art === 'gesamt' ? 'border-accent bg-accent-soft' : 'border-line hover:border-mute'" @click="art = 'gesamt'">
          <div class="flex items-center gap-2 font-semibold"><FileText :size="17" class="text-accent" /> Gesamtrechnung</div>
          <p class="mt-1 text-xs text-mute">Alles, was noch nicht berechnet ist, mit allen Sonderkosten. Die Lieferscheine werden bei jedem Bauteil aufgeführt.</p>
        </button>
        <button type="button" class="rounded-2xl border p-4 text-left transition" :class="[art === 'teil' ? 'border-accent bg-accent-soft' : 'border-line hover:border-mute', teilMoeglich ? '' : 'pointer-events-none opacity-50']" @click="art = 'teil'">
          <div class="flex items-center gap-2 font-semibold"><Layers :size="17" class="text-accent" /> Teilrechnung</div>
          <p class="mt-1 text-xs text-mute">{{ teilMoeglich ? 'Menge je Lieferschein wählen. Die Sonderkosten kommen in die erste Rechnung vollständig.' : 'Dafür braucht es einen Lieferschein mit noch nicht berechneter Menge.' }}</p>
        </button>
      </div>

      <!-- Gesamtrechnung -->
      <section v-if="art === 'gesamt'" class="space-y-2">
        <div v-for="p in positionen" :key="p.key" class="flex items-center gap-3 rounded-xl border border-line p-3" :class="p.offen ? '' : 'opacity-50'">
          <PartImage :teil="p.teil" :groesse="44" />
          <div class="min-w-0 flex-1">
            <div class="truncate font-medium">{{ p.teil.name }} <span class="text-xs font-normal text-mute">{{ p.teil.teilenummer }}</span></div>
            <div class="text-xs text-mute tnum">bestellt {{ p.bestellt }} · geliefert {{ p.geliefert }} · schon berechnet {{ p.berechnet }} · <span class="font-medium text-ink">jetzt {{ p.offen }}</span></div>
          </div>
          <div class="text-right text-sm tnum">{{ eur(p.offen * p.einzelpreis) }}</div>
        </div>
      </section>

      <!-- Teilrechnung -->
      <section v-else class="space-y-3">
        <div v-for="l in lieferscheine" :key="l.id" class="rounded-xl border border-line">
          <div class="flex items-center gap-3 border-b border-line bg-surface2 px-4 py-2 text-sm"><Truck :size="15" class="text-accent" /><span class="font-semibold tnum">{{ l.id }}</span><StatusBadge :status="l.status" /><span class="ml-auto text-xs text-mute">{{ de(l.datum) }}</span></div>
          <div v-for="x in l.positionen" :key="x.auftragPosKey" class="flex flex-wrap items-center gap-3 px-4 py-2.5">
            <PartImage :teil="pos(x.auftragPosKey).teil" :groesse="36" />
            <div class="min-w-0 flex-1"><div class="truncate text-sm font-medium">{{ pos(x.auftragPosKey).teil.name }}</div><div class="text-xs text-mute tnum">geliefert {{ x.menge }} · schon berechnet {{ x.berechnet }} · frei {{ x.frei }}</div></div>
            <NumField v-if="x.frei > 0" v-model="mengen[`${l.id}|${x.auftragPosKey}`]" label="Menge" unit="Stk" :decimals="0" :min="0" class="w-32" />
            <span v-else class="inline-flex items-center gap-1 text-xs text-ok"><Check :size="13" /> berechnet</span>
          </div>
        </div>
      </section>

      <!-- Vorschau -->
      <section v-if="zeilen.length" class="rounded-2xl bg-surface2 p-4 text-sm">
        <div v-for="z in zeilen" :key="z.p.key" class="mb-2 border-b border-line pb-2 last:mb-0 last:border-0 last:pb-0">
          <div class="flex justify-between gap-3"><span>{{ z.menge }} Stk {{ z.p.teil.name }} × {{ eur(z.p.einzelpreis) }}</span><span class="tnum">{{ eur(z.netto) }}</span></div>
          <div v-for="k in z.kosten" :key="k.name" class="flex justify-between gap-3 pl-4 text-xs text-mute"><span>↳ {{ k.label }}</span><span class="tnum">{{ eur(k.betrag) }}</span></div>
          <div v-for="k in z.p.kosten.filter((x) => x.inRechnung)" :key="k.name" class="flex justify-between gap-3 pl-4 text-xs text-mute opacity-60"><span>↳ {{ k.label }} · schon in einer früheren Rechnung</span><span>–</span></div>
          <p v-if="art === 'gesamt' && z.ungeliefert > 0" class="mt-1 flex items-center gap-1.5 pl-4 text-xs text-warn"><AlertTriangle :size="12" /> {{ z.ungeliefert }} Stk sind noch nicht geliefert und stehen als „noch nicht geliefert“ in der Rechnung.</p>
        </div>
        <div class="mt-3 grid grid-cols-[1fr_auto] gap-x-6 gap-y-0.5 text-right">
          <span class="text-mute">Netto</span><span class="tnum">{{ eur(netto) }}</span>
          <span class="text-mute">Umsatzsteuer {{ SATZ }} %</span><span class="tnum">{{ eur(steuer) }}</span>
          <span class="font-semibold">Brutto</span><span class="text-base font-semibold tnum">{{ eur(brutto) }}</span>
        </div>
      </section>
      <p v-if="fehler && zeilen.length" class="flex items-center gap-1.5 text-xs text-accent"><AlertTriangle :size="13" /> {{ fehler }}</p>

      <div class="grid gap-3 sm:grid-cols-[200px_1fr]">
        <label class="block"><span class="label mb-1 block">Rechnungsdatum</span><input v-model="kopf.rechnungsdatum" type="date" class="field" /><span class="mt-1 block text-[11px] text-mute">Beim Festschreiben gilt das Tagesdatum.</span></label>
        <label class="block"><span class="label mb-1 block">Bemerkung (steht auf der Rechnung)</span><input v-model="kopf.bemerkung" class="field" /></label>
      </div>
    </template>
  </StammDialog>
</template>
