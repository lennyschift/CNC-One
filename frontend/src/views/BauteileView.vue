<script setup>
import FilterLeiste from '../components/FilterLeiste.vue';
import ListenTabelle from '../components/ListenTabelle.vue';
import { ref, computed, onMounted } from 'vue';
import { Plus, Search, Workflow, Hash, FileText, Box, History } from '@lucide/vue';
import Toggle from '../components/Toggle.vue';
import NumField from '../components/NumField.vue';
import SerienFeld from '../components/SerienFeld.vue';
import { formatNr } from '../lib/serien.js';
import StammNav from '../components/StammNav.vue';
import StammDialog from '../components/StammDialog.vue';
import PartImage from '../components/PartImage.vue';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import ArbeitsplanEditor from '../components/ArbeitsplanEditor.vue';
import BauteilHistorie from '../components/BauteilHistorie.vue';
import AehnlicheBauteile from '../components/AehnlicheBauteile.vue';
import TeilefamilieKarte from '../components/TeilefamilieKarte.vue';
import { repo } from '../data/repo.js';
import { useStammdaten } from '../stores/stammdaten.js';

const store = useStammdaten();
const kunden = ref([]);
const materialien = ref([]);
onMounted(async () => {
  store.laden('bauteil');
  [kunden.value, materialien.value] = await Promise.all([repo.kunden.liste(), repo.materialien.liste()]);
});

const kundenName = (id) => kunden.value.find((k) => k.id === id)?.name ?? id;
const SPALTEN = [
  { key: 'name', label: 'Bezeichnung' },
  { key: 'teilenummer', label: 'Teilenummer' },
  { key: 'zeichnungsnr', label: 'Zeichnung' },
  { key: 'material', label: 'Werkstoff' },
  { key: 'kunde', label: 'Kunde', wert: (x) => kundenName(x.kundeId) },
  { key: 'serie', label: 'Seriennr.', wert: (x) => (x.seriennummern ? 1 : 0) },
  { key: 'plan', label: 'Arbeitsplan', wert: (x) => x.arbeitsgaenge.length },
];
const suche = ref('');
const kundeFilter = ref('');
const liste = computed(() => store.listen.bauteil ?? []);
// Filter (anpassbar, siehe FilterLeiste): erst die Schnellfilter oben, dann die gespeicherten/angehefteten Filter
const zeilen = ref([]);
const beschriftungen = {'kundeName': 'Kunde', 'name': 'Bezeichnung', 'teilenummer': 'Teilenummer', 'material': 'Werkstoff', 'status': 'Status', 'seriennummern': 'Mit Seriennummern', 'revision': 'Revision'};
const vorgefiltert = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return liste.value.filter((b) => (!kundeFilter.value || b.kundeId === kundeFilter.value)
    && (!q || `${b.name} ${b.teilenummer} ${b.zeichnungsnr} ${b.material} ${kundenName(b.kundeId)}`.toLowerCase().includes(q)));
});
const kundenMitBauteil = computed(() => kunden.value.filter((k) => liste.value.some((b) => b.kundeId === k.id)));

const leer = () => ({ id: '', kundeId: kundeFilter.value, teilenummer: '', name: '', zeichnungsnr: '', revision: '', material: '', status: 'Aktiv', notizIntern: '', seriennummern: false, serienStellen: 4, letzteSeriennummer: 0, arbeitsgaenge: [] });
const b = ref(null);
const revisionsNamen = computed(() => [...new Set((b.value?.revisionen ?? []).map((r) => r.revision).filter(Boolean))]);
const speichert = ref(false);
const neu = computed(() => !b.value?.id);
const darf = computed(() => store.darf('bauteil'));
function oeffnen(x) { b.value = x ? JSON.parse(JSON.stringify(x)) : leer(); }
async function speichern() {
  speichert.value = true;
  const rec = await store.speichern('bauteil', b.value);
  speichert.value = false;
  if (rec) b.value = null;
}
async function loeschen() { if (await store.loeschen('bauteil', b.value.id)) b.value = null; }
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <StammNav />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <p class="mr-auto text-sm text-mute">Bauteile der Kunden. Ein gespeicherter Arbeitsplan gilt automatisch für neue Angebote und Aufträge.</p>
      <select v-model="kundeFilter" class="field !w-auto"><option value="">Alle Kunden</option><option v-for="k in kundenMitBauteil" :key="k.id" :value="k.id">{{ k.name }}</option></select>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-60 !pl-9" placeholder="Bauteil suchen …" />
      </label>
      <button v-if="darf" class="btn btn-primary" @click="oeffnen()"><Plus :size="16" /> Neues Bauteil</button>
    </div>

    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="bauteile" :beschriftungen="beschriftungen" :standard-angeheftet="['material']" />
    <ListenTabelle :spalten="SPALTEN" :zeilen="zeilen" min-breite="1000px" @oeffnen="oeffnen">
      <template #name="{ x }"><div class="flex items-center gap-3"><PartImage :teil="x" :groesse="36" /><div class="min-w-0"><div class="flex flex-wrap items-center gap-1.5"><span class="truncate font-medium">{{ x.name || 'Ohne Bezeichnung' }}</span><span v-if="x.status === 'Gesperrt'" class="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] text-accent">gesperrt</span></div></div></div></template>
      <template #teilenummer="{ x }"><span class="tnum">{{ x.teilenummer || '–' }}</span></template>
      <template #zeichnungsnr="{ x }"><span class="tnum">{{ x.zeichnungsnr || '–' }}</span><span v-if="x.revision" class="ml-1 text-xs text-mute">Rev. {{ x.revision }}</span></template>
      <template #material="{ x }">{{ x.material || '–' }}</template>
      <template #kunde="{ x }">{{ kundenName(x.kundeId) }}</template>
      <template #serie="{ x }"><span v-if="x.seriennummern" class="inline-flex items-center gap-1 text-xs"><Hash :size="11" class="text-mute" />{{ x.letzteSeriennummer ? `bis ${formatNr(x.letzteSeriennummer, x.serienStellen)}` : 'ja' }}</span><span v-else class="text-mute">–</span></template>
      <template #plan="{ x }"><span class="flex max-w-[220px] items-center gap-1 truncate text-xs" :title="x.arbeitsgaenge.map((a) => a.name).join(' → ')" :class="x.arbeitsgaenge.length ? '' : 'text-mute'"><Workflow :size="12" class="text-mute" />{{ x.arbeitsgaenge.length ? x.arbeitsgaenge.map((a) => a.name).filter(Boolean).join(' → ') : 'kein Arbeitsplan' }}</span></template>
      <template #leer><p class="px-6 py-12 text-center text-sm text-mute">{{ store.listen.bauteil === null ? 'Lädt …' : liste.length ? 'Keine Treffer.' : 'Noch keine Bauteile. Sie entstehen auch automatisch, wenn ein Angebot ein Bauteil mit Teilenummer enthält.' }}</p></template>
    </ListenTabelle>

    <StammDialog v-if="b" :titel="neu ? 'Neues Bauteil' : (b.name || b.teilenummer)" :untertitel="neu ? '' : `${b.id} · ${kundenName(b.kundeId)}`" breite="900px" :neu="neu" :schreibgeschuetzt="!darf" :speichert="speichert" :gueltig="!!b.kundeId && !!b.teilenummer.trim()" @schliessen="b = null" @speichern="speichern" @loeschen="loeschen">
      <div class="flex gap-4">
        <PartImage :teil="b" :groesse="96" />
        <div class="grid flex-1 gap-3 sm:grid-cols-2">
          <CustomerCombobox v-model="b.kundeId" />
          <label class="block"><span class="label mb-1 block">Teilenummer</span><input v-model="b.teilenummer" class="field" autofocus /></label>
          <label class="block"><span class="label mb-1 block">Bezeichnung</span><input v-model="b.name" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Zeichnungsnummer</span><input v-model="b.zeichnungsnr" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Revision</span><input v-model="b.revision" class="field" placeholder="z. B. B" list="bauteil-revisionen" />
            <datalist id="bauteil-revisionen"><option v-for="r in revisionsNamen" :key="r" :value="r" /></datalist>
          </label>
          <label class="block"><span class="label mb-1 block">Rohmaterial</span>
            <select v-model="b.material" class="field"><option value="">– keiner –</option><option v-for="m in materialien" :key="m.name" :value="m.name">{{ m.name }}</option></select>
          </label>
          <label class="block"><span class="label mb-1 block">Status</span><select v-model="b.status" class="field"><option>Aktiv</option><option>Gesperrt</option></select></label>
          <label class="block sm:col-span-2"><span class="label mb-1 block">Interne Notiz <span class="font-normal normal-case text-mute">(steht nicht auf Belegen)</span></span><textarea v-model="b.notizIntern" rows="2" class="field min-h-[56px] resize-y" /></label>
          <div class="flex flex-wrap items-end gap-4 sm:col-span-2">
            <Toggle v-model="b.seriennummern" klein label="Seriennummern führen" />
            <NumField v-if="b.seriennummern" v-model="b.serienStellen" label="Stellen der Seriennummer" :decimals="0" :min="1" class="w-44" hint="immer mit führenden Nullen" />
            <SerienFeld v-if="b.seriennummern" :model-value="b.letzteSeriennummer ? formatNr(b.letzteSeriennummer, b.serienStellen) : ''" :stellen="b.serienStellen" label="Letzte vergebene Seriennummer" hint="Der nächste Auftrag macht hier weiter" class="w-48" @update:model-value="b.letzteSeriennummer = Number($event) || 0" />
          </div>
        </div>
      </div>
      <!-- Frühere Angebote, Aufträge und Fertigungen (aus den Belegen gelesen) -->
      <BauteilHistorie v-if="b.id" :bauteil-id="b.id" />
      <TeilefamilieKarte v-if="b.id && b.teilefamilie" :bauteil-id="b.id" :aktionen="darf" />
      <AehnlicheBauteile v-if="b.id" :bauteil-id="b.id" :kunde-id="b.kundeId" :teil="{ teilenummer: b.teilenummer, name: b.name, zeichnungsnr: b.zeichnungsnr, material: b.material, vorschaubild: b.vorschaubild }" :aktionen="darf" />
      <section v-if="b.revisionen?.length">
        <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold"><History :size="15" class="text-accent" /> Revisionen und Dateien</h3>
        <div class="divide-y divide-line rounded-xl border border-line">
          <div v-for="(r, i) in b.revisionen" :key="i" class="flex flex-wrap items-center gap-3 px-3 py-2 text-sm" :class="r.aeltereFassung ? 'opacity-60' : ''">
            <PartImage :teil="b" :bild="r.vorschaubild" :groesse="36" />
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium">Rev. {{ r.revision || '–' }}</span>
                <span v-if="r.aktuell" class="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">aktuell</span>
                <span v-else-if="r.aeltereFassung" class="rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute">ältere Fassung</span>
              </div>
              <div class="text-xs text-mute">
                <template v-if="r.datum">{{ new Date(r.datum.replace(' ', 'T')).toLocaleDateString('de-DE') }}</template><template v-if="r.angebot"> · mit Angebot {{ r.angebot }}</template>
              </div>
            </div>
            <a v-if="r.zeichnung" :href="r.zeichnung" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-xs text-accent hover:underline"><FileText :size="13" /> Zeichnung</a>
            <a v-if="r.stepDatei" :href="r.stepDatei" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-xs text-accent hover:underline"><Box :size="13" /> 3D-Modell</a>
          </div>
        </div>
        <p class="mt-1.5 text-xs text-mute">Neue Revisionen und Dateien kommen mit der Zeichnung aus der Workbench. Eine hier gewählte Revision wird wieder die aktuelle.</p>
      </section>
      <section>
        <h3 class="mb-2 text-sm font-semibold">Arbeitsplan</h3>
        <ArbeitsplanEditor :arbeitsgaenge="b.arbeitsgaenge" :kunde-id="b.kundeId" :teilenummer="b.teilenummer" ohne-speichern />
      </section>
    </StammDialog>
  </div>
</template>
