<script setup>
// Zeichnung und 3D-Modell eines Workbench-Bauteils nebeneinander. Dateien lassen sich direkt auf die Fläche ziehen oder auswählen;
// sie werden sofort hochgeladen. Aus dem ersten gelesenen Modell entsteht automatisch das Vorschaubild des Bauteils.
import { ref, computed, defineAsyncComponent, onMounted } from 'vue';
import { Box, FileText, Loader, UploadCloud, X, FileWarning, ScanText } from '@lucide/vue';
import ErkennungsHinweis from './ErkennungsHinweis.vue';
import { useAngebot } from '../stores/angebot.js';
import { useUi } from '../stores/ui.js';
import { repo } from '../data/repo.js';
import { zahl } from '../lib/format.js';
import { dichteSchaetzen } from '../lib/erkennung.js';

const ModelViewer = defineAsyncComponent(() => import('./ModelViewer.vue'));
const DrawingViewer = defineAsyncComponent(() => import('./DrawingViewer.vue'));

const props = defineProps({ teil: { type: Object, required: true } });
const angebot = useAngebot();
const ui = useUi();

// Dichte des gewählten Rohmaterials (kg/dm³) für das Gewicht des Rohteils
const materialien = ref([]);
onMounted(async () => { materialien.value = await repo.materialien.liste(); });
// Dichte des gewählten Rohmaterials; ist keine gepflegt, ein Richtwert aus dem Werkstoff (als geschätzt gekennzeichnet)
const gepflegteDichte = computed(() => materialien.value.find((m) => m.name === props.teil.material)?.dichte ?? 0);
const dichte = computed(() => gepflegteDichte.value || dichteSchaetzen(props.teil.material));
const dichteGeschaetzt = computed(() => !gepflegteDichte.value && !!dichte.value);
const aufmass = computed({ get: () => props.teil.aufmass ?? 0, set: (v) => { props.teil.aufmass = v; } });
function gewichtUebernehmen(kg) {
  props.teil.gewichtKg = kg;
  ui.toast(`Rohteilgewicht ${zahl(kg, 3)} kg übernommen`, 'ok');
}

const hochgeladen = (art) => computed(() => props.teil.dateien.filter((d) => d.art === art && d.url));
const zeichnungen = hochgeladen('Zeichnung');
const modelle = hochgeladen('STEP');
const ohneDatei = computed(() => props.teil.dateien.filter((d) => !d.url));
const laufend = computed(() => angebot.uploads[props.teil.id] ?? []);

const zWahl = ref(0);
const mWahl = ref(0);
const zeichnung = computed(() => zeichnungen.value[zWahl.value] ?? zeichnungen.value[0] ?? null);
const modell = computed(() => modelle.value[mWahl.value] ?? modelle.value[0] ?? null);

const auswahlZ = ref(null);
const auswahlM = ref(null);
const ueber = ref('');

function ablegen(e, art) {
  ueber.value = '';
  const files = Array.from(e.dataTransfer?.files ?? []);
  if (!files.length) return;
  e.stopPropagation(); // nicht zusätzlich als neue Bauteile anlegen (DropOverlay)
  angebot.dateienHinzufuegen(files, props.teil);
  if (art === 'Zeichnung') zWahl.value = zeichnungen.value.length;
  else mWahl.value = modelle.value.length;
}
function gewaehlt(e) {
  const files = Array.from(e.target.files ?? []);
  e.target.value = '';
  if (files.length) angebot.dateienHinzufuegen(files, props.teil);
}

async function modellGeladen(netze) {
  if (props.teil.vorschaubild) return;
  const { vorschauPng } = await import('../lib/modell3d.js');
  angebot.vorschaubildSetzen(props.teil, await vorschauPng(netze));
}
const vorschauUebernehmen = (blob) => angebot.vorschaubildSetzen(props.teil, blob, true);

const groesse = (b) => (!b ? '' : b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);
</script>

<template>
  <section class="card p-5">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><Box :size="16" class="text-accent" /> Zeichnung und 3D-Modell</h3>
      <span v-if="laufend.length" class="ml-auto inline-flex items-center gap-1.5 text-xs text-mute"><Loader :size="13" class="animate-spin" /> {{ laufend.join(', ') }} wird hochgeladen …</span>
    </div>

    <ErkennungsHinweis :teil="teil" class="mb-4" />

    <div class="grid gap-4 xl:grid-cols-2">
      <!-- Zeichnung -->
      <div class="flex min-w-0 flex-col gap-2">
        <div class="flex min-h-7 flex-wrap items-center gap-1.5">
          <span class="label mr-1">Zeichnung</span>
          <span v-for="(d, i) in zeichnungen" :key="d.url" class="datei" :class="d === zeichnung ? 'datei-aktiv' : ''">
            <button class="truncate" :title="d.name" @click="zWahl = i">{{ d.name }}</button>
            <span class="text-[10px] opacity-70 tnum">{{ groesse(d.groesse) }}</span>
            <button class="opacity-60 hover:opacity-100" title="Vom Bauteil entfernen" @click="angebot.dateiEntfernen(teil, d)"><X :size="12" /></button>
          </span>
          <button v-if="zeichnung" class="ml-auto inline-flex items-center gap-1 text-xs text-mute hover:text-ink" title="Angaben aus der Zeichnung erneut lesen" @click="angebot.erkennenFuer(teil, zeichnung)"><ScanText :size="13" /> Erkennen</button>
          <button v-if="zeichnungen.length" class="text-xs text-mute hover:text-ink" @click="auswahlZ.click()">+ PDF</button>
        </div>
        <div class="h-[460px]" @dragover.prevent="ueber = 'z'" @dragleave="ueber = ''" @drop.prevent="ablegen($event, 'Zeichnung')">
          <DrawingViewer
            v-if="zeichnung" :key="zeichnung.url" :url="zeichnung.url" :name="zeichnung.name"
            :markierung="angebot.markierung?.teilId === teil.id ? angebot.markierung.lage : null"
            :fokus="angebot.fokus?.teilId === teil.id ? angebot.fokus : null"
            :anlernen="angebot.anlernen?.teilId === teil.id"
            @punkt="(p) => angebot.anlernPunkt(teil, p.x, p.y)"
          />
          <button v-else class="leer" :class="ueber === 'z' ? 'leer-aktiv' : ''" @click="auswahlZ.click()">
            <FileText :size="30" :stroke-width="1.4" />
            <span class="mt-2 text-sm font-medium text-ink">PDF-Zeichnung hierher ziehen</span>
            <span class="mt-0.5 text-xs">oder klicken zum Auswählen</span>
          </button>
        </div>
        <input ref="auswahlZ" type="file" accept=".pdf,application/pdf" multiple class="hidden" @change="gewaehlt" />
      </div>

      <!-- 3D-Modell -->
      <div class="flex min-w-0 flex-col gap-2">
        <div class="flex min-h-7 flex-wrap items-center gap-1.5">
          <span class="label mr-1">3D-Modell</span>
          <span v-for="(d, i) in modelle" :key="d.url" class="datei" :class="d === modell ? 'datei-aktiv' : ''">
            <button class="truncate" :title="d.name" @click="mWahl = i">{{ d.name }}</button>
            <span class="text-[10px] opacity-70 tnum">{{ groesse(d.groesse) }}</span>
            <button class="opacity-60 hover:opacity-100" title="Vom Bauteil entfernen" @click="angebot.dateiEntfernen(teil, d)"><X :size="12" /></button>
          </span>
          <button v-if="modelle.length" class="ml-auto text-xs text-mute hover:text-ink" @click="auswahlM.click()">+ STEP</button>
        </div>
        <div class="h-[460px]" @dragover.prevent="ueber = 'm'" @dragleave="ueber = ''" @drop.prevent="ablegen($event, 'STEP')">
          <ModelViewer
            v-if="modell" :key="modell.url" v-model:aufmass="aufmass" :url="modell.url" :name="modell.name" :dichte="dichte" :dichte-geschaetzt="dichteGeschaetzt"
            @geladen="modellGeladen" @vorschau="vorschauUebernehmen" @gewicht="gewichtUebernehmen"
          />
          <button v-else class="leer" :class="ueber === 'm' ? 'leer-aktiv' : ''" @click="auswahlM.click()">
            <UploadCloud :size="30" :stroke-width="1.4" />
            <span class="mt-2 text-sm font-medium text-ink">STEP-Modell hierher ziehen</span>
            <span class="mt-0.5 text-xs">.step oder .stp, oder klicken zum Auswählen</span>
          </button>
        </div>
        <input ref="auswahlM" type="file" accept=".step,.stp" multiple class="hidden" @change="gewaehlt" />
      </div>
    </div>

    <p v-if="ohneDatei.length" class="mt-3 flex items-start gap-1.5 rounded-xl bg-surface2 px-3 py-2 text-xs text-mute">
      <FileWarning :size="14" class="mt-0.5 shrink-0" />
      <span>Nur als Name vermerkt (aus der Zeit vor dem Hochladen): {{ ohneDatei.map((d) => d.name).join(', ') }}. Zum Ansehen die Datei erneut hineinziehen.</span>
    </p>
  </section>
</template>

<style scoped>
.datei { display: inline-flex; max-width: 16rem; align-items: center; gap: 0.35rem; border-radius: 0.6rem; background: var(--surface-2); padding: 0.2rem 0.5rem; font-size: 0.75rem; color: var(--mute); }
.datei-aktiv { background: var(--accent-soft); color: var(--accent); }
.leer { display: flex; height: 100%; width: 100%; flex-direction: column; align-items: center; justify-content: center; border-radius: 1rem; border: 2px dashed var(--line); color: var(--mute); transition: border-color 0.15s, background 0.15s; }
.leer:hover, .leer-aktiv { border-color: var(--accent); background: var(--accent-soft); }
</style>
