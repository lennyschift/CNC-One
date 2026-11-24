<script setup>
// Angebot eines Lieferanten aus dem PDF einlesen (lib/lieferangebot.js): links das PDF, rechts was erkannt wurde.
// Jede Angebotsposition wird einer Position unserer Anfrage zugeordnet (Vorschlag nach Werkstoff und Maßen), daraus
// entsteht der Preis je angefragter Einheit. Nebenkosten (Verpackung, Fracht) kommen einmal je Angebot dazu.
// Je Lieferant lassen sich die Spalten und die Preiseinheit anlernen; sie gelten dann für seine nächsten Angebote.
import { ref, computed, watch } from 'vue';
import { X, FileUp, FileText, AlertTriangle, CheckCircle2, CircleHelp, Columns3, Save, RefreshCw, Loader, Check, Trash2, Plus } from '@lucide/vue';
import NumField from './NumField.vue';
import { hochladen } from '../data/api.js';
import { pdfjs } from '../lib/pdf.js';
import { textAusSeite } from '../lib/zeichnungText.js';
import { angebotLesen, zuordnen, preiseFuer, abgleich, spaltenVorlage, ROLLEN, PREIS_JE } from '../lib/lieferangebot.js';
import { eur, zahl } from '../lib/format.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ anfrage: { type: Object, required: true }, datei: { type: Object, default: null } });
const emit = defineEmits(['schliessen', 'erfasst']);
const store = useAnfragen();
const ui = useUi();

// PDFs aus den Mails des Lieferanten (neueste zuerst)
const pdfs = computed(() => [...props.anfrage.nachrichten].reverse().filter((n) => n.richtung === 'Eingang')
  .flatMap((n) => n.anhaenge.filter((a) => /\.pdf$/i.test(a.name) && a.url).map((a) => ({ name: a.name, url: a.url, datum: n.datum }))));

const quelle = ref(null); // { name, url } oder { name, file }
const ansicht = ref(''); // URL für die Vorschau
const seiten = ref(null);
const vorlage = ref({});
const r = ref(null);
const zuordnung = ref([]);
const neben = ref([]); // [{ text, betrag, an }]
const kopf = ref({ angebotsnr: '', gueltigBis: '', lieferzeit: '' });
const liest = ref(false);
const fehler = ref('');
const anlernen = ref(false);
const speichert = ref(false);

async function lesen(q) {
  quelle.value = q;
  fehler.value = '';
  liest.value = true;
  try {
    const daten = q.file ? await q.file.arrayBuffer() : await (await fetch(q.url, { credentials: 'same-origin' })).arrayBuffer();
    ansicht.value = q.url || URL.createObjectURL(q.file);
    const aufgabe = pdfjs.getDocument({ data: new Uint8Array(daten) });
    const doc = await aufgabe.promise;
    const s = [];
    for (let i = 1; i <= Math.min(doc.numPages, 10); i++) s.push(await textAusSeite(await doc.getPage(i)));
    aufgabe.destroy();
    seiten.value = s;
    vorlage.value = (await store.angebotsvorlage(props.anfrage.lieferantId)) ?? {};
    auswerten();
  } catch (e) {
    fehler.value = `Das PDF ließ sich nicht lesen${e?.message ? `: ${e.message}` : '.'}`;
  } finally {
    liest.value = false;
  }
}

function auswerten() {
  r.value = angebotLesen(seiten.value, vorlage.value);
  zuordnung.value = zuordnen(r.value.positionen, props.anfrage);
  neben.value = r.value.nebenkosten.map((n) => ({ ...n, an: true }));
  const lt = r.value.positionen.map((p) => p.liefertermin).find(Boolean) ?? '';
  kopf.value = { angebotsnr: r.value.kopf.angebotsnr || '', gueltigBis: r.value.kopf.gueltigBis || '', lieferzeit: lt.slice(0, 140) };
}

if (props.datei) lesen(props.datei);
else if (pdfs.value.length === 1) lesen(pdfs.value[0]);

function abgelegt(e) {
  const f = [...(e.dataTransfer?.files ?? [])].find((x) => /\.pdf$/i.test(x.name) || x.type === 'application/pdf');
  if (f && !liest.value) lesen({ name: f.name, file: f });
}
function dateiGewaehlt(e) {
  const f = e.target.files?.[0];
  if (f) lesen({ name: f.name, file: f });
}

// ------------------------------------------------------------------ Ergebnis
const unsere = computed(() => props.anfrage.positionen.map((p, i) => ({ ...p, nr: i + 1 })));
const position = (key) => unsere.value.find((p) => p.key === key) ?? null;
const ergebnis = computed(() => (r.value ? preiseFuer(props.anfrage, r.value.positionen, zuordnung.value) : { preise: [], je: {} }));
const nebenSumme = computed(() => Math.round(neben.value.filter((n) => n.an).reduce((s, n) => s + (Number(n.betrag) || 0), 0) * 100) / 100);
const ohne = computed(() => unsere.value.filter((p) => !ergebnis.value.je[p.key]));
const pruefung = (o, key) => (key && position(key) ? abgleich(o, position(key)) : []);
const einheitText = (e) => ({ kg: 'kg', Stk: 'Stk', m: 'm' })[e] ?? e;
const mengen = (o) => [o.stueck != null && `${zahl(o.stueck, 0)} Stk`, o.kg != null && `${zahl(o.kg, 2)} kg`, o.meter != null && `${zahl(o.meter, 3)} m`].filter(Boolean).join(' · ');
const unserText = (p) => `${p.nr}. ${p.teil.name}${p.abmessung ? ` · ${p.abmessung.split(' · ')[0]}` : ''}`;

// Spalten anlernen: Rolle je Überschrift, Preiseinheit
const spalten = ref([]);
watch(r, (x) => { spalten.value = (x?.spalten ?? []).map((s) => ({ ...s })); });
const preisJe = ref('');
watch(vorlage, (v) => { preisJe.value = v?.preisJe ?? ''; }, { immediate: true });
function neuLesen() {
  vorlage.value = { spalten: spaltenVorlage(spalten.value), preisJe: preisJe.value };
  auswerten();
}
async function merken() {
  neuLesen();
  await store.angebotsvorlageLernen(props.anfrage.lieferantId, vorlage.value);
}
async function vergessen() {
  vorlage.value = {};
  preisJe.value = '';
  await store.angebotsvorlageLernen(props.anfrage.lieferantId, {});
  auswerten();
}

function nebenDazu() { neben.value.push({ text: '', betrag: 0, an: true }); }

async function uebernehmen() {
  if (!ergebnis.value.preise.length) { ui.toast('Bitte mindestens eine Angebotsposition einer Position der Anfrage zuordnen', 'warn'); return; }
  speichert.value = true;
  try {
    let pdf = quelle.value?.url ?? '';
    if (!pdf && quelle.value?.file) pdf = (await hochladen(quelle.value.file, { doctype: 'Lieferantenanfrage', docname: props.anfrage.id }))?.file_url ?? '';
    const n = neben.value.filter((x) => x.an && Number(x.betrag));
    const rec = await store.antwortErfassen(props.anfrage.id, {
      ...kopf.value,
      preise: ergebnis.value.preise,
      nebenkosten: nebenSumme.value,
      nebenkostenText: n.map((x) => `${x.text || 'Nebenkosten'}: ${eur(x.betrag)}`).join('\n'),
      pdf,
      daten: {
        datei: quelle.value?.name ?? '', kopf: r.value.kopf, netto: r.value.netto, stimmt: r.value.stimmt,
        positionen: r.value.positionen.map((o, i) => ({ ...o, zuordnung: zuordnung.value[i] || '' })),
        nebenkosten: n, je: ergebnis.value.je,
      },
    });
    if (rec) emit('erfasst', rec);
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    speichert.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <!-- abgelegtes PDF hier einlesen, nicht in der Workbench (globales Ablegen im Fenster) -->
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-3 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')" @dragover.prevent @drop.prevent.stop="abgelegt">
      <Transition name="pop" appear>
        <div class="card flex h-[95vh] w-[min(1500px,98vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
            <div class="min-w-0">
              <h2 class="text-base font-semibold">Angebot von {{ anfrage.lieferantName }} einlesen</h2>
              <p class="truncate text-xs text-mute">zu unserer Anfrage {{ anfrage.id }} · {{ anfrage.positionen.length }} Position{{ anfrage.positionen.length === 1 ? '' : 'en' }}<template v-if="quelle"> · {{ quelle.name }}</template></p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <!-- PDF wählen -->
          <div v-if="!r && !liest" class="grid flex-1 place-items-center overflow-auto p-8">
            <div class="w-full max-w-xl space-y-3">
              <p v-if="fehler" class="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-sm"><AlertTriangle :size="16" class="mt-0.5 shrink-0 text-warn" /> {{ fehler }}</p>
              <p class="text-sm text-mute">{{ pdfs.length ? 'PDF aus den Mails des Lieferanten wählen oder eine Datei hochladen:' : 'In den Mails zu dieser Anfrage liegt kein PDF. Datei wählen:' }}</p>
              <button v-for="p in pdfs" :key="p.url" class="flex w-full items-center gap-3 rounded-xl border border-line px-4 py-3 text-left hover:border-accent/50 hover:bg-surface2" @click="lesen(p)">
                <FileText :size="18" class="shrink-0 text-accent" /><span class="min-w-0 flex-1 truncate text-sm font-medium">{{ p.name }}</span>
                <span class="text-xs text-mute">{{ p.datum ? new Date(p.datum).toLocaleDateString('de-DE') : '' }}</span>
              </button>
              <label class="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line px-4 py-5 text-sm text-mute hover:border-accent/50 hover:text-ink">
                <FileUp :size="17" /> PDF-Datei wählen <input type="file" accept="application/pdf,.pdf" class="hidden" @change="dateiGewaehlt" />
              </label>
            </div>
          </div>
          <div v-else-if="liest" class="grid flex-1 place-items-center text-sm text-mute"><span class="inline-flex items-center gap-2"><Loader :size="16" class="animate-spin" /> PDF wird gelesen …</span></div>

          <!-- Ergebnis: PDF links, Erkanntes rechts -->
          <div v-else class="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <iframe :src="ansicht" class="hidden h-full w-full border-r border-line bg-surface2 lg:block" title="Angebot als PDF" />
            <div class="min-h-0 space-y-4 overflow-auto p-5">
              <section class="grid gap-3 sm:grid-cols-3">
                <label class="block"><span class="label mb-1 block">Angebotsnummer</span><input v-model="kopf.angebotsnr" class="field" /></label>
                <label class="block"><span class="label mb-1 block">Gültig bis</span><input v-model="kopf.gueltigBis" type="date" class="field" /></label>
                <label class="block"><span class="label mb-1 block">Lieferzeit</span><input v-model="kopf.lieferzeit" class="field" placeholder="z. B. 2 Arbeitstage" /></label>
              </section>

              <p v-if="!r.positionen.length" class="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-sm"><AlertTriangle :size="16" class="mt-0.5 shrink-0 text-warn" />
                Keine Positionstabelle erkannt. Unter „Spalten anlernen“ die Überschriften zuordnen oder die Preise bei der Anfrage von Hand eintragen.</p>

              <!-- Angebotspositionen -->
              <section v-for="(o, i) in r.positionen" :key="i" class="rounded-xl border p-3" :class="zuordnung[i] ? 'border-line' : 'border-dashed border-line opacity-80'">
                <div class="flex flex-wrap items-start gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2 text-sm font-medium">
                      <span v-if="o.pos" class="rounded-md bg-surface2 px-1.5 text-xs tnum text-mute">Pos {{ o.pos }}</span>
                      <span v-if="o.option" class="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">Option</span>
                      <span>{{ [o.werkstoff, o.zustand].filter(Boolean).join(' ') || 'Werkstoff?' }}</span>
                      <span class="text-mute">{{ [o.form, o.abmessung || o.masse.join(' × ')].filter(Boolean).join(' · ') }}</span>
                    </div>
                    <div class="mt-0.5 line-clamp-2 whitespace-pre-line text-xs text-mute" :title="o.text">{{ o.text }}</div>
                    <div class="mt-1 text-xs tnum">{{ mengen(o) || 'Menge?' }}<template v-if="o.liefertermin"> · <span class="text-mute">Liefertermin {{ o.liefertermin }}</span></template></div>
                  </div>
                  <div class="text-right tnum">
                    <div class="text-sm font-semibold">{{ o.betrag != null ? eur(o.betrag) : '–' }}</div>
                    <div class="text-xs text-mute">{{ o.preis != null ? `${eur(o.preis)} / ${einheitText(o.preisJe)}` : '' }}</div>
                  </div>
                </div>
                <div class="mt-2 flex flex-wrap items-center gap-2">
                  <span class="text-xs text-mute">gehört zu</span>
                  <select v-model="zuordnung[i]" class="field !w-auto !py-1 !text-xs">
                    <option value="">– nicht übernehmen –</option>
                    <option v-for="p in unsere" :key="p.key" :value="p.key">{{ unserText(p) }}</option>
                  </select>
                  <template v-for="c in pruefung(o, zuordnung[i])" :key="c.feld">
                    <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]" :class="c.ok === true ? 'bg-ok/10 text-ok' : c.ok === false ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'" :title="`angefragt: ${c.angefragt} · angeboten: ${c.angeboten}`">
                      <CheckCircle2 v-if="c.ok === true" :size="12" /><AlertTriangle v-else-if="c.ok === false" :size="12" /><CircleHelp v-else :size="12" />
                      {{ c.feld }}<template v-if="c.ok === false">: {{ c.angeboten }} statt {{ c.angefragt }}</template><template v-else-if="c.feld === 'Anforderungen'">: {{ c.angeboten }}</template>
                    </span>
                  </template>
                </div>
              </section>

              <!-- Nebenkosten -->
              <section class="rounded-xl border border-line p-3">
                <div class="mb-2 flex items-center justify-between"><h3 class="text-sm font-semibold">Nebenkosten</h3><button class="btn !py-1 !text-xs" @click="nebenDazu"><Plus :size="13" /> Zeile</button></div>
                <p v-if="!neben.length" class="text-xs text-mute">Keine erkannt (Verpackung, Fracht, Zuschläge).</p>
                <div v-for="(n, i) in neben" :key="i" class="mb-1.5 grid grid-cols-[auto_1fr_140px_auto] items-center gap-2">
                  <input v-model="n.an" type="checkbox" class="h-4 w-4 accent-[var(--accent)]" :title="n.an ? 'zählt mit' : 'zählt nicht'" />
                  <input v-model="n.text" class="field !py-1 text-sm" placeholder="z. B. Fracht" />
                  <NumField v-model="n.betrag" unit="€" />
                  <button class="grid h-7 w-7 place-items-center rounded-md text-mute hover:bg-surface2" @click="neben.splice(i, 1)"><Trash2 :size="13" /></button>
                </div>
                <p v-if="neben.some((n) => n.zusaetzlich)" class="text-xs text-mute">Aus dem Text unter der Tabelle erkannt (z. B. „zzgl. Transportkostenanteil“): bitte prüfen.</p>
              </section>

              <!-- Ergebnis für unsere Anfrage -->
              <section class="rounded-xl bg-surface2 p-3 text-sm">
                <h3 class="mb-2 font-semibold">Für unsere Anfrage</h3>
                <div v-for="p in unsere" :key="p.key" class="flex flex-wrap items-baseline justify-between gap-2 py-0.5">
                  <span class="min-w-0 truncate">{{ unserText(p) }} <span class="text-xs text-mute">· angefragt {{ p.mengen.join(' / ') }} {{ p.einheit }}</span></span>
                  <span v-if="ergebnis.je[p.key]" class="tnum">
                    <strong>{{ eur(ergebnis.je[p.key].einzel) }}</strong> je {{ p.einheit === 'Stk' || !p.einheit ? 'Stück' : p.einheit }}
                    <span class="text-xs text-mute">({{ eur(ergebnis.je[p.key].betrag) }}<template v-if="ergebnis.je[p.key].angeboten != null"> für {{ zahl(ergebnis.je[p.key].angeboten, 2) }} {{ p.einheit }}</template>)</span>
                    <span v-if="ergebnis.je[p.key].abweichung" class="ml-1 rounded-full bg-warn/15 px-2 py-0.5 text-[11px] text-warn">andere Menge angeboten</span>
                    <span v-if="ergebnis.je[p.key].geschaetzt" class="ml-1 rounded-full bg-warn/15 px-2 py-0.5 text-[11px] text-warn">Menge in {{ p.einheit }} nicht im Angebot</span>
                  </span>
                  <span v-else class="text-xs text-mute">nicht angeboten</span>
                </div>
                <div class="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2 tnum">
                  <span>Nebenkosten {{ eur(nebenSumme) }}</span>
                  <span v-if="r.netto != null" class="inline-flex items-center gap-1 text-xs" :class="r.stimmt ? 'text-ok' : 'text-warn'">
                    <CheckCircle2 v-if="r.stimmt" :size="13" /><AlertTriangle v-else :size="13" />
                    Positionen {{ eur(r.summePositionen) }} + Nebenkosten {{ eur(r.summeNebenkosten) }} {{ r.stimmt ? '=' : '≠' }} Netto laut PDF {{ eur(r.netto) }}
                  </span>
                </div>
                <p v-if="ohne.length && Object.keys(ergebnis.je).length" class="mt-1 text-xs text-warn">Ohne Preis: {{ ohne.map((p) => p.nr).join(', ') }}</p>
              </section>

              <!-- Anlernen je Lieferant -->
              <section class="rounded-xl border border-line">
                <button class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm" @click="anlernen = !anlernen">
                  <Columns3 :size="15" class="text-accent" /> Spalten und Preiseinheit für {{ anfrage.lieferantName }} anlernen
                  <span v-if="vorlage.preisJe || Object.keys(vorlage.spalten ?? {}).length" class="ml-auto rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent">Vorlage aktiv</span>
                </button>
                <div v-if="anlernen" class="space-y-3 border-t border-line p-3">
                  <p class="text-xs text-mute">Erkannt wurde die Kopfzeile der Tabelle. Stimmt eine Spalte nicht, hier die Rolle ändern; „Neu lesen“ zeigt das Ergebnis, „Merken“ gilt für alle weiteren Angebote dieses Lieferanten.</p>
                  <div class="grid gap-2 sm:grid-cols-2">
                    <label v-for="(s, i) in spalten" :key="i" class="flex items-center gap-2 text-sm">
                      <span class="min-w-0 flex-1 truncate rounded-md bg-surface2 px-2 py-1 text-xs">{{ s.text }}</span>
                      <select v-model="s.rolle" class="field !w-40 !py-1 !text-xs"><option value="">– nicht benutzen –</option><option v-for="x in ROLLEN" :key="x.id" :value="x.id">{{ x.label }}</option></select>
                    </label>
                  </div>
                  <label class="flex items-center gap-2 text-sm"><span class="text-xs text-mute">Preis gilt</span>
                    <select v-model="preisJe" class="field !w-40 !py-1 !text-xs"><option v-for="x in PREIS_JE" :key="x.id" :value="x.id">{{ x.label }}</option></select>
                  </label>
                  <div class="flex flex-wrap gap-2">
                    <button class="btn !py-1 !text-xs" @click="neuLesen"><RefreshCw :size="13" /> Neu lesen</button>
                    <button class="btn !py-1 !text-xs" @click="merken"><Save :size="13" /> Für {{ anfrage.lieferantName }} merken</button>
                    <button v-if="vorlage.preisJe || Object.keys(vorlage.spalten ?? {}).length" class="btn !py-1 !text-xs !text-mute" @click="vergessen">Vorlage vergessen</button>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <footer v-if="r" class="flex flex-wrap items-center justify-end gap-2 border-t border-line px-6 py-3">
            <button class="btn mr-auto !text-mute" @click="r = null; quelle = null">Anderes PDF</button>
            <button class="btn" @click="emit('schliessen')">Abbrechen</button>
            <button class="btn btn-primary" :disabled="speichert || !ergebnis.preise.length" @click="uebernehmen"><Check :size="15" /> {{ speichert ? 'Wird übernommen …' : 'Angebot übernehmen' }}</button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
