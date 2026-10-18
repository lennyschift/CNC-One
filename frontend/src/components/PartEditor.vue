<script setup>
import { ref, onMounted, computed } from 'vue';
import { Cog, Clock, Layers, Receipt, TrendingDown, FileBox, ListChecks, Workflow, Database, Hash, Info } from '@lucide/vue';
import NumField from './NumField.vue';
import Toggle from './Toggle.vue';
import TierTable from './TierTable.vue';
import PriceChart from './PriceChart.vue';
import AnimatedNumber from './AnimatedNumber.vue';
import PartImage from './PartImage.vue';
import ArbeitsplanEditor from './ArbeitsplanEditor.vue';
import { useAngebot } from '../stores/angebot.js';
import { repo } from '../data/repo.js';
import { eur, zahl } from '../lib/format.js';
import { ruestKosten, stueckKosten, fremdProStueck, hatPlan, materialProStueck } from '../lib/calc.js';

const props = defineProps({ teil: { type: Object, required: true }, ergebnis: { type: Object, required: true } });
const emit = defineEmits(['anfrage']);

if (!props.teil.arbeitsgaenge) props.teil.arbeitsgaenge = [];
const angebot = useAngebot();
const ausPlan = computed(() => hatPlan(props.teil));
const zuordnung = computed(() => angebot.zuordnung[props.teil.id] ?? null);
const bestand = computed(() => zuordnung.value?.herkunft === 'bestand');

const maschinen = ref([]);
const materialien = ref([]);
onMounted(async () => {
  [maschinen.value, materialien.value] = await Promise.all([repo.maschinen.liste(), repo.materialien.liste()]);
});

function maschineWechsel(name) {
  props.teil.maschine = name;
  const m = maschinen.value.find((x) => x.name === name);
  if (m) { props.teil.satzRuest = m.satz; props.teil.satzStueck = m.satz; }
}
function materialWechsel(name) {
  props.teil.material = name;
  const m = materialien.value.find((x) => x.name === name);
  if (m) props.teil.materialPreisKg = m.preisKg;
}

const kosten = [
  { key: 'messkosten', flag: 'mess', label: 'Messkosten' },
  { key: 'sonderkosten', flag: 'sonder', label: 'Sonderkosten' },
  { key: 'expresskosten', flag: 'express', label: 'Expresskosten' },
];

const staffelModus = computed(() => props.teil.staffel.aktiv);
const groesse = (b) => (b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);
</script>

<template>
  <div class="space-y-4">
    <!-- Kopf -->
    <section class="card p-5">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <PartImage :teil="teil" :groesse="104" />
        <div class="min-w-[260px] flex-1">
          <input v-model="teil.name" class="w-full bg-transparent text-2xl font-semibold tracking-tight outline-none placeholder:text-mute" placeholder="Bezeichnung des Bauteils" />
          <div class="mt-3 grid max-w-xl grid-cols-2 gap-3">
            <label class="block"><span class="label mb-1 block">Teilenummer</span><input v-model="teil.teilenummer" class="field" :disabled="bestand" placeholder="z. B. F31.683.122" /></label>
            <label class="block"><span class="label mb-1 block">Zeichnungsnummer</span><input v-model="teil.zeichnungsnr" class="field" placeholder="optional" /></label>
          </div>
          <div class="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
            <Toggle v-if="!bestand" v-model="teil.seriennummern" klein label="Seriennummern führen" />
            <span v-else class="inline-flex items-center gap-1.5 text-xs text-mute"><Hash :size="13" /> Seriennummern: {{ teil.seriennummern ? 'ja' : 'nein' }} <span class="opacity-70">(in den Stammdaten ändern)</span></span>
          </div>
          <!-- Stammdaten: Bestand oder neu angelegt -->
          <div class="mt-3 flex flex-wrap items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs" :class="zuordnung?.herkunft === 'neu' ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'">
            <Database v-if="zuordnung" :size="14" class="shrink-0" /><Info v-else :size="14" class="shrink-0" />
            <span v-if="zuordnung?.herkunft === 'neu'"><strong>Neu angelegt</strong> mit diesem Angebot, steht schon in den Stammdaten (<span class="tnum">{{ zuordnung.bauteilId }}</span>). Änderungen hier gelten dort mit.</span>
            <span v-else-if="bestand"><strong>Bestandsbauteil</strong> <span class="tnum">{{ zuordnung.bauteilId }}</span> aus den Stammdaten. Teilenummer und Stammdaten bleiben unverändert; „Am Bauteil speichern“ aktualisiert den Arbeitsplan.</span>
            <span v-else>Noch nicht in den Stammdaten: Sobald Kunde und Teilenummer eingetragen sind, wird das Bauteil dort angelegt. Eine vorhandene Teilenummer wird als Bestandsbauteil erkannt, es entsteht keine Dublette.</span>
            <RouterLink v-if="zuordnung" to="/stammdaten/bauteile" class="ml-auto underline-offset-2 hover:underline">In den Stammdaten ansehen</RouterLink>
          </div>
        </div>
        <div class="flex gap-3">
          <div class="min-w-[130px] rounded-2xl bg-surface2 px-4 py-3">
            <div class="label">Stückpreis</div>
            <div class="mt-1 text-xl font-semibold"><AnimatedNumber :value="ergebnis.stueckpreis" :format="eur" /></div>
          </div>
          <div class="min-w-[150px] rounded-2xl bg-accent-soft px-4 py-3">
            <div class="label !text-accent">Gesamt netto</div>
            <div class="mt-1 text-xl font-semibold text-accent"><AnimatedNumber :value="ergebnis.gesamt" :format="eur" /></div>
          </div>
        </div>
      </div>
    </section>

    <div class="grid gap-4 xl:grid-cols-2">
      <!-- Menge & Maschine -->
      <section class="card p-5">
        <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><Cog :size="16" class="text-accent" /> Menge und Maschine</h3>
        <div class="grid grid-cols-2 gap-3">
          <NumField v-model="teil.menge" label="Stückzahl" unit="Stk" :decimals="0" :min="1" />
          <template v-if="!ausPlan">
            <label class="block">
              <span class="label mb-1 block">Maschine</span>
              <select class="field" :value="teil.maschine" @change="maschineWechsel($event.target.value)">
                <option value="">– wählen –</option>
                <option v-for="m in maschinen" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
            </label>
            <NumField v-model="teil.satzRuest" label="Stundensatz Rüsten" unit="€/h" />
            <NumField v-model="teil.satzStueck" label="Stundensatz Fertigung" unit="€/h" />
          </template>
        </div>
        <p v-if="ausPlan" class="mt-3 rounded-xl bg-surface2 px-3.5 py-2.5 text-xs text-mute">Maschinen und Stundensätze kommen aus den Arbeitsgängen weiter unten.</p>
      </section>

      <!-- Zeiten -->
      <section class="card p-5">
        <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><Clock :size="16" class="text-accent" /> Zeiten</h3>
        <div v-if="!ausPlan" class="grid grid-cols-2 gap-3">
          <NumField v-model="teil.ruestMin" label="Rüstzeit" unit="min" :step="5" :hint="'= ' + eur(ruestKosten(teil))" />
          <NumField v-model="teil.stueckMin" label="Stückzeit" unit="min" :step="0.5" :hint="'= ' + eur(stueckKosten(teil)) + ' / Stk'" />
        </div>
        <dl v-else class="space-y-2 text-sm">
          <div class="flex justify-between"><dt class="text-mute">Rüstkosten aus Arbeitsgängen</dt><dd class="font-medium tnum">{{ eur(ruestKosten(teil)) }}</dd></div>
          <div class="flex justify-between"><dt class="text-mute">Stückkosten aus Arbeitsgängen</dt><dd class="font-medium tnum">{{ eur(stueckKosten(teil)) }}</dd></div>
          <div v-if="fremdProStueck(teil)" class="flex justify-between"><dt class="text-mute">Fremdvergabe je Stück</dt><dd class="font-medium tnum">{{ eur(fremdProStueck(teil)) }}</dd></div>
        </dl>
        <p v-if="!ausPlan" class="mt-3 text-xs text-mute">Pfeiltasten ändern den Wert, <span class="kbd">Shift</span> in Zehnerschritten, <span class="kbd">Alt</span> in Zehntelschritten.</p>
      </section>

      <!-- Material -->
      <section class="card p-5">
        <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><Layers :size="16" class="text-accent" /> Rohmaterial</h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2 flex items-end gap-3">
            <PartImage art="material" :groesse="42" />
            <label class="block flex-1">
              <span class="label mb-1 block">Rohmaterial</span>
              <select class="field" :value="teil.material" @change="materialWechsel($event.target.value)">
                <option value="">– wählen –</option>
                <option v-for="m in materialien" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
            </label>
          </div>
          <NumField v-model="teil.materialPreisKg" label="Preis" unit="€/kg" />
          <NumField v-model="teil.gewichtKg" label="Gewicht" unit="kg" :step="0.05" :decimals="3" :hint="'= ' + eur(materialProStueck(teil)) + ' / Stk'" />
          <NumField v-model="teil.pauschalMaterial" label="Pauschal Material (einmalig)" unit="€" class="col-span-2" />
        </div>
        <div class="mt-3"><Toggle v-model="teil.pauschalAlsZeile" klein label="Pauschal Material als eigene Zeile im Angebot" /></div>
      </section>

      <!-- Zusatzkosten -->
      <section class="card p-5">
        <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><Receipt :size="16" class="text-accent" /> Zusatzkosten (einmalig)</h3>
        <div class="space-y-3">
          <div v-for="k in kosten" :key="k.key" class="grid grid-cols-[1fr_auto] items-end gap-3">
            <NumField v-model="teil[k.key]" :label="k.label" unit="€" />
            <div class="pb-2.5"><Toggle v-model="teil.inStueckpreis[k.flag]" klein label="im Stückpreis" /></div>
          </div>
          <div class="grid grid-cols-[1fr_auto] items-center gap-3 border-t border-line pt-3">
            <span class="text-sm text-mute">Rüstkosten</span>
            <Toggle v-model="teil.inStueckpreis.ruest" klein label="im Stückpreis" :class="staffelModus ? 'pointer-events-none opacity-40' : ''" />
          </div>
          <p v-if="staffelModus" class="text-xs text-mute">Bei Staffelpreisen sind Rüstkosten immer im Stückpreis enthalten.</p>
        </div>
      </section>
    </div>

    <!-- Arbeitsgänge -->
    <section class="card p-5">
      <h3 class="mb-1 flex items-center gap-2 text-sm font-semibold"><Workflow :size="16" class="text-accent" /> Arbeitsgänge</h3>
      <p class="mb-4 text-xs text-mute">Rüst- und Stückkosten rechnen sich aus Zeit und Maschinensatz je Arbeitsgang. Fremdvergaben bringen ihren Preis mit. Der Plan lässt sich am Bauteil speichern.</p>
      <ArbeitsplanEditor :arbeitsgaenge="teil.arbeitsgaenge" :kunde-id="angebot.kopf.kundeId" :teilenummer="teil.teilenummer" :teil="teil" @anfrage="emit('anfrage', $event)" />
    </section>

    <!-- Staffel -->
    <section class="card p-5">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 class="flex items-center gap-2 text-sm font-semibold"><TrendingDown :size="16" class="text-accent" /> Staffelpreise</h3>
        <Toggle v-model="teil.staffel.aktiv" label="Mehrere Mengen anbieten" />
      </div>
      <div class="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <TierTable v-if="staffelModus" :teil="teil" :ergebnis="ergebnis" />
          <p v-else class="rounded-xl bg-surface2 px-4 py-6 text-center text-sm text-mute">Aus. Das Angebot enthält nur die Stückzahl {{ teil.menge }}.</p>
        </div>
        <div>
          <div class="label mb-1">Stückpreis nach Menge</div>
          <PriceChart :teil="teil" />
          <p class="mt-1 text-xs text-mute">Zeigt, wie stark die Rüstkosten mit der Menge verschwinden.</p>
        </div>
      </div>
    </section>

    <div class="grid gap-4 xl:grid-cols-2">
      <!-- Vorschau -->
      <section class="card p-5">
        <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><ListChecks :size="16" class="text-accent" /> So erscheint es im Angebot</h3>
        <table class="w-full text-sm">
          <tbody>
            <template v-if="staffelModus">
              <tr class="text-xs text-mute"><td class="pb-1">Menge</td><td class="pb-1 text-right">Stückpreis</td><td class="pb-1 text-right">Gesamt</td></tr>
              <tr v-for="s in ergebnis.stufen" :key="s.menge" class="border-t border-line">
                <td class="py-1.5 tnum">{{ s.menge }} Stk</td><td class="py-1.5 text-right tnum">{{ eur(s.stueckpreis) }}</td><td class="py-1.5 text-right font-medium tnum">{{ eur(s.gesamt) }}</td>
              </tr>
              <tr v-for="z in ergebnis.zeilen" :key="z.label" class="border-t border-line text-mute">
                <td class="py-1.5 pl-3" colspan="2">↳ {{ z.label }}</td><td class="py-1.5 text-right tnum">{{ eur(z.betrag) }}</td>
              </tr>
            </template>
            <template v-else>
              <tr v-for="(z, i) in ergebnis.zeilen" :key="z.label + i" class="border-t border-line first:border-0" :class="z.typ === 'kosten' ? 'text-mute' : ''">
                <td class="py-1.5" :class="z.typ === 'kosten' ? 'pl-3' : 'font-medium'">{{ z.typ === 'kosten' ? '↳ ' : '' }}{{ z.label }}</td>
                <td class="py-1.5 text-right tnum">{{ z.typ === 'teil' ? `${z.menge} × ${eur(z.einzel)}` : '' }}</td>
                <td class="py-1.5 text-right tnum" :class="z.typ === 'teil' ? 'font-medium' : ''">{{ eur(z.betrag) }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </section>

      <!-- Dateien -->
      <section class="card p-5">
        <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><FileBox :size="16" class="text-accent" /> Dateien</h3>
        <ul v-if="teil.dateien.length" class="space-y-1.5">
          <li v-for="(d, i) in teil.dateien" :key="i" class="flex items-center gap-2.5 rounded-xl bg-surface2 px-3 py-2 text-sm">
            <span class="rounded-md bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold uppercase text-accent">{{ d.art }}</span>
            <span class="flex-1 truncate">{{ d.name }}</span>
            <span class="text-xs text-mute tnum">{{ groesse(d.groesse) }}</span>
          </li>
        </ul>
        <p v-else class="rounded-xl border border-dashed border-line px-4 py-8 text-center text-sm text-mute">
          Keine Dateien. STEP- oder PDF-Dateien einfach irgendwo ins Fenster ziehen.<br />
          <span class="text-xs">(3D-Ansicht und automatische Messung folgen im nächsten Schritt)</span>
        </p>
      </section>
    </div>
  </div>
</template>
