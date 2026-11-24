<script setup>
import { ref, onMounted, computed } from 'vue';
import { TrendingDown, ListChecks, Database, Hash, Info, History, CalendarDays, ShoppingCart, BadgeCheck } from '@lucide/vue';
import Toggle from './Toggle.vue';
import KalkulationTabelle from './KalkulationTabelle.vue';
import PriceChart from './PriceChart.vue';
import AnimatedNumber from './AnimatedNumber.vue';
import PartImage from './PartImage.vue';
import TeilDateien from './TeilDateien.vue';
import BauteilHistorie from './BauteilHistorie.vue';
import AehnlicheBauteile from './AehnlicheBauteile.vue';
import TeilefamilieKarte from './TeilefamilieKarte.vue';
import { kalkulationUebernehmen, festpreisUebernehmen } from '../lib/historie.js';
import { call } from '../data/api.js';
import { uid, zahl } from '../lib/format.js';
import { useUi } from '../stores/ui.js';
import { useAngebot } from '../stores/angebot.js';
import { repo } from '../data/repo.js';
import { eur } from '../lib/format.js';
import { festerPreis, berechne } from '../lib/calc.js';

const props = defineProps({ teil: { type: Object, required: true }, ergebnis: { type: Object, required: true } });
const emit = defineEmits(['anfrage']);

if (!props.teil.arbeitsgaenge) props.teil.arbeitsgaenge = [];
const angebot = useAngebot();
const zuordnung = computed(() => angebot.zuordnung[props.teil.id] ?? null);
const bestand = computed(() => zuordnung.value?.herkunft === 'bestand');
// Revision dieses Angebots im Vergleich zum Bauteil: neue Revision, ältere oder die aktuelle (mit früheren)
const revisionHinweis = computed(() => {
  const z = zuordnung.value;
  const r = (props.teil.revision ?? '').trim();
  if (!z?.bauteilId) return null;
  const gleich = (a, b) => (a ?? '').toLowerCase() === (b ?? '').toLowerCase();
  const bekannt = z.revisionen ?? [];
  const frueher = bekannt.filter((x) => !gleich(x, z.revision));
  if (!r || gleich(r, z.revision)) return frueher.length ? { text: `Revision ${z.revision || r} ist am Bauteil aktuell, frühere: ${frueher.join(', ')}` } : null;
  if (bekannt.some((x) => gleich(x, r))) return { warn: true, text: `Am Bauteil ist Revision ${z.revision} aktuell, dieses Angebot gilt für die ältere Revision ${r}.` };
  return { text: `Neue Revision ${r}: wird beim Speichern am Bauteil abgelegt und ist dann die aktuelle${z.revision ? `, Revision ${z.revision} bleibt mit ihren Dateien erhalten` : ''}.` };
});

const materialien = ref([]);
onMounted(async () => { materialien.value = await repo.materialien.liste(); });

const staffelModus = computed(() => props.teil.staffel.aktiv);
// Fester Stückpreis: ohne Kalkulation, Zeiten, Material und Rüstkosten zählen dann nicht
const fest = computed(() => festerPreis(props.teil));
// Kachel „Stückpreis“: beim festen Preis genau der eingegebene (ohne anteilige einmalige Kosten)
const anzeigePreis = computed(() => (fest.value && !staffelModus.value ? props.ergebnis.zeilen.find((z) => z.typ === 'teil')?.einzel ?? 0 : props.ergebnis.stueckpreis));
// Frühere Preise aus der Historie übernehmen (Wiederholanfrage); alles bleibt danach änderbar
const ui = useUi();
async function kalkulationAus(a) {
  if (!confirm(`Kalkulation aus ${a.angebot} übernehmen? Zeiten, Material, Kosten, Staffeln und Arbeitsgänge dieses Bauteils werden ersetzt.`)) return;
  try {
    const alt = await call('cnc_one.api.historie.kalkulation', { angebot: a.angebot, position_key: a.positionKey });
    kalkulationUebernehmen(props.teil, alt, uid);
    ui.toast(`Kalkulation aus ${a.angebot} übernommen`);
  } catch { ui.toast('Die Kalkulation ließ sich nicht laden.', 'warn'); }
}
// Teilefamilie: Kalkulation dieses Bauteils auf die anderen Varianten im selben Angebot übertragen
const andereImAngebot = computed(() => angebot.teile.filter((t) => t !== props.teil).map((t) => ({ teil: t, bauteilId: angebot.zuordnung[t.id]?.bauteilId ?? '' })).filter((x) => x.bauteilId));
function aufVariantenUebertragen(liste) {
  const namen = liste.map((x) => x.teil.teilenummer || x.teil.name).join(', ');
  if (!confirm(`Kalkulation von ${props.teil.teilenummer || props.teil.name} auf ${namen} übertragen? Zeiten, Material, Kosten, Staffeln und Arbeitsgänge dort werden ersetzt.`)) return;
  for (const x of liste) kalkulationUebernehmen(x.teil, JSON.parse(JSON.stringify(props.teil)), uid);
  ui.toast(`Kalkulation auf ${liste.length} Variante${liste.length === 1 ? '' : 'n'} übertragen`, 'ok');
}
const familieKarte = ref(null);
function festpreisAus(e, umgelegt) {
  festpreisUebernehmen(props.teil, e, { umgelegt });
  ui.toast(`Preis aus ${e.angebot || e.auftrag} als festen Stückpreis übernommen`);
}
// Aus einer Bestellung: Preis wie bestellt; daneben, was die Kalkulation (Zeiten, Material, Arbeitsgänge) ergäbe
const bestellung = computed(() => props.teil.bestellung ?? null);
const kalkuliert = computed(() => {
  if (!bestellung.value) return null;
  const r = berechne({ ...props.teil, preisart: 'kalkuliert', staffel: { ...props.teil.staffel, aktiv: false } });
  return r.gesamt > 0 ? Math.round((r.gesamt / Math.max(1, props.teil.menge)) * 100) / 100 : null;
});
// Schon gefertigt, bevor es CNC One gab (von Hand; am Bauteil gespeichert). Aufträge in CNC One zeigt die Historie.
const frueher = computed(() => props.teil.frueher ?? zuordnung.value?.frueher ?? { gefertigt: false, notiz: '' });
function frueherSetzen(feld, wert) { props.teil.frueher = { ...frueher.value, [feld]: wert }; }
const groesse = (b) => (b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);
</script>

<template>
  <div class="space-y-4">
    <!-- Kopf -->
    <fieldset :disabled="!!angebot.nurAnsicht" class="m-0 min-w-0 border-0 p-0">
    <section class="card p-5">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <PartImage iso :teil="teil" :groesse="104" />
        <div class="min-w-[260px] flex-1">
          <input v-model="teil.name" class="w-full bg-transparent text-2xl font-semibold tracking-tight outline-none placeholder:text-mute" placeholder="Bezeichnung des Bauteils" />
          <div class="mt-3 grid max-w-2xl grid-cols-[1fr_1fr_90px] gap-3">
            <label class="block"><span class="label mb-1 block">Teilenummer</span><input v-model="teil.teilenummer" class="field" :disabled="bestand" placeholder="z. B. F31.683.122" /></label>
            <label class="block"><span class="label mb-1 block">Zeichnungsnummer</span><input v-model="teil.zeichnungsnr" class="field" placeholder="optional" /></label>
            <label class="block"><span class="label mb-1 block">Revision</span><input v-model="teil.revision" class="field" placeholder="–" /></label>
          </div>
          <div class="mt-3 grid max-w-2xl gap-3 md:grid-cols-2">
            <label class="block"><span class="label mb-1 block">Beschreibung für den Kunden <span class="font-normal normal-case text-mute">(steht im Angebot)</span></span>
              <textarea v-model="teil.infoKunde" rows="2" class="field min-h-[60px] resize-y" placeholder="z. B. gleitgeschliffen, entgratet" /></label>
            <label class="block"><span class="label mb-1 block">Interne Notiz <span class="font-normal normal-case text-mute">(am Bauteil gespeichert)</span></span>
              <textarea v-model="teil.notizIntern" rows="2" class="field min-h-[60px] resize-y" placeholder="nur für uns, z. B. Spannen, Besonderheiten" /></label>
          </div>
          <p v-if="revisionHinweis" class="mt-2 flex max-w-2xl items-start gap-1.5 text-xs" :class="revisionHinweis.warn ? 'text-warn' : 'text-mute'"><History :size="13" class="mt-0.5 shrink-0" /> {{ revisionHinweis.text }}</p>
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
          <div class="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <label class="inline-flex cursor-pointer items-center gap-1.5" :class="frueher.gefertigt ? 'font-medium text-ok' : 'text-mute'" title="Wurde schon einmal gefertigt, bevor es CNC One gab; wird am Bauteil gespeichert">
              <input type="checkbox" class="accent-[var(--accent)]" :checked="frueher.gefertigt" @change="frueherSetzen('gefertigt', $event.target.checked)" /><BadgeCheck :size="14" /> Schon gefertigt (vor CNC One)
            </label>
            <input v-if="frueher.gefertigt" :value="frueher.notiz" class="field !w-56 !py-0.5 !text-xs" placeholder="z. B. 2022, alter Auftrag 4711" @change="frueherSetzen('notiz', $event.target.value)" />
          </div>
          <!-- aus einer Bestellung des Kunden -->
          <div v-if="bestellung" class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl bg-accent-soft/60 px-3.5 py-2 text-xs">
            <span class="inline-flex items-center gap-1.5 font-medium text-accent"><ShoppingCart :size="14" /> Bestellt{{ bestellung.position ? ` (Pos. ${bestellung.position})` : '' }}: {{ bestellung.menge }} Stk × {{ eur(bestellung.preis) }}</span>
            <span v-if="kalkuliert != null" :class="kalkuliert > bestellung.preis ? 'text-warn' : 'text-mute'">Kalkulation ergäbe {{ eur(kalkuliert) }} je Stk<template v-if="bestellung.preis"> ({{ kalkuliert > bestellung.preis ? '+' : '' }}{{ Math.round(((kalkuliert - bestellung.preis) / bestellung.preis) * 100) }} %)</template></span>
            <span v-else class="text-mute">Noch keine Kalkulation (Zeiten, Material) für den Vergleich</span>
            <button v-if="teil.preisart !== 'fest' || teil.festpreis !== bestellung.preis" class="underline-offset-2 hover:underline" @click="teil.preisart = 'fest'; teil.festpreis = bestellung.preis; teil.staffel.aktiv = false">Preis der Bestellung wieder einsetzen</button>
          </div>
        </div>
        <div class="flex flex-col gap-3">
        <div class="flex gap-3">
          <div class="min-w-[130px] rounded-2xl bg-surface2 px-4 py-3">
            <div class="label">Stückpreis</div>
            <div class="mt-1 text-xl font-semibold"><AnimatedNumber :value="anzeigePreis" :format="eur" /></div>
          </div>
          <div class="min-w-[150px] rounded-2xl bg-accent-soft px-4 py-3">
            <div class="label !text-accent">Gesamt netto</div>
            <div class="mt-1 text-xl font-semibold text-accent"><AnimatedNumber :value="ergebnis.gesamt" :format="eur" /></div>
          </div>
        </div>
        <!-- Liefertermin der Position: steht nicht im Angebot, geht in Auftrag und Fertigung -->
        <label class="block" title="Steht nicht im Angebot; wird in den Auftrag und die Fertigung übernommen und lässt sich dort ändern">
          <span class="label mb-1 flex items-center gap-1.5"><CalendarDays :size="12" /> Liefertermin <span class="font-normal normal-case text-mute">(intern)</span></span>
          <input v-model="teil.liefertermin" type="date" class="field" />
        </label>
        </div>
      </div>
    </section>

    </fieldset>

    <!-- außerhalb des gesperrten Bereichs: auch beim reinen Ansehen auf- und zuklappbar -->
    <BauteilHistorie v-if="zuordnung?.bauteilId || (angebot.kopf.kundeId && teil.teilenummer)" class="card" :bauteil-id="zuordnung?.bauteilId ?? ''" :kunde-id="angebot.kopf.kundeId" :teilenummer="teil.teilenummer" :ohne-angebot="angebot.angebotId ?? ''" :aktionen="!angebot.nurAnsicht" :offen="false" @kalkulation="kalkulationAus" @festpreis="festpreisAus" />
    <TeilefamilieKarte v-if="zuordnung?.bauteilId" ref="familieKarte" class="card" :bauteil-id="zuordnung.bauteilId" :teile-im-angebot="andereImAngebot" :aktionen="!angebot.nurAnsicht" @uebertragen="aufVariantenUebertragen" />
    <AehnlicheBauteile class="card" :bauteil-id="zuordnung?.bauteilId ?? ''" :kunde-id="angebot.kopf.kundeId" :teil="teil" :aktionen="!angebot.nurAnsicht" @kalkulation="kalkulationAus" @familie="familieKarte?.laden()" />

    <TeilDateien :teil="teil" />

    <fieldset :disabled="!!angebot.nurAnsicht" class="m-0 min-w-0 space-y-4 border-0 p-0">

    <!-- Kalkulation: Zeile für Zeile die Kosten, je Staffel eine Spalte -->
    <KalkulationTabelle :teil="teil" :ergebnis="ergebnis" :materialien="materialien" :kunde-id="angebot.kopf.kundeId" :nur-ansicht="!!angebot.nurAnsicht" @anfrage="emit('anfrage', $event)" />

    <!-- Preiskurve und Vorschau -->
    <div class="grid items-start gap-4 lg:grid-cols-2">
      <section class="card p-5">
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><TrendingDown :size="16" class="text-accent" /> Stückpreis nach Menge</h3>
        <template v-if="!fest">
          <PriceChart :teil="teil" />
          <p class="mt-1 text-xs text-mute">Zeigt, wie stark die Rüstkosten mit der Menge verschwinden.</p>
        </template>
        <p v-else class="rounded-xl bg-surface2 px-4 py-6 text-center text-sm text-mute">Fester Stückpreis: hängt nicht von der Menge ab{{ staffelModus ? ', außer den Preisen je Staffel' : '' }}.</p>
      </section>

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
    </div>
    </fieldset>
  </div>
</template>
