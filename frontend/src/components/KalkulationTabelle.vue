<script setup>
// Kalkulation eines Workbench-Bauteils als Tabelle: Zeile für Zeile entstehen die Kosten (Material, jeder Arbeitsgang mit
// Rüsten und je Stück, Fremdvergaben, einmalige Kosten), rechts je Staffel eine Spalte mit dem Anteil am Stückpreis.
// Rüsten und je Stück lassen sich je Arbeitsgang als Zeit × Satz oder direkt als Betrag eingeben. Unten Selbstkosten,
// Aufschlag, Stückpreis und Gesamt je Staffel. Ohne Staffeln gibt es eine Spalte für die Stückzahl.
import { computed } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, X, Truck, Cog, ChevronUp, ChevronDown, Trash2, Save, DownloadCloud, FileText, Send, Euro, Hash, Layers, Workflow, Receipt, Calculator, Sigma } from '@lucide/vue';
import NumField from './NumField.vue';
import Toggle from './Toggle.vue';
import RohmaterialKarte from './RohmaterialKarte.vue';
import { eur, zahl } from '../lib/format.js';
import { kostenTabelle, festerPreis, hatPlan, materialProStueck, ruestKosten } from '../lib/calc.js';
import { useArbeitsplan } from '../lib/arbeitsplan.js';

const props = defineProps({
  teil: { type: Object, required: true },
  ergebnis: { type: Object, required: true },
  materialien: { type: Array, default: () => [] },
  kundeId: { type: String, default: '' },
  nurAnsicht: { type: Boolean, default: false },
});
const emit = defineEmits(['anfrage']);

// Arbeitsplan-Logik wie im Arbeitsplan-Editor (Vorlagen, speichern, Maschinen, Anfragen)
const plan = useArbeitsplan({
  get arbeitsgaenge() { return props.teil.arbeitsgaenge; },
  get kundeId() { return props.kundeId; },
  get teilenummer() { return props.teil.teilenummer; },
  get teil() { return props.teil; },
  teilInfo: null,
});
const { stamm, maschinen, lieferanten, vorlagen, gespeichert, schluesselOk, ausBauteilLaden, bauteilSpeichern, serienArbeitsgang, hinzu, typSetzen, maschinenFuerAg, unbekannteArt, weg, schieben, vorlageAnwenden, maschineWechsel, arten, anfragenZu, preisUebernehmen, farbe, SPALTEN, umschalten } = plan;

const fest = computed(() => festerPreis(props.teil));
const staffel = computed(() => !!props.teil.staffel?.aktiv);
const ausPlan = computed(() => hatPlan(props.teil));
const t = computed(() => kostenTabelle(props.teil, props.ergebnis));
const ruestIn = computed(() => staffel.value || !!props.teil.inStueckpreis?.ruest);
const preisart = computed({
  get: () => (fest.value ? 'fest' : 'kalkuliert'),
  set: (v) => { props.teil.preisart = v; if (props.teil.festpreis == null) props.teil.festpreis = 0; },
});

// Spalten: je Staffel eine, sonst die Stückzahl
const stufen = computed(() => props.teil.staffel.stufen);
function staffelHinzu() {
  const letzte = Math.max(0, ...stufen.value.map((s) => Number(s.menge) || 0));
  stufen.value.push({ menge: letzte ? letzte * 2 : 5, extra: 0 });
}
function staffelWeg(i) { if (stufen.value.length > 1) stufen.value.splice(i, 1); }
const raster = computed(() => `minmax(250px, 1.7fr) 150px 150px repeat(${t.value.spalten.length}, minmax(112px, 1fr)) 34px`);
const mindestBreite = computed(() => 250 + 150 * 2 + t.value.spalten.length * 112 + 34 + 24);

// Ohne Arbeitsplan: eine Maschine mit Rüst- und Stückzeit
function einfacheMaschine(name) {
  props.teil.maschine = name;
  const m = maschinen.value.find((x) => x.name === name);
  if (m) { props.teil.satzRuest = m.satz; props.teil.satzStueck = m.satz; }
}

const KOSTEN = [
  { key: 'mess', feld: 'messkosten', label: 'Messkosten' },
  { key: 'sonder', feld: 'sonderkosten', label: 'Sonderkosten' },
  { key: 'express', feld: 'expresskosten', label: 'Expresskosten' },
];
const imStueckpreis = (k) => !fest.value && !!props.teil.inStueckpreis?.[k];
const wert = (v) => (Math.abs(v) < 0.005 ? '–' : eur(v));
const einzelnGesamt = computed(() => t.value.einzeln.some((v) => v > 0));
// Material für die ganze Stückzahl: Kosten (mit Pauschale), Gewicht und Stangenlänge bzw. Plattenfläche
const materialGesamt = (menge) => materialProStueck(props.teil) * menge + (Number(props.teil.pauschalMaterial) || 0);
function bedarfText(menge) {
  const r = props.teil.roh ?? {};
  const kg = (Number(props.teil.gewichtKg) || 0) * menge;
  const s = Number(r.saege) || 0;
  const l = Number(r.laenge) || 0;
  let mass = '';
  if (l && r.form === 'Platte') mass = `${zahl(((l + s) * ((Number(r.breite) || 0) + s) * menge) / 1e6, 2)} m²`;
  else if (l) mass = `${zahl(((l + s) * menge) / 1000, 2)} m`;
  return [kg ? `${zahl(kg, kg < 10 ? 2 : 1)} kg` : '', mass].filter(Boolean).join(' · ');
}
</script>

<template>
  <section class="card overflow-hidden">
    <!-- Kopf: Preisart, Staffeln (der Liefertermin steht im Kopf der Position) -->
    <header class="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 pb-4 pt-5">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><Calculator :size="16" class="text-accent" /> Kalkulation</h3>
      <div class="flex gap-0.5 rounded-xl border border-line bg-surface2 p-0.5 text-xs" role="radiogroup" aria-label="Preis">
        <button v-for="o in [['kalkuliert', 'Kalkulieren'], ['fest', 'Fester Stückpreis']]" :key="o[0]" type="button" role="radio" :aria-checked="preisart === o[0]" class="rounded-lg px-2.5 py-1 transition" :class="preisart === o[0] ? 'bg-surface font-medium text-ink shadow-sm' : 'text-mute hover:text-ink'" @click="preisart = o[0]">{{ o[1] }}</button>
      </div>
      <Toggle v-model="teil.staffel.aktiv" klein label="Staffeln" />
      <NumField v-if="fest && staffel" v-model="teil.festpreis" unit="€" class="klein w-32" title="Gilt für jede Staffel ohne eigenen Preis" />
    </header>

    <div class="overflow-x-auto pb-1">
      <div class="tabelle" :style="{ '--spalten': raster, minWidth: mindestBreite + 'px' }">
        <!-- Spaltenköpfe: Mengen -->
        <div class="zeile kopf">
          <div class="pl-1">Kostenposition</div>
          <div /><div />
          <div v-for="(s, k) in t.spalten" :key="'k' + k" class="spalte" :class="k === t.haupt && staffel ? 'haupt' : ''">
            <div class="flex items-center gap-1">
              <NumField v-if="staffel" v-model="stufen[s.i].menge" unit="Stk" :decimals="0" :min="1" class="klein min-w-0 flex-1" />
              <NumField v-else v-model="teil.menge" unit="Stk" :decimals="0" :min="1" class="klein min-w-0 flex-1" />
              <button v-if="staffel && stufen.length > 1" type="button" class="grid h-6 w-5 shrink-0 place-items-center rounded text-mute hover:text-accent" title="Staffel entfernen" @click="staffelWeg(s.i)"><X :size="13" /></button>
            </div>
            <div class="mt-1 h-3.5 text-[10px] font-medium normal-case tracking-normal" :class="k === t.haupt && staffel ? 'text-accent' : 'text-transparent'">zählt für Summe</div>
          </div>
          <div class="grid place-items-center">
            <button v-if="staffel" type="button" class="grid h-8 w-8 place-items-center rounded-lg border border-dashed border-line text-mute transition hover:border-accent hover:text-accent" title="Staffel hinzufügen" @click="staffelHinzu"><Plus :size="15" /></button>
          </div>
        </div>

        <div :class="fest ? 'gedimmt' : ''">
          <!-- Material -->
          <div class="abschnitt"><Layers :size="13" /> Material<span v-if="fest" class="ml-2 font-normal normal-case tracking-normal">· zählt beim festen Stückpreis nicht</span></div>
          <div class="zeile">
            <div class="pl-1"><RohmaterialKarte zeile :teil="teil" :materialien="materialien" :nur-ansicht="nurAnsicht" :kunde-id="kundeId" /></div>
            <div>
              <div class="oben">Pauschale einmalig</div>
              <NumField v-model="teil.pauschalMaterial" unit="€" class="klein" />
              <div class="unter">{{ teil.pauschalMaterial > 0 ? (staffel || !teil.pauschalAlsZeile ? 'im Stückpreis' : 'eigene Zeile') : '&nbsp;' }}</div>
            </div>
            <div class="betrag-eingabe">
              <div class="oben">Material je Stück</div>
              <span class="tnum text-base font-semibold">{{ eur(materialProStueck(teil)) }}</span>
              <div class="unter tnum">{{ zahl(teil.gewichtKg || 0, 3) }} kg × {{ zahl(teil.materialPreisKg || 0, 2) }} €/kg</div>
            </div>
            <div v-for="(v, k) in t.zeilen.material.je" :key="k" class="wert material" :class="k === t.haupt && staffel ? 'haupt' : ''">
              <span class="text-[10px] text-mute">je Stück</span>
              <span>{{ wert(v) }}</span>
              <span class="mt-1 text-[10px] text-mute">gesamt {{ t.spalten[k].menge }} Stk</span>
              <span class="font-semibold">{{ eur(materialGesamt(t.spalten[k].menge)) }}</span>
              <span class="text-[10px] text-mute">{{ bedarfText(t.spalten[k].menge) }}</span>
            </div>
            <div />
          </div>

          <!-- Fertigung: je Arbeitsgang eine Zeile -->
          <div class="abschnitt">
            <Workflow :size="13" /> Fertigung
            <span class="ml-auto flex flex-wrap items-center gap-1.5 normal-case tracking-normal">
              <select class="field !w-auto !py-0.5 !text-xs" @change="vorlageAnwenden($event.target.value, $event.target)">
                <option value="">Vorlage …</option>
                <option v-for="v in vorlagen" :key="v.id" :value="v.id">{{ v.name }}{{ v.kundeId ? ' (Kunde)' : '' }}</option>
              </select>
              <select class="field !w-auto !py-0.5 !text-xs" aria-label="Arbeitsgang hinzufügen" @change="hinzu($event.target.value, $event.target)">
                <option value="">+ Arbeitsgang …</option>
                <option v-for="a in stamm.arten" :key="a.id" :value="a.name">{{ a.name }}{{ a.typ === 'fremd' ? ' (extern)' : '' }}</option>
              </select>
              <button v-if="gespeichert && !teil.arbeitsgaenge.length" type="button" class="mini" @click="ausBauteilLaden()"><DownloadCloud :size="12" /> Vom Bauteil</button>
              <button type="button" class="mini" :disabled="!schluesselOk" :class="!schluesselOk ? 'pointer-events-none opacity-40' : ''" :title="schluesselOk ? 'Arbeitsplan am Bauteil speichern (für spätere Angebote und Aufträge)' : 'Dafür braucht das Bauteil einen Kunden und eine Teilenummer'" @click="bauteilSpeichern"><Save :size="12" /> Am Bauteil speichern</button>
            </span>
          </div>

          <div class="zeile kopf unterkopf">
            <div /><div>Rüsten / einmalig</div><div>Je Stück</div>
            <div v-for="k in t.spalten.length" :key="'u' + k" /><div />
          </div>

          <!-- Ohne Arbeitsplan: eine Maschine -->
          <div v-if="!ausPlan" class="zeile">
            <div class="pl-1">
              <div class="flex items-center gap-2"><span class="nr"><Cog :size="12" /></span><span class="text-sm font-medium">Fertigung</span><span class="text-[11px] text-mute">ohne Arbeitsplan</span></div>
              <select class="field mt-1.5 !py-1 !text-xs" :value="teil.maschine" @change="einfacheMaschine($event.target.value)">
                <option value="">Maschine wählen …</option>
                <option v-for="m in maschinen" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
            </div>
            <div>
              <NumField v-model="teil.ruestMin" unit="min" :step="5" class="klein" />
              <div class="mt-1 flex items-center gap-1 text-[11px] text-mute">× <NumField v-model="teil.satzRuest" unit="€/h" class="mikro w-[84px]" /></div>
            </div>
            <div>
              <NumField v-model="teil.stueckMin" unit="min" :step="0.5" class="klein" />
              <div class="mt-1 flex items-center gap-1 text-[11px] text-mute">× <NumField v-model="teil.satzStueck" unit="€/h" class="mikro w-[84px]" /></div>
            </div>
            <div v-for="(v, k) in t.zeilen.fertigung.je" :key="k" class="wert" :class="k === t.haupt && staffel ? 'haupt' : ''">{{ wert(v) }}</div>
            <div />
          </div>

          <div v-auto-animate>
            <template v-for="(ag, i) in teil.arbeitsgaenge" :key="ag.id">
              <!-- Interner Arbeitsgang: Maschine und Satz, Rüsten und je Stück als Zeit oder Betrag -->
              <div v-if="ag.typ === 'intern'" class="zeile group">
                <div class="min-w-0 pl-1">
                  <div class="flex items-center gap-2">
                    <span class="nr tnum">{{ i + 1 }}</span>
                    <select v-model="ag.name" class="name" :class="!ag.name || unbekannteArt(ag) ? '!border-warn' : ''" aria-label="Arbeitsgang">
                      <option value="" disabled>Arbeitsgang wählen …</option>
                      <option v-if="unbekannteArt(ag)" :value="ag.name">{{ ag.name }} (nicht in den Stammdaten)</option>
                      <option v-for="a in stamm.arten" :key="a.id" :value="a.name">{{ a.name }}</option>
                    </select>
                    <span class="modus" role="radiogroup" aria-label="Intern oder extern">
                      <button type="button" :class="ag.typ === 'intern' ? 'aktiv' : ''" title="Intern" @click="typSetzen(ag, 'intern')">intern</button>
                      <button type="button" :class="ag.typ === 'fremd' ? 'aktiv' : ''" title="Extern (Fremdvergabe)" @click="typSetzen(ag, 'fremd')">extern</button>
                    </span>
                  </div>
                  <div class="mt-1.5 flex items-center gap-1.5 pl-7">
                    <select class="field min-w-0 flex-1 !py-1 !text-xs" :value="ag.maschine" @change="maschineWechsel(ag, $event.target.value)"><option value="">Maschine (optional) …</option><option v-for="m in maschinenFuerAg(ag)" :key="m.name" :value="m.name">{{ m.name }}</option></select>
                    <NumField v-model="ag.satz" unit="€/h" class="mikro w-[84px] shrink-0" :class="ag.ruestDirekt && ag.stueckDirekt ? 'opacity-50' : ''" />
                  </div>
                  <p v-if="stamm.istSerienart(ag.name)" class="mt-1 flex items-center gap-1 pl-7 text-[11px] text-accent"><Hash :size="11" /> bringt die Seriennummern an</p>
                </div>
                <div v-for="sp in SPALTEN" :key="sp.art">
                  <div class="flex items-center gap-1">
                    <span class="modus" role="radiogroup" :aria-label="`${sp.label}: Zeit oder Betrag`">
                      <button type="button" role="radio" :aria-checked="!ag[sp.direkt]" :class="!ag[sp.direkt] ? 'aktiv' : ''" title="Zeit × Satz der Maschine" @click="umschalten(ag, sp, false)">min</button>
                      <button type="button" role="radio" :aria-checked="!!ag[sp.direkt]" :class="ag[sp.direkt] ? 'aktiv' : ''" title="Kosten direkt eintragen" @click="umschalten(ag, sp, true)"><Euro :size="11" /></button>
                    </span>
                    <NumField v-if="ag[sp.direkt]" v-model="ag[sp.euro]" unit="€" class="klein min-w-0 flex-1" />
                    <NumField v-else v-model="ag[sp.zeit]" unit="min" :step="sp.schritt" class="klein min-w-0 flex-1" />
                  </div>
                  <div class="unter tnum">
                    <template v-if="!ag[sp.direkt]">= {{ eur(sp.kosten(ag)) }}</template><template v-else>direkt</template>
                    <template v-if="sp.art === 'ruest'"> · {{ ruestIn ? 'im Stückpreis' : 'eigene Zeile' }}</template><template v-else> je Stk</template>
                  </div>
                </div>
                <div v-for="(v, k) in t.zeilen['ag-' + ag.id]?.je ?? []" :key="k" class="wert" :class="k === t.haupt && staffel ? 'haupt' : ''">{{ wert(v) }}</div>
                <div class="aktionen">
                  <button type="button" title="Nach oben" @click="schieben(i, -1)"><ChevronUp :size="13" /></button>
                  <button type="button" title="Nach unten" @click="schieben(i, 1)"><ChevronDown :size="13" /></button>
                  <button type="button" class="weg" title="Entfernen" @click="weg(i)"><Trash2 :size="13" /></button>
                </div>
              </div>

              <!-- Fremdvergabe: Lieferant, Preis je Stück und einmalig, Anfragen -->
              <div v-else class="zeile group">
                <div class="min-w-0 pl-1">
                  <div class="flex items-center gap-2">
                    <span class="nr"><Truck :size="12" /></span>
                    <select v-model="ag.name" class="name" :class="!ag.name || unbekannteArt(ag) ? '!border-warn' : ''" aria-label="Arbeitsgang">
                      <option value="" disabled>Arbeitsgang wählen …</option>
                      <option v-if="unbekannteArt(ag)" :value="ag.name">{{ ag.name }} (nicht in den Stammdaten)</option>
                      <option v-for="a in stamm.arten" :key="a.id" :value="a.name">{{ a.name }}</option>
                    </select>
                    <span class="modus" role="radiogroup" aria-label="Intern oder extern">
                      <button type="button" :class="ag.typ === 'intern' ? 'aktiv' : ''" title="Intern" @click="typSetzen(ag, 'intern')">intern</button>
                      <button type="button" :class="ag.typ === 'fremd' ? 'aktiv' : ''" title="Extern (Fremdvergabe)" @click="typSetzen(ag, 'fremd')">extern</button>
                    </span>
                  </div>
                  <div class="mt-1.5 pl-7">
                    <select v-model="ag.lieferant" class="field !py-1 !text-xs"><option value="">Lieferant …</option><option v-for="l in lieferanten" :key="l.id" :value="l.name">{{ l.name }}</option></select>
                  </div>
                  <div class="mt-1.5 flex flex-wrap items-center gap-1.5 pl-7 text-[11px]">
                    <button v-if="!nurAnsicht" type="button" class="mini" @click="emit('anfrage', ag)"><Send :size="11" /> Anfrage</button>
                    <template v-for="a in anfragenZu(ag)" :key="a.id">
                      <RouterLink :to="`/anfragen/${a.id}`" class="inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 hover:border-accent/50"><FileText :size="11" class="text-mute" /><span class="tnum">{{ a.id }}</span><span :class="farbe[a.status]">{{ a.status }}</span></RouterLink>
                      <button v-if="a.antwort" type="button" class="mini" @click="preisUebernehmen(ag, a)"><Euro :size="11" /> Preis übernehmen</button>
                    </template>
                    <span v-if="ag.anfrageId" class="text-mute">Preis aus {{ ag.anfrageId }}</span>
                  </div>
                </div>
                <div>
                  <NumField v-model="ag.fremdEinmal" unit="€" class="klein" />
                  <div class="unter">einmalig · eigene Zeile</div>
                </div>
                <div>
                  <NumField v-model="ag.fremdProStk" unit="€" class="klein" />
                  <div class="unter">je Stk vom Lieferanten</div>
                </div>
                <div v-for="(v, k) in t.zeilen['ag-' + ag.id]?.je ?? []" :key="k" class="wert" :class="k === t.haupt && staffel ? 'haupt' : ''">{{ wert(v) }}</div>
                <div class="aktionen">
                  <button type="button" title="Nach oben" @click="schieben(i, -1)"><ChevronUp :size="13" /></button>
                  <button type="button" title="Nach unten" @click="schieben(i, 1)"><ChevronDown :size="13" /></button>
                  <button type="button" class="weg" title="Entfernen" @click="weg(i)"><Trash2 :size="13" /></button>
                </div>
              </div>
            </template>
          </div>

          <div v-if="teil.seriennummern && !teil.arbeitsgaenge.some((a) => stamm.istSerienart(a.name))" class="hinweis">
            <Hash :size="13" /> Seriennummern sind aktiv, der Arbeitsgang „{{ stamm.serienart }}“ fehlt.
            <button type="button" class="mini" @click="serienArbeitsgang"><Plus :size="12" /> ergänzen</button>
          </div>
          <!-- Ohne Staffeln: Rüstkosten im Stückpreis oder als eigene Zeile -->
          <div v-if="!staffel && !fest && ruestKosten(teil) > 0" class="zeile leise">
            <div class="pl-1 text-xs text-mute">Rüstkosten gesamt</div>
            <div class="text-sm font-medium tnum">{{ eur(ruestKosten(teil)) }}</div>
            <div><Toggle v-model="teil.inStueckpreis.ruest" klein label="im Stückpreis" /></div>
            <div v-for="k in t.spalten.length" :key="k" />
            <div />
          </div>

        </div>

        <!-- Einmalige Kosten (zählen auch beim festen Stückpreis, dann als eigene Zeilen) -->
        <div>

          <div class="abschnitt"><Receipt :size="13" /> Einmalige Kosten</div>
          <div v-for="k in KOSTEN" :key="k.key" class="zeile">
            <div class="pl-1 text-sm">{{ k.label }}</div>
            <div><NumField v-model="teil[k.feld]" unit="€" class="klein" /></div>
            <div><Toggle v-model="teil.inStueckpreis[k.key]" klein label="im Stückpreis" :class="fest ? 'pointer-events-none opacity-40' : ''" /></div>
            <div v-for="(v, s) in t.zeilen[k.key].je" :key="s" class="wert" :class="s === t.haupt && staffel ? 'haupt' : ''">
              <template v-if="imStueckpreis(k.key) || !(teil[k.feld] > 0)">{{ wert(v) }}</template>
              <span v-else class="text-[11px] text-mute">eigene Zeile</span>
            </div>
            <div />
          </div>
        </div>

        <!-- Summen -->
        <div class="zeile summe">
          <div class="pl-1 flex items-center gap-1.5"><Sigma :size="14" class="text-mute" /> Selbstkosten je Stück<span v-if="fest" class="text-[11px] font-normal text-mute">(nur zum Vergleich)</span></div>
          <div /><div />
          <div v-for="(v, k) in t.selbstkosten" :key="k" class="wert" :class="k === t.haupt && staffel ? 'haupt' : ''">{{ eur(v) }}</div>
          <div />
        </div>
        <div v-if="staffel && !fest" class="zeile">
          <div class="pl-1 text-sm">Aufschlag je Stück</div>
          <div /><div />
          <div v-for="(s, k) in t.spalten" :key="k" class="wert" :class="k === t.haupt ? 'haupt' : ''"><NumField v-model="stufen[s.i].extra" unit="€" class="klein w-full" /></div>
          <div />
        </div>
        <div class="zeile preis">
          <div class="pl-1 font-semibold">Stückpreis</div>
          <div /><div />
          <div v-for="(s, k) in t.spalten" :key="k" class="wert" :class="k === t.haupt && staffel ? 'haupt' : ''">
            <NumField v-if="fest && staffel" v-model="stufen[s.i].preis" unit="€" class="klein w-full" :title="'0 € = fester Stückpreis ' + eur(teil.festpreis || 0)" />
            <NumField v-else-if="fest" v-model="teil.festpreis" unit="€" class="klein w-full" />
            <span v-else class="text-base font-semibold">{{ eur(t.stueckpreis[k]) }}</span>
          </div>
          <div />
        </div>
        <div v-if="einzelnGesamt" class="zeile leise">
          <div class="pl-1 text-xs text-mute">zzgl. einmalig (eigene Zeilen im Angebot)</div>
          <div /><div />
          <div v-for="(v, k) in t.einzeln" :key="k" class="wert text-mute" :class="k === t.haupt && staffel ? 'haupt' : ''">{{ eur(v) }}</div>
          <div />
        </div>
        <div class="zeile gesamt">
          <div class="pl-1 font-semibold">Gesamt netto</div>
          <div /><div />
          <div v-for="(v, k) in t.gesamt" :key="k" class="wert" :class="k === t.haupt && staffel ? 'haupt' : ''">{{ eur(v) }}</div>
          <div />
        </div>
      </div>
    </div>
    <p v-if="fest" class="mx-5 mb-4 mt-2 rounded-xl bg-accent-soft/60 px-3.5 py-2.5 text-xs text-accent">Fester Stückpreis: Material, Zeiten und Fremdvergabe zählen nicht, sie stehen nur zum Vergleich da. Mess-, Sonder- und Expresskosten kommen als eigene Zeilen dazu.{{ staffel ? ' Preis je Staffel direkt; 0 € = der feste Stückpreis oben.' : '' }}</p>
    <p v-else-if="staffel" class="mx-5 mb-4 mt-2 text-xs text-mute">Bei Staffeln stecken die Rüstkosten immer im Stückpreis. Die kleinste Staffel zählt für die Summe des Angebots.</p>
  </section>
</template>

<style scoped>
.tabelle { padding: 0 0.75rem; }
.zeile { display: grid; grid-template-columns: var(--spalten); align-items: center; gap: 0 0.6rem; padding: 0.55rem 0; border-top: 1px solid var(--line); }
.zeile > .wert { text-align: right; font-variant-numeric: tabular-nums; font-size: 0.875rem; align-self: stretch; display: flex; align-items: center; justify-content: flex-end; padding: 0 0.6rem; margin: -0.55rem 0; }
.zeile > .wert.haupt, .kopf > .spalte.haupt { background: color-mix(in srgb, var(--accent) 6%, transparent); }
.kopf { border-top: 0; align-items: end; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--mute); padding-top: 0.2rem; }
.kopf > .spalte { padding: 0.4rem 0.45rem 0.15rem; border-radius: 0.6rem 0.6rem 0 0; margin-bottom: -0.55rem; text-transform: none; letter-spacing: normal; font-weight: 400; }
.abschnitt { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.5rem; padding: 0.55rem 0.25rem 0.35rem; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent); border-top: 1px solid var(--line); }
.unter { margin-top: 0.2rem; font-size: 0.68rem; color: var(--mute); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.betrag-eingabe { padding-left: 0.2rem; }
.oben { margin-bottom: 0.2rem; font-size: 0.62rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--mute); }
.zeile > .wert.material { flex-direction: column; align-items: flex-end; justify-content: center; line-height: 1.25; padding-top: 0.4rem; padding-bottom: 0.4rem; }
.unterkopf { border-top: 0; padding: 0.1rem 0 0.15rem; }
.nr { display: grid; place-items: center; height: 1.35rem; width: 1.35rem; flex-shrink: 0; border-radius: 999px; background: var(--surface-2); font-size: 0.7rem; font-weight: 600; color: var(--mute); }
.name { min-width: 0; flex: 1; border-radius: 0.5rem; background: transparent; padding: 0.15rem 0.35rem; font-size: 0.875rem; font-weight: 500; outline: none; border: 1px solid transparent; }
.name:hover { border-color: var(--line); }
.name:focus { border-color: var(--accent); background: var(--surface); }
.modus { display: inline-flex; flex-shrink: 0; border-radius: 0.5rem; border: 1px solid var(--line); background: var(--surface-2); padding: 1px; font-size: 0.65rem; }
.modus button { display: grid; place-items: center; height: 1.45rem; min-width: 1.6rem; border-radius: 0.38rem; padding: 0 0.25rem; color: var(--mute); }
.modus button.aktiv { background: var(--surface); color: var(--accent); font-weight: 600; box-shadow: 0 1px 2px rgb(0 0 0 / 0.08); }
.aktionen { display: flex; flex-direction: column; align-items: center; gap: 1px; opacity: 0; transition: opacity 0.15s; }
.group:hover .aktionen, .aktionen:focus-within { opacity: 1; }
.aktionen button { display: grid; place-items: center; height: 1.2rem; width: 1.5rem; border-radius: 0.35rem; color: var(--mute); }
.aktionen button:hover { background: var(--surface-2); color: var(--ink); }
.aktionen button.weg:hover { background: var(--accent-soft); color: var(--accent); }
.mini { display: inline-flex; align-items: center; gap: 0.25rem; border-radius: 0.5rem; border: 1px solid var(--line); background: var(--surface); padding: 0.15rem 0.5rem; font-size: 0.72rem; color: var(--ink); transition: border-color 0.15s, color 0.15s; }
.mini:hover { border-color: var(--accent); color: var(--accent); }
.hinweis { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 0.4rem 0; border-radius: 0.75rem; background: var(--accent-soft); padding: 0.5rem 0.75rem; font-size: 0.75rem; color: var(--accent); }
.leise { padding: 0.35rem 0; }
.summe { margin-top: 0.4rem; border-top: 2px solid var(--line); font-size: 0.875rem; font-weight: 500; }
.preis { background: var(--accent-soft); border-top: 0; border-radius: 0.75rem; margin-top: 0.25rem; }
.preis > .wert.haupt { background: transparent; }
.gesamt { font-size: 0.9rem; }
.gesamt > .wert { font-weight: 600; }
.gedimmt { opacity: 0.55; }
:deep(.klein .field) { padding-top: 0.3rem; padding-bottom: 0.3rem; padding-left: 0.55rem; font-size: 0.8125rem; }
:deep(.mikro .field) { padding: 0.15rem 2.3rem 0.15rem 0.4rem; font-size: 0.75rem; }
:deep(.mikro .field + span) { right: 0.45rem; font-size: 0.65rem; }
</style>
