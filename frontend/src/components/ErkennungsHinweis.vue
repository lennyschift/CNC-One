<script setup>
// Aus der Zeichnung erkannte Angaben zum Bestätigen: jede Zeile lässt sich ändern und einzeln an- oder abwählen.
// Dazu vorhandene Bauteile mit derselben Teile- oder Zeichnungsnummer als Vorschlag. Übernommen wird erst per Knopf.
import { ref, computed, watch, onMounted } from 'vue';
import { ScanText, Loader, AlertTriangle, Database, Check, X } from '@lucide/vue';
import PartImage from './PartImage.vue';
import { useAngebot } from '../stores/angebot.js';
import { repo } from '../data/repo.js';
import { materialFinden } from '../lib/erkennung.js';

const props = defineProps({ teil: { type: Object, required: true } });
const angebot = useAngebot();
const e = computed(() => angebot.erkennungen[props.teil.id] ?? null);

const materialien = ref([]);
const kunden = ref([]);
onMounted(async () => { [materialien.value, kunden.value] = await Promise.all([repo.materialien.liste(), repo.kunden.liste()]); });

const ohneZeichen = (s) => String(s ?? '').toLowerCase().replace(/[^\p{L}\d]+/gu, '');
// Kunde aus den Stammdaten zum erkannten Namen (enthält oder ist enthalten)
function kundeFinden(name) {
  const n = ohneZeichen(name);
  if (n.length < 3) return null;
  return kunden.value.find((k) => { const m = ohneZeichen(k.name); return m && (m.includes(n) || n.includes(m)); }) ?? null;
}

// Zeilen der Maske: Feld, Ziel im Workbench-Bauteil, erkannter Wert (änderbar), bisheriger Wert, Haken
const zeilen = ref([]);
watch(e, (x) => {
  if (x?.stand !== 'fertig') { zeilen.value = []; return; }
  const f = x.felder;
  const z = [];
  const zeile = (feld, label, ziel, bisher) => {
    if (!f[feld]) return;
    const wert = f[feld].wert;
    z.push({ feld, label, ziel, wert, bisher: bisher ?? '', sicherheit: f[feld].sicherheit, quelle: f[feld].quelle, an: f[feld].sicherheit !== 'niedrig' || !bisher });
  };
  zeile('bezeichnung', 'Bezeichnung', 'name', props.teil.name);
  zeile('teilenummer', 'Teilenummer', 'teilenummer', props.teil.teilenummer);
  zeile('zeichnungsnr', 'Zeichnungsnummer', 'zeichnungsnr', props.teil.zeichnungsnr);
  zeile('revision', 'Revision', 'revision', props.teil.revision);
  zeile('werkstoff', 'Werkstoff', 'material', props.teil.material);
  if (!angebot.kopf.kundeId) zeile('kunde', 'Kunde', 'kundeId', '');
  for (const r of z) if (r.wert === r.bisher) r.an = false;
  zeilen.value = z;
}, { immediate: true });

const info = computed(() => ['toleranz', 'oberflaeche'].map((k) => e.value?.felder?.[k] && { label: k === 'toleranz' ? 'Allgemeintoleranz' : 'Oberfläche', wert: e.value.felder[k].wert }).filter(Boolean));
const material = (r) => materialFinden(r.wert, materialien.value);
const kunde = (r) => kundeFinden(r.wert);
// Eine Zeile lässt sich nur übernehmen, wenn es ein Ziel gibt (Rohmaterial bzw. Kunde in den Stammdaten)
const moeglich = (r) => (r.ziel === 'material' ? !!material(r) : r.ziel === 'kundeId' ? !!kunde(r) : !!r.wert.trim());
const anzahl = computed(() => zeilen.value.filter((r) => r.an && moeglich(r)).length);

function uebernehmen() {
  const werte = {};
  for (const r of zeilen.value) {
    if (!r.an || !moeglich(r)) continue;
    if (r.ziel === 'material') werte.material = material(r);
    else if (r.ziel === 'kundeId') werte.kundeId = kunde(r).id;
    else werte[r.ziel] = r.wert.trim();
  }
  angebot.erkennungUebernehmen(props.teil, werte);
}

const passende = computed(() => (e.value?.passende ?? []).slice(0, 3));
const fremd = (b) => !!angebot.kopf.kundeId && b.kundeId !== angebot.kopf.kundeId;
// Andere Revision auf der Zeichnung als in den Stammdaten (z. B. geänderte Zeichnung)
const andereRevision = (b) => {
  const r = e.value?.felder?.revision?.wert;
  return r && b.revision && r.toLowerCase() !== b.revision.toLowerCase() ? r : '';
};
const punkt = { hoch: 'bg-ok', mittel: 'bg-warn', niedrig: 'bg-mute/50' };
const titel = { hoch: 'sicher erkannt', mittel: 'wahrscheinlich', niedrig: 'nur geraten' };
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
        <span class="text-xs text-mute">Bitte prüfen, ändern und übernehmen.</span>
        <button class="ml-auto grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface hover:text-ink" title="Verwerfen" @click="angebot.erkennungVerwerfen(teil)"><X :size="15" /></button>
      </div>

      <p v-if="!zeilen.length && !passende.length" class="text-sm text-mute">In dieser Zeichnung wurden keine bekannten Angaben gefunden.</p>

      <div v-if="zeilen.length" class="grid gap-x-3 gap-y-1.5 text-sm sm:grid-cols-[auto_150px_1fr_auto]">
        <template v-for="r in zeilen" :key="r.feld">
          <input v-model="r.an" type="checkbox" class="mt-2.5 h-4 w-4 accent-[var(--accent)]" :disabled="!moeglich(r)" />
          <span class="mt-2 flex items-center gap-1.5 text-xs text-mute"><span class="h-2 w-2 shrink-0 rounded-full" :class="punkt[r.sicherheit]" :title="`${titel[r.sicherheit]} (${r.quelle})`" />{{ r.label }}</span>
          <div class="min-w-0">
            <input v-model="r.wert" class="field !py-1.5" :class="!r.an ? 'opacity-60' : ''" />
            <div class="mt-0.5 truncate text-[11px] text-mute">
              <template v-if="r.ziel === 'material'">
                <span v-if="material(r)">→ Rohmaterial <strong>{{ material(r).name }}</strong></span>
                <span v-else>Kein passendes Rohmaterial in den Stammdaten</span>
              </template>
              <template v-else-if="r.ziel === 'kundeId'">
                <span v-if="kunde(r)">→ Kunde <strong>{{ kunde(r).name }}</strong> wählen</span>
                <span v-else>Kein passender Kunde in den Stammdaten</span>
              </template>
              <span v-if="r.bisher && r.bisher !== r.wert"> · bisher: {{ r.bisher }}</span>
              <span v-else-if="r.bisher === r.wert"> · stimmt schon</span>
            </div>
          </div>
          <span class="mt-2 hidden text-[10px] uppercase tracking-wide text-mute sm:block">{{ r.quelle }}</span>
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
      </div>
    </div>
  </div>
</template>
