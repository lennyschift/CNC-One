<script setup>
import { ref, computed, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Search, Workflow, Hash } from '@lucide/vue';
import Toggle from '../components/Toggle.vue';
import NumField from '../components/NumField.vue';
import StammNav from '../components/StammNav.vue';
import StammDialog from '../components/StammDialog.vue';
import PartImage from '../components/PartImage.vue';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import ArbeitsplanEditor from '../components/ArbeitsplanEditor.vue';
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
const suche = ref('');
const kundeFilter = ref('');
const liste = computed(() => store.listen.bauteil ?? []);
const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return liste.value.filter((b) => (!kundeFilter.value || b.kundeId === kundeFilter.value)
    && (!q || `${b.name} ${b.teilenummer} ${b.zeichnungsnr} ${b.material} ${kundenName(b.kundeId)}`.toLowerCase().includes(q)));
});
const kundenMitBauteil = computed(() => kunden.value.filter((k) => liste.value.some((b) => b.kundeId === k.id)));

const leer = () => ({ id: '', kundeId: kundeFilter.value, teilenummer: '', name: '', zeichnungsnr: '', revision: '', material: '', status: 'Aktiv', seriennummern: false, letzteSeriennummer: 0, arbeitsgaenge: [] });
const b = ref(null);
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

    <div v-auto-animate class="space-y-2">
      <button v-for="x in zeilen" :key="x.id" class="card flex w-full items-center gap-4 p-3.5 text-left transition hover:-translate-y-px hover:border-accent/40" @click="oeffnen(x)">
        <PartImage :teil="x" :groesse="48" />
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2"><span class="font-medium">{{ x.name || 'Ohne Bezeichnung' }}</span><span v-if="x.status === 'Gesperrt'" class="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] text-accent">gesperrt</span><span v-if="x.seriennummern" class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-[10px] text-mute"><Hash :size="10" /> Serie{{ x.letzteSeriennummer ? ` bis ${x.letzteSeriennummer}` : '' }}</span></div>
          <div class="truncate text-xs text-mute">{{ x.teilenummer }}<template v-if="x.zeichnungsnr"> · Zeichnung {{ x.zeichnungsnr }}</template><template v-if="x.revision"> · Rev. {{ x.revision }}</template><template v-if="x.material"> · {{ x.material }}</template></div>
          <div class="truncate text-xs text-mute">{{ kundenName(x.kundeId) }}</div>
        </div>
        <span class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-surface2 px-2.5 py-1 text-xs text-mute"><Workflow :size="13" /> {{ x.arbeitsgaenge.length ? `${x.arbeitsgaenge.length} Arbeitsgänge` : 'kein Arbeitsplan' }}</span>
      </button>
      <p v-if="!zeilen.length" class="card px-6 py-12 text-center text-sm text-mute">{{ store.listen.bauteil === null ? 'Lädt …' : liste.length ? 'Keine Treffer.' : 'Noch keine Bauteile. Sie entstehen auch automatisch, wenn ein Angebot ein Bauteil mit Teilenummer enthält.' }}</p>
    </div>

    <StammDialog v-if="b" :titel="neu ? 'Neues Bauteil' : (b.name || b.teilenummer)" :untertitel="neu ? '' : `${b.id} · ${kundenName(b.kundeId)}`" breite="900px" :neu="neu" :schreibgeschuetzt="!darf" :speichert="speichert" :gueltig="!!b.kundeId && !!b.teilenummer.trim()" @schliessen="b = null" @speichern="speichern" @loeschen="loeschen">
      <div class="flex gap-4">
        <PartImage :teil="b" :groesse="96" />
        <div class="grid flex-1 gap-3 sm:grid-cols-2">
          <CustomerCombobox v-model="b.kundeId" />
          <label class="block"><span class="label mb-1 block">Teilenummer</span><input v-model="b.teilenummer" class="field" autofocus /></label>
          <label class="block"><span class="label mb-1 block">Bezeichnung</span><input v-model="b.name" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Zeichnungsnummer</span><input v-model="b.zeichnungsnr" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Revision</span><input v-model="b.revision" class="field" placeholder="z. B. B" /></label>
          <label class="block"><span class="label mb-1 block">Werkstoff</span>
            <select v-model="b.material" class="field"><option value="">– keiner –</option><option v-for="m in materialien" :key="m.name" :value="m.name">{{ m.name }}</option></select>
          </label>
          <label class="block"><span class="label mb-1 block">Status</span><select v-model="b.status" class="field"><option>Aktiv</option><option>Gesperrt</option></select></label>
          <div class="flex flex-wrap items-end gap-4 sm:col-span-2">
            <Toggle v-model="b.seriennummern" klein label="Seriennummern führen" />
            <NumField v-if="b.seriennummern" v-model="b.letzteSeriennummer" label="Letzte vergebene Seriennummer" :decimals="0" class="w-56" hint="Setzt der nächste Auftrag fort" />
          </div>
        </div>
      </div>
      <section>
        <h3 class="mb-2 text-sm font-semibold">Arbeitsplan</h3>
        <ArbeitsplanEditor :arbeitsgaenge="b.arbeitsgaenge" :kunde-id="b.kundeId" :teilenummer="b.teilenummer" ohne-speichern />
      </section>
    </StammDialog>
  </div>
</template>
