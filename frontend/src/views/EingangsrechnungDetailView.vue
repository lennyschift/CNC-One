<script setup>
// Eine Eingangsrechnung: links das PDF, rechts die Angaben (bei E-Rechnungen aus der XML gelesen, bei PDF-Rechnungen
// von Hand). Prüfen setzt „sachlich und rechnerisch richtig“ mit Name und Zeit; danach nur noch die Bemerkung.
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft, Check, CheckCircle2, Banknote, XCircle, RotateCcw, Trash2, Inbox, FileCode2, AlertTriangle, Plus, Save } from '@lucide/vue';
import BelegPdf from '../components/BelegPdf.vue';
import StatusBadge from '../components/StatusBadge.vue';
import NumField from '../components/NumField.vue';
import { call } from '../data/api.js';
import { repo } from '../data/repo.js';
import { eur } from '../lib/format.js';
import { useUi } from '../stores/ui.js';

const route = useRoute();
const router = useRouter();
const ui = useUi();
const r = ref(null);
const form = ref(null);
const lieferanten = ref([]);
const speichert = ref(false);
repo.lieferanten.liste().then((l) => { lieferanten.value = l; }).catch(() => {});

const FELDER = ['lieferantId', 'lieferantName', 'lieferantUstId', 'rechnungsnr', 'rechnungsdatum', 'faelligAm', 'art', 'netto', 'steuer', 'brutto', 'waehrung', 'iban', 'bestellreferenz', 'bemerkung', 'positionen'];
function setzen(x) {
  r.value = x;
  form.value = JSON.parse(JSON.stringify(Object.fromEntries(FELDER.map((k) => [k, x[k]]))));
}
async function laden() {
  try { setzen(await call('cnc_one.api.eingangsrechnung.detail', { id: route.params.id })); } catch (e) { ui.toast(e.message, 'warn'); }
}
watch(() => route.params.id, (id) => { if (id) laden(); }, { immediate: true });

const neu = computed(() => r.value?.status === 'Neu');
const geaendert = computed(() => r.value && JSON.stringify(form.value) !== JSON.stringify(Object.fromEntries(FELDER.map((k) => [k, r.value[k]]))));
const summePos = computed(() => (form.value?.positionen ?? []).reduce((n, p) => n + (Number(p.betrag) || 0), 0));
const rechenfehler = computed(() => form.value && Math.abs((form.value.netto || 0) + (form.value.steuer || 0) - (form.value.brutto || 0)) > 0.02);
function steuerRechnen() { form.value.steuer = Math.round((form.value.netto || 0) * 19) / 100; form.value.brutto = Math.round(((form.value.netto || 0) + form.value.steuer) * 100) / 100; }

async function speichern() {
  speichert.value = true;
  try {
    setzen(await call('cnc_one.api.eingangsrechnung.speichern', { id: r.value.id, daten: neu.value ? form.value : { bemerkung: form.value.bemerkung } }));
    ui.toast('Gespeichert', 'ok');
    return true;
  } catch (e) {
    ui.toast(e.message, 'warn');
    return false;
  } finally {
    speichert.value = false;
  }
}
async function status(s) {
  if (geaendert.value && neu.value && !(await speichern())) return;
  try {
    setzen(await call('cnc_one.api.eingangsrechnung.status_setzen', { id: r.value.id, status: s }));
    ui.toast(s === 'Neu' ? 'Wieder geöffnet' : `Als ${s.toLowerCase()} markiert`, 'ok');
  } catch (e) { ui.toast(e.message, 'warn'); }
}
const loeschFrage = ref(false);
async function loeschen() {
  if (!loeschFrage.value) { loeschFrage.value = true; return; }
  try {
    await call('cnc_one.api.eingangsrechnung.loeschen', { id: r.value.id });
    ui.toast('Eingangsrechnung gelöscht (die Mail bleibt)', 'ok');
    router.push('/eingangsrechnungen');
  } catch (e) { ui.toast(e.message, 'warn'); }
}
const de = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
</script>

<template>
  <div v-if="r && form" class="mx-auto grid max-w-[1400px] items-start gap-6 xl:grid-cols-[1fr_460px]">
    <div>
      <RouterLink to="/eingangsrechnungen" class="mb-3 inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Eingangsrechnungen</RouterLink>
      <BelegPdf v-if="r.pdf" :url="r.pdf" :name="`${r.lieferantName} ${r.rechnungsnr}.pdf`" />
      <div v-else class="card grid min-h-[300px] place-items-center p-10 text-center text-sm text-mute">
        <div><FileCode2 :size="30" class="mx-auto mb-2 text-accent" />Reine E-Rechnung (XRechnung) ohne PDF.<br>Die Angaben rechts stammen aus der XML.
          <a v-if="r.xml" :href="r.xml" target="_blank" rel="noopener" class="mt-3 block text-accent hover:underline">XML öffnen</a></div>
      </div>
    </div>

    <aside class="space-y-4 xl:sticky xl:top-0">
      <section class="card p-5">
        <div class="flex items-center justify-between gap-2">
          <h2 class="font-semibold tnum">{{ r.id }}</h2>
          <div class="flex items-center gap-2"><span class="rounded-full bg-surface2 px-2 py-0.5 text-xs text-mute">{{ r.format }}</span><StatusBadge :status="r.status" /></div>
        </div>
        <RouterLink v-if="r.mailId" :to="`/posteingang/${r.mailId}`" class="mt-3 flex items-center gap-2 rounded-xl bg-surface2 px-3 py-2 text-xs hover:text-accent"><Inbox :size="14" class="text-accent" /> Aus der Mail {{ r.mailId }}</RouterLink>
        <div v-if="r.hinweise.length" class="mt-3 space-y-1 rounded-xl bg-warn/10 px-3 py-2 text-xs text-warn">
          <div v-for="h in r.hinweise" :key="h" class="flex gap-1.5"><AlertTriangle :size="13" class="mt-0.5 shrink-0" /> {{ h }}</div>
        </div>
        <p v-if="r.geprueftVon" class="mt-3 flex items-center gap-1.5 text-xs text-ok"><CheckCircle2 :size="13" /> geprüft von {{ r.geprueftVon }} am {{ de(r.geprueftAm) }}</p>

        <fieldset :disabled="!neu" class="m-0 mt-4 grid min-w-0 grid-cols-2 gap-3 border-0 p-0">
          <label class="col-span-2 block"><span class="label mb-1 block">Lieferant</span>
            <select v-model="form.lieferantId" class="field"><option value="">– noch keiner –</option><option v-for="l in lieferanten" :key="l.id" :value="l.id">{{ l.name }}</option></select>
            <span v-if="!form.lieferantId && form.lieferantName" class="mt-1 block text-xs text-warn">Laut Rechnung: {{ form.lieferantName }}{{ form.lieferantUstId ? ` (${form.lieferantUstId})` : '' }} – bitte zuordnen oder in den Stammdaten anlegen.</span>
          </label>
          <label class="block"><span class="label mb-1 block">Rechnungsnummer</span><input v-model="form.rechnungsnr" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Art</span><select v-model="form.art" class="field"><option>Rechnung</option><option>Gutschrift</option></select></label>
          <label class="block"><span class="label mb-1 block">Rechnungsdatum</span><input v-model="form.rechnungsdatum" type="date" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Fällig am</span><input v-model="form.faelligAm" type="date" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Netto</span><NumField v-model="form.netto" unit="€" /></label>
          <label class="block"><span class="label mb-1 flex items-center justify-between">USt <button v-if="neu" type="button" class="normal-case text-accent hover:underline" title="19 % aus Netto, Brutto mitrechnen" @click="steuerRechnen">19 %</button></span><NumField v-model="form.steuer" unit="€" /></label>
          <label class="col-span-2 block"><span class="label mb-1 block">Brutto</span><NumField v-model="form.brutto" unit="€" />
            <span v-if="rechenfehler" class="mt-1 block text-xs text-warn">Netto + USt ergibt nicht den Bruttobetrag.</span></label>
          <label class="block"><span class="label mb-1 block">IBAN</span><input v-model="form.iban" class="field tnum" /></label>
          <label class="block"><span class="label mb-1 block">Unsere Bestellung</span><input v-model="form.bestellreferenz" class="field" /></label>
        </fieldset>
        <label class="mt-3 block"><span class="label mb-1 block">Bemerkung (intern)</span><textarea v-model="form.bemerkung" rows="2" class="field resize-y text-sm" /></label>

        <div class="mt-4 flex flex-wrap gap-2">
          <button v-if="geaendert" class="btn btn-primary" :disabled="speichert" @click="speichern"><Save :size="15" /> Speichern</button>
          <button v-if="r.status === 'Neu'" class="btn" :class="geaendert ? '' : 'btn-primary'" title="Sachlich und rechnerisch richtig" @click="status('Geprüft')"><Check :size="15" /> Geprüft</button>
          <button v-if="['Neu', 'Geprüft'].includes(r.status)" class="btn" @click="status('Bezahlt')"><Banknote :size="15" /> Bezahlt</button>
          <button v-if="r.status === 'Neu'" class="btn !text-mute" @click="status('Abgelehnt')"><XCircle :size="15" /> Ablehnen</button>
          <button v-if="r.status !== 'Neu'" class="btn !text-mute" @click="status('Neu')"><RotateCcw :size="15" /> Wieder öffnen</button>
          <button v-if="r.status === 'Neu'" class="btn !text-mute" :class="loeschFrage ? '!border-accent !text-accent' : ''" @click="loeschen" @blur="loeschFrage = false"><Trash2 :size="15" /> {{ loeschFrage ? 'Wirklich löschen?' : 'Löschen' }}</button>
        </div>
      </section>

      <section class="card p-5">
        <div class="mb-2 flex items-center justify-between"><h3 class="text-sm font-semibold">Positionen</h3><span class="text-xs text-mute tnum">Summe {{ eur(summePos) }}</span></div>
        <div class="space-y-2">
          <div v-for="(p, i) in form.positionen" :key="i" class="grid grid-cols-[1fr_70px_100px_auto] items-center gap-2 text-sm">
            <input v-model="p.bezeichnung" class="field !py-1 text-sm" :disabled="!neu" />
            <NumField v-model="p.menge" :decimals="2" :class="!neu ? 'pointer-events-none opacity-60' : ''" />
            <NumField v-model="p.betrag" unit="€" :class="!neu ? 'pointer-events-none opacity-60' : ''" />
            <button v-if="neu" type="button" class="text-mute hover:text-accent" @click="form.positionen.splice(i, 1)"><Trash2 :size="14" /></button>
          </div>
        </div>
        <p v-if="!form.positionen.length" class="text-xs text-mute">Keine Positionen{{ r.format === 'PDF' ? ' – bei PDF-Rechnungen optional' : '' }}.</p>
        <button v-if="neu" type="button" class="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:underline" @click="form.positionen.push({ bezeichnung: '', menge: 1, einheit: '', einzelpreis: 0, betrag: 0, steuersatz: 19 })"><Plus :size="12" /> Position</button>
        <a v-if="r.xml" :href="r.xml" target="_blank" rel="noopener" class="mt-3 flex items-center gap-1.5 text-xs text-accent hover:underline"><FileCode2 :size="13" /> E-Rechnung (XML)</a>
      </section>
    </aside>
  </div>
  <div v-else class="card mx-auto max-w-lg p-10 text-center text-sm text-mute">Wird geladen …</div>
</template>
