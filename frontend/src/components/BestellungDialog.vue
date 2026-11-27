<script setup>
// Bestellung des Kunden (PDF) einlesen und prüfen. Ohne `auftrag`: daraus einen Auftrag anlegen (aus dem passenden
// Angebot, einem früheren Angebot oder nur mit dem Preis der Bestellung). Mit `auftrag`: die Bestellung an diesen Auftrag
// koppeln und abgleichen. Gelesen wird im Browser (lib/bestellung.js), abgeglichen auf dem Server (api/bestellung.py).
// Alles Erkannte lässt sich vor dem Anlegen ändern. Links steht das PDF, rechts was daraus gelesen wurde; alle Spalten
// der Bestellung bleiben an der Auftragsposition gespeichert (bestellung).
import { ref, computed, watch, onBeforeUnmount, defineAsyncComponent } from 'vue';
import { X, FileUp, AlertTriangle, CheckCircle2, CircleHelp, ShoppingCart, Link2, Columns3, Save, Plus, Trash2 } from '@lucide/vue';
import PartImage from './PartImage.vue';
import NumField from './NumField.vue';
import SerienFeld from './SerienFeld.vue';
import CustomerCombobox from './CustomerCombobox.vue';
import { call, hochladen } from '../data/api.js';
import { pdfjs } from '../lib/pdf.js';
import { textAusSeite } from '../lib/zeichnungText.js';
import { bestellungLesen, positionenAus, zeilenAus, vorlageAus, ROLLEN } from '../lib/bestellung.js';
import { formatNr } from '../lib/serien.js';
import { eur } from '../lib/format.js';
import { useBelege } from '../stores/belege.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({
  auftrag: { type: Object, default: null }, // Bestellung an diesen Auftrag koppeln
  kundeId: { type: String, default: '' },
  datei: { type: Object, default: null }, // schon gewählte Datei (z. B. per Drag & Drop)
});
const emit = defineEmits(['schliessen', 'fertig']);
const DrawingViewer = defineAsyncComponent(() => import('./DrawingViewer.vue'));
const b = useBelege();
const ui = useUi();

const schritt = ref('datei'); // datei | lesen | pruefen
const pdf = ref(null);
const fehler = ref('');
const kunde = ref(props.auftrag?.kunde?.id ?? props.kundeId);
const kopf = ref({ bestellnr: '', datum: '', email: '' });
const vorlage = ref({});
const spalten = ref([]);
const zeilen = ref([]);
const text = ref('');
const pos = ref([]); // Positionen mit Abgleich vom Server und der Auswahl hier
const vorhanden = ref([]);
const toleranz = ref(0.5);
const spaltenOffen = ref(false);
const arbeitet = ref(false);
// das PDF zum Ansehen neben den erkannten Werten
const pdfUrl = ref('');
watch(pdf, (f) => { if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); pdfUrl.value = f ? URL.createObjectURL(f) : ''; });
onBeforeUnmount(() => { if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); });

// ------------------------------------------------------------------ Lesen
async function dateiGewaehlt(f) {
  if (!f) return;
  if (!/\.pdf$/i.test(f.name) && f.type !== 'application/pdf') { fehler.value = 'Bitte eine PDF-Datei wählen.'; return; }
  pdf.value = f;
  fehler.value = '';
  schritt.value = 'lesen';
  try {
    const aufgabe = pdfjs.getDocument({ data: new Uint8Array(await f.arrayBuffer()) });
    const doc = await aufgabe.promise;
    const seiten = [];
    for (let i = 1; i <= Math.min(doc.numPages, 10); i++) seiten.push(await textAusSeite(await doc.getPage(i)));
    aufgabe.destroy();
    zeilen.value = zeilenAus(seiten);
    text.value = zeilen.value.map((z) => z.zellen.map((c) => c.text).join(' ')).join('\n');
    // Kunde aus dem Text (wenn nicht schon bekannt) und seine angelernten Spalten
    const e = await call('cnc_one.api.bestellung.erkennen', { text: text.value, kunde: kunde.value });
    if (!kunde.value) kunde.value = e.kunde;
    vorlage.value = e.vorlage ?? {};
    const r = bestellungLesen(seiten, vorlage.value);
    kopf.value = r.kopf;
    spalten.value = r.spalten;
    pos.value = r.positionen.map(neuePosition);
    if (!pos.value.length) { spaltenOffen.value = true; pos.value = [neuePosition({})]; }
    await abgleichen();
    schritt.value = 'pruefen';
  } catch (e) {
    fehler.value = e?.message ? `Das PDF ließ sich nicht lesen: ${e.message}` : 'Das PDF ließ sich nicht lesen.';
    schritt.value = 'datei';
  }
}
if (props.datei) dateiGewaehlt(props.datei);

function neuePosition(p) {
  return {
    aktiv: true, bestellposition: p.bestellposition ?? '', teilenummer: p.teilenummer ?? '', bezeichnung: p.bezeichnung ?? '',
    menge: p.menge ?? 1, preis: p.preis ?? 0, preiseinheit: p.preiseinheit ?? 1, betrag: p.betrag ?? null, termin: p.termin ?? '', text: p.text ?? '',
    einheit: p.einheit ?? '', zeichnungsdatum: p.zeichnungsdatum ?? '', zeichnungsnr: p.zeichnungsnr ?? '', index: p.index ?? '', angaben: p.angaben ?? [],
    bauteil: null, quellen: [], quelle: -1, abgleich: null, letzterAuftrag: null, preisform: '', serienStart: '', auftragKey: '', erwartet: null,
  };
}

// Spalten anders zuordnen und neu lesen; auf Wunsch für diesen Kunden merken
async function neuLesen() {
  const v = { ...vorlage.value, spalten: { ...(vorlage.value.spalten ?? {}), ...vorlageAus(spalten.value) } };
  pos.value = positionenAus(zeilen.value, v).positionen.map(neuePosition);
  if (!pos.value.length) pos.value = [neuePosition({})];
  await abgleichen();
}
async function spaltenMerken() {
  if (!kunde.value) { ui.toast('Bitte zuerst den Kunden wählen.', 'warn'); return; }
  vorlage.value = await call('cnc_one.api.bestellung.vorlage_lernen', { kunde: kunde.value, vorlage: { ...vorlage.value, spalten: { ...(vorlage.value.spalten ?? {}), ...vorlageAus(spalten.value) } } });
  ui.toast('Spalten für diesen Kunden gemerkt');
}

// ------------------------------------------------------------------ Abgleich
let lauf = 0;
async function abgleichen() {
  if (!kunde.value && !props.auftrag) return;
  const nr = ++lauf;
  const anfrage = pos.value.map((p) => ({ bestellposition: p.bestellposition, teilenummer: p.teilenummer, text: `${p.bezeichnung}\n${p.text}`, menge: p.menge, preis: p.preis, termin: p.termin }));
  const r = await call('cnc_one.api.bestellung.vorschlag', { kunde: kunde.value, positionen: anfrage, kundenbestellnr: kopf.value.bestellnr, auftrag: props.auftrag?.id ?? '' });
  if (nr !== lauf) return;
  toleranz.value = r.toleranz;
  vorhanden.value = r.vorhanden;
  r.positionen.forEach((s, i) => {
    const p = pos.value[i];
    if (!p) return;
    // die gewählte Quelle bleibt gewählt, wenn es sie noch gibt
    const vorher = p.quelle >= 0 ? p.quellen[p.quelle] : null;
    const ohneAngebot = p.quelle === -2 && p.geladen; // „ohne Angebot“ selbst gewählt
    Object.assign(p, { bauteil: s.bauteil, quellen: s.quellen ?? [], letzterAuftrag: s.letzterAuftrag ?? null, auftragKey: s.auftragKey ?? '', erwartet: s.erwartet ?? null });
    if (!p.teilenummer && s.teilenummer) p.teilenummer = s.teilenummer;
    const gleich = vorher ? p.quellen.findIndex((q) => q.angebot === vorher.angebot && q.angebotKey === vorher.angebotKey) : -1;
    p.quelle = ohneAngebot ? -2 : gleich >= 0 ? gleich : s.quelle ?? -1;
    p.geladen = true;
    p.abgleich = s.abgleich ?? null;
    if (!p.preisform) p.preisform = vorschlagPreisform(p);
    if (s.bauteil?.seriennummern && !p.serienStart) p.serienStart = formatNr((s.bauteil.letzteSeriennummer || 0) + 1, s.bauteil.serienStellen);
  });
}
let warten = null;
const neuAbgleichen = () => { clearTimeout(warten); warten = setTimeout(abgleichen, 450); };
watch(kunde, async (k, alt) => {
  if (schritt.value !== 'pruefen' || k === alt) return;
  vorlage.value = k ? ((await call('cnc_one.api.bestellung.erkennen', { kunde: k })).vorlage ?? {}) : {};
  abgleichen();
});

// Abgleich der gewählten Quelle (Angebot) oder, ohne Angebot, gegen den letzten Auftrag bzw. den Auftrag beim Koppeln
const abgleichVon = (p) => (p.quelle >= 0 && p.quellen[p.quelle] ? p.quellen[p.quelle].abgleich : p.abgleich);
const erwartetVon = (p) => (p.quelle >= 0 && p.quellen[p.quelle] ? p.quellen[p.quelle].erwartet : p.erwartet);
function vorschlagPreisform(p) {
  const a = abgleichVon(p);
  // umgelegt bestellt: Rechnung und Auftragsbestätigung so, wie der Kunde bestellt hat (sonst passt es in SAP nicht)
  return a?.status === 'umgelegt' ? 'Bestellung' : 'Angebot';
}
function quelleWaehlen(p, i) { p.quelle = Number(i); p.preisform = vorschlagPreisform(p); }

const STATUS = {
  gleich: { text: 'passt wie angeboten', klasse: 'bg-ok/10 text-ok', icon: CheckCircle2 },
  umgelegt: { text: 'passt, Kosten auf den Stückpreis umgelegt', klasse: 'bg-ok/10 text-ok', icon: CheckCircle2 },
  abweichend: { text: 'weicht ab', klasse: 'bg-warn/10 text-warn', icon: AlertTriangle },
  ohne_preis: { text: 'kein Preis in der Bestellung', klasse: 'bg-surface2 text-mute', icon: CircleHelp },
  ohne_vergleich: { text: 'nichts zum Vergleichen', klasse: 'bg-surface2 text-mute', icon: CircleHelp },
};
const kostenSumme = (e) => (e?.kosten ?? []).reduce((s, k) => s + (k.betrag || 0), 0);
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');

// Was in der Bestellung steht, wird an der Auftragsposition gespeichert (ohne den Rohtext)
const bestellungVon = (p) => ({
  bestellposition: p.bestellposition, teilenummer: p.teilenummer, bezeichnung: p.bezeichnung, menge: p.menge, einheit: p.einheit,
  preis: p.preis, preiseinheit: p.preiseinheit, betrag: p.betrag, termin: p.termin, zeichnungsdatum: p.zeichnungsdatum,
  zeichnungsnr: p.zeichnungsnr, index: p.index, angaben: p.angaben,
});
// Betrag laut Bestellung passt nicht zu Menge × Stückpreis (Tippfehler im PDF oder falsch gelesen)
const betragAbweichung = (p) => (p.betrag && p.preis && p.menge && Math.abs(p.preis * p.menge - p.betrag) > Math.max(0.05, p.betrag * 0.01) ? p.preis * p.menge - p.betrag : 0);

const aktive = computed(() => pos.value.filter((p) => p.aktiv));
const summe = computed(() => aktive.value.reduce((s, p) => {
  const e = erwartetVon(p);
  if (p.quelle >= 0 && p.preisform === 'Angebot' && e) return s + e.einzelpreis * p.menge + kostenSumme(e);
  return s + (p.preis || 0) * (p.menge || 0);
}, 0));
const abweichungen = computed(() => aktive.value.filter((p) => abgleichVon(p)?.status === 'abweichend').length);
const fehlt = computed(() => {
  if (!kunde.value) return 'Bitte den Kunden wählen.';
  if (!aktive.value.length) return 'Keine Position gewählt.';
  if (props.auftrag) return aktive.value.some((p) => !p.auftragKey) ? 'Nicht jede Position passt zu einer Position des Auftrags (sie wird übersprungen).' : '';
  const ohne = aktive.value.find((p) => p.quelle < 0 && !(p.preis > 0));
  if (ohne) return `Position ${ohne.bestellposition || ohne.teilenummer || ''}: ohne Angebot braucht es den Stückpreis der Bestellung.`;
  const ohneTeil = aktive.value.find((p) => p.quelle < 0 && !p.bauteil && !p.teilenummer.trim());
  if (ohneTeil) return 'Jede Position braucht eine Teilenummer oder ein Angebot.';
  const serie = aktive.value.find((p) => p.bauteil?.seriennummern && !String(p.serienStart).trim());
  if (serie) return `Für ${serie.bauteil.teilenummer} bitte die erste Seriennummer eingeben.`;
  return '';
});
const blockiert = computed(() => !!fehlt.value && !props.auftrag);

// ------------------------------------------------------------------ Anlegen / Koppeln
async function pdfAblegen(auftragId) {
  if (!pdf.value) return null;
  const f = await hochladen(pdf.value, { doctype: 'Auftrag', docname: auftragId, name: `Bestellung ${(kopf.value.bestellnr || auftragId).replace(/[\\/:*?"<>|]+/g, '-')}.pdf` });
  return call('cnc_one.api.bestellung.datei_setzen', { auftrag: auftragId, datei: f.file_url });
}

async function anlegen() {
  if (arbeitet.value || blockiert.value) return;
  arbeitet.value = true;
  try {
    const positionen = aktive.value.map((p) => {
      const q = p.quellen[p.quelle];
      const gemeinsam = { menge: p.menge, termin: p.termin, bestellposition: p.bestellposition, bestellpreis: p.preis, serienStart: p.bauteil?.seriennummern ? String(p.serienStart) : '', bestellung: bestellungVon(p) };
      if (p.quelle >= 0 && q) return { ...gemeinsam, angebot: q.angebot, angebotKey: q.angebotKey, optionId: q.optionId, preisform: p.preisform };
      return { ...gemeinsam, bauteil: p.bauteil?.id ?? '', teilenummer: p.teilenummer, bezeichnung: p.bezeichnung };
    });
    let rec = await call('cnc_one.api.bestellung.auftrag_anlegen', { kunde: kunde.value, positionen, kundenbestellnr: kopf.value.bestellnr, bestelldatum: kopf.value.datum || '' });
    try { rec = (await pdfAblegen(rec.id)) ?? rec; } catch { ui.toast('Der Auftrag ist angelegt, das PDF ließ sich aber nicht ablegen.', 'warn'); }
    b.auftragEinsetzen(rec);
    ui.toast(`Auftrag ${rec.id} aus der Bestellung angelegt`);
    emit('fertig', rec);
  } catch (e) {
    ui.toast(e?.message ?? 'Der Auftrag ließ sich nicht anlegen.', 'warn');
  } finally { arbeitet.value = false; }
}

async function koppeln() {
  if (arbeitet.value) return;
  arbeitet.value = true;
  try {
    const positionen = aktive.value.filter((p) => p.auftragKey).map((p) => ({ auftragKey: p.auftragKey, bestellposition: p.bestellposition, bestellpreis: p.preis, termin: p.termin, bestellung: bestellungVon(p) }));
    let rec = await call('cnc_one.api.bestellung.koppeln', { auftrag: props.auftrag.id, positionen, kundenbestellnr: kopf.value.bestellnr, bestelldatum: kopf.value.datum || '' });
    try { rec = (await pdfAblegen(rec.id)) ?? rec; } catch { ui.toast('Die Angaben sind übernommen, das PDF ließ sich aber nicht ablegen.', 'warn'); }
    b.auftragEinsetzen(rec);
    ui.toast('Bestellung an den Auftrag gekoppelt');
    emit('fertig', rec);
  } catch (e) {
    ui.toast(e?.message ?? 'Die Bestellung ließ sich nicht koppeln.', 'warn');
  } finally { arbeitet.value = false; }
}

const ziehen = ref(false);
function fallen(e) { ziehen.value = false; dateiGewaehlt(e.dataTransfer?.files?.[0]); }
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[95vh] flex-col overflow-hidden shadow-2xl" :class="schritt === 'pruefen' && pdfUrl ? 'h-[95vh] w-[min(1700px,98vw)]' : 'w-[min(1080px,97vw)]'">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h2 class="text-base font-semibold">{{ auftrag ? 'Bestellung an den Auftrag koppeln' : 'Auftrag aus Bestellung' }}</h2>
              <p class="text-xs text-mute">{{ auftrag ? `${auftrag.id} · ${auftrag.kundeName}` : 'PDF der Bestellung des Kunden einlesen, prüfen und als Auftrag anlegen' }}<template v-if="pdf"> · {{ pdf.name }}</template></p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <!-- Datei wählen -->
          <div v-if="schritt !== 'pruefen'" class="p-6">
            <label class="grid cursor-pointer place-items-center rounded-2xl border-2 border-dashed px-6 py-16 text-center transition" :class="ziehen ? 'border-accent bg-accent-soft' : 'border-line hover:border-accent/50'"
              @dragover.prevent="ziehen = true" @dragleave="ziehen = false" @drop.prevent.stop="fallen">
              <FileUp :size="34" class="text-accent" :stroke-width="1.5" />
              <span class="mt-3 text-sm font-medium">{{ schritt === 'lesen' ? 'Bestellung wird gelesen …' : 'PDF der Bestellung hierher ziehen oder klicken' }}</span>
              <span class="mt-1 text-xs text-mute">Bestellnummer, Positionen, Mengen, Preise und Liefertermine werden erkannt und mit Angeboten und früheren Aufträgen abgeglichen.</span>
              <input type="file" accept="application/pdf,.pdf" class="hidden" @change="dateiGewaehlt($event.target.files[0])" />
            </label>
            <p v-if="fehler" class="mt-3 text-sm text-warn">{{ fehler }}</p>
          </div>

          <!-- Prüfen: links das PDF, rechts die erkannten Werte -->
          <div v-else class="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,45vh)_minmax(0,1fr)]" :class="pdfUrl ? 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:grid-rows-1' : 'grid-rows-1'">
          <section v-if="pdfUrl" class="min-h-0 min-w-0 border-b border-line bg-surface2/50 p-3 lg:border-b-0 lg:border-r">
            <DrawingViewer :url="pdfUrl" :name="pdf?.name || 'Bestellung.pdf'" />
          </section>
          <div class="min-h-0 min-w-0 space-y-4 overflow-auto px-6 py-5">
            <div class="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
              <div v-if="!auftrag"><CustomerCombobox v-model="kunde" /></div>
              <label class="block"><span class="label mb-1 block">Bestellnummer des Kunden</span><input v-model="kopf.bestellnr" class="field" placeholder="z. B. 4500012345" @change="neuAbgleichen" /></label>
              <label class="block"><span class="label mb-1 block">Bestelldatum</span><input v-model="kopf.datum" type="date" class="field" /></label>
            </div>
            <p v-if="vorhanden.length" class="flex items-center gap-2 rounded-xl bg-warn/10 px-3.5 py-2.5 text-sm text-warn"><AlertTriangle :size="15" /> Zu dieser Bestellnummer gibt es schon
              <RouterLink v-for="a in vorhanden" :key="a" :to="`/auftraege/${a}`" class="font-semibold underline" @click="emit('schliessen')">{{ a }}</RouterLink>.</p>

            <!-- erkannte Spalten -->
            <div class="rounded-xl border border-line">
              <button type="button" class="flex w-full items-center gap-2 px-3.5 py-2 text-left text-xs text-mute" @click="spaltenOffen = !spaltenOffen">
                <Columns3 :size="14" /> Erkannte Spalten der Tabelle <span v-if="!spalten.length" class="text-warn">· keine Tabelle erkannt, Positionen bitte von Hand eintragen oder Spalten zuordnen</span>
                <span class="ml-auto">{{ spaltenOffen ? 'ausblenden' : 'ändern' }}</span>
              </button>
              <div v-if="spaltenOffen" class="border-t border-line px-3.5 py-3">
                <div v-if="spalten.length" class="flex flex-wrap gap-2">
                  <label v-for="(s, i) in spalten" :key="i" class="flex flex-col gap-1 rounded-lg bg-surface2 px-2.5 py-1.5 text-xs">
                    <span class="font-medium">{{ s.text }}</span>
                    <select v-model="s.rolle" class="field !py-1 text-xs"><option value="">– nicht verwenden –</option><option v-for="r in ROLLEN" :key="r.id" :value="r.id">{{ r.label }}</option></select>
                    <span class="text-[10px] text-mute">Zeile darunter</span>
                    <select v-model="s.rolle2" class="field !py-1 text-xs" title="Wenn in der Spalte zwei Angaben untereinander stehen (z. B. Bezeichnung und darunter die Materialnummer)"><option value="">– nichts –</option><option v-for="r in ROLLEN" :key="r.id" :value="r.id">{{ r.label }}</option></select>
                  </label>
                </div>
                <p v-else class="text-xs text-mute">Im PDF wurde keine Kopfzeile mit „Menge“ gefunden. Ist das PDF ein Scan (nur Bild)? Dann bitte die Positionen unten eintragen.</p>
                <div v-if="spalten.length" class="mt-2 flex gap-2">
                  <button class="btn !py-1 text-xs" @click="neuLesen">Neu lesen</button>
                  <button class="btn !py-1 text-xs" :disabled="!kunde" title="Beim nächsten PDF dieses Kunden gelten diese Spalten" @click="spaltenMerken"><Save :size="13" /> Für diesen Kunden merken</button>
                </div>
              </div>
            </div>

            <!-- Positionen -->
            <div v-for="(p, i) in pos" :key="i" class="rounded-2xl border p-4 transition" :class="p.aktiv ? 'border-line bg-surface' : 'border-line/60 bg-surface2 opacity-60'">
              <div class="flex items-start gap-4">
                <input v-model="p.aktiv" type="checkbox" class="mt-1.5 h-4 w-4 accent-[var(--color-accent)]" title="Position übernehmen" />
                <PartImage :teil="p.bauteil ?? { name: p.bezeichnung }" :bild="p.bauteil?.vorschaubild" :groesse="56" />
                <div class="min-w-0 flex-1 space-y-3">
                  <div class="grid gap-3 sm:grid-cols-[80px_1fr_1fr]">
                    <label class="block"><span class="label mb-1 block">Pos.</span><input v-model="p.bestellposition" class="field" /></label>
                    <label class="block"><span class="label mb-1 block">Teilenummer</span><input v-model="p.teilenummer" class="field" @change="neuAbgleichen" /></label>
                    <label class="block"><span class="label mb-1 block">Bezeichnung (Bestellung)</span><input v-model="p.bezeichnung" class="field" :placeholder="p.bauteil ? '' : 'neu: Bezeichnung'" :title="p.bauteil ? '' : 'Kein Bauteil gefunden, es wird mit dieser Bezeichnung angelegt'" /></label>
                  </div>
                  <div v-if="p.bauteil" class="rounded-lg bg-surface2 px-2.5 py-1.5 text-xs"><span class="text-mute">Bauteil bei uns:</span> <span class="font-medium">{{ p.bauteil.name || p.bauteil.teilenummer }}</span> <span class="text-mute tnum">{{ p.bauteil.teilenummer }}<template v-if="p.bauteil.zeichnungsnr && p.bauteil.zeichnungsnr !== p.bauteil.teilenummer"> · Zeichnung {{ p.bauteil.zeichnungsnr }}</template><template v-if="p.bauteil.revision"> · Rev. {{ p.bauteil.revision }}</template></span></div>
                  <div class="grid gap-3 sm:grid-cols-[110px_70px_150px_130px]">
                    <NumField v-model="p.menge" label="Menge" :unit="p.einheit || 'Stk'" :decimals="0" :min="1" @update:model-value="neuAbgleichen" />
                    <label class="block"><span class="label mb-1 block">ME</span><input v-model="p.einheit" class="field" placeholder="ST" /></label>
                    <NumField v-model="p.preis" label="Preis je Stück (Bestellung)" unit="€" :decimals="4" @update:model-value="neuAbgleichen" />
                    <NumField v-model="p.betrag" label="Betrag (Bestellung)" unit="€" :decimals="2" />
                  </div>
                  <p v-if="betragAbweichung(p)" class="flex items-center gap-1.5 text-xs text-warn"><AlertTriangle :size="13" /> Menge × Stückpreis = {{ eur(p.menge * p.preis) }}, in der Bestellung steht {{ eur(p.betrag) }}.</p>
                  <div class="grid gap-3 sm:grid-cols-[150px_150px_1fr]">
                    <label class="block"><span class="label mb-1 block">Liefertermin</span><input v-model="p.termin" type="date" class="field" /></label>
                    <label class="block" title="Datum bzw. Stand der Zeichnung laut Bestellung"><span class="label mb-1 block">Zeichnungsdatum</span><input v-model="p.zeichnungsdatum" type="date" class="field" /></label>
                    <label v-if="!auftrag" class="block"><span class="label mb-1 block">Preise aus</span>
                      <select class="field" :value="p.quelle < 0 ? -2 : p.quelle" @change="quelleWaehlen(p, $event.target.value)">
                        <option v-for="(q, qi) in p.quellen" :key="qi" :value="qi">{{ q.angebot }} · {{ de(q.datum) }} · {{ q.status }}{{ q.erwartet.staffelMenge ? ` · Staffel ${q.erwartet.staffelMenge}` : '' }}</option>
                        <option :value="-2">ohne Angebot: Preis laut Bestellung</option>
                      </select>
                    </label>
                    <div v-else class="text-xs"><span class="label mb-1 block">Im Auftrag</span><span v-if="p.auftragKey" class="text-ok">Position gefunden ({{ p.erwartet?.menge }} Stk)</span><span v-else class="text-warn">keine passende Position</span></div>
                  </div>
                  <p v-if="p.preiseinheit > 1" class="text-xs text-mute">Preis in der Bestellung je {{ p.preiseinheit }} Stück, umgerechnet auf ein Stück.</p>
                  <!-- alles, was im PDF zu dieser Position steht -->
                  <details v-if="p.angaben?.length" class="rounded-xl border border-line px-3 py-2 text-xs" open>
                    <summary class="cursor-pointer text-mute">Laut Bestellung (alle Spalten)</summary>
                    <dl class="mt-1.5 grid gap-x-4 gap-y-1 sm:grid-cols-[auto_1fr]">
                      <template v-for="a in p.angaben" :key="a.spalte"><dt class="text-mute">{{ a.spalte }}</dt><dd class="tnum">{{ a.wert }}</dd></template>
                    </dl>
                  </details>

                  <!-- Abgleich -->
                  <div v-if="abgleichVon(p)" class="rounded-xl px-3.5 py-2.5 text-xs" :class="STATUS[abgleichVon(p).status]?.klasse">
                    <div class="flex flex-wrap items-center gap-2 font-medium">
                      <component :is="STATUS[abgleichVon(p).status]?.icon" :size="14" /> {{ STATUS[abgleichVon(p).status]?.text }}
                      <span v-if="abgleichVon(p).status === 'abweichend'" class="tnum">({{ abgleichVon(p).differenz > 0 ? '+' : '' }}{{ eur(abgleichVon(p).differenz) }} auf die Position)</span>
                      <span v-if="abgleichVon(p).gegen" class="font-normal opacity-80">· verglichen mit dem letzten Auftrag</span>
                    </div>
                    <div v-if="abgleichVon(p).hinweis" class="mt-0.5">{{ abgleichVon(p).hinweis }}</div>
                    <div v-if="erwartetVon(p) && abgleichVon(p).bestellt != null" class="mt-1 grid gap-x-6 gap-y-0.5 text-ink/80 tnum sm:grid-cols-2">
                      <span>{{ auftrag ? 'Auftrag' : 'Angebot' }}: {{ p.menge }} × {{ eur(erwartetVon(p).einzelpreis) }}<template v-if="kostenSumme(erwartetVon(p))"> + {{ eur(kostenSumme(erwartetVon(p))) }} Kosten</template> = {{ eur(abgleichVon(p).angeboten) }} ({{ eur(abgleichVon(p).umgelegt) }} je Stück)</span>
                      <span>Bestellung: {{ p.menge }} × {{ eur(p.preis) }} = {{ eur(abgleichVon(p).bestellt) }}</span>
                    </div>
                  </div>
                  <p v-if="!auftrag && p.letzterAuftrag" class="text-xs text-mute">Zuletzt bestellt in <RouterLink :to="`/auftraege/${p.letzterAuftrag.auftrag}`" class="text-accent hover:underline" @click="emit('schliessen')">{{ p.letzterAuftrag.auftrag }}</RouterLink>: {{ p.letzterAuftrag.menge }} Stk zu {{ eur(p.letzterAuftrag.jeStueck) }} je Stück ({{ de(p.letzterAuftrag.datum) }})</p>

                  <div class="flex flex-wrap items-end gap-4">
                    <div v-if="!auftrag && p.quelle >= 0" class="flex flex-wrap gap-1.5 text-xs">
                      <span class="label w-full">Im Auftrag (und auf AB und Rechnung)</span>
                      <button type="button" class="rounded-full border px-3 py-1" :class="p.preisform === 'Bestellung' ? 'border-accent bg-accent-soft text-accent' : 'border-line text-mute'" @click="p.preisform = 'Bestellung'">wie bestellt: alles im Stückpreis</button>
                      <button type="button" class="rounded-full border px-3 py-1" :class="p.preisform === 'Angebot' ? 'border-accent bg-accent-soft text-accent' : 'border-line text-mute'" @click="p.preisform = 'Angebot'">wie angeboten: Stückpreis und Kosten</button>
                    </div>
                    <SerienFeld v-if="!auftrag && p.bauteil?.seriennummern" v-model="p.serienStart" :stellen="p.bauteil.serienStellen" label="Erste Seriennummer" :hint="p.bauteil.letzteSeriennummer ? `zuletzt ${formatNr(p.bauteil.letzteSeriennummer, p.bauteil.serienStellen)}` : ''" class="w-44" />
                    <button v-if="pos.length > 1" type="button" class="ml-auto inline-flex items-center gap-1 text-xs text-mute hover:text-warn" @click="pos.splice(i, 1)"><Trash2 :size="13" /> entfernen</button>
                  </div>
                </div>
              </div>
            </div>
            <button type="button" class="btn text-xs" @click="pos.push(neuePosition({}))"><Plus :size="14" /> Position hinzufügen</button>
          </div>
          </div>

          <footer v-if="schritt === 'pruefen'" class="flex flex-wrap items-center gap-3 border-t border-line px-6 py-4">
            <div class="text-sm">
              <span class="text-mute">{{ aktive.length }} {{ aktive.length === 1 ? 'Position' : 'Positionen' }}</span>
              <template v-if="!auftrag"> · <span class="font-semibold tnum">{{ eur(summe) }}</span> netto</template>
              <span v-if="abweichungen" class="ml-2 text-warn">· {{ abweichungen }} mit Preisabweichung (Toleranz {{ String(toleranz).replace('.', ',') }} %)</span>
            </div>
            <span v-if="fehlt" class="text-xs" :class="auftrag ? 'text-mute' : 'text-warn'">{{ fehlt }}</span>
            <button class="btn ml-auto" @click="emit('schliessen')">Abbrechen</button>
            <button v-if="auftrag" class="btn btn-primary" :disabled="arbeitet || !kunde" @click="koppeln"><Link2 :size="16" /> An Auftrag koppeln</button>
            <button v-else class="btn btn-primary" :disabled="arbeitet || blockiert" @click="anlegen"><ShoppingCart :size="16" /> Auftrag anlegen</button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
