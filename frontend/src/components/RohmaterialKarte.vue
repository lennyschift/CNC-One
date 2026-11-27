<script setup>
// Rohmaterial eines Workbench-Bauteils: kompakte Karte (ISO-Gruppe, Artikel, Rohteil, Gewicht, € je Stück, Anforderungen).
// Ein Klick öffnet das Popup: links die Auswahl in Stufen (RohmaterialWahl, mit „+ Neu“ je Stufe), rechts Zuschnitt,
// Gewicht und Preis, Anforderungen (Werkszeugnis, Prüfungen, mindestens die Vorgabe des Kunden) und passende Chargen im Lager.
import { ref, reactive, computed, watch } from 'vue';
import { Layers, X, Wand2, Check, FileBadge, ShieldCheck, Warehouse, Pencil, Plus, Tag, Scissors } from '@lucide/vue';
import NumField from './NumField.vue';
import Toggle from './Toggle.vue';
import FormSymbol from './FormSymbol.vue';
import RohmaterialWahl from './RohmaterialWahl.vue';
import { isoGruppe } from '../lib/iso.js';
import { leeresRoh, rohGewicht, rohText, vollstaendig } from '../lib/rohmaterial.js';
import {
  ZEUGNISSE, zeugnisKurz, anforderungenVon, artikelText, anforderungenMit, chargePruefen, reichtFuer, rohAusAbmessung, vorschlagAbmessung, abmessungAusAltemRoh, kgJeMeter, kgJeQm,
} from '../lib/werkstoffbaum.js';
import { dichteSchaetzen } from '../lib/erkennung.js';
import { materialProStueck } from '../lib/calc.js';
import { eur, zahl } from '../lib/format.js';
import { aufmassText } from '../lib/aufmass.js';
import { stammdatenRoh } from '../data/repo.js';
import { useWerkstoff } from '../stores/werkstoff.js';

const props = defineProps({
  teil: { type: Object, required: true },
  materialien: { type: Array, default: () => [] }, // veraltet: die Liste kommt aus dem Werkstoff-Store
  fest: { type: Boolean, default: false }, // fester Stückpreis: Materialkosten zählen nicht
  nurAnsicht: { type: Boolean, default: false },
  zeile: { type: Boolean, default: false }, // kompakt als Zeile der Kalkulationstabelle
  kundeId: { type: String, default: '' },
  ohnePreis: { type: Boolean, default: false }, // Fertigung: keine Preise, kein Gewicht/Preis-Abschnitt
});
const ws = useWerkstoff();

// Ältere Bauteile haben noch kein Rohteil: angelegt wird es erst beim Bearbeiten (Ansehen ändert nichts)
const LEER = Object.freeze(leeresRoh());
const roh = computed(() => props.teil.roh ?? LEER);

const stamm = computed(() => ws.werkstoff(props.teil.material));
const iso = computed(() => isoGruppe(props.teil.material, stamm.value?.isoGruppe ?? ''));
const dichte = computed(() => stamm.value?.dichte || dichteSchaetzen(props.teil.material) || 0);
const dichteGeschaetzt = computed(() => !stamm.value?.dichte && !!dichte.value);
const berechnet = computed(() => (vollstaendig(roh.value) && dichte.value ? rohGewicht(roh.value, dichte.value) : 0));
const artikel = computed(() => artikelText(props.teil.material, roh.value));
const anf = computed(() => (props.teil.roh ? anforderungenVon(props.teil.roh) : { zeugnis: '', pruefungen: [] }));

// Gewicht aus den Maßen ins Bauteil schreiben (das rechnet die Kalkulation)
watch(berechnet, (kg) => {
  if (props.nurAnsicht || !roh.value.gewichtAuto || !kg) return;
  if (Math.abs((props.teil.gewichtKg || 0) - kg) > 0.0005) props.teil.gewichtKg = kg;
}, { immediate: true });

// Vorschlag aus dem 3D-Modell (bzw. aus den Maßen eines alten Bauteils) als Abmessung der Reihe
const vorschlag = computed(() => vorschlagAbmessung(ws.baum, stamm.value, props.teil.rohVorschlag) ?? abmessungAusAltemRoh(ws.baum, stamm.value, props.teil.roh));
const vorschlagText = computed(() => (vorschlag.value ? `${vorschlag.value.abm.form} ${vorschlag.value.abm.text} × ${vorschlag.value.breite ? `${vorschlag.value.breite} × ` : ''}${vorschlag.value.laenge}` : ''));
const vorschlagNeu = computed(() => !!vorschlag.value && (roh.value.abmessungId !== vorschlag.value.abm.id || Number(roh.value.laenge) !== vorschlag.value.laenge));
function vorschlagUebernehmen() {
  const v = vorschlag.value;
  props.teil.roh = rohAusAbmessung({ ...leeresRoh(), ...(props.teil.roh ?? {}), laenge: v.laenge, breite: v.abm.form === 'Platte' ? v.breite : props.teil.roh?.breite ?? 0 }, v.abm);
  props.teil.roh.gewichtAuto = true;
  wahl.form = v.abm.form;
  wahl.abmessungId = v.abm.id;
}

function materialWechsel(name) {
  props.teil.material = name;
  const m = ws.werkstoff(name);
  if (m) props.teil.materialPreisKg = m.preisKg;
}

// ---- Auswahl (Werkstoff, Zustand, Form, Ausführung, Abmessung) mit dem Bauteil abgleichen
const wahl = reactive({ werkstoff: '', zustand: '', form: 'Rund', ausfuehrung: '', abmessungId: '' });
function wahlLaden() {
  Object.assign(wahl, { werkstoff: props.teil.material || '', zustand: roh.value.zustand || '', form: roh.value.form || 'Rund', ausfuehrung: roh.value.ausfuehrung || '', abmessungId: roh.value.abmessungId || '' });
}
watch(wahl, (x) => {
  if (props.nurAnsicht || !offen.value || !props.teil.roh) return;
  if (x.werkstoff && x.werkstoff !== props.teil.material) materialWechsel(x.werkstoff);
  const r = props.teil.roh;
  r.zustand = x.zustand;
  r.ausfuehrung = x.ausfuehrung;
  if (x.abmessungId !== (r.abmessungId || '')) {
    const abm = ws.baum.abmessungen.find((a) => a.id === x.abmessungId);
    if (abm) props.teil.roh = rohAusAbmessung(r, abm);
    else { r.abmessungId = ''; r.abmessung = ''; }
  }
  if (x.form !== props.teil.roh.form) {
    props.teil.roh.form = x.form;
    if (!x.abmessungId) props.teil.roh.abmessung = '';
  }
}, { deep: true });

// ---- Anforderungen: eigene, mindestens die Vorgabe des Kunden
const vorgabe = computed(() => (stammdatenRoh().kunden ?? []).find((k) => k.id === props.kundeId)?.materialVorgabe ?? { zeugnis: '', pruefungen: [] });
const vomKunden = (p) => vorgabe.value.pruefungen.includes(p);
const zeugnisGesperrt = (z) => ZEUGNISSE.indexOf(z) < ZEUGNISSE.indexOf(vorgabe.value.zeugnis || '');
function anforderungenSetzen(a) {
  props.teil.roh.anforderungen = a;
  props.teil.roh.zeugnis = a.zeugnis; // ältere Anzeigen lesen roh.zeugnis
}
function zeugnisSetzen(z) { if (!props.nurAnsicht && !zeugnisGesperrt(z)) anforderungenSetzen({ ...anf.value, zeugnis: z }); }
function pruefungUmschalten(p) {
  if (props.nurAnsicht || vomKunden(p)) return;
  const l = anf.value.pruefungen ?? [];
  anforderungenSetzen({ ...anf.value, pruefungen: l.includes(p) ? l.filter((x) => x !== p) : [...l, p] });
}
const neueAnforderung = ref(null);
async function anforderungAnlegen() {
  const a = await ws.anforderungHinzu(neueAnforderung.value);
  if (a) { anforderungenSetzen({ ...anf.value, pruefungen: [...new Set([...(anf.value.pruefungen ?? []), a.name])] }); neueAnforderung.value = null; }
}

// ---- Chargen im Rohmaterial-Lager, die zu Werkstoff, Zustand und Abmessung passen
const chargen = computed(() => (ws.chargenListe ?? [])
  .filter((c) => c.werkstoff === props.teil.material && c.abmessung === roh.value.abmessungId && (!roh.value.zustand || c.zustand === roh.value.zustand))
  .map((c) => ({ ...c, pruefung: chargePruefen(c, anf.value), teile: reichtFuer(c, roh.value) })));
function chargeWaehlen(c) {
  if (props.nurAnsicht) return;
  const r = props.teil.roh;
  if (r.charge === c.id) { r.charge = ''; r.ausLager = false; r.lagerHinweis = ''; return; }
  r.charge = c.id;
  r.ausLager = true;
  r.lagerHinweis = [c.id, c.lagerplatz].filter(Boolean).join(' · ');
}

// ---- Popup
const offen = ref(false);
function oeffnen() {
  if (!props.teil.roh && !props.nurAnsicht) props.teil.roh = leeresRoh();
  if (!props.nurAnsicht && props.teil.roh) {
    const r = props.teil.roh;
    if (r.saege === undefined) r.saege = 3;
    const neu = anforderungenMit(anforderungenVon(r), vorgabe.value);
    if (JSON.stringify(neu) !== JSON.stringify(r.anforderungen)) anforderungenSetzen(neu);
  }
  wahlLaden();
  ws.chargenLaden().catch(() => {});
  offen.value = true;
}
const platte = computed(() => roh.value.form === 'Platte');
const abmessung = computed(() => ws.baum.abmessungen.find((a) => a.id === roh.value.abmessungId) ?? null);
const jeEinheit = computed(() => {
  const a = abmessung.value;
  if (!a || !dichte.value) return 0;
  return a.form === 'Platte' ? kgJeQm(a.m1, dichte.value) : kgJeMeter(a.form, a.m1, a.m2, dichte.value);
});
const kg = (v) => `${zahl(v, v < 1 ? 3 : 2)} kg`;
const proStueck = computed(() => materialProStueck(props.teil));
</script>

<template>
  <div :class="[zeile ? 'min-w-0' : 'card overflow-hidden', fest ? 'opacity-60' : '']">
    <!-- Kompakt als Zeile der Kalkulationstabelle: ISO-Kennzeichen, Artikel, Rohteil; Klick öffnet das Popup -->
    <template v-if="zeile">
      <div role="button" tabindex="0" class="group -m-1.5 flex cursor-pointer items-center gap-3 rounded-xl p-1.5 transition hover:bg-surface2" :title="nurAnsicht ? 'Rohmaterial ansehen' : 'Rohmaterial bearbeiten: Werkstoff, Zustand, Abmessung, Anforderungen, Lager'" @click="oeffnen" @keydown.enter.prevent="oeffnen" @keydown.space.prevent="oeffnen">
        <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-lg font-bold" :style="iso ? { background: iso.farbe, color: iso.schrift } : {}" :class="iso ? '' : 'border-2 border-dashed border-line text-mute'" :title="iso ? `ISO ${iso.code}: ${iso.name}` : 'ISO-Gruppe unbekannt'">{{ iso?.code ?? '?' }}</div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5"><span class="truncate font-medium" :class="teil.material ? '' : 'text-mute'">{{ artikel || 'Werkstoff wählen' }}</span><Pencil :size="12" class="shrink-0 text-mute opacity-0 transition group-hover:opacity-100" /></div>
          <div class="truncate text-xs text-mute tnum">{{ rohText(roh) ? rohText(roh) + ' mm' : 'Abmessung und Zuschnitt fehlen' }}<template v-if="!ohnePreis"> · {{ kg(teil.gewichtKg || 0) }} × {{ eur(teil.materialPreisKg || 0) }}/kg</template></div>
          <div v-if="anf.zeugnis || anf.pruefungen?.length || roh.ausLager" class="mt-1 flex flex-wrap gap-1">
            <span v-if="anf.zeugnis" class="chip !text-[10px]"><FileBadge :size="11" /> {{ zeugnisKurz(anf.zeugnis) }}</span>
            <span v-for="p in anf.pruefungen" :key="p" class="chip !text-[10px]"><ShieldCheck :size="11" /> {{ p }}</span>
            <span v-if="roh.ausLager" class="chip !text-[10px]"><Warehouse :size="11" /> {{ roh.charge || 'Lager' }}</span>
          </div>
        </div>
      </div>
      <div v-if="vorschlagNeu && !nurAnsicht" class="mt-2 flex items-center gap-1.5 rounded-lg bg-accent-soft/60 px-2 py-1 text-[11px] text-accent">
        <Wand2 :size="12" class="shrink-0" /><span class="truncate">{{ teil.rohVorschlag ? '3D' : 'Passend' }}: <strong class="tnum">{{ vorschlagText }} mm</strong></span>
        <button type="button" class="ml-auto shrink-0 font-semibold hover:underline" @click="vorschlagUebernehmen">Übernehmen</button>
      </div>
    </template>
    <template v-else>
      <div role="button" tabindex="0" class="group block w-full cursor-pointer p-5 text-left transition hover:bg-surface2/60" :title="nurAnsicht ? 'Rohmaterial ansehen' : 'Rohmaterial bearbeiten'" @click="oeffnen" @keydown.enter.prevent="oeffnen" @keydown.space.prevent="oeffnen">
        <div class="mb-3 flex items-center gap-2">
          <h3 class="flex items-center gap-2 text-sm font-semibold"><Layers :size="16" class="text-accent" /> Rohmaterial</h3>
          <span v-if="fest" class="text-[11px] text-mute">· zählt beim festen Stückpreis nicht</span>
          <span class="ml-auto flex items-center gap-1 text-xs text-mute opacity-0 transition group-hover:opacity-100"><Pencil :size="12" /> {{ nurAnsicht ? 'Ansehen' : 'Bearbeiten' }}</span>
        </div>
        <div class="flex items-center gap-4">
          <div class="grid h-14 w-14 shrink-0 place-items-center rounded-2xl text-2xl font-bold" :style="iso ? { background: iso.farbe, color: iso.schrift } : {}" :class="iso ? '' : 'border-2 border-dashed border-line text-mute'">{{ iso?.code ?? '?' }}</div>
          <div class="min-w-0 flex-1">
            <div class="truncate text-base font-semibold" :class="teil.material ? '' : 'text-mute'">{{ artikel || 'Werkstoff wählen' }}</div>
            <div class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-mute">
              <span v-if="rohText(roh)" class="font-medium text-ink tnum">{{ rohText(roh) }} mm</span><span v-else>Abmessung und Zuschnitt fehlen</span>
              <span v-if="!ohnePreis" class="tnum">{{ kg(teil.gewichtKg || 0) }} × {{ eur(teil.materialPreisKg || 0) }}/kg</span>
            </div>
          </div>
          <div v-if="!ohnePreis" class="shrink-0 text-right"><div class="label">je Stück</div><div class="text-xl font-semibold tnum">{{ eur(proStueck) }}</div></div>
        </div>
      </div>
    </template>

    <!-- Popup -->
    <Teleport to="body">
      <div v-if="offen" class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="offen = false" @keydown.esc="offen = false">
        <Transition name="pop" appear>
          <div class="card flex max-h-[94vh] w-[min(1280px,97vw)] flex-col overflow-hidden shadow-2xl">
            <header class="flex items-center gap-3 border-b border-line px-6 py-3.5">
              <div class="grid h-9 w-9 place-items-center rounded-xl text-base font-bold" :style="iso ? { background: iso.farbe, color: iso.schrift } : {}" :class="iso ? '' : 'bg-surface2 text-mute'">{{ iso?.code ?? '?' }}</div>
              <FormSymbol :form="roh.form" :groesse="30" :farbe="iso?.farbe || ''" />
              <div class="min-w-0">
                <h2 class="truncate text-base font-semibold">{{ artikel || 'Rohmaterial' }}</h2>
                <p class="truncate text-xs text-mute">{{ teil.name || 'Bauteil' }}<template v-if="teil.teilenummer"> · {{ teil.teilenummer }}</template><template v-if="stamm?.kurz"> · {{ stamm.kurz }}</template></p>
              </div>
              <div v-if="!ohnePreis" class="ml-auto text-right"><div class="label">je Stück</div><div class="text-lg font-semibold tnum">{{ eur(proStueck) }}</div></div>
              <div v-else class="ml-auto" />
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" title="Schließen" @click="offen = false"><X :size="18" /></button>
            </header>

            <div class="grid min-h-0 flex-1 overflow-auto lg:grid-cols-[minmax(0,1fr)_380px] lg:overflow-hidden">
              <div class="border-line p-5 lg:overflow-auto lg:border-r">
                <RohmaterialWahl :wahl="wahl" :nur-ansicht="nurAnsicht" :chargen="ws.chargenListe ?? []" />
              </div>

              <p v-if="!teil.roh" class="p-5 text-sm text-mute">Für dieses Bauteil ist kein Rohmaterial hinterlegt.</p>
              <fieldset v-else :disabled="nurAnsicht" class="m-0 space-y-5 border-0 p-5 lg:overflow-auto">
                <!-- Vorschlag aus 3D / alten Maßen -->
                <div v-if="vorschlag" class="flex flex-wrap items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs" :class="vorschlagNeu ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'">
                  <Wand2 :size="14" class="shrink-0" />
                  <span>{{ teil.rohVorschlag ? '3D-Modell' : 'Aus den bisherigen Maßen' }}: <strong class="tnum">{{ vorschlagText }} mm</strong><template v-if="teil.rohVorschlag"> (Aufmaß {{ aufmassText(teil.aufmass, teil.rohVorschlag.form === 'Rund' ? 'Rund' : 'Quader') }})</template></span>
                  <button v-if="vorschlagNeu" type="button" class="btn ml-auto !py-0.5 text-xs" @click="vorschlagUebernehmen">Übernehmen</button>
                  <span v-else class="ml-auto flex items-center gap-1"><Check :size="13" /> übernommen</span>
                </div>

                <!-- 7 Zuschnitt -->
                <section>
                  <div class="label mb-1.5 flex items-center gap-1.5"><Scissors :size="12" /> Zuschnitt je Teil</div>
                  <div class="grid gap-2.5" :class="platte ? 'grid-cols-3' : 'grid-cols-2'">
                    <NumField v-if="platte" v-model="teil.roh.breite" label="Breite" unit="mm" :decimals="1" />
                    <NumField v-model="teil.roh.laenge" label="Länge" unit="mm" :decimals="1" />
                    <NumField v-model="teil.roh.saege" :label="platte ? 'Sägezugabe je Maß' : 'Sägezugabe'" unit="mm" :decimals="1" />
                  </div>
                  <p class="mt-1 text-[11px] text-mute tnum">{{ platte ? 'Gewicht je m²' : 'Gewicht je Meter' }}: {{ jeEinheit ? `${zahl(jeEinheit, 2)} kg` : '–' }}</p>
                </section>

                <!-- Gewicht und Preis -->
                <section v-if="!ohnePreis" class="grid gap-3 sm:grid-cols-2">
                  <div>
                    <div class="mb-1 flex items-center justify-between gap-2"><span class="label">Gewicht je Stück</span><Toggle v-model="teil.roh.gewichtAuto" klein label="aus Maßen" /></div>
                    <div v-if="roh.gewichtAuto" class="field flex items-center justify-between !bg-surface2 tnum">
                      <span>{{ berechnet ? kg(berechnet) : '–' }}</span>
                      <span class="text-xs text-mute">{{ dichte ? `${zahl(dichte, 2)} g/cm³${dichteGeschaetzt ? ' (geschätzt)' : ''}` : 'Dichte fehlt' }}</span>
                    </div>
                    <NumField v-else v-model="teil.gewichtKg" unit="kg" :step="0.05" :decimals="3" />
                  </div>
                  <NumField v-model="teil.materialPreisKg" label="Preis" unit="€/kg" :hint="'= ' + eur(proStueck) + ' je Stück'" />
                  <NumField v-model="teil.pauschalMaterial" label="Pauschal Material (einmalig)" unit="€" />
                  <div class="flex flex-col justify-end gap-2 pb-1">
                    <Toggle v-model="teil.pauschalAlsZeile" klein label="Pauschale als eigene Zeile" />
                    <Toggle v-model="teil.werkstoffDrucken" klein label="Werkstoff im Angebots-PDF" />
                  </div>
                </section>

                <!-- 8 Anforderungen -->
                <section>
                  <div class="label mb-1.5">Werkszeugnis (EN 10204)</div>
                  <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1 text-xs" role="radiogroup" aria-label="Werkszeugnis">
                    <button v-for="z in ZEUGNISSE" :key="z" type="button" role="radio" :aria-checked="anf.zeugnis === z" :disabled="zeugnisGesperrt(z)" class="flex-1 rounded-lg py-1.5 transition disabled:cursor-not-allowed disabled:opacity-35" :class="anf.zeugnis === z ? 'bg-surface font-medium text-ink shadow-sm' : 'text-mute hover:text-ink'" @click="zeugnisSetzen(z)">{{ zeugnisKurz(z) }}</button>
                  </div>
                  <div class="label mb-1.5 mt-3">Prüfungen und Nachweise</div>
                  <div class="flex flex-wrap gap-1.5">
                    <button v-for="a in ws.baum.anforderungen" :key="a.name" type="button" class="pill" :class="anf.pruefungen?.includes(a.name) ? 'aktiv' : ''" :title="vomKunden(a.name) ? 'Vorgabe des Kunden' : ''" @click="pruefungUmschalten(a.name)">
                      <ShieldCheck v-if="anf.pruefungen?.includes(a.name)" :size="12" /> {{ a.name }}<Tag v-if="vomKunden(a.name)" :size="10" class="opacity-70" />
                    </button>
                    <button v-if="!nurAnsicht && neueAnforderung === null" type="button" class="pill border-dashed" @click="neueAnforderung = ''"><Plus :size="12" /> Neu</button>
                  </div>
                  <div v-if="neueAnforderung !== null" class="mt-2 flex gap-1.5">
                    <input v-model="neueAnforderung" class="field !py-1.5 text-sm" placeholder="z. B. Röntgengeprüft" autofocus @keydown.enter="neueAnforderung.trim() && anforderungAnlegen()" @keydown.esc.stop="neueAnforderung = null" />
                    <button type="button" class="btn btn-primary !py-1.5 text-xs" :disabled="!neueAnforderung.trim()" @click="anforderungAnlegen"><Check :size="13" /></button>
                    <button type="button" class="btn !py-1.5" @click="neueAnforderung = null"><X :size="13" /></button>
                  </div>
                  <p v-if="vorgabe.zeugnis || vorgabe.pruefungen.length" class="mt-2 text-[11px] text-mute"><Tag :size="10" class="inline" /> Kunde fordert immer: {{ [vorgabe.zeugnis && `Zeugnis ${vorgabe.zeugnis}`, ...vorgabe.pruefungen].filter(Boolean).join(', ') }}</p>
                </section>

                <!-- Lager -->
                <section>
                  <div class="label mb-1.5 flex items-center gap-1.5"><Warehouse :size="12" /> Rohmaterial-Lager</div>
                  <div v-if="chargen.length" class="space-y-1.5">
                    <button v-for="c in chargen" :key="c.id" type="button" class="w-full rounded-xl border px-3 py-2 text-left transition" :class="roh.charge === c.id ? 'border-accent bg-accent-soft/50' : c.pruefung.ok ? 'border-ok/40 hover:border-ok' : 'border-line hover:border-mute'" @click="chargeWaehlen(c)">
                      <div class="flex items-center gap-2 text-sm"><FileBadge :size="14" :class="c.zeugnisDatei ? 'text-accent' : 'text-mute'" /><span class="font-semibold tnum">{{ c.id }}</span><span class="text-[11px] text-mute">{{ c.chargennr }}</span>
                        <span class="ml-auto text-[11px] text-mute tnum">reicht für {{ c.teile }}</span><Check v-if="roh.charge === c.id" :size="14" class="text-accent" /></div>
                      <div class="mt-0.5 text-[11px] text-mute">{{ c.lieferant || 'Lieferant ?' }} · {{ c.form === 'Platte' ? `${zahl(c.breite, 0)} × ${zahl(c.laenge, 0)}` : `${c.stueck} × ${zahl(c.laenge, 0)}` }} mm · Zeugnis {{ c.zeugnis || 'keins' }}<template v-if="c.lagerplatz"> · {{ c.lagerplatz }}</template></div>
                      <div class="mt-1 text-[11px]"><span v-if="c.pruefung.ok" class="text-ok">erfüllt alle Anforderungen</span><span v-else class="text-warn">fehlt: {{ c.pruefung.fehlt.join(', ') }}</span></div>
                    </button>
                  </div>
                  <p v-else class="rounded-xl bg-surface2 px-3 py-2.5 text-xs text-mute">{{ roh.abmessungId ? 'Keine passende Charge im Lager, wird bestellt.' : 'Nach der Wahl der Abmessung erscheinen hier passende Chargen.' }}</p>
                </section>
              </fieldset>
            </div>

            <footer class="flex items-center gap-2 border-t border-line bg-surface2 px-6 py-3">
              <span v-if="!ohnePreis" class="text-xs text-mute tnum">{{ kg(teil.gewichtKg || 0) }} × {{ eur(teil.materialPreisKg || 0) }}/kg = {{ eur(proStueck) }} je Stück</span>
              <button type="button" class="btn btn-primary ml-auto" @click="offen = false"><Check :size="15" /> Fertig</button>
            </footer>
          </div>
        </Transition>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.chip { display: inline-flex; align-items: center; gap: 0.3rem; border-radius: 999px; background: var(--surface-2); padding: 0.1rem 0.55rem; font-size: 0.72rem; color: var(--mute); }
.pill { display: inline-flex; align-items: center; gap: 0.3rem; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); padding: 0.18rem 0.6rem; font-size: 0.75rem; color: var(--mute); }
.pill.aktiv { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
</style>
