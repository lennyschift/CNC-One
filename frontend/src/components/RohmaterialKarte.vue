<script setup>
// Rohmaterial eines Workbench-Bauteils: kompakte Karte (ISO-Gruppe, Werkstoff, Rohteil, Gewicht, € je Stück, Vorschlag aus dem
// 3D-Modell). Ein Klick öffnet das Popup mit Werkstoffwahl nach ISO-Gruppe, Form und Maßen, Gewicht, Preis, Zeugnis und Lager.
// Das Gewicht rechnet sich aus Form, Maßen und Dichte, solange „aus Maßen“ an ist und alle Maße da sind.
import { ref, computed, watch } from 'vue';
import { Layers, X, Wand2, Check, Search, Circle, Square, CircleDot, Hexagon, FileBadge, Warehouse, Pencil } from '@lucide/vue';
import NumField from './NumField.vue';
import Toggle from './Toggle.vue';
import { ISO_GRUPPEN, isoGruppe } from '../lib/iso.js';
import { FORMEN, FELD_LABEL, ZEUGNISSE, leeresRoh, rohGewicht, rohText, vollstaendig, vorschlagAnwenden } from '../lib/rohmaterial.js';
import { dichteSchaetzen } from '../lib/erkennung.js';
import { materialProStueck } from '../lib/calc.js';
import { eur, zahl } from '../lib/format.js';

const props = defineProps({
  teil: { type: Object, required: true },
  materialien: { type: Array, default: () => [] },
  fest: { type: Boolean, default: false }, // fester Stückpreis: Materialkosten zählen nicht
  nurAnsicht: { type: Boolean, default: false },
  zeile: { type: Boolean, default: false }, // kompakt als Zeile der Kalkulationstabelle
});

// Ältere Bauteile haben noch kein Rohteil: angelegt wird es erst beim Bearbeiten (Ansehen ändert nichts)
const LEER = Object.freeze(leeresRoh());
const roh = computed(() => props.teil.roh ?? LEER);

const stamm = computed(() => props.materialien.find((m) => m.name === props.teil.material) ?? null);
const iso = computed(() => isoGruppe(props.teil.material, stamm.value?.isoGruppe ?? ''));
const dichte = computed(() => stamm.value?.dichte || dichteSchaetzen(props.teil.material) || 0);
const dichteGeschaetzt = computed(() => !stamm.value?.dichte && !!dichte.value);
const berechnet = computed(() => (vollstaendig(roh.value) && dichte.value ? rohGewicht(roh.value, dichte.value) : 0));

// Gewicht aus den Maßen ins Bauteil schreiben (das rechnet die Kalkulation)
watch(berechnet, (kg) => {
  if (props.nurAnsicht || !roh.value.gewichtAuto || !kg) return;
  if (Math.abs((props.teil.gewichtKg || 0) - kg) > 0.0005) props.teil.gewichtKg = kg;
}, { immediate: true });

const vorschlag = computed(() => props.teil.rohVorschlag ?? null);
const vorschlagText = computed(() => (vorschlag.value ? rohText({ ...leeresRoh(), ...vorschlag.value }) : ''));
const vorschlagNeu = computed(() => !!vorschlagText.value && vorschlagText.value !== rohText(roh.value));
function vorschlagUebernehmen() {
  props.teil.roh = vorschlagAnwenden(roh.value, vorschlag.value);
  props.teil.roh.gewichtAuto = true;
}

function materialWechsel(name) {
  props.teil.material = name;
  const m = props.materialien.find((x) => x.name === name);
  if (m) props.teil.materialPreisKg = m.preisKg;
}

// ---- Popup
const offen = ref(false);
const isoFilter = ref('');
const suche = ref('');
const gruppeVon = (m) => isoGruppe(m.name, m.isoGruppe)?.code ?? '';
const liste = computed(() => {
  const s = suche.value.trim().toLowerCase();
  return props.materialien.filter((m) => (!isoFilter.value || gruppeVon(m) === isoFilter.value) && (!s || m.name.toLowerCase().includes(s) || (m.schreibweisen ?? []).some((x) => x.toLowerCase().includes(s))));
});
const anzahlJe = (code) => props.materialien.filter((m) => gruppeVon(m) === code).length;
function oeffnen() {
  if (!props.teil.roh && !props.nurAnsicht) props.teil.roh = leeresRoh();
  isoFilter.value = '';
  suche.value = '';
  offen.value = true;
}
const FORM_ICON = { Rund: Circle, Flach: Square, Rohr: CircleDot, Sechskant: Hexagon };
const felder = computed(() => FORMEN.find((f) => f.id === roh.value.form)?.felder ?? []);
const kg = (v) => `${zahl(v, v < 1 ? 3 : 2)} kg`;
const proStueck = computed(() => materialProStueck(props.teil));
</script>

<template>
  <div :class="[zeile ? 'min-w-0' : 'card overflow-hidden', fest ? 'opacity-60' : '']">
    <!-- Kompakt als Zeile der Kalkulationstabelle: ISO-Kennzeichen, Werkstoff, Rohteil; Klick öffnet das Popup -->
    <template v-if="zeile">
      <div role="button" tabindex="0" class="group -m-1.5 flex cursor-pointer items-center gap-3 rounded-xl p-1.5 transition hover:bg-surface2" :title="nurAnsicht ? 'Rohmaterial ansehen' : 'Rohmaterial bearbeiten: Werkstoff, Rohteil, Zeugnis, Lager'" @click="oeffnen" @keydown.enter.prevent="oeffnen" @keydown.space.prevent="oeffnen">
        <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-lg font-bold" :style="iso ? { background: iso.farbe, color: iso.schrift } : {}" :class="iso ? '' : 'border-2 border-dashed border-line text-mute'" :title="iso ? `ISO ${iso.code}: ${iso.name}` : 'ISO-Gruppe unbekannt'">{{ iso?.code ?? '?' }}</div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5"><span class="truncate font-medium" :class="teil.material ? '' : 'text-mute'">{{ teil.material || 'Werkstoff wählen' }}</span><Pencil :size="12" class="shrink-0 text-mute opacity-0 transition group-hover:opacity-100" /></div>
          <div class="truncate text-xs text-mute tnum">{{ rohText(roh) ? rohText(roh) + ' mm' : 'Rohteil-Maße fehlen' }} · {{ kg(teil.gewichtKg || 0) }} × {{ eur(teil.materialPreisKg || 0) }}/kg</div>
          <div v-if="roh.zeugnis || roh.ausLager" class="mt-1 flex flex-wrap gap-1">
            <span v-if="roh.zeugnis" class="chip !text-[10px]"><FileBadge :size="11" /> {{ roh.zeugnis }}</span>
            <span v-if="roh.ausLager" class="chip !text-[10px]"><Warehouse :size="11" /> Lager</span>
          </div>
        </div>
      </div>
      <div v-if="vorschlagNeu && !nurAnsicht" class="mt-2 flex items-center gap-1.5 rounded-lg bg-accent-soft/60 px-2 py-1 text-[11px] text-accent">
        <Wand2 :size="12" class="shrink-0" /><span class="truncate">3D: <strong class="tnum">{{ vorschlagText }} mm</strong></span>
        <button type="button" class="ml-auto shrink-0 font-semibold hover:underline" @click="vorschlagUebernehmen">Übernehmen</button>
      </div>
    </template>
    <template v-else>
    <!-- div statt button: bleibt auch im gesperrten Bereich (nur ansehen) anklickbar -->
    <div role="button" tabindex="0" class="group block w-full cursor-pointer p-5 text-left transition hover:bg-surface2/60" :title="nurAnsicht ? 'Rohmaterial ansehen' : 'Rohmaterial bearbeiten'" @click="oeffnen" @keydown.enter.prevent="oeffnen" @keydown.space.prevent="oeffnen">
      <div class="mb-3 flex items-center gap-2">
        <h3 class="flex items-center gap-2 text-sm font-semibold"><Layers :size="16" class="text-accent" /> Rohmaterial</h3>
        <span v-if="fest" class="text-[11px] text-mute">· zählt beim festen Stückpreis nicht</span>
        <span class="ml-auto flex items-center gap-1 text-xs text-mute opacity-0 transition group-hover:opacity-100"><Pencil :size="12" /> {{ nurAnsicht ? 'Ansehen' : 'Bearbeiten' }}</span>
      </div>
      <div class="flex items-center gap-4">
        <!-- ISO-Gruppe als farbiges Kennzeichen -->
        <div class="grid h-14 w-14 shrink-0 place-items-center rounded-2xl text-2xl font-bold" :style="iso ? { background: iso.farbe, color: iso.schrift } : {}" :class="iso ? '' : 'border-2 border-dashed border-line text-mute'" :title="iso ? `ISO ${iso.code}: ${iso.name}${iso.abgeleitet ? ' (aus dem Namen abgeleitet)' : ''}` : 'ISO-Gruppe unbekannt'">
          {{ iso?.code ?? '?' }}
        </div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-base font-semibold" :class="teil.material ? '' : 'text-mute'">{{ teil.material || 'Werkstoff wählen' }}</div>
          <div class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-mute">
            <span v-if="rohText(roh)" class="font-medium text-ink tnum">{{ rohText(roh) }} mm</span>
            <span v-else>Rohteil-Maße fehlen</span>
            <span class="tnum">{{ kg(teil.gewichtKg || 0) }} × {{ eur(teil.materialPreisKg || 0) }}/kg</span>
          </div>
          <div v-if="roh.zeugnis || roh.ausLager || teil.pauschalMaterial" class="mt-1.5 flex flex-wrap gap-1.5">
            <span v-if="roh.zeugnis" class="chip"><FileBadge :size="12" /> Zeugnis {{ roh.zeugnis }}</span>
            <span v-if="roh.ausLager" class="chip"><Warehouse :size="12" /> aus Lager</span>
            <span v-if="teil.pauschalMaterial" class="chip tnum">+ {{ eur(teil.pauschalMaterial) }} einmalig</span>
          </div>
        </div>
        <div class="shrink-0 text-right">
          <div class="label">je Stück</div>
          <div class="text-xl font-semibold tnum">{{ eur(proStueck) }}</div>
        </div>
      </div>
    </div>
    <!-- Vorschlag aus dem 3D-Modell -->
    <div v-if="vorschlagNeu && !nurAnsicht" class="flex flex-wrap items-center gap-2 border-t border-line bg-accent-soft/50 px-5 py-2.5 text-sm">
      <Wand2 :size="15" class="shrink-0 text-accent" />
      <span>Aus dem 3D-Modell: <strong class="tnum">{{ vorschlagText }} mm</strong><span v-if="vorschlag.drehteil" class="text-mute"> · Drehfrästeil</span></span>
      <button type="button" class="btn btn-primary ml-auto !py-1 text-xs" @click="vorschlagUebernehmen"><Check :size="13" /> Übernehmen</button>
    </div>
    </template>

    <!-- Popup -->
    <Teleport to="body">
      <div v-if="offen" class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="offen = false" @keydown.esc="offen = false">
        <Transition name="pop" appear>
          <div class="card flex max-h-[92vh] w-[min(980px,96vw)] flex-col overflow-hidden shadow-2xl">
            <header class="flex items-center gap-3 border-b border-line px-6 py-4">
              <div class="grid h-9 w-9 place-items-center rounded-xl text-base font-bold" :style="iso ? { background: iso.farbe, color: iso.schrift } : {}" :class="iso ? '' : 'bg-surface2 text-mute'">{{ iso?.code ?? '?' }}</div>
              <div class="min-w-0">
                <h2 class="text-base font-semibold">Rohmaterial</h2>
                <p class="truncate text-xs text-mute">{{ teil.name || 'Bauteil' }}<template v-if="teil.teilenummer"> · {{ teil.teilenummer }}</template></p>
              </div>
              <div class="ml-auto text-right">
                <div class="label">je Stück</div>
                <div class="text-lg font-semibold tnum">{{ eur(proStueck) }}</div>
              </div>
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" title="Schließen" @click="offen = false"><X :size="18" /></button>
            </header>

            <fieldset :disabled="nurAnsicht" class="m-0 grid min-h-0 flex-1 overflow-auto border-0 p-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
              <!-- Werkstoff nach ISO-Gruppe -->
              <div class="flex min-h-0 flex-col border-line p-5 md:border-r">
                <div class="label mb-2">Werkstoff</div>
                <div class="mb-2 flex flex-wrap gap-1.5">
                  <button type="button" class="iso-chip" :class="isoFilter === '' ? 'aktiv' : ''" @click="isoFilter = ''">Alle</button>
                  <button v-for="g in ISO_GRUPPEN" :key="g.code" type="button" class="iso-chip" :class="isoFilter === g.code ? 'aktiv' : ''" :title="g.name" @click="isoFilter = isoFilter === g.code ? '' : g.code">
                    <span class="grid h-5 w-5 place-items-center rounded-md text-[11px] font-bold" :style="{ background: g.farbe, color: g.schrift }">{{ g.code }}</span>
                    <span class="tnum text-mute">{{ anzahlJe(g.code) }}</span>
                  </button>
                </div>
                <label class="relative mb-2 block">
                  <Search :size="14" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
                  <input v-model="suche" class="field !py-1.5 !pl-8 text-sm" placeholder="Werkstoff suchen, z. B. 1.4305 oder AlMg" />
                </label>
                <div class="min-h-[180px] flex-1 overflow-auto rounded-xl border border-line md:max-h-[46vh]">
                  <button
                    v-for="m in liste" :key="m.name" type="button" class="flex w-full items-center gap-2.5 border-b border-line px-3 py-2 text-left text-sm last:border-0 hover:bg-surface2"
                    :class="m.name === teil.material ? 'bg-accent-soft/60' : ''" @click="materialWechsel(m.name)"
                  >
                    <span class="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[11px] font-bold" :style="isoGruppe(m.name, m.isoGruppe) ? { background: isoGruppe(m.name, m.isoGruppe).farbe, color: isoGruppe(m.name, m.isoGruppe).schrift } : {}" :class="isoGruppe(m.name, m.isoGruppe) ? '' : 'bg-surface2 text-mute'">{{ isoGruppe(m.name, m.isoGruppe)?.code ?? '?' }}</span>
                    <span class="min-w-0 flex-1 truncate" :class="m.name === teil.material ? 'font-semibold' : ''">{{ m.name }}</span>
                    <span class="shrink-0 text-xs text-mute tnum">{{ m.dichte ? `${zahl(m.dichte, 2)} g/cm³` : '' }}</span>
                    <span class="w-16 shrink-0 text-right text-xs tnum">{{ m.preisKg ? `${zahl(m.preisKg, 2)} €/kg` : '' }}</span>
                    <Check v-if="m.name === teil.material" :size="14" class="shrink-0 text-accent" />
                  </button>
                  <p v-if="!liste.length" class="px-3 py-6 text-center text-xs text-mute">Kein Werkstoff gefunden. Neue Werkstoffe in den Stammdaten unter Rohmaterial anlegen.</p>
                </div>
                <p v-if="teil.material && !stamm" class="mt-2 text-xs text-warn">„{{ teil.material }}“ steht nicht in den Stammdaten.</p>
              </div>

              <!-- Rohteil, Gewicht, Preis, Zeugnis, Lager -->
              <div class="space-y-5 p-5">
                <div>
                  <div class="label mb-2">Rohteil</div>
                  <div class="mb-3 grid grid-cols-4 gap-1 rounded-xl border border-line bg-surface2 p-1" role="radiogroup" aria-label="Form">
                    <button v-for="f in FORMEN" :key="f.id" type="button" role="radio" :aria-checked="roh.form === f.id" class="flex flex-col items-center gap-1 rounded-lg px-2 py-2 text-xs transition" :class="roh.form === f.id ? 'bg-surface font-medium text-ink shadow-sm' : 'text-mute hover:text-ink'" @click="roh.form = f.id">
                      <component :is="FORM_ICON[f.id]" :size="18" :class="roh.form === f.id ? 'text-accent' : ''" /> {{ f.label }}
                    </button>
                  </div>
                  <div class="grid gap-3" :class="felder.length === 3 ? 'grid-cols-3' : 'grid-cols-2'">
                    <NumField v-for="f in felder" :key="f" v-model="roh[f]" :label="FELD_LABEL[f]" unit="mm" :decimals="1" :step="1" />
                  </div>
                  <div v-if="vorschlagText" class="mt-3 flex flex-wrap items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs" :class="vorschlagNeu ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'">
                    <Wand2 :size="14" class="shrink-0" />
                    <span>3D-Modell: <strong class="tnum">{{ vorschlagText }} mm</strong> (auf volle mm, Aufmaß {{ zahl(teil.aufmass || 0, 1) }} mm je Seite)</span>
                    <button v-if="vorschlagNeu" type="button" class="btn ml-auto !py-0.5 text-xs" @click="vorschlagUebernehmen">Übernehmen</button>
                    <span v-else class="ml-auto flex items-center gap-1"><Check :size="13" /> übernommen</span>
                  </div>
                  <p v-else class="mt-3 text-xs text-mute">Mit einem 3D-Modell schlägt CNC One das Rohteil vor (Quader, Rund oder Drehfräs-Rohteil, siehe 3D-Ansicht).</p>
                </div>

                <div class="grid gap-3 sm:grid-cols-2">
                  <div>
                    <div class="mb-1 flex items-center justify-between gap-2"><span class="label">Gewicht je Stück</span><Toggle v-model="roh.gewichtAuto" klein label="aus Maßen" /></div>
                    <div v-if="roh.gewichtAuto" class="field flex items-center justify-between !bg-surface2 tnum">
                      <span>{{ berechnet ? kg(berechnet) : '–' }}</span>
                      <span class="text-xs text-mute">{{ dichte ? `${zahl(dichte, 2)} g/cm³${dichteGeschaetzt ? ' (geschätzt)' : ''}` : 'Dichte fehlt' }}</span>
                    </div>
                    <NumField v-else v-model="teil.gewichtKg" unit="kg" :step="0.05" :decimals="3" />
                    <p v-if="roh.gewichtAuto && !berechnet" class="mt-1 text-[11px] text-mute">{{ !dichte ? 'Für das Gewicht einen Werkstoff mit Dichte wählen.' : 'Maße eintragen, dann rechnet sich das Gewicht.' }} Bis dahin gilt {{ kg(teil.gewichtKg || 0) }}.</p>
                  </div>
                  <NumField v-model="teil.materialPreisKg" label="Preis" unit="€/kg" :hint="'= ' + eur(proStueck) + ' je Stück'" />
                  <NumField v-model="teil.pauschalMaterial" label="Pauschal Material (einmalig)" unit="€" />
                  <div class="flex flex-col justify-end gap-2 pb-1">
                    <Toggle v-model="teil.pauschalAlsZeile" klein label="Pauschale als eigene Zeile" />
                    <Toggle v-model="teil.werkstoffDrucken" klein label="Werkstoff im Angebots-PDF" />
                  </div>
                </div>

                <div class="grid gap-3 sm:grid-cols-2">
                  <div>
                    <div class="label mb-1">Materialzeugnis</div>
                    <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1 text-xs" role="radiogroup" aria-label="Materialzeugnis">
                      <button v-for="z in ZEUGNISSE" :key="z" type="button" role="radio" :aria-checked="roh.zeugnis === z" class="flex-1 rounded-lg py-1.5 transition" :class="roh.zeugnis === z ? 'bg-surface font-medium text-ink shadow-sm' : 'text-mute hover:text-ink'" @click="roh.zeugnis = z">{{ z || 'keins' }}</button>
                    </div>
                  </div>
                  <div>
                    <div class="mb-1 flex items-center justify-between gap-2"><span class="label">Lager</span><Toggle v-model="roh.ausLager" klein label="aus eigenem Lager" /></div>
                    <input v-model="roh.lagerHinweis" class="field" :placeholder="roh.ausLager ? 'Lagerplatz, Charge, Reststück …' : 'Wird bestellt'" :disabled="!roh.ausLager" />
                  </div>
                </div>
                <p class="flex items-start gap-1.5 text-[11px] text-mute"><Warehouse :size="12" class="mt-0.5 shrink-0" /> Bestände aus dem Rohmaterial-Lager erscheinen hier, sobald das Rohmaterial-Lager gebaut ist.</p>
              </div>
            </fieldset>

            <footer class="flex items-center gap-2 border-t border-line bg-surface2 px-6 py-3">
              <span class="text-xs text-mute tnum">{{ kg(teil.gewichtKg || 0) }} × {{ eur(teil.materialPreisKg || 0) }}/kg = {{ eur(proStueck) }} je Stück</span>
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
.iso-chip { display: inline-flex; align-items: center; gap: 0.35rem; border-radius: 0.6rem; border: 1px solid var(--line); background: var(--surface); padding: 0.2rem 0.45rem; font-size: 0.75rem; }
.iso-chip.aktiv { border-color: var(--accent); background: var(--accent-soft); }
</style>
