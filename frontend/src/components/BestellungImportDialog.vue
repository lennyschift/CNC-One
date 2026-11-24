<script setup>
// Workbench: Bestellung des Kunden mit allen Zeichnungen und STEP-Modellen auf einmal einlesen. Die PDF mit der
// Positionstabelle ist die Bestellung (lib/bestellung.js), die übrigen Dateien gehören über Artikel- oder
// Zeichnungsnummer im Dateinamen zu ihrer Position (lib/bestellimport.js, von Hand änderbar). Der Server sucht je
// Position das Bauteil und frühere Angebote/Aufträge (api/bestellung.vorschlag). Wiederholteile übernehmen Kalkulation,
// Rohmaterial und Arbeitsgänge aus dem gewählten Angebot; Teile, die schon vor CNC One gefertigt wurden, bekommen hier
// ihren Haken. Danach entsteht ein Workbench-Entwurf mit dem Preis der Bestellung, aus dem direkt der Auftrag wird.
import { ref, computed } from 'vue';
import { X, FileUp, Loader, AlertTriangle, FileText, Box, CheckCircle2, History, Sparkles, PackageCheck, ShoppingCart, Trash2 } from '@lucide/vue';
import PartImage from './PartImage.vue';
import CustomerCombobox from './CustomerCombobox.vue';
import { call } from '../data/api.js';
import { pdfjs } from '../lib/pdf.js';
import { textAusSeite } from '../lib/zeichnungText.js';
import { bestellungLesen } from '../lib/bestellung.js';
import { bestellungFinden, dateienZuordnen, bekanntheit } from '../lib/bestellimport.js';
import { dateiArt } from '../stores/angebot.js';
import { eur } from '../lib/format.js';
import { useAngebot } from '../stores/angebot.js';
import { useUi } from '../stores/ui.js';

const emit = defineEmits(['schliessen']);
const angebot = useAngebot();
const ui = useUi();

const dateien = ref([]); // [{ file, art, pos }] ohne die Bestellung; pos = Index der Position oder -1
const bestellPdf = ref(null);
const seiten = ref(null);
const kopf = ref({ bestellnr: '', datum: '', liefertermin: '' });
const kunde = ref('');
const pos = ref([]);
const liest = ref(false);
const fehler = ref('');
const uebernimmt = ref(false);

async function seitenAus(file) {
  const aufgabe = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
  const doc = await aufgabe.promise;
  const s = [];
  for (let i = 1; i <= Math.min(doc.numPages, 10); i++) s.push(await textAusSeite(await doc.getPage(i)));
  aufgabe.destroy();
  return s;
}

async function dazu(files) {
  const neu = [...files].filter((f) => f.size > 0);
  if (!neu.length) return;
  liest.value = true;
  fehler.value = '';
  try {
    // ohne Bestellung: unter den neuen PDFs die mit der Positionstabelle suchen
    if (!bestellPdf.value) {
      const pdfs = neu.filter((f) => dateiArt(f.name) === 'Zeichnung');
      const lesungen = [];
      for (const f of pdfs) {
        try { const s = await seitenAus(f); lesungen.push({ name: f.name, f, s, r: bestellungLesen(s) }); } catch { lesungen.push({ name: f.name, f, r: null }); }
      }
      const i = bestellungFinden(lesungen);
      if (i >= 0) {
        bestellPdf.value = lesungen[i].f;
        seiten.value = lesungen[i].s;
        await lesen();
      }
    }
    for (const f of neu) if (f !== bestellPdf.value && !dateien.value.some((d) => d.file.name === f.name && d.file.size === f.size)) dateien.value.push({ file: f, art: dateiArt(f.name), pos: -1 });
    zuordnen();
    if (!bestellPdf.value) fehler.value = 'Unter den Dateien ist keine Bestellung mit Positionstabelle. Bitte das Bestell-PDF dazulegen.';
  } finally {
    liest.value = false;
  }
}
function gewaehlt(e) { dazu(e.target.files ?? []); e.target.value = ''; }
function abgelegt(e) { dazu(e.dataTransfer?.files ?? []); }

// Bestellung lesen: Kunde aus dem Text, seine angelernten Spalten, dann Abgleich mit Bauteilen und Belegen
async function lesen() {
  const text = seiten.value.flatMap((s) => s.elemente.map((e) => e.text)).join(' ');
  const e = await call('cnc_one.api.bestellung.erkennen', { text, kunde: kunde.value });
  if (!kunde.value) kunde.value = e.kunde || '';
  const r = bestellungLesen(seiten.value, e.vorlage ?? {});
  kopf.value = r.kopf;
  pos.value = r.positionen.map((p) => ({ ...p, aktiv: true, bauteil: null, quellen: [], quelle: -1, letzterAuftrag: null, frueher: null }));
  await abgleichen();
}

async function abgleichen() {
  if (!kunde.value || !pos.value.length) return;
  const anfrage = pos.value.map((p) => ({ bestellposition: p.bestellposition, teilenummer: p.teilenummer, text: `${p.bezeichnung}\n${p.text}`, menge: p.menge, preis: p.preis, termin: p.termin }));
  const r = await call('cnc_one.api.bestellung.vorschlag', { kunde: kunde.value, positionen: anfrage, kundenbestellnr: kopf.value.bestellnr });
  r.positionen.forEach((s, i) => {
    const p = pos.value[i];
    if (!p) return;
    p.bauteil = s.bauteil;
    p.quellen = s.quellen ?? [];
    p.quelle = s.quelle ?? -1;
    p.letzterAuftrag = s.letzterAuftrag;
    p.frueher = s.bauteil ? { gefertigt: !!s.bauteil.frueherGefertigt, notiz: s.bauteil.frueherNotiz ?? '' } : { gefertigt: false, notiz: '' };
  });
  vorhanden.value = r.vorhanden ?? [];
  zuordnen();
}
const vorhanden = ref([]);
async function kundeGeaendert(k) { kunde.value = k; if (seiten.value) await lesen(); }

function zuordnen() {
  const ziel = dateienZuordnen(pos.value, dateien.value.map((d) => d.file.name));
  dateien.value.forEach((d, i) => { if (d.pos < 0 || d.pos >= pos.value.length) d.pos = ziel[i]; });
}
const dateienVon = (i) => dateien.value.filter((d) => d.pos === i);
const ohnePosition = computed(() => dateien.value.filter((d) => d.pos < 0));
const posText = (p) => `${p.bestellposition ? `Pos. ${p.bestellposition} · ` : ''}${p.teilenummer || p.bezeichnung}`;

const aktive = computed(() => pos.value.filter((p) => p.aktiv));
const summe = computed(() => aktive.value.reduce((s, p) => s + (Number(p.preis) || 0) * (Number(p.menge) || 0), 0));
const fertig = computed(() => !!kunde.value && aktive.value.length > 0 && !liest.value);
const FARBE = { auftrag: 'bg-ok/15 text-ok', angebot: 'bg-accent-soft text-accent', frueher: 'bg-ok/15 text-ok', bauteil: 'bg-surface2 text-mute', neu: 'bg-warn/15 text-warn' };

async function uebernehmen() {
  if (!fertig.value || uebernimmt.value) return;
  uebernimmt.value = true;
  try {
    const positionen = pos.value.map((p, i) => ({ p, i })).filter(({ p }) => p.aktiv).map(({ p, i }) => ({
      bestellposition: p.bestellposition, teilenummer: p.teilenummer, bezeichnung: p.bezeichnung, menge: p.menge, preis: p.preis,
      termin: p.termin, zeichnungsnr: p.zeichnungsnr, index: p.index, bauteil: p.bauteil,
      quelle: p.quelle >= 0 ? p.quellen[p.quelle] : null,
      // den Haken nur mitgeben, wenn er hier gesetzt oder geändert wurde
      frueher: p.frueher && (p.frueher.gefertigt !== !!p.bauteil?.frueherGefertigt || (p.frueher.notiz ?? '') !== (p.bauteil?.frueherNotiz ?? '')) ? p.frueher : null,
      dateien: dateienVon(i).map((d) => d.file),
    }));
    await angebot.ausBestellung({ kundeId: kunde.value, bestellung: { nr: kopf.value.bestellnr, datum: kopf.value.datum }, positionen, bestellPdf: bestellPdf.value });
    emit('schliessen');
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    uebernimmt.value = false;
  }
}
const de = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('de-DE') : '–');
</script>

<template>
  <Teleport to="body">
    <!-- Ablegen selbst behandeln: sonst landen die Dateien zusätzlich in der Workbench (globales Ablegen im Fenster) -->
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-3 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')" @dragover.prevent @drop.prevent.stop="abgelegt">
      <Transition name="pop" appear>
        <div class="card flex max-h-[95vh] w-[min(1250px,98vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
            <div>
              <h2 class="flex items-center gap-2 text-base font-semibold"><ShoppingCart :size="18" class="text-accent" /> Bestellung einlesen</h2>
              <p class="text-xs text-mute">Bestell-PDF und alle Zeichnungen und STEP-Modelle hierher ziehen. Wiederholteile bringen ihre Kalkulation mit, der Preis kommt aus der Bestellung; danach in der Workbench Rohmaterial usw. ergänzen und den Auftrag anlegen.</p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="min-h-0 flex-1 space-y-4 overflow-auto p-5">
            <label class="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line px-4 py-5 text-sm text-mute hover:border-accent/50 hover:text-ink">
              <Loader v-if="liest" :size="17" class="animate-spin" /><FileUp v-else :size="17" />
              {{ liest ? 'Wird gelesen …' : bestellPdf ? 'Weitere Zeichnungen oder Modelle hinzufügen' : 'Bestell-PDF mit Zeichnungen und STEP-Dateien wählen oder hierher ziehen (alles auf einmal)' }}
              <input type="file" multiple accept=".pdf,.step,.stp,application/pdf" class="hidden" @change="gewaehlt" />
            </label>
            <p v-if="fehler" class="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-sm"><AlertTriangle :size="16" class="mt-0.5 shrink-0 text-warn" /> {{ fehler }}</p>

            <template v-if="bestellPdf">
              <div class="grid gap-3 md:grid-cols-[minmax(240px,1.3fr)_1fr_1fr_1fr]">
                <CustomerCombobox :model-value="kunde" @update:model-value="kundeGeaendert" />
                <label class="block"><span class="label mb-1 block">Bestellnummer</span><input v-model="kopf.bestellnr" class="field" /></label>
                <label class="block"><span class="label mb-1 block">Bestelldatum</span><input v-model="kopf.datum" type="date" class="field" /></label>
                <div class="text-xs text-mute"><span class="label mb-1 block">Bestellung</span><span class="inline-flex items-center gap-1"><FileText :size="13" class="text-accent" /> {{ bestellPdf.name }}</span><div v-if="kopf.liefertermin">Liefertermin {{ de(kopf.liefertermin) }}</div></div>
              </div>
              <p v-if="vorhanden.length" class="flex items-center gap-2 rounded-xl bg-warn/10 px-3 py-2 text-xs"><AlertTriangle :size="14" class="shrink-0 text-warn" /> Zu dieser Bestellnummer gibt es schon den Auftrag {{ vorhanden.join(', ') }}.</p>
              <p v-if="!kunde" class="text-sm text-warn">Bitte den Kunden wählen: erst dann werden Bauteile und frühere Aufträge gesucht.</p>

              <div class="divide-y divide-line rounded-xl border border-line">
                <div v-for="(p, i) in pos" :key="i" class="flex flex-wrap items-start gap-3 px-3 py-3" :class="p.aktiv ? '' : 'opacity-50'">
                  <input v-model="p.aktiv" type="checkbox" class="mt-3 h-4 w-4 accent-[var(--accent)]" title="Position übernehmen" />
                  <PartImage :teil="{ name: p.bezeichnung, vorschaubild: p.bauteil?.vorschaubild ?? '', material: p.bauteil?.material ?? '' }" :groesse="48" />
                  <div class="min-w-[230px] flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="text-xs text-mute">Pos. {{ p.bestellposition || i + 1 }}</span>
                      <input v-model="p.bezeichnung" class="min-w-0 flex-1 bg-transparent text-sm font-medium outline-none" />
                    </div>
                    <div class="mt-0.5 flex flex-wrap gap-x-3 text-xs text-mute">
                      <span>Artikel <input v-model="p.teilenummer" class="w-28 bg-transparent text-ink outline-none" @change="abgleichen" /></span>
                      <span v-if="p.zeichnungsnr">Zeichnung {{ p.zeichnungsnr }}<template v-if="p.index"> · Index {{ p.index }}</template></span>
                    </div>
                    <!-- was CNC One schon weiß -->
                    <div v-if="kunde" class="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                      <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium" :class="FARBE[bekanntheit(p).art]">
                        <History v-if="['auftrag', 'angebot', 'frueher'].includes(bekanntheit(p).art)" :size="12" /><Sparkles v-else-if="bekanntheit(p).art === 'neu'" :size="12" /><PackageCheck v-else :size="12" />
                        {{ bekanntheit(p).text }}
                      </span>
                      <label v-if="p.quellen.length" class="inline-flex items-center gap-1 text-mute">Kalkulation aus
                        <select v-model.number="p.quelle" class="field !w-auto !py-0.5 !text-xs">
                          <option :value="-1">– keine, neu kalkulieren –</option>
                          <option v-for="(q, qi) in p.quellen" :key="q.angebot + q.angebotKey" :value="qi">{{ q.angebot }} ({{ q.status }}{{ q.datum ? `, ${new Date(q.datum).toLocaleDateString('de-DE')}` : '' }})</option>
                        </select>
                      </label>
                      <!-- ohne Auftrag in CNC One: von Hand vermerken, dass es früher schon gefertigt wurde -->
                      <template v-if="!p.letzterAuftrag && p.frueher">
                        <label class="inline-flex cursor-pointer items-center gap-1.5"><input v-model="p.frueher.gefertigt" type="checkbox" class="accent-[var(--accent)]" /> schon gefertigt (vor CNC One)</label>
                        <input v-if="p.frueher.gefertigt" v-model="p.frueher.notiz" class="field !w-48 !py-0.5 !text-xs" placeholder="z. B. 2022, alter Auftrag 4711" />
                      </template>
                    </div>
                  </div>
                  <div class="w-[260px] text-xs">
                    <div class="flex flex-wrap gap-1">
                      <span v-for="d in dateienVon(i)" :key="d.file.name" class="inline-flex max-w-full items-center gap-1 rounded-lg border border-line bg-surface2 px-1.5 py-0.5">
                        <FileText v-if="d.art === 'Zeichnung'" :size="12" class="shrink-0 text-accent" /><Box v-else :size="12" class="shrink-0 text-accent" />
                        <span class="truncate">{{ d.file.name }}</span>
                        <button class="text-mute hover:text-warn" title="Von dieser Position lösen" @click="d.pos = -1"><X :size="11" /></button>
                      </span>
                      <span v-if="!dateienVon(i).length" class="text-mute">{{ p.bauteil?.zeichnung || p.bauteil?.stepDatei ? 'Dateien vom Bauteil' : 'keine Zeichnung' }}</span>
                    </div>
                  </div>
                  <div class="w-[190px] text-right text-sm tnum">
                    <div class="font-semibold">{{ p.menge }} Stk × {{ eur(p.preis) }}</div>
                    <div class="text-xs text-mute">{{ eur((p.preis || 0) * (p.menge || 0)) }} · Termin {{ de(p.termin) }}</div>
                  </div>
                </div>
              </div>

              <div v-if="ohnePosition.length" class="rounded-xl border border-warn/40 bg-warn/5 p-3">
                <div class="mb-2 text-xs font-semibold text-warn">Ohne Position ({{ ohnePosition.length }}): bitte zuordnen</div>
                <div class="flex flex-col gap-1.5">
                  <div v-for="d in ohnePosition" :key="d.file.name" class="flex flex-wrap items-center gap-2 text-sm">
                    <FileText v-if="d.art === 'Zeichnung'" :size="14" class="text-accent" /><Box v-else :size="14" class="text-accent" />
                    <span class="min-w-0 flex-1 truncate">{{ d.file.name }}</span>
                    <select v-model.number="d.pos" class="field !w-72 !py-1 !text-xs">
                      <option :value="-1">– keiner Position –</option>
                      <option v-for="(p, i) in pos" :key="i" :value="i">{{ posText(p) }}</option>
                    </select>
                    <button class="text-mute hover:text-warn" title="Datei weglassen" @click="dateien.splice(dateien.indexOf(d), 1)"><Trash2 :size="14" /></button>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <footer class="flex flex-wrap items-center gap-3 border-t border-line bg-surface2 px-6 py-4">
            <div class="text-sm"><span class="text-mute">{{ aktive.length }} von {{ pos.length }} Positionen ·</span> <span class="font-semibold tnum">{{ eur(summe) }}</span> <span class="text-xs text-mute">netto laut Bestellung</span></div>
            <span v-if="pos.length" class="text-xs text-mute"><CheckCircle2 :size="13" class="mr-1 inline text-ok" />{{ pos.filter((p) => p.letzterAuftrag || p.quellen.length || p.frueher?.gefertigt).length }} Wiederholteile</span>
            <button class="btn ml-auto" @click="emit('schliessen')">Abbrechen</button>
            <button class="btn btn-primary" :disabled="!fertig || uebernimmt" :class="!fertig || uebernimmt ? 'pointer-events-none opacity-40' : ''" @click="uebernehmen"><Loader v-if="uebernimmt" :size="15" class="animate-spin" /><ShoppingCart v-else :size="15" /> In die Workbench übernehmen</button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
