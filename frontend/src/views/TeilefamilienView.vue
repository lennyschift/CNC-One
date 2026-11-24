<script setup>
// Teilefamilien: Varianten eines Teils (z. B. zehn Teile auf einer Zeichnung, nur die Gewindelänge verschieden).
// Oben die Familien, darunter Vorschläge aus Bauteilen ohne Familie (gleiche Zeichnung, gleicher Nummernstamm mit Index).
// Dazu „Geometrie einlesen“: Fingerabdruck aus den STEP-Modellen der Bauteile für die Ähnlichkeitssuche.
import { ref, computed, onMounted } from 'vue';
import { Network, Plus, Lightbulb, Search, Box, Loader, Pencil } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import PartImage from '../components/PartImage.vue';
import TeilefamilieDialog from '../components/TeilefamilieDialog.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';

const ui = useUi();
const familien = ref(null);
const vorschlaege = ref([]);
const suche = ref('');
async function laden() {
  [familien.value, vorschlaege.value] = await Promise.all([call('cnc_one.api.teilefamilie.liste'), call('cnc_one.api.teilefamilie.vorschlaege')]);
}
onMounted(() => { laden(); ohneZaehlen(); });
const gefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return (familien.value ?? []).filter((f) => !q || `${f.bezeichnung} ${f.merkmal} ${f.zeichnungsnr} ${f.kundeName} ${f.varianten.map((v) => `${v.teilenummer} ${v.name} ${v.variante}`).join(' ')}`.toLowerCase().includes(q));
});
const dialog = ref(null);
function gespeichert() { dialog.value = null; laden(); }

// ---- Geometrie aller Bauteile mit STEP-Modell einlesen (nacheinander, im Browser)
const ohne = ref(null);
const lauf = ref(null); // { fertig, gesamt, fehler }
async function ohneZaehlen() { try { ohne.value = await call('cnc_one.api.aehnlich.ohne_fingerabdruck'); } catch { ohne.value = []; } }
async function geometrieEinlesen() {
  const liste = ohne.value ?? [];
  if (!liste.length) return;
  const [{ stepNetze }, { fingerabdruck }] = await Promise.all([import('../lib/step.js'), import('../lib/geometrie.js')]);
  lauf.value = { fertig: 0, gesamt: liste.length, fehler: 0 };
  for (const b of liste) {
    try {
      const f = fingerabdruck(await stepNetze(b.stepDatei));
      if (f) await call('cnc_one.api.aehnlich.fingerabdruck_speichern', { bauteil: b.id, daten: f });
      else lauf.value.fehler += 1;
    } catch { lauf.value.fehler += 1; }
    lauf.value.fertig += 1;
  }
  ui.toast(`Geometrie von ${lauf.value.fertig - lauf.value.fehler} Bauteilen eingelesen${lauf.value.fehler ? `, ${lauf.value.fehler} ließen sich nicht lesen` : ''}`, lauf.value.fehler ? 'warn' : 'ok');
  lauf.value = null;
  ohneZaehlen();
}
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <StammNav />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <p class="mr-auto max-w-[560px] text-sm text-mute">Varianten eines Teils, z. B. mehrere Teile auf einer Zeichnung mit verschiedener Gewindelänge. Jede Variante bleibt ein eigenes Bauteil und einzeln bestellbar.</p>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-60 !pl-9" placeholder="Familie oder Teilenummer …" />
      </label>
      <button class="btn btn-primary" @click="dialog = { familie: null, vorschlag: { bauteile: [] } }"><Plus :size="16" /> Neue Familie</button>
    </div>

    <div v-if="ohne?.length || lauf" class="card mb-4 flex flex-wrap items-center gap-3 p-4 text-sm">
      <Box :size="16" class="text-[#7c3aed]" />
      <span v-if="lauf" class="flex items-center gap-2"><Loader :size="14" class="animate-spin" /> Geometrie wird eingelesen: {{ lauf.fertig }} von {{ lauf.gesamt }}</span>
      <span v-else>{{ ohne.length }} Bauteile mit 3D-Modell haben noch keinen Geometrie-Fingerabdruck. Ohne ihn werden sie bei „ähnliche Bauteile“ nur über Nummer, Werkstoff und Rohteil gefunden.</span>
      <button v-if="!lauf" class="btn ml-auto" @click="geometrieEinlesen"><Box :size="15" /> Geometrie einlesen</button>
    </div>

    <div v-if="familien === null" class="card p-10 text-center text-sm text-mute">Lädt …</div>
    <div v-else class="space-y-3">
      <p v-if="!gefiltert.length" class="card p-10 text-center text-sm text-mute">{{ familien.length ? 'Keine Treffer.' : `Noch keine Teilefamilien. ${vorschlaege.length ? 'Unten stehen Vorschläge' : 'Vorschläge erscheinen, sobald Bauteile dieselbe Zeichnung oder dieselbe Nummer mit anderem Index haben'}; oder in der Workbench bei „Ähnliche Bauteile“ auf „Familie“ klicken.` }}</p>
      <section v-for="f in gefiltert" :key="f.id" class="card p-4">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Network :size="16" class="text-accent" />
          <span class="font-semibold">{{ f.bezeichnung }}</span>
          <span class="text-xs text-mute">{{ f.id }} · {{ f.varianten.length }} Varianten<template v-if="f.merkmal"> · Unterschied: {{ f.merkmal }}</template><template v-if="f.zeichnungsnr"> · Zeichnung {{ f.zeichnungsnr }}</template><template v-if="f.kundeName"> · {{ f.kundeName }}</template></span>
          <button class="btn ml-auto !px-2.5 !py-1 text-xs" @click="dialog = { familie: f }"><Pencil :size="13" /> Bearbeiten</button>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <div v-for="v in f.varianten" :key="v.id" class="flex items-center gap-2 rounded-xl border border-line px-2.5 py-1.5 text-xs">
            <PartImage :teil="v" :groesse="28" />
            <div><div class="font-medium tnum">{{ v.teilenummer }}</div><div class="text-mute">{{ v.variante || v.name || '–' }}</div></div>
          </div>
        </div>
      </section>

      <template v-if="vorschlaege.length">
        <h3 class="flex items-center gap-2 pt-4 text-sm font-semibold"><Lightbulb :size="16" class="text-warn" /> Vorschläge <span class="font-normal text-mute">aus Bauteilen ohne Familie</span></h3>
        <section v-for="v in vorschlaege" :key="v.schluessel" class="card border-dashed p-4">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="font-medium">{{ v.bezeichnung }}</span>
            <span class="text-xs text-mute">{{ v.grund }} · {{ v.bauteile.length }} Bauteile</span>
            <button class="btn btn-primary ml-auto !px-2.5 !py-1 text-xs" @click="dialog = { vorschlag: v }"><Network :size="13" /> Familie bilden</button>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <div v-for="b in v.bauteile" :key="b.id" class="flex items-center gap-2 rounded-xl border border-line px-2.5 py-1.5 text-xs">
              <PartImage :teil="b" :groesse="28" />
              <div><div class="font-medium tnum">{{ b.teilenummer }}</div><div class="text-mute">{{ b.name || '–' }}<template v-if="b.variante"> · {{ b.variante }}</template></div></div>
            </div>
          </div>
        </section>
      </template>
    </div>
    <TeilefamilieDialog v-if="dialog" :familie="dialog.familie ?? null" :vorschlag="dialog.vorschlag ?? null" @schliessen="dialog = null" @gespeichert="gespeichert" />
  </div>
</template>
