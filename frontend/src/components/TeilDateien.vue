<script setup>
// Zeichnung und 3D-Modell eines Workbench-Bauteils nebeneinander. Dateien lassen sich direkt auf die Fläche ziehen oder auswählen;
// sie werden sofort hochgeladen. Aus dem ersten gelesenen Modell entsteht automatisch das Vorschaubild des Bauteils.
import { ref, computed, defineAsyncComponent, onMounted, onBeforeUnmount, watch } from 'vue';
import { Box, FileText, Loader, UploadCloud, X, FileWarning, ScanText, Merge, MonitorUp, Undo2 } from '@lucide/vue';
import { fenster, oeffnen, senden, schliessen, empfangen } from '../lib/fenster.js';
import ErkennungsHinweis from './ErkennungsHinweis.vue';
import { useAngebot } from '../stores/angebot.js';
import { useUi } from '../stores/ui.js';
import { repo } from '../data/repo.js';
import { zahl } from '../lib/format.js';
import { dichteSchaetzen } from '../lib/erkennung.js';
import { ausModell, vorschlagAnwenden, rohText } from '../lib/rohmaterial.js';

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
  if (angebot.nurAnsicht) { ui.toast('Gesendetes Angebot: nur ansehen', 'warn'); return; }
  props.teil.gewichtKg = kg;
  ui.toast(`Rohteilgewicht ${zahl(kg, 3)} kg übernommen`, 'ok');
}
// Rohteil aus dem 3D-Modell: als Vorschlag merken (zeigt das Rohmaterial an) bzw. ins Rohmaterial übernehmen
function vorschlagMerken(r) {
  if (angebot.nurAnsicht) return;
  const v = ausModell(r);
  if (JSON.stringify(v) !== JSON.stringify(props.teil.rohVorschlag ?? null)) props.teil.rohVorschlag = v;
}
function rohteilUebernehmen(r) {
  if (angebot.nurAnsicht) { ui.toast('Gesendetes Angebot: nur ansehen', 'warn'); return; }
  const v = ausModell(r);
  props.teil.rohVorschlag = v;
  props.teil.roh = vorschlagAnwenden(props.teil.roh, v);
  // ohne gepflegte Dichte rechnet das Rohmaterial kein Gewicht: dann das Gewicht aus dem Modell nehmen
  if (!dichte.value && r.gewicht) props.teil.gewichtKg = r.gewicht;
  ui.toast(`Rohteil ${rohText(props.teil.roh)} mm übernommen`, 'ok');
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
  if (props.teil.vorschaubild || angebot.nurAnsicht) return;
  const { vorschauPng } = await import('../lib/modell3d.js');
  angebot.vorschaubildSetzen(props.teil, await vorschauPng(netze));
}
const vorschauUebernehmen = (blob) => angebot.vorschaubildSetzen(props.teil, blob, true);
const nurAnsicht = computed(() => !!angebot.nurAnsicht);

// Zeichnung und Modell im eigenen Fenster (zweiter Bildschirm): es zeigt immer das gewählte Bauteil
const titel = computed(() => [props.teil.teilenummer, props.teil.name].filter(Boolean).join(' · '));
const inhaltZ = computed(() => ({ teilId: props.teil.id, titel: titel.value, url: zeichnung.value?.url ?? '', name: zeichnung.value?.name ?? '' }));
const inhaltM = computed(() => ({
  teilId: props.teil.id, titel: titel.value, url: modell.value?.url ?? '', name: modell.value?.name ?? '',
  dichte: dichte.value, dichteGeschaetzt: dichteGeschaetzt.value, aufmass: JSON.parse(JSON.stringify(aufmass.value ?? 0)), vorschauFehlt: !props.teil.vorschaubild && !nurAnsicht.value, nurAnsicht: nurAnsicht.value,
}));
watch(inhaltZ, (v) => senden('zeichnung', v), { immediate: true });
watch(inhaltM, (v) => senden('modell', v), { immediate: true });
function imFenster(art) {
  if (!oeffnen(art, art === 'zeichnung' ? inhaltZ.value : inhaltM.value)) ui.toast('Der Browser hat das Fenster blockiert: Pop-ups für CNC One erlauben', 'warn');
}
let abmelden = null;
onMounted(() => {
  abmelden = empfangen((m) => {
    if (m.teilId !== props.teil.id) return;
    if (m.typ === 'gewicht') gewichtUebernehmen(m.kg);
    else if (m.typ === 'rohteil' && m.r) rohteilUebernehmen(m.r);
    else if (m.typ === 'vorschlag' && m.r) vorschlagMerken(m.r);
    else if (m.typ === 'vorschau' && m.blob && !nurAnsicht.value) angebot.vorschaubildSetzen(props.teil, m.blob, !m.auto);
    else if (m.typ === 'aufmass' && !nurAnsicht.value) aufmass.value = m.wert;
  });
});
onBeforeUnmount(() => abmelden?.());

const groesse = (b) => (!b ? '' : b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);

// Zeichnung und Modell sind auf zwei Bauteile verteilt (Namen passten nicht): das andere hierher holen
const fehlt = computed(() => (zeichnungen.value.length && !modelle.value.length ? 'STEP' : modelle.value.length && !zeichnungen.value.length ? 'Zeichnung' : ''));
const gegenstuecke = computed(() => {
  if (!fehlt.value) return [];
  const hat = fehlt.value === 'STEP' ? 'Zeichnung' : 'STEP';
  return angebot.teile.filter((t) => t.id !== props.teil.id && t.dateien.some((d) => d.art === fehlt.value && d.url) && !t.dateien.some((d) => d.art === hat));
});
const zusammenMit = ref('');
function zusammenfuehren() {
  if (zusammenMit.value) angebot.zusammenfuehren(props.teil.id, zusammenMit.value);
  zusammenMit.value = '';
}
</script>

<template>
  <section class="card p-5">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><Box :size="16" class="text-accent" /> Zeichnung und 3D-Modell</h3>
      <span v-if="laufend.length" class="ml-auto inline-flex items-center gap-1.5 text-xs text-mute"><Loader :size="13" class="animate-spin" /> {{ laufend.join(', ') }} wird hochgeladen …</span>
    </div>

    <ErkennungsHinweis v-if="!nurAnsicht" :teil="teil" class="mb-4" />

    <div v-if="gegenstuecke.length && !nurAnsicht" class="mb-4 flex flex-wrap items-center gap-2 rounded-xl bg-surface2 px-3 py-2 text-xs">
      <Merge :size="14" class="shrink-0 text-accent" />
      <span>{{ fehlt === 'STEP' ? 'Das 3D-Modell' : 'Die Zeichnung' }} liegt in einem anderen Bauteil? Gehört zusammen mit</span>
      <select v-model="zusammenMit" class="field !w-auto !py-1 !text-xs">
        <option value="">Bauteil wählen …</option>
        <option v-for="t in gegenstuecke" :key="t.id" :value="t.id">{{ t.name }}</option>
      </select>
      <button class="btn !py-1 !text-xs" :disabled="!zusammenMit" @click="zusammenfuehren">Zusammenführen</button>
      <span class="text-mute">Dateien kommen hierher, das andere Bauteil entfällt.</span>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <!-- Zeichnung -->
      <div class="flex min-w-0 flex-col gap-2">
        <div class="flex min-h-7 flex-wrap items-center gap-1.5">
          <span class="label mr-1">Zeichnung</span>
          <span v-for="(d, i) in zeichnungen" :key="d.url" class="datei" :class="d === zeichnung ? 'datei-aktiv' : ''">
            <button class="truncate" :title="d.name" @click="zWahl = i">{{ d.name }}</button>
            <span class="text-[10px] opacity-70 tnum">{{ groesse(d.groesse) }}</span>
            <button v-if="!nurAnsicht" class="opacity-60 hover:opacity-100" title="Vom Bauteil entfernen" @click="angebot.dateiEntfernen(teil, d)"><X :size="12" /></button>
          </span>
          <button v-if="zeichnung && !nurAnsicht" class="ml-auto inline-flex items-center gap-1 text-xs text-mute hover:text-ink" title="Angaben aus der Zeichnung erneut lesen" @click="angebot.erkennenFuer(teil, zeichnung)"><ScanText :size="13" /> Erkennen</button>
          <button v-if="zeichnungen.length && !nurAnsicht" class="text-xs text-mute hover:text-ink" @click="auswahlZ.click()">+ PDF</button>
          <button v-if="!fenster.zeichnung" class="inline-flex items-center gap-1 text-xs text-mute hover:text-ink" :class="zeichnung && !nurAnsicht ? '' : 'ml-auto'" title="Zeichnung in einem eigenen Fenster zeigen, z. B. auf dem zweiten Bildschirm" @click="imFenster('zeichnung')"><MonitorUp :size="13" /> 2. Bildschirm</button>
        </div>
        <div class="h-[460px]" @dragover.prevent="ueber = 'z'" @dragleave="ueber = ''" @drop.prevent="ablegen($event, 'Zeichnung')">
          <div v-if="zeichnung && fenster.zeichnung" class="leer">
            <MonitorUp :size="26" :stroke-width="1.4" />
            <span class="mt-2 text-sm font-medium text-ink">Zeichnung im eigenen Fenster</span>
            <span class="mt-0.5 text-xs">Es zeigt immer das gewählte Bauteil.</span>
            <span class="mt-3 flex gap-2"><button class="btn !py-1 !text-xs" @click="imFenster('zeichnung')">Nach vorne holen</button><button class="btn !py-1 !text-xs" @click="schliessen('zeichnung')"><Undo2 :size="13" /> Zurückholen</button></span>
          </div>
          <DrawingViewer
            v-else-if="zeichnung" :key="zeichnung.url" :url="zeichnung.url" :name="zeichnung.name"
            :markierung="angebot.markierung?.teilId === teil.id ? angebot.markierung.lage : null"
            :fokus="angebot.fokus?.teilId === teil.id ? angebot.fokus : null"
            :anlernen="angebot.anlernen?.teilId === teil.id"
            fenster="knopf" @punkt="(p) => angebot.anlernPunkt(teil, p.x, p.y)" @fenster="imFenster('zeichnung')"
          />
          <div v-else-if="nurAnsicht" class="leer">Keine Zeichnung</div>
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
            <button v-if="!nurAnsicht" class="opacity-60 hover:opacity-100" title="Vom Bauteil entfernen" @click="angebot.dateiEntfernen(teil, d)"><X :size="12" /></button>
          </span>
          <button v-if="modelle.length && !nurAnsicht" class="ml-auto text-xs text-mute hover:text-ink" @click="auswahlM.click()">+ STEP</button>
          <button v-if="!fenster.modell" class="inline-flex items-center gap-1 text-xs text-mute hover:text-ink" :class="modelle.length && !nurAnsicht ? '' : 'ml-auto'" title="3D-Modell in einem eigenen Fenster zeigen, z. B. auf dem zweiten Bildschirm" @click="imFenster('modell')"><MonitorUp :size="13" /> 2. Bildschirm</button>
        </div>
        <div class="h-[460px]" @dragover.prevent="ueber = 'm'" @dragleave="ueber = ''" @drop.prevent="ablegen($event, 'STEP')">
          <div v-if="modell && fenster.modell" class="leer">
            <MonitorUp :size="26" :stroke-width="1.4" />
            <span class="mt-2 text-sm font-medium text-ink">3D-Modell im eigenen Fenster</span>
            <span class="mt-0.5 text-xs">Es zeigt immer das gewählte Bauteil.</span>
            <span class="mt-3 flex gap-2"><button class="btn !py-1 !text-xs" @click="imFenster('modell')">Nach vorne holen</button><button class="btn !py-1 !text-xs" @click="schliessen('modell')"><Undo2 :size="13" /> Zurückholen</button></span>
          </div>
          <ModelViewer
            v-else-if="modell" :key="modell.url" v-model:aufmass="aufmass" :url="modell.url" :name="modell.name" :dichte="dichte" :dichte-geschaetzt="dichteGeschaetzt"
            :nur-ansehen="nurAnsicht" fenster-knopf @geladen="modellGeladen" @vorschau="vorschauUebernehmen" @gewicht="gewichtUebernehmen" @rohteil="rohteilUebernehmen" @vorschlag="vorschlagMerken" @fenster="imFenster('modell')"
          />
          <div v-else-if="nurAnsicht" class="leer">Kein 3D-Modell</div>
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
