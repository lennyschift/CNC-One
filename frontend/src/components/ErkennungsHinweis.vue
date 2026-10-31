<script setup>
// Aus der Zeichnung erkannte Angaben zum Bestätigen: jede Zeile lässt sich ändern und einzeln an- oder abwählen.
// Fehlt eine Angabe oder ist sie falsch, wird sie angelernt: Feld wählen, Wert in der Zeichnung anklicken. Beim Übernehmen
// merkt sich der Kunde die Stelle (Kundenvorlage), die nächste Zeichnung dieses Kunden wird dann von selbst erkannt.
// Dazu vorhandene Bauteile mit derselben Teile- oder Zeichnungsnummer als Vorschlag.
import { ref, computed, watch, onMounted } from 'vue';
import { useEventListener } from '@vueuse/core';
import { ScanText, Loader, AlertTriangle, Database, Check, X, Crosshair, GraduationCap } from '@lucide/vue';
import PartImage from './PartImage.vue';
import { useAngebot } from '../stores/angebot.js';
import { repo } from '../data/repo.js';
import { materialFinden, kundeFinden, elementMitWert, lernregel, regelnAus, rohmaterialName } from '../lib/erkennung.js';

const props = defineProps({ teil: { type: Object, required: true } });
const angebot = useAngebot();
const e = computed(() => angebot.erkennungen[props.teil.id] ?? null);

const materialien = ref([]);
const kunden = ref([]);
onMounted(async () => { [materialien.value, kunden.value] = await Promise.all([repo.materialien.liste(), repo.kunden.liste()]); });

const FELDER = [
  ['bezeichnung', 'Bezeichnung', 'name'],
  ['teilenummer', 'Teilenummer', 'teilenummer'],
  ['zeichnungsnr', 'Zeichnungsnummer', 'zeichnungsnr'],
  ['revision', 'Revision', 'revision'],
  ['werkstoff', 'Werkstoff', 'material'],
  ['kunde', 'Kunde', 'kundeId'],
];

// Zeilen der Maske. Wird eine Angabe angelernt, bleibt in den anderen Zeilen stehen, was schon geändert wurde.
const zeilen = ref([]);
watch(e, (x) => {
  if (x?.stand !== 'fertig') { zeilen.value = []; return; }
  const vorher = Object.fromEntries(zeilen.value.map((r) => [r.feld, r]));
  zeilen.value = FELDER.filter(([feld]) => feld !== 'kunde' || !angebot.kopf.kundeId).map(([feld, label, ziel]) => {
    const quelle = x.felder[feld] ?? null;
    const bisher = ziel === 'kundeId' ? '' : String(props.teil[ziel] ?? '');
    if (vorher[feld] && vorher[feld].von === quelle && vorher[feld].bisher === bisher) return vorher[feld];
    const wert = quelle?.wert ?? '';
    return { feld, label, ziel, wert, bisher, von: quelle, sicherheit: quelle?.sicherheit ?? '', quelle: quelle?.quelle ?? '', materialWahl: '', waehlen: false,
      an: !!wert && wert !== bisher && (quelle.sicherheit !== 'niedrig' || !bisher) };
  });
}, { immediate: true });

const info = computed(() => ['toleranz', 'oberflaeche'].map((k) => e.value?.felder?.[k] && { label: k === 'toleranz' ? 'Allgemeintoleranz' : 'Oberfläche', wert: e.value.felder[k].wert }).filter(Boolean));
// Rohmaterial der Werkstoff-Zeile: von Hand gewählt, sonst über Schreibweise bzw. Werkstoffnummer gefunden
const material = (r) => (r.materialWahl ? materialien.value.find((m) => m.name === r.materialWahl) : materialFinden(r.wert, materialien.value)) ?? null;
async function rohmaterialAnlegen(r) {
  const m = await angebot.rohmaterialAnlegen(rohmaterialName(r.wert), r.wert.trim());
  if (!m) return;
  materialien.value = [...(await repo.materialien.liste())];
  r.materialWahl = m.name;
  r.waehlen = false;
  r.an = true;
}
const kunde = (r) => kundeFinden(r.wert, kunden.value);
// Eine Zeile lässt sich nur übernehmen, wenn es ein Ziel gibt (Rohmaterial bzw. Kunde in den Stammdaten)
const moeglich = (r) => !!r.wert.trim() && (r.ziel === 'material' ? !!material(r) : r.ziel === 'kundeId' ? !!kunde(r) : true);
const anzahl = computed(() => zeilen.value.filter((r) => r.an && moeglich(r)).length);
// Von Hand geändert? Steht der neue Wert so in der Zeichnung, wird seine Stelle beim Übernehmen mitgelernt.
const korrigiert = (r) => !!r.wert.trim() && r.wert.trim() !== (r.von?.wert ?? '').trim();
const fundstelle = (r) => (korrigiert(r) && !e.value?.gelernt?.[r.feld] ? elementMitWert(e.value?.seite, r.wert.trim()) : null);
function regelnFuer(r) {
  if (e.value.gelernt?.[r.feld]) return e.value.gelernt[r.feld];
  const el = fundstelle(r);
  return el ? regelnAus(lernregel(e.value.seite, el)) : null;
}
const lernAnzahl = computed(() => zeilen.value.filter((r) => r.an && moeglich(r) && (e.value?.gelernt?.[r.feld] || fundstelle(r))).length);

function uebernehmen() {
  const werte = {};
  const lernen = {};
  for (const r of zeilen.value) {
    if (!r.an || !moeglich(r)) continue;
    if (r.ziel === 'material') {
      werte.material = material(r);
      if (r.materialWahl) angebot.schreibweiseMerken(r.materialWahl, r.wert.trim()); // von Hand zugeordnet: fürs nächste Mal merken
    }
    else if (r.ziel === 'kundeId') werte.kundeId = kunde(r).id;
    else werte[r.ziel] = r.wert.trim();
    const regeln = regelnFuer(r);
    if (regeln) lernen[r.feld] = { regeln, wert: r.wert.trim() };
  }
  angebot.erkennungUebernehmen(props.teil, werte, lernen);
}

// ---- Anlernen und Zeigen in der Zeichnung
const lerntGerade = (r) => angebot.anlernen?.teilId === props.teil.id && angebot.anlernen.feld === r.feld;
// Fadenkreuz: die bisher erkannte Stelle in der Zeichnung markieren und nah heranzoomen, dann den richtigen Wert anklicken
function anlernenUmschalten(r) {
  if (lerntGerade(r)) { angebot.anlernen = null; angebot.markierung = null; return; }
  angebot.anlernen = { teilId: props.teil.id, feld: r.feld, label: r.label };
  angebot.markierung = r.von?.lage ? { teilId: props.teil.id, lage: r.von.lage } : null;
  if (r.von?.lage) angebot.fokus = { teilId: props.teil.id, lage: r.von.lage, n: Date.now() };
}
useEventListener(window, 'keydown', (ev) => { if (ev.key === 'Escape' && angebot.anlernen) { angebot.anlernen = null; angebot.markierung = null; } });

const passende = computed(() => (e.value?.passende ?? []).slice(0, 3));
const fremd = (b) => !!angebot.kopf.kundeId && b.kundeId !== angebot.kopf.kundeId;
// Andere Revision auf der Zeichnung als in den Stammdaten (z. B. geänderte Zeichnung)
const andereRevision = (b) => {
  const r = e.value?.felder?.revision?.wert;
  return r && b.revision && r.toLowerCase() !== b.revision.toLowerCase() ? r : '';
};
const punkt = { hoch: 'bg-ok', mittel: 'bg-warn', niedrig: 'bg-mute/50', '': 'bg-line' };
const titel = { hoch: 'sicher erkannt', mittel: 'wahrscheinlich', niedrig: 'nur geraten', '': 'nicht gefunden' };
</script>

<template>
  <div v-if="e">
    <div v-if="e.stand === 'laeuft'" class="flex items-center gap-2 rounded-xl bg-surface2 px-4 py-3 text-sm text-mute"><Loader :size="15" class="animate-spin" /> Zeichnung wird gelesen …</div>
    <div v-else-if="e.stand === 'fehler'" class="flex items-center gap-2 rounded-xl bg-surface2 px-4 py-3 text-sm text-mute">
      <AlertTriangle :size="15" class="text-accent" /> Die Angaben ließen sich nicht lesen ({{ e.fehler }}).
      <button class="ml-auto text-xs hover:text-ink" @click="angebot.erkennungVerwerfen(teil)">Schließen</button>
    </div>

    <div v-else class="rounded-2xl border border-accent/30 bg-accent-soft/40 p-4">
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <ScanText :size="16" class="text-accent" />
        <h4 class="text-sm font-semibold">Aus der Zeichnung erkannt</h4>
        <span class="text-xs text-mute">Prüfen, ändern, fehlende Angaben per <Crosshair :size="11" class="inline" /> in der Zeichnung anklicken.</span>
        <span v-if="e.vorlage" class="inline-flex items-center gap-1 rounded-lg bg-surface px-2 py-0.5 text-[11px] text-mute" :title="`${e.vorlage.anzahl} angelernte Regeln`">
          <GraduationCap :size="12" class="text-accent" /> Vorlage {{ e.vorlage.kundeName }}
          <button class="ml-1 underline-offset-2 hover:text-accent hover:underline" title="Angelernte Regeln dieses Kunden löschen" @click="angebot.vorlageVergessen(teil)">zurücksetzen</button>
        </span>
        <button class="ml-auto grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface hover:text-ink" title="Verwerfen" @click="angebot.erkennungVerwerfen(teil)"><X :size="15" /></button>
      </div>

      <div v-if="e.automatisch" class="mb-3 flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-sm">
        <Database :size="15" class="shrink-0 text-ok" />
        <span>Dieses Bauteil gibt es bei diesem Kunden schon (<strong class="tnum">{{ e.automatisch }}</strong>). Es wird verwendet, die Angaben kommen aus den Stammdaten.</span>
      </div>

      <div v-if="angebot.anlernen?.teilId === teil.id" class="mb-3 flex items-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm text-white">
        <Crosshair :size="15" /> In der Zeichnung auf den richtigen Wert für <strong>{{ angebot.anlernen.label }}</strong> klicken.
        <button class="ml-auto text-xs opacity-80 hover:opacity-100" @click="angebot.anlernen = null">Abbrechen (Esc)</button>
      </div>

      <div class="grid gap-x-3 gap-y-1.5 text-sm sm:grid-cols-[auto_150px_1fr_auto]">
        <template v-for="r in zeilen" :key="r.feld">
          <input v-model="r.an" type="checkbox" class="mt-2.5 h-4 w-4 accent-[var(--accent)]" :disabled="!moeglich(r)" />
          <span class="mt-2 flex items-center gap-1.5 text-xs text-mute"><span class="h-2 w-2 shrink-0 rounded-full" :class="punkt[r.sicherheit]" :title="titel[r.sicherheit] + (r.quelle ? ` (${r.quelle})` : '')" />{{ r.label }}</span>
          <div class="min-w-0">
            <input v-model="r.wert" class="field !py-1.5" :class="!r.an ? 'opacity-60' : ''" :placeholder="r.von ? '' : 'nicht gefunden'" @input="r.an = !!r.wert.trim()" />
            <div v-if="r.ziel === 'material' && r.wert.trim() && (!material(r) || r.waehlen)" class="mt-1 flex flex-wrap items-center gap-1.5">
              <select v-model="r.materialWahl" class="field !w-auto !py-1 text-xs" @change="r.an = !!r.materialWahl; r.waehlen = false">
                <option value="">Rohmaterial wählen …</option>
                <option v-for="m in materialien" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
              <span class="text-[11px] text-mute">oder</span>
              <button class="btn !py-1 text-xs" @click="rohmaterialAnlegen(r)">„{{ rohmaterialName(r.wert) }}“ anlegen</button>
            </div>
            <div class="mt-0.5 truncate text-[11px] text-mute">
              <template v-if="r.ziel === 'material' && r.wert">
                <span v-if="material(r) && !r.waehlen">→ Rohmaterial <strong>{{ material(r).name }}</strong><template v-if="r.materialWahl"> (Schreibweise wird gemerkt)</template> <button class="ml-1 underline-offset-2 hover:text-accent hover:underline" @click="r.waehlen = true">ändern</button></span>
                <span v-else-if="!material(r)">Kein passendes Rohmaterial in den Stammdaten:</span>
              </template>
              <template v-else-if="r.ziel === 'kundeId' && r.wert">
                <span v-if="kunde(r)">→ Kunde <strong>{{ kunde(r).name }}</strong> wählen</span>
                <span v-else>Kein passender Kunde in den Stammdaten</span>
              </template>
              <span v-if="r.bisher && r.bisher !== r.wert && r.ziel !== 'material'"> · bisher: {{ r.bisher }}</span>
              <span v-else-if="r.bisher && r.bisher === r.wert"> · stimmt schon</span>
              <span v-if="e.gelernt?.[r.feld] || fundstelle(r)" class="text-accent"> · wird für den Kunden gemerkt</span>
              <span v-else-if="korrigiert(r)" class="text-warn"> · steht so nicht in der Zeichnung, wird nicht gemerkt</span>
            </div>
          </div>
          <div class="mt-1 flex items-start gap-1">
            <span class="mt-1 hidden w-24 truncate text-right text-[10px] uppercase tracking-wide text-mute sm:block">{{ r.quelle }}</span>
            <button class="grid h-7 w-7 place-items-center rounded-lg" :class="lerntGerade(r) ? 'bg-accent text-white' : 'text-mute hover:bg-surface hover:text-accent'" title="Stelle in der Zeichnung zeigen und ändern (richtigen Wert anklicken)" @click="anlernenUmschalten(r)"><Crosshair :size="15" /></button>
          </div>
        </template>
      </div>
      <p v-if="info.length" class="mt-2 text-xs text-mute"><span v-for="(i, n) in info" :key="i.label">{{ n ? ' · ' : '' }}{{ i.label }}: <strong class="font-medium text-ink">{{ i.wert }}</strong></span></p>

      <!-- Vorhandene Bauteile -->
      <div v-if="passende.length" class="mt-3 space-y-1.5 border-t border-accent/20 pt-3">
        <div class="flex items-center gap-1.5 text-xs font-medium"><Database :size="13" class="text-accent" /> Gibt es schon in den Stammdaten</div>
        <div v-for="b in passende" :key="b.id" class="flex flex-wrap items-center gap-3 rounded-xl bg-surface px-3 py-2">
          <PartImage :teil="b" :groesse="38" />
          <div class="min-w-0 flex-1 text-sm">
            <div class="truncate font-medium">{{ b.name || b.teilenummer }} <span class="text-xs font-normal text-mute tnum">{{ b.id }}</span></div>
            <div class="truncate text-xs text-mute">{{ b.teilenummer }}<template v-if="b.zeichnungsnr"> · {{ b.zeichnungsnr }}</template><template v-if="b.revision"> · Rev. {{ b.revision }}</template> · {{ b.kundeName }} · gleiche {{ b.grund === 'teilenummer' ? 'Teilenummer' : 'Zeichnungsnummer' }}</div>
            <div v-if="andereRevision(b)" class="mt-0.5 flex items-center gap-1 text-xs text-warn"><AlertTriangle :size="12" /> Die Zeichnung hat Revision {{ andereRevision(b) }}, in den Stammdaten steht {{ b.revision }}.</div>
          </div>
          <span v-if="angebot.zuordnung[teil.id]?.bauteilId === b.id" class="inline-flex items-center gap-1 text-xs text-ok"><Check :size="13" /> verknüpft</span>
          <span v-else-if="fremd(b)" class="text-xs text-mute">anderer Kunde</span>
          <button v-else class="btn !py-1.5 text-xs" @click="angebot.bestandUebernehmen(teil, b, materialien)"><Check :size="14" /> Verwenden</button>
        </div>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button class="btn btn-primary !py-1.5" :disabled="!anzahl" :class="!anzahl ? 'pointer-events-none opacity-40' : ''" @click="uebernehmen"><Check :size="15" /> {{ anzahl }} Angabe{{ anzahl === 1 ? '' : 'n' }} übernehmen</button>
        <button class="btn !py-1.5 !text-mute" @click="angebot.erkennungVerwerfen(teil)">Verwerfen</button>
        <span v-if="lernAnzahl" class="text-xs text-mute">Wird für den Kunden gemerkt: {{ lernAnzahl }} Angabe{{ lernAnzahl === 1 ? '' : 'n' }}<template v-if="!angebot.kopf.kundeId && !zeilen.some((r) => r.ziel === 'kundeId' && r.an && moeglich(r))"> (dafür muss ein Kunde gewählt sein)</template></span>
      </div>
    </div>
  </div>
</template>
