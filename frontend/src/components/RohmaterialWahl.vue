<script setup>
// Rohmaterial in Stufen wählen: ISO-Gruppe → Werkstoff → Zustand → Form → Ausführung → Abmessung. Alles Auswahl aus den
// Stammdaten; in jeder Stufe legt „+ Neu“ direkt einen Eintrag an (gilt danach für alle). `wahl` wird direkt geändert:
// { werkstoff, zustand, form, ausfuehrung, abmessungId }. `chargen` (optional) markiert Abmessungen, die im Lager liegen.
import { ref, computed, watch, nextTick } from 'vue';
import { Search, Check, Plus, X, Info, Unlock } from '@lucide/vue';
import FormSymbol from './FormSymbol.vue';
import NumField from './NumField.vue';
import { ISO_GRUPPEN, isoGruppe } from '../lib/iso.js';
import { FORMEN, formenVon, ausfuehrungenFuer, abmessungenFuer } from '../lib/werkstoffbaum.js';
import { zahl } from '../lib/format.js';
import { useWerkstoff } from '../stores/werkstoff.js';

const props = defineProps({
  wahl: { type: Object, required: true },
  nurAnsicht: { type: Boolean, default: false },
  chargen: { type: Array, default: () => [] },
});
const ws = useWerkstoff();

const gruppeVon = (m) => isoGruppe(m.name, m.isoGruppe)?.code ?? '';
const w = computed(() => ws.werkstoff(props.wahl.werkstoff));
const iso = ref(w.value ? gruppeVon(w.value) : 'P');
const isoInfo = computed(() => ISO_GRUPPEN[iso.value] ?? ISO_GRUPPEN.P); // gerade angesehene Gruppe (für neue Werkstoffe)
const wIso = computed(() => (w.value ? gruppeVon(w.value) : '') || iso.value); // Gruppe des gewählten Werkstoffs
const isoW = computed(() => ISO_GRUPPEN[wIso.value] ?? ISO_GRUPPEN.P);
const suche = ref('');
const anzahlJe = (code) => ws.materialien.filter((m) => gruppeVon(m) === code).length;
const werkstoffe = computed(() => {
  const q = suche.value.trim().toLowerCase();
  if (q) return ws.materialien.filter((m) => [m.name, m.kurz, ...(m.schreibweisen ?? [])].some((x) => (x || '').toLowerCase().includes(q)));
  return ws.materialien.filter((m) => gruppeVon(m) === iso.value);
});
const zustaende = computed(() => w.value?.zustaende ?? []);
const formen = computed(() => formenVon(w.value));
const ausfuehrungen = computed(() => ausfuehrungenFuer(ws.baum, props.wahl.form, wIso.value));
const abmessungen = computed(() => abmessungenFuer(ws.baum, props.wahl.form));
const imLager = (a) => props.chargen.some((c) => c.werkstoff === props.wahl.werkstoff && c.abmessung === a.id && (!props.wahl.zustand || c.zustand === props.wahl.zustand));

function isoWaehlen(code) {
  if (props.nurAnsicht) return;
  iso.value = code;
  suche.value = '';
}
function werkstoffWaehlen(m) {
  if (props.nurAnsicht) return;
  props.wahl.werkstoff = m.name;
  iso.value = gruppeVon(m) || iso.value;
  suche.value = '';
}
// Abhängige Stufen bereinigen: nur gültige Kombinationen bleiben stehen
watch(w, (x) => {
  if (!x || props.nurAnsicht) return;
  if (props.wahl.zustand && !x.zustaende.includes(props.wahl.zustand)) props.wahl.zustand = '';
  if (!props.wahl.zustand && x.zustaende.length === 1) props.wahl.zustand = x.zustaende[0];
  if (!formen.value.includes(props.wahl.form)) props.wahl.form = formen.value[0];
}, { immediate: true });
watch(() => [props.wahl.form, wIso.value, ws.baum], () => {
  if (props.nurAnsicht) return;
  if (props.wahl.ausfuehrung && !ausfuehrungen.value.some((a) => a.name === props.wahl.ausfuehrung)) props.wahl.ausfuehrung = '';
  if (!props.wahl.ausfuehrung && ausfuehrungen.value.length) props.wahl.ausfuehrung = ausfuehrungen.value[0].name;
  if (props.wahl.abmessungId && !abmessungen.value.some((a) => a.id === props.wahl.abmessungId)) props.wahl.abmessungId = '';
}, { immediate: true });

// ---- „+ Neu“ je Stufe (immer nur eins offen)
const neu = ref(null);
const speichert = ref(false);
async function oeffneNeu(stufe, werte = {}) {
  neu.value = { stufe, ...werte };
  await nextTick();
  document.querySelector('[data-neu-fokus]')?.focus();
}
async function anlegen() {
  const x = neu.value;
  speichert.value = true;
  try {
    if (x.stufe === 'werkstoff') {
      const m = await ws.werkstoffAnlegen({ name: x.name, iso: iso.value, kurz: x.kurz, dichte: x.dichte, preisKg: x.preisKg });
      if (m) { props.wahl.werkstoff = m.name; neu.value = null; }
    } else if (x.stufe === 'zustand') {
      const z = await ws.zustandHinzu(props.wahl.werkstoff, x.code, x.text);
      if (z) { props.wahl.zustand = z.code; neu.value = null; }
    } else if (x.stufe === 'form') {
      if (await ws.formFreigeben(props.wahl.werkstoff, x.form)) { props.wahl.form = x.form; neu.value = null; }
    } else if (x.stufe === 'ausfuehrung') {
      const a = await ws.ausfuehrungHinzu(props.wahl.form, x.name, x.nurGruppe ? wIso.value : '');
      if (a) { props.wahl.ausfuehrung = a.name; neu.value = null; }
    } else if (x.stufe === 'abmessung') {
      const a = await ws.abmessungHinzu(props.wahl.form, x.m1, x.m2);
      if (a) { props.wahl.abmessungId = a.id; neu.value = null; }
    }
  } finally {
    speichert.value = false;
  }
}
// Zustände, die es schon gibt, aber nicht bei diesem Werkstoff: zum schnellen Übernehmen
const andereZustaende = computed(() => ws.baum.zustaende.filter((z) => !zustaende.value.includes(z.code)));
const formInfo = computed(() => FORMEN.find((f) => f.id === props.wahl.form) ?? FORMEN[0]);
const neuGueltig = computed(() => {
  const x = neu.value;
  if (!x) return false;
  if (x.stufe === 'werkstoff') return !!x.name?.trim();
  if (x.stufe === 'zustand') return !!x.code?.trim();
  if (x.stufe === 'ausfuehrung') return !!x.name?.trim();
  if (x.stufe === 'abmessung') return x.m1 > 0 && (!formInfo.value.m2 || x.m2 > 0);
  return true;
});
const tasten = (e) => { if (e.key === 'Enter' && neuGueltig.value) anlegen(); if (e.key === 'Escape') { e.stopPropagation(); neu.value = null; } };
</script>

<template>
  <div class="space-y-4" @keydown="neu && tasten($event)">
    <!-- 1 ISO-Gruppe -->
    <section>
      <div class="stufe"><span class="nr">1</span> ISO-Werkstoffgruppe</div>
      <div class="grid grid-cols-3 gap-1.5 sm:grid-cols-6">
        <button v-for="g in ISO_GRUPPEN" :key="g.code" type="button" class="iso-kachel" :class="iso === g.code && !suche ? 'aktiv' : ''" :style="{ '--iso': g.farbe }" :title="g.name" @click="isoWaehlen(g.code)">
          <span class="grid h-9 w-9 place-items-center rounded-lg text-lg font-bold" :style="{ background: g.farbe, color: g.schrift }">{{ g.code }}</span>
          <span class="text-[10.5px] leading-tight text-mute">{{ g.name }}</span>
          <span class="text-[10px] text-mute tnum">{{ anzahlJe(g.code) }}</span>
        </button>
      </div>
    </section>

    <!-- 2 Werkstoff -->
    <section>
      <div class="stufe"><span class="nr">2</span> Werkstoff
        <label class="relative ml-auto block w-full max-w-[260px] font-normal">
          <Search :size="14" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
          <input v-model="suche" class="field !py-1.5 !pl-8 text-sm" placeholder="Suchen: 3.4365, V2A, AlMg …" />
        </label>
      </div>
      <div class="grid max-h-[240px] gap-1.5 overflow-auto pr-1 sm:grid-cols-2 xl:grid-cols-3">
        <button v-for="m in werkstoffe" :key="m.name" type="button" class="wahl flex items-center gap-2.5 text-left" :class="wahl.werkstoff === m.name ? 'aktiv' : ''" @click="werkstoffWaehlen(m)">
          <span class="grid h-7 w-7 shrink-0 place-items-center rounded-md text-xs font-bold" :style="isoGruppe(m.name, m.isoGruppe) ? { background: isoGruppe(m.name, m.isoGruppe).farbe, color: isoGruppe(m.name, m.isoGruppe).schrift } : {}" :class="isoGruppe(m.name, m.isoGruppe) ? '' : 'bg-surface2 text-mute'">{{ gruppeVon(m) || '?' }}</span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-semibold">{{ m.name }}<span v-if="m.kurz" class="font-normal text-mute"> · {{ m.kurz }}</span></span>
            <span class="block truncate text-[10.5px] text-mute">{{ m.zustaende?.length ? m.zustaende.join(' · ') : 'noch ohne Zustände' }}<template v-if="m.dichte"> · {{ zahl(m.dichte, 2) }} g/cm³</template></span>
          </span>
          <Check v-if="wahl.werkstoff === m.name" :size="14" class="shrink-0 text-accent" />
        </button>
        <button v-if="!nurAnsicht && neu?.stufe !== 'werkstoff' && !suche" type="button" class="wahl neu-knopf" @click="oeffneNeu('werkstoff', { name: '', kurz: '', dichte: 0, preisKg: 0 })"><Plus :size="14" /> Neuer Werkstoff in {{ isoInfo.code }}</button>
      </div>
      <p v-if="!werkstoffe.length && suche" class="py-3 text-center text-xs text-mute">Kein Werkstoff gefunden.</p>
      <div v-if="neu?.stufe === 'werkstoff'" class="neu-box">
        <span class="grid h-7 w-7 shrink-0 place-items-center rounded-md text-xs font-bold" :style="{ background: isoInfo.farbe, color: isoInfo.schrift }">{{ isoInfo.code }}</span>
        <label class="min-w-[150px] flex-1"><span class="label">Werkstoff (Nr. / EN)</span><input v-model="neu.name" data-neu-fokus class="field !py-1.5 text-sm" placeholder="z. B. 1.4542 oder EN AW-6061" /></label>
        <label class="min-w-[130px] flex-1"><span class="label">Kurzname</span><input v-model="neu.kurz" class="field !py-1.5 text-sm" placeholder="z. B. X5CrNiCuNb16-4" /></label>
        <div class="w-28"><NumField v-model="neu.dichte" label="Dichte" unit="g/cm³" :decimals="2" /></div>
        <div class="w-28"><NumField v-model="neu.preisKg" label="Preis" unit="€/kg" /></div>
        <div class="flex gap-1 self-end"><button type="button" class="btn btn-primary !py-1.5 text-xs" :disabled="!neuGueltig || speichert" @click="anlegen"><Check :size="13" /> Anlegen</button><button type="button" class="btn !py-1.5" title="Abbrechen" @click="neu = null"><X :size="13" /></button></div>
      </div>
    </section>

    <template v-if="w">
      <!-- 3 Zustand · 4 Form -->
      <div class="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section>
          <div class="stufe"><span class="nr">3</span> Zustand</div>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="z in zustaende" :key="z" type="button" class="wahl !px-2.5 !py-1.5 text-left" :class="wahl.zustand === z ? 'aktiv' : ''" :title="ws.zustandText[z] || ''" @click="!nurAnsicht && (wahl.zustand = wahl.zustand === z ? '' : z)">
              <span class="block text-sm font-semibold">{{ z }}</span>
              <span v-if="ws.zustandText[z]" class="block max-w-[150px] truncate text-[10px] leading-tight text-mute">{{ ws.zustandText[z] }}</span>
            </button>
            <button v-if="!nurAnsicht && neu?.stufe !== 'zustand'" type="button" class="wahl neu-knopf !py-1.5" @click="oeffneNeu('zustand', { code: '', text: '' })"><Plus :size="13" /> Neu</button>
          </div>
          <div v-if="neu?.stufe === 'zustand'" class="neu-box">
            <label class="w-28"><span class="label">Zustand</span><input v-model="neu.code" data-neu-fokus class="field !py-1.5 text-sm" placeholder="z. B. T6511" list="zustaende-alle" /></label>
            <datalist id="zustaende-alle"><option v-for="z in andereZustaende" :key="z.code" :value="z.code">{{ z.beschreibung }}</option></datalist>
            <label class="min-w-[150px] flex-1"><span class="label">Beschreibung (bei neuem Zustand)</span><input v-model="neu.text" class="field !py-1.5 text-sm" placeholder="z. B. lösungsgeglüht, gereckt" /></label>
            <div class="flex gap-1 self-end"><button type="button" class="btn btn-primary !py-1.5 text-xs" :disabled="!neuGueltig || speichert" @click="anlegen"><Check :size="13" /> Hinzufügen</button><button type="button" class="btn !py-1.5" title="Abbrechen" @click="neu = null"><X :size="13" /></button></div>
            <div v-if="andereZustaende.length" class="flex w-full flex-wrap gap-1"><span class="text-[11px] text-mute">Vorhandene übernehmen:</span>
              <button v-for="z in andereZustaende.slice(0, 18)" :key="z.code" type="button" class="rounded-full border border-line px-2 py-0.5 text-[11px] hover:border-accent" :title="z.beschreibung" @click="neu.code = z.code; anlegen()">{{ z.code }}</button>
            </div>
          </div>
          <p v-if="!zustaende.length && neu?.stufe !== 'zustand'" class="mt-1.5 text-[11px] text-mute">Für {{ w.name }} sind noch keine Zustände hinterlegt.</p>
        </section>
        <section>
          <div class="stufe"><span class="nr">4</span> Form</div>
          <div class="grid grid-cols-6 gap-1.5">
            <button v-for="f in FORMEN" :key="f.id" type="button" class="wahl flex flex-col items-center gap-0.5 !px-1 !py-2" :class="[wahl.form === f.id ? 'aktiv' : '', formen.includes(f.id) ? '' : 'gesperrt']" :title="formen.includes(f.id) ? f.label : `${f.label}: für ${w.name} nicht hinterlegt – klicken zum Freigeben`" @click="nurAnsicht ? null : formen.includes(f.id) ? (wahl.form = f.id) : oeffneNeu('form', { form: f.id })">
              <FormSymbol :form="f.id" :groesse="28" :farbe="wahl.form === f.id ? isoW.farbe : ''" :class="wahl.form === f.id ? '' : 'text-mute'" />
              <span class="text-[10.5px]">{{ f.label }}</span>
            </button>
          </div>
          <div v-if="neu?.stufe === 'form'" class="neu-box">
            <Unlock :size="15" class="text-mute" /><span class="text-sm">{{ neu.form }} ist für {{ w.name }} nicht hinterlegt.</span>
            <div class="ml-auto flex gap-1"><button type="button" class="btn btn-primary !py-1.5 text-xs" :disabled="speichert" @click="anlegen"><Check :size="13" /> Freigeben</button><button type="button" class="btn !py-1.5" title="Abbrechen" @click="neu = null"><X :size="13" /></button></div>
          </div>
        </section>
      </div>

      <!-- 5 Ausführung -->
      <section>
        <div class="stufe"><span class="nr">5</span> Ausführung <span class="font-normal text-mute">· {{ formInfo.label }}</span></div>
        <div class="flex flex-wrap gap-1.5">
          <button v-for="a in ausfuehrungen" :key="a.id" type="button" class="wahl !px-3 !py-1.5 text-sm" :class="wahl.ausfuehrung === a.name ? 'aktiv' : ''" @click="!nurAnsicht && (wahl.ausfuehrung = a.name)">{{ a.name }}</button>
          <button v-if="!nurAnsicht && neu?.stufe !== 'ausfuehrung'" type="button" class="wahl neu-knopf !py-1.5" @click="oeffneNeu('ausfuehrung', { name: '', nurGruppe: false })"><Plus :size="13" /> Neu</button>
        </div>
        <div v-if="neu?.stufe === 'ausfuehrung'" class="neu-box">
          <label class="min-w-[180px] flex-1"><span class="label">Ausführung für {{ formInfo.label }}</span><input v-model="neu.name" data-neu-fokus class="field !py-1.5 text-sm" placeholder="z. B. geschliffen h6" /></label>
          <label class="flex items-center gap-1.5 self-end pb-2 text-xs text-mute"><input v-model="neu.nurGruppe" type="checkbox" class="accent-[var(--accent)]" /> nur für ISO {{ isoW.code }}</label>
          <div class="flex gap-1 self-end"><button type="button" class="btn btn-primary !py-1.5 text-xs" :disabled="!neuGueltig || speichert" @click="anlegen"><Check :size="13" /> Anlegen</button><button type="button" class="btn !py-1.5" title="Abbrechen" @click="neu = null"><X :size="13" /></button></div>
        </div>
      </section>

      <!-- 6 Abmessung -->
      <section>
        <div class="stufe"><span class="nr">6</span> Abmessung <span class="font-normal text-mute">· {{ formInfo.label }}{{ formInfo.m2 ? ` (${formInfo.m1} × ${formInfo.m2})` : ` (${formInfo.m1})` }}</span></div>
        <div class="flex flex-wrap gap-1">
          <button v-for="a in abmessungen" :key="a.id" type="button" class="mas tnum" :class="wahl.abmessungId === a.id ? 'aktiv' : ''" :style="wahl.abmessungId === a.id ? { '--iso': isoW.farbe, color: isoW.schrift } : {}" @click="!nurAnsicht && (wahl.abmessungId = a.id)">
            {{ a.text }}<span v-if="imLager(a)" class="lager" title="Im Rohmaterial-Lager vorhanden" />
          </button>
          <button v-if="!nurAnsicht && neu?.stufe !== 'abmessung'" type="button" class="mas neu-knopf" @click="oeffneNeu('abmessung', { m1: 0, m2: 0 })"><Plus :size="12" /> Neu</button>
        </div>
        <div v-if="neu?.stufe === 'abmessung'" class="neu-box">
          <FormSymbol :form="wahl.form" :groesse="24" class="text-mute" />
          <div class="w-32"><NumField v-model="neu.m1" :label="formInfo.m1" unit="mm" :decimals="1" /></div>
          <div v-if="formInfo.m2" class="w-32"><NumField v-model="neu.m2" :label="formInfo.m2" unit="mm" :decimals="1" /></div>
          <div class="flex gap-1 self-end"><button type="button" class="btn btn-primary !py-1.5 text-xs" :disabled="!neuGueltig || speichert" @click="anlegen"><Check :size="13" /> Anlegen</button><button type="button" class="btn !py-1.5" title="Abbrechen" @click="neu = null"><X :size="13" /></button></div>
        </div>
        <p class="mt-1.5 flex items-center gap-1.5 text-[11px] text-mute"><template v-if="chargen.length"><span class="lager !static" /> im Lager · </template><Info :size="11" /> Neue Abmessungen gelten danach für alle Werkstoffe dieser Form.</p>
      </section>
    </template>
    <p v-else class="rounded-xl bg-surface2 px-4 py-3 text-sm text-mute">Erst einen Werkstoff wählen.</p>
  </div>
</template>

<style scoped>
.stufe { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; font-size: 0.82rem; font-weight: 600; }
.nr { display: grid; place-items: center; width: 1.25rem; height: 1.25rem; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--line); font-size: 0.68rem; color: var(--mute); }
.wahl { border: 1px solid var(--line); border-radius: 0.7rem; background: var(--surface); padding: 0.45rem 0.6rem; transition: border-color .15s, background .15s; }
.wahl:hover { border-color: color-mix(in srgb, var(--mute) 45%, var(--line)); }
.wahl.aktiv { border-color: var(--accent); background: var(--accent-soft); }
.wahl.gesperrt { opacity: 0.35; }
.wahl.gesperrt:hover { opacity: 0.7; }
.neu-knopf { display: inline-flex; align-items: center; justify-content: center; gap: 0.3rem; border-style: dashed; color: var(--mute); font-size: 0.78rem; }
.neu-knopf:hover { color: var(--accent); border-color: var(--accent); }
.neu-box { margin-top: 0.5rem; display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; border: 1px dashed var(--accent); border-radius: 0.8rem; background: color-mix(in srgb, var(--accent-soft) 45%, var(--surface)); padding: 0.6rem 0.75rem; }
.iso-kachel { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; padding: 0.45rem 0.25rem; border: 2px solid transparent; border-radius: 0.8rem; background: var(--surface-2); text-align: center; transition: border-color .15s; }
.iso-kachel.aktiv { border-color: var(--iso); background: color-mix(in srgb, var(--iso) 9%, var(--surface)); }
.mas { position: relative; min-width: 3.2rem; border: 1px solid var(--line); border-radius: 0.5rem; background: var(--surface); padding: 0.25rem 0.5rem; font-size: 0.78rem; }
.mas:hover { border-color: color-mix(in srgb, var(--mute) 45%, var(--line)); }
.mas.aktiv { border-color: var(--iso); background: var(--iso); font-weight: 600; }
.lager { position: absolute; top: 2px; right: 2px; display: inline-block; width: 6px; height: 6px; border-radius: 999px; background: var(--ok); }
</style>
