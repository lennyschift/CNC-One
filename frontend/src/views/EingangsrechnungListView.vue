<script setup>
// Eingangsrechnungen (Rechnungen der Lieferanten): aus dem Posteingang (E-Rechnungen von selbst) oder hochgeladen.
// Prüfen, als bezahlt markieren; Zahlung und DATEV folgen mit dem Steuerberater.
import { ref, computed, onMounted, watch } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Search, Upload, Receipt, FileCode2, FileText, AlertTriangle } from '@lucide/vue';
import RechnungNav from '../components/RechnungNav.vue';
import StatusBadge from '../components/StatusBadge.vue';
import FilterLeiste from '../components/FilterLeiste.vue';
import { call, hochladen } from '../data/api.js';
import { eur } from '../lib/format.js';
import { useUi } from '../stores/ui.js';
import { useRouter } from 'vue-router';

const ui = useUi();
const router = useRouter();
const liste = ref([]);
const geladen = ref(false);
async function laden() {
  try { liste.value = await call('cnc_one.api.eingangsrechnung.liste'); } catch (e) { ui.toast(e.message, 'warn'); }
  geladen.value = true;
}
onMounted(laden);

const filter = ref('Offen');
const FILTER = { Alle: () => true, Offen: (r) => ['Neu', 'Geprüft'].includes(r.status), Neu: (r) => r.status === 'Neu', Geprüft: (r) => r.status === 'Geprüft', Bezahlt: (r) => r.status === 'Bezahlt', Abgelehnt: (r) => r.status === 'Abgelehnt' };
const suche = ref('');
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return liste.value.filter((r) => FILTER[filter.value](r) && (!q || `${r.id} ${r.lieferantName} ${r.lieferantId} ${r.rechnungsnr} ${r.bestellreferenz}`.toLowerCase().includes(q)));
});
const zeilen = ref([]);
const beschriftungen = { status: 'Status', lieferantName: 'Rechnungssteller', rechnungsnr: 'Rechnungsnummer', rechnungsdatum: 'Rechnungsdatum', faelligAm: 'Fällig am', brutto: 'Brutto', format: 'Format' };
const offen = computed(() => liste.value.filter(FILTER.Offen));
const summe = (l) => l.reduce((n, r) => n + (r.brutto || 0), 0);
const heute = new Date().toISOString().slice(0, 10);
const faellig = computed(() => offen.value.filter((r) => r.faelligAm && r.faelligAm <= heute));
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');

// Hochladen (Knopf oder Drag and Drop, auch mehrere): PDF (ZUGFeRD oder Papier-/PDF-Rechnung) oder XML (XRechnung).
// Eine Datei öffnet die neue Rechnung, mehrere bleiben in der Liste.
const laedt = ref(false);
const fortschritt = ref('');
const ERLAUBT = /\.(pdf|xml)$/i;
async function dateienEinlesen(files) {
  const liste_ = Array.from(files || []);
  const passend = liste_.filter((f) => ERLAUBT.test(f.name));
  if (passend.length < liste_.length) ui.toast(`${liste_.length - passend.length} Datei(en) übersprungen – nur PDF und XML`, 'warn');
  if (!passend.length || laedt.value) return;
  laedt.value = true;
  const neu = [];
  try {
    for (const [i, f] of passend.entries()) {
      fortschritt.value = passend.length > 1 ? `${i + 1}/${passend.length}` : '';
      try {
        const datei = await hochladen(f, { doctype: '', docname: '' });
        const r = await call('cnc_one.api.eingangsrechnung.aus_datei', { file_url: datei.file_url });
        neu.push(r.rechnung);
      } catch (e) {
        ui.toast(`${f.name}: ${e.message}`, 'warn');
      }
    }
  } finally {
    laedt.value = false;
    fortschritt.value = '';
  }
  if (neu.length === 1 && passend.length === 1) {
    const r = neu[0];
    ui.toast(r.format === 'PDF' ? 'PDF-Rechnung angelegt, bitte die Angaben ergänzen' : `E-Rechnung ${r.rechnungsnr} eingelesen`, 'ok');
    router.push(`/eingangsrechnungen/${r.id}`);
  } else if (neu.length) {
    const e = neu.filter((r) => r.format !== 'PDF').length;
    ui.toast(`${neu.length} Rechnungen angelegt (${e} E-Rechnung${e === 1 ? '' : 'en'} gelesen, ${neu.length - e} PDF zum Ergänzen)`, 'ok');
    filter.value = 'Neu';
    laden();
  }
}
watch(() => ui.abgelegt, (x) => {
  if (x?.ziel !== 'eingangsrechnung') return;
  ui.abgelegt = null;
  dateienEinlesen(x.files);
});
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <RechnungNav />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <div class="rounded-2xl bg-surface2 px-4 py-2.5"><div class="label">Offen (Neu und geprüft)</div><div class="text-xl font-semibold tnum">{{ eur(summe(offen)) }}</div><div class="text-[11px] text-mute">{{ offen.length }} Rechnung{{ offen.length === 1 ? '' : 'en' }}</div></div>
      <div v-if="faellig.length" class="rounded-2xl bg-accent-soft px-4 py-2.5 text-accent"><div class="label !text-accent">Fällig</div><div class="text-xl font-semibold tnum">{{ eur(summe(faellig)) }}</div><div class="text-[11px]">{{ faellig.length }} Rechnung{{ faellig.length === 1 ? '' : 'en' }}</div></div>
      <label class="btn btn-primary ml-auto cursor-pointer" :class="laedt ? 'pointer-events-none opacity-60' : ''" title="PDF- oder XML-Rechnungen hochladen oder einfach hierher ziehen (ZUGFeRD und XRechnung werden gelesen)">
        <Upload :size="16" /> {{ laedt ? `Wird gelesen … ${fortschritt}` : 'Rechnungen hochladen' }}
        <input type="file" multiple accept=".pdf,.xml,application/pdf,application/xml,text/xml" class="hidden" @change="dateienEinlesen($event.target.files); $event.target.value = ''" />
      </label>
    </div>
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in Object.keys(FILTER)" :key="f" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f">{{ f }}</button>
      </div>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-64 !pl-9" placeholder="Lieferant, Nummer, Bestellung …" />
      </label>
      <span class="ml-auto text-sm text-mute tnum">{{ zeilen.length }} von {{ liste.length }}</span>
    </div>
    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="eingangsrechnungen" :beschriftungen="beschriftungen" :standard-angeheftet="['lieferantName']" />

    <section class="card overflow-hidden">
      <div v-if="!geladen" class="p-6 text-sm text-mute">Wird geladen …</div>
      <div v-else-if="!zeilen.length" class="flex flex-col items-center px-6 py-14 text-center text-sm text-mute">
        <Receipt :size="34" :stroke-width="1.4" class="mb-3" />
        <span class="font-medium text-ink">Keine Eingangsrechnungen</span>
        <span class="mt-1 max-w-md text-xs">E-Rechnungen (ZUGFeRD, XRechnung) aus dem Posteingang werden von selbst angelegt; PDF-Rechnungen mit „Rechnung aus …“ an der Mail, hier hochladen oder einfach auf diese Seite ziehen.</span>
      </div>
      <div v-auto-animate class="divide-y divide-line">
        <RouterLink v-for="r in zeilen" :key="r.id" :to="`/eingangsrechnungen/${r.id}`" class="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5 transition hover:bg-surface2">
          <component :is="r.format === 'PDF' || r.format === 'Papier' ? FileText : FileCode2" :size="18" class="shrink-0" :class="r.format === 'PDF' ? 'text-mute' : 'text-accent'" :title="r.format" />
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2"><span class="truncate font-medium">{{ r.lieferantName || 'Rechnungssteller fehlt' }}</span><span v-if="!r.lieferantId" class="text-xs text-warn">kein Lieferant</span></div>
            <div class="text-xs text-mute tnum">{{ r.rechnungsnr || 'ohne Nummer' }} · {{ de(r.rechnungsdatum) }}<template v-if="r.bestellreferenz"> · Bestellung {{ r.bestellreferenz }}</template> · {{ r.id }}</div>
          </div>
          <AlertTriangle v-if="r.hinweise.length" :size="15" class="text-warn" :title="r.hinweise.join('\n')" />
          <div class="text-right text-xs text-mute">fällig<br><span :class="r.faelligAm && r.faelligAm <= heute && ['Neu', 'Geprüft'].includes(r.status) ? 'font-semibold text-accent' : ''">{{ de(r.faelligAm) }}</span></div>
          <div class="w-28 text-right font-semibold tnum">{{ eur(r.brutto) }}</div>
          <StatusBadge :status="r.status" />
        </RouterLink>
      </div>
    </section>
  </div>
</template>
