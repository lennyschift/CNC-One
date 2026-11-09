<script setup>
// Tabelle aus einer Anfrage-Mail vor der Übernahme in die Workbench bestätigen. Spalten zuordnen (Teilenummer, Menge,
// Liefertermin) per Auswahl oder per Klick in die Spalte, Kopfzeile wählen, je Zeile die Zeichnung wählen und Werte
// ändern. Übernommen werden nur Zeilen mit Zeichnung/Modell. Die Spalten werden für den Kontakt (und als Standard des
// Kunden) gemerkt.
import { ref, computed, watch, defineAsyncComponent } from 'vue';
import { useEventListener } from '@vueuse/core';
import { X, Table2, Check, Sparkles, AlertTriangle, MousePointerClick, Heading, Mail } from '@lucide/vue';
import { ROLLEN, tabelleDeuten, rollenMitKopf, zeileWerte, passtZu, vorlageAus } from '../lib/mailtabelle.js';
import { dateiPfad } from '../lib/mailanfrage.js';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ anfrage: { type: Object, required: true } });
const emit = defineEmits(['schliessen', 'uebernehmen']);
const ui = useUi();

// Die Mail links daneben, damit sich die Werte mit dem Original vergleichen lassen (ein- und ausblendbar, gemerkt)
const MailHtml = defineAsyncComponent(() => import('./MailHtml.vue'));
const eingaenge = computed(() => props.anfrage.nachrichten.filter((n) => n.richtung === 'Eingang'));
const mailZeigen = ref((() => { try { return localStorage.getItem('cnc_one_tabelle_mail') !== '0'; } catch { return true; } })());
watch(mailZeigen, (v) => { try { localStorage.setItem('cnc_one_tabelle_mail', v ? '1' : '0'); } catch { /* ohne Speicher */ } });

const FARBE = { teilenummer: 'rolle-teil', menge: 'rolle-menge', liefertermin: 'rolle-termin' };
const QUELLE = { vorlage: 'angelernt', stichwort: 'Überschrift', inhalt: 'Inhalt' };

const dateien = computed(() => props.anfrage.nachrichten.flatMap((n) => n.anhaenge).filter((a) => a.art === 'Zeichnung' || a.art === 'STEP').map(dateiPfad));
let vorlage = props.anfrage.tabellenVorlage ?? { spalten: {}, quelle: '' };
let erkannt = tabelleDeuten(props.anfrage.tabellen, vorlage.spalten, dateien.value);

const tIndex = ref(erkannt?.tabelle ?? 0);
const kopfIndex = ref(erkannt?.kopf ?? 0);
const tabelle = computed(() => props.anfrage.tabellen[tIndex.value]);
const breite = computed(() => Math.max(...tabelle.value.map((z) => z.length)));
const leer = () => Array(breite.value).fill('');
const rollen = ref(erkannt ? [...erkannt.rollen] : leer());
const quellen = ref(erkannt ? [...erkannt.quellen] : leer());
const anfang = JSON.stringify(rollen.value);

const kopfzeile = computed(() => (kopfIndex.value >= 0 ? tabelle.value[kopfIndex.value] : []));
const datenStart = computed(() => kopfIndex.value + 1);

function neuErkennen() {
  const r = rollenMitKopf(tabelle.value, kopfIndex.value, vorlage.spalten, dateien.value);
  rollen.value = r.rollen;
  quellen.value = r.quellen;
}
// Angelernte Spalten vergessen und neu erkennen (z. B. nach einer falschen Zuordnung)
const vorlageDa = ref(!!vorlage.quelle);
async function vorlageVergessen() {
  try {
    vorlage = await call('cnc_one.api.mail.tabellenvorlage_vergessen', { id: props.anfrage.id });
    vorlageDa.value = !!vorlage.quelle;
    erkannt = tabelleDeuten(props.anfrage.tabellen, vorlage.spalten, dateien.value);
    if (erkannt) { tIndex.value = erkannt.tabelle; kopfIndex.value = erkannt.kopf; }
    neuErkennen();
  } catch (e) { ui.toast(e.message, 'warn'); }
}
function tabelleWaehlen(i) {
  tIndex.value = i;
  const d = tabelleDeuten([props.anfrage.tabellen[i]], vorlage.spalten, dateien.value);
  kopfIndex.value = d?.kopf ?? 0;
  neuErkennen();
}
function kopfWaehlen(i) {
  kopfIndex.value = kopfIndex.value === i ? -1 : i;
  neuErkennen();
}
// Jede Rolle nur einmal: bekommt eine Spalte sie, verliert die bisherige sie
function rolleSetzen(sp, rolle) {
  rollen.value = rollen.value.map((r, i) => (i === sp ? rolle : r === rolle && rolle ? '' : r));
  quellen.value = quellen.value.map((q, i) => (i === sp ? (rolle ? 'hand' : '') : rollen.value[i] ? q : ''));
}
// Zuordnen per Klick: Rolle wählen, dann in eine Zelle der Spalte klicken
const waehle = ref('');
useEventListener(window, 'keydown', (ev) => { if (ev.key === 'Escape' && waehle.value) { ev.stopPropagation(); waehle.value = ''; } });
function zelleGeklickt(sp) {
  if (!waehle.value) return;
  rolleSetzen(sp, waehle.value);
  waehle.value = '';
}

// Werte je Datenzeile (aus den Spalten) mit Zeichnung, Änderungen von Hand und Haken
const eingaben = ref([]);
watch([rollen, tIndex, kopfIndex], () => {
  eingaben.value = tabelle.value.map((z, zi) => {
    if (zi < datenStart.value) return null;
    const w = zeileWerte(z, rollen.value);
    const datei = dateien.value.find((n) => passtZu(w.teilenummer, n)) ?? '';
    return { teilenummer: w.teilenummer, menge: w.menge.join('/'), liefertermin: w.liefertermin, datei, an: !!datei };
  });
}, { immediate: true, deep: true });

const hatTeilenummer = computed(() => rollen.value.includes('teilenummer'));
const gewaehlt = computed(() => eingaben.value.filter((e) => e?.an && e.datei));
const geaendert = computed(() => JSON.stringify(rollen.value) !== anfang);
const quelleText = computed(() => {
  if (!erkannt) return 'Keine Spalten erkannt, bitte zuordnen';
  if (geaendert.value) return 'Geänderte Zuordnung';
  if (vorlage.quelle === 'Kontakt' && quellen.value.includes('vorlage')) return `Spalten wie zuletzt bei ${props.anfrage.vonName || props.anfrage.vonEmail}`;
  if (vorlage.quelle === 'Kunde' && quellen.value.includes('vorlage')) return `Spalten wie zuletzt bei ${props.anfrage.kundeName}`;
  return 'Spalten automatisch erkannt';
});
const rollenLabel = (r) => ROLLEN.find((x) => x.id === r)?.label ?? '';

function uebernehmen() {
  const zeilen = gewaehlt.value.map((e) => ({
    teilenummer: e.teilenummer, datei: e.datei, menge: e.menge.split(/[^\d]+/).map(Number).filter((n) => n > 0), liefertermin: e.liefertermin,
  }));
  const spalten = hatTeilenummer.value && kopfIndex.value >= 0 ? vorlageAus(kopfzeile.value, rollen.value) : null;
  emit('uebernehmen', { zeilen, spalten: spalten?.teilenummer ? spalten : null });
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[94vh] flex-col overflow-hidden shadow-2xl" :class="mailZeigen ? 'h-[94vh] w-[98vw] max-w-[1900px]' : 'w-[min(1250px,97vw)]'">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h2 class="flex items-center gap-2 text-base font-semibold"><Table2 :size="17" class="text-accent" /> Tabelle aus der Mail übernehmen</h2>
              <p class="text-xs text-mute">{{ anfrage.betreff }} · {{ anfrage.kundeName }}</p>
            </div>
            <div class="flex items-center gap-2">
              <button class="btn !py-1 !text-xs" :class="mailZeigen ? '!border-accent !bg-accent-soft !text-accent' : ''" :title="mailZeigen ? 'Mail ausblenden' : 'Mail links daneben anzeigen'" @click="mailZeigen = !mailZeigen"><Mail :size="14" /> {{ mailZeigen ? 'Mail ausblenden' : 'Mail anzeigen' }}</button>
              <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
            </div>
          </header>

          <div class="flex min-h-0 flex-1 flex-col lg:flex-row">
          <aside v-if="mailZeigen" class="max-h-[35vh] shrink-0 overflow-auto border-b border-line bg-white px-5 py-4 text-[#1c1c1c] lg:max-h-none lg:w-[42%] lg:border-b-0 lg:border-r">
            <div v-for="(n, i) in eingaenge" :key="i" :class="i ? 'mt-5 border-t border-neutral-200 pt-4' : ''">
              <p class="mb-2 text-[11px] text-neutral-500">{{ n.vonName || n.vonEmail }} · {{ new Date(n.datum).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' }) }}</p>
              <MailHtml v-if="n.html" :html="n.html" />
              <div v-else class="whitespace-pre-wrap break-words text-sm">{{ n.text }}</div>
            </div>
          </aside>
          <div class="min-w-0 flex-1 space-y-3 overflow-auto px-6 py-5">
            <div class="flex flex-wrap items-center gap-2 text-xs">
              <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1" :class="erkannt && !geaendert ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'"><Sparkles :size="13" /> {{ quelleText }}</span>
              <button v-if="vorlageDa" class="text-mute underline hover:text-ink" @click="vorlageVergessen">angelernte Spalten zurücksetzen</button>
              <select v-if="anfrage.tabellen.length > 1" class="field !w-auto !py-1 text-xs" :value="tIndex" @change="tabelleWaehlen(Number($event.target.value))">
                <option v-for="(t, i) in anfrage.tabellen" :key="i" :value="i">Tabelle {{ i + 1 }} ({{ t.length }} Zeilen)</option>
              </select>
              <span class="ml-auto inline-flex items-center gap-1 text-mute"><MousePointerClick :size="13" /> Per Klick zuordnen:</span>
              <button
                v-for="r in ROLLEN" :key="r.id" class="rounded-full border px-2.5 py-1 font-medium transition"
                :class="waehle === r.id ? `${FARBE[r.id]} border-transparent ring-2 ring-accent` : `${FARBE[r.id]} border-transparent opacity-80 hover:opacity-100`"
                @click="waehle = waehle === r.id ? '' : r.id"
              >{{ r.label }}</button>
            </div>
            <p v-if="waehle" class="rounded-lg bg-accent-soft/60 px-3 py-1.5 text-xs text-accent">Jetzt in eine Zelle der Spalte für <strong>{{ rollenLabel(waehle) }}</strong> klicken (Esc oder erneut auf die Schaltfläche zum Abbrechen).</p>

            <div class="overflow-x-auto rounded-xl border border-line">
              <table class="w-full text-sm">
                <thead>
                  <tr class="bg-surface2">
                    <th class="w-16 px-2 py-1.5" />
                    <th v-for="i in breite" :key="i" class="min-w-[110px] px-2 py-1.5 text-left font-normal" :class="FARBE[rollen[i - 1]]">
                      <select class="field !py-1 text-xs" :value="rollen[i - 1] ?? ''" @change="rolleSetzen(i - 1, $event.target.value)">
                        <option value="">–</option>
                        <option v-for="r in ROLLEN" :key="r.id" :value="r.id">{{ r.label }}</option>
                      </select>
                      <div v-if="rollen[i - 1] && quellen[i - 1] && quellen[i - 1] !== 'hand'" class="mt-0.5 text-[10px] text-mute">aus {{ QUELLE[quellen[i - 1]] }}</div>
                    </th>
                    <th class="min-w-[190px] px-2 py-1.5 text-left text-xs font-medium text-mute">Zeichnung / Modell</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(z, zi) in tabelle" :key="zi" class="border-b border-line last:border-0"
                    :class="[zi === kopfIndex ? 'bg-surface2 font-medium' : '', zi < datenStart && zi !== kopfIndex ? 'opacity-40' : '', zi >= datenStart && !eingaben[zi]?.datei ? 'text-mute' : '']"
                  >
                    <td class="whitespace-nowrap px-2 py-1.5">
                      <input v-if="zi >= datenStart" v-model="eingaben[zi].an" type="checkbox" class="mr-1.5 h-4 w-4 align-middle accent-[var(--accent)]" :disabled="!eingaben[zi]?.datei" />
                      <button class="align-middle text-mute hover:text-accent" :class="zi === kopfIndex ? '!text-accent' : ''" :title="zi === kopfIndex ? 'Kopfzeile (Klick: keine Kopfzeile)' : 'Diese Zeile ist die Kopfzeile'" @click="kopfWaehlen(zi)"><Heading :size="14" /></button>
                    </td>
                    <td
                      v-for="i in breite" :key="i" class="px-2 py-1.5 align-top" :class="[FARBE[rollen[i - 1]], waehle ? 'cursor-crosshair hover:outline hover:outline-2 hover:outline-accent' : '']"
                      @click="zelleGeklickt(i - 1)"
                    >
                      <template v-if="zi >= datenStart && rollen[i - 1] === 'menge' && eingaben[zi]?.datei && !waehle">
                        <input v-model="eingaben[zi].menge" class="field !w-24 !py-1 tnum" placeholder="Menge" @click.stop />
                        <div v-if="z[i - 1] && z[i - 1] !== eingaben[zi].menge" class="mt-0.5 text-[10px] text-mute">Mail: {{ z[i - 1] }}</div>
                      </template>
                      <template v-else-if="zi >= datenStart && rollen[i - 1] === 'liefertermin' && eingaben[zi]?.datei && !waehle">
                        <input v-model="eingaben[zi].liefertermin" type="date" class="field !w-36 !py-1" @click.stop />
                        <div v-if="z[i - 1]" class="mt-0.5 text-[10px]" :class="eingaben[zi].liefertermin ? 'text-mute' : 'text-warn'">Mail: {{ z[i - 1] }}<template v-if="!eingaben[zi].liefertermin"> (kein Datum)</template></div>
                      </template>
                      <span v-else>{{ z[i - 1] }}</span>
                    </td>
                    <td class="px-2 py-1.5 align-top">
                      <select v-if="zi >= datenStart" v-model="eingaben[zi].datei" class="field !py-1 text-xs" @change="eingaben[zi].an = !!eingaben[zi].datei">
                        <option value="">– keine –</option>
                        <option v-for="n in dateien" :key="n" :value="n">{{ n }}</option>
                      </select>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="text-xs text-mute">Die Zeichnung je Zeile ist vorgeschlagen, wenn die Teilenummer zum Dateinamen passt; sonst hier wählen. Zeilen ohne Zeichnung werden nicht übernommen.</p>
            <p v-if="!hatTeilenummer" class="flex items-center gap-1.5 text-xs text-warn"><AlertTriangle :size="13" /> Bitte die Spalte mit der Teilenummer zuordnen.</p>
          </div>
          </div>

          <footer class="flex flex-wrap items-center justify-end gap-2 border-t border-line px-6 py-4">
            <button class="btn mr-auto !text-mute" @click="emit('uebernehmen', { zeilen: [], spalten: null })">Ohne Tabelle übernehmen</button>
            <span v-if="kopfIndex >= 0 && hatTeilenummer" class="text-xs text-mute">Spalten werden für {{ anfrage.vonEmail }} gemerkt</span>
            <button class="btn" @click="emit('schliessen')">Abbrechen</button>
            <button class="btn btn-primary" @click="uebernehmen">
              <Check :size="15" /> Übernehmen<template v-if="gewaehlt.length"> · Werte für {{ gewaehlt.length }} Bauteil{{ gewaehlt.length === 1 ? '' : 'e' }}</template>
            </button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<style scoped>
.rolle-teil { background: color-mix(in srgb, #2563eb 9%, transparent); }
.rolle-menge { background: color-mix(in srgb, #16a34a 10%, transparent); }
.rolle-termin { background: color-mix(in srgb, #d97706 11%, transparent); }
</style>
