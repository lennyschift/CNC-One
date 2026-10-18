<script setup>
import { ref, computed, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Search, Building2, Trash2, MapPin, UserRound } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import StammDialog from '../components/StammDialog.vue';
import Toggle from '../components/Toggle.vue';
import { useStammdaten } from '../stores/stammdaten.js';

const store = useStammdaten();
onMounted(() => store.laden('kunde'));

const suche = ref('');
const inaktive = ref(false);
const liste = computed(() => store.listen.kunde ?? []);
const ort = (k) => { const a = k.adressen.find((x) => x.standard) ?? k.adressen[0]; return a ? [a.plz, a.ort].filter(Boolean).join(' ') : ''; };
const kontakt = (k) => { const c = k.kontakte.find((x) => x.rechnungskontakt) ?? k.kontakte[0]; return c ? [c.vorname, c.nachname].filter(Boolean).join(' ') : ''; };
const zeilen = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return liste.value.filter((k) => (inaktive.value || k.aktiv) && (!q || `${k.name} ${k.kuerzel} ${k.id} ${ort(k)} ${kontakt(k)} ${k.ustId}`.toLowerCase().includes(q)));
});

const leerAdresse = () => ({ typ: 'Rechnung und Lieferung', strasse: '', plz: '', ort: '', land: '', standard: false });
const leerKontakt = () => ({ anrede: '', vorname: '', nachname: '', email: '', telefon: '', rechnungskontakt: false });
const leer = () => ({ id: '', name: '', kuerzel: '', aktiv: true, ustId: '', steuernummer: '', zahlungsbedingung: '', leitwegId: '', lieferantennr: '', adressen: [leerAdresse()], kontakte: [leerKontakt()] });

const k = ref(null);
const speichert = ref(false);
const neu = computed(() => !k.value?.id);
const darf = computed(() => store.darf('kunde'));
function oeffnen(x) { k.value = x ? JSON.parse(JSON.stringify(x)) : leer(); }
function standardAdresse(i) { k.value.adressen.forEach((a, j) => { a.standard = j === i; }); }
function rechnungsKontakt(i) { k.value.kontakte.forEach((c, j) => { c.rechnungskontakt = j === i && !c.rechnungskontakt; }); }
async function speichern() {
  speichert.value = true;
  const rec = await store.speichern('kunde', k.value);
  speichert.value = false;
  if (rec) k.value = null;
}
async function loeschen() { if (await store.loeschen('kunde', k.value.id)) k.value = null; }
</script>

<template>
  <div class="mx-auto max-w-[1100px]">
    <StammNav />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <p class="mr-auto text-sm text-mute">Firmen, für die Angebote, Aufträge und Rechnungen entstehen.</p>
      <label class="relative">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !w-60 !pl-9" placeholder="Kunde suchen …" />
      </label>
      <Toggle v-model="inaktive" klein label="Inaktive anzeigen" />
      <button v-if="darf" class="btn btn-primary" @click="oeffnen()"><Plus :size="16" /> Neuer Kunde</button>
    </div>

    <div class="card overflow-hidden">
      <div class="grid grid-cols-[minmax(200px,1.6fr)_80px_minmax(120px,1fr)_minmax(120px,1fr)_100px] items-center gap-4 border-b border-line bg-surface2 px-5 py-2.5 text-xs font-medium text-mute">
        <span>Name</span><span>Kürzel</span><span>Ort</span><span>Ansprechpartner</span><span>Nummer</span>
      </div>
      <div v-auto-animate>
        <button v-for="x in zeilen" :key="x.id" class="grid w-full grid-cols-[minmax(200px,1.6fr)_80px_minmax(120px,1fr)_minmax(120px,1fr)_100px] items-center gap-4 border-b border-line px-5 py-3 text-left text-sm transition last:border-0 hover:bg-surface2" @click="oeffnen(x)">
          <span class="flex items-center gap-2.5 font-medium"><Building2 :size="16" class="text-mute" />{{ x.name }}<span v-if="!x.aktiv" class="rounded-full bg-surface2 px-2 py-0.5 text-[10px] font-normal text-mute">inaktiv</span></span>
          <span class="text-mute">{{ x.kuerzel || '–' }}</span>
          <span class="truncate text-mute">{{ ort(x) || '–' }}</span>
          <span class="truncate text-mute">{{ kontakt(x) || '–' }}</span>
          <span class="text-mute tnum">{{ x.id }}</span>
        </button>
      </div>
      <p v-if="!zeilen.length" class="px-6 py-12 text-center text-sm text-mute">{{ store.listen.kunde === null ? 'Lädt …' : liste.length ? 'Keine Treffer.' : 'Noch keine Kunden.' }}</p>
    </div>

    <StammDialog v-if="k" :titel="neu ? 'Neuer Kunde' : k.name" :untertitel="neu ? '' : k.id" breite="760px" :neu="neu" :schreibgeschuetzt="!darf" :speichert="speichert" :gueltig="!!k.name.trim()" @schliessen="k = null" @speichern="speichern" @loeschen="loeschen">
      <div class="grid gap-3 sm:grid-cols-[1fr_140px]">
        <label class="block"><span class="label mb-1 block">Name der Firma</span><input v-model="k.name" class="field" autofocus /></label>
        <label class="block"><span class="label mb-1 block">Kürzel</span><input v-model="k.kuerzel" class="field" placeholder="z. B. MUM" /></label>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block"><span class="label mb-1 block">USt-IdNr.</span><input v-model="k.ustId" class="field" placeholder="DE123456789" /></label>
        <label class="block"><span class="label mb-1 block">Steuernummer</span><input v-model="k.steuernummer" class="field" /></label>
        <label class="block"><span class="label mb-1 block">Zahlungsbedingung</span><input v-model="k.zahlungsbedingung" class="field" placeholder="z. B. 14 Tage netto" /></label>
        <label class="block"><span class="label mb-1 block">Leitweg-ID (E-Rechnung)</span><input v-model="k.leitwegId" class="field" /></label>
        <label class="block"><span class="label mb-1 block">Unsere Lieferantennummer beim Kunden</span><input v-model="k.lieferantennr" class="field" /></label>
      </div>

      <section>
        <div class="mb-2 flex items-center justify-between"><h3 class="flex items-center gap-2 text-sm font-semibold"><MapPin :size="15" class="text-accent" /> Adressen</h3><button type="button" class="btn !py-1 !text-xs" @click="k.adressen.push(leerAdresse())"><Plus :size="13" /> Adresse</button></div>
        <div class="space-y-2">
          <div v-for="(a, i) in k.adressen" :key="i" class="rounded-xl border border-line p-3">
            <div class="grid gap-2 sm:grid-cols-[1fr_1fr]">
              <select v-model="a.typ" class="field"><option>Rechnung und Lieferung</option><option>Rechnung</option><option>Lieferung</option></select>
              <input v-model="a.strasse" class="field" placeholder="Straße und Hausnummer" />
              <div class="grid grid-cols-[90px_1fr] gap-2"><input v-model="a.plz" class="field" placeholder="PLZ" /><input v-model="a.ort" class="field" placeholder="Ort" /></div>
              <input v-model="a.land" class="field" placeholder="Land (leer = Deutschland)" />
            </div>
            <div class="mt-2 flex items-center justify-between">
              <label class="flex cursor-pointer items-center gap-2 text-xs text-mute"><input type="radio" :checked="a.standard" class="accent-[var(--accent)]" @change="standardAdresse(i)" /> Standardadresse</label>
              <button type="button" class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:text-accent" title="Adresse entfernen" @click="k.adressen.splice(i, 1)"><Trash2 :size="14" /></button>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="mb-2 flex items-center justify-between"><h3 class="flex items-center gap-2 text-sm font-semibold"><UserRound :size="15" class="text-accent" /> Ansprechpartner</h3><button type="button" class="btn !py-1 !text-xs" @click="k.kontakte.push(leerKontakt())"><Plus :size="13" /> Kontakt</button></div>
        <div class="space-y-2">
          <div v-for="(c, i) in k.kontakte" :key="i" class="rounded-xl border border-line p-3">
            <div class="grid gap-2 sm:grid-cols-[100px_1fr_1fr]">
              <select v-model="c.anrede" class="field"><option value="">–</option><option>Herr</option><option>Frau</option></select>
              <input v-model="c.vorname" class="field" placeholder="Vorname" />
              <input v-model="c.nachname" class="field" placeholder="Nachname" />
              <span class="hidden sm:block" />
              <input v-model="c.email" class="field" placeholder="E-Mail" />
              <input v-model="c.telefon" class="field" placeholder="Telefon" />
            </div>
            <div class="mt-2 flex items-center justify-between">
              <label class="flex cursor-pointer items-center gap-2 text-xs text-mute"><input type="checkbox" :checked="c.rechnungskontakt" class="accent-[var(--accent)]" @change="rechnungsKontakt(i)" /> Rechnungskontakt (Empfänger von Angeboten und Rechnungen)</label>
              <button type="button" class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:text-accent" title="Kontakt entfernen" @click="k.kontakte.splice(i, 1)"><Trash2 :size="14" /></button>
            </div>
          </div>
        </div>
      </section>

      <Toggle v-model="k.aktiv" label="Aktiv (in Auswahllisten sichtbar)" />
    </StammDialog>
  </div>
</template>
