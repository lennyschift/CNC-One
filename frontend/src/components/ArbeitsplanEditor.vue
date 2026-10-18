<script setup>
// Arbeitsplan eines Bauteils. Wird in der Workbench, beim Beauftragen und in der Fertigung genutzt.
// Der Plan lässt sich am Bauteil speichern (Kunde + Teilenummer), damit spätere Angebote und Aufträge ihn schon haben.
import { ref, computed, onMounted, watch } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Truck, Cog, ChevronUp, ChevronDown, Trash2, Save, DownloadCloud, FileText, Send, Euro } from '@lucide/vue';
import NumField from './NumField.vue';
import { repo } from '../data/repo.js';
import { leererArbeitsgang } from '../lib/fertigung.js';
import { preisFuerMenge } from '../lib/anfrage.js';
import { uid } from '../lib/format.js';
import { useStamm } from '../stores/stamm.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({
  arbeitsgaenge: { type: Array, required: true },
  kundeId: { type: String, default: '' },
  teilenummer: { type: String, default: '' },
  // Bauteil der Workbench; nur damit lassen sich Lieferantenanfragen auslösen
  teil: { type: Object, default: null },
  // Angaben zum Bauteil, wenn kein Workbench-Bauteil übergeben wird (z. B. im Auftrag)
  teilInfo: { type: Object, default: null },
  // Für Vorlagen: kein Bauteil, daher weder Vorlage anwenden noch am Bauteil speichern
  ohneBauteil: { type: Boolean, default: false },
  // Vorlagen bleiben nutzbar, nur das Speichern am Bauteil entfällt (z. B. im Bauteil-Editor, der selbst speichert)
  ohneSpeichern: { type: Boolean, default: false },
});
const emit = defineEmits(['anfrage']);

const stamm = useStamm();
const anfragen = useAnfragen();
const ui = useUi();

const maschinen = ref([]);
const lieferanten = ref([]);
onMounted(async () => { [maschinen.value, lieferanten.value] = await Promise.all([repo.maschinen.liste(), repo.lieferanten.liste()]); });

const vorlagen = computed(() => stamm.vorlagenFuer(props.kundeId));
const gespeichert = computed(() => stamm.hatPlan(props.kundeId, props.teilenummer));
const schluesselOk = computed(() => !!stamm.teilKey(props.kundeId, props.teilenummer));

// Hat das Bauteil schon einen gespeicherten Plan und der aktuelle ist leer, wird er übernommen.
function ausBauteilLaden(still = false) {
  const p = stamm.planFuer(props.kundeId, props.teilenummer);
  if (!p) return;
  props.arbeitsgaenge.splice(0, props.arbeitsgaenge.length, ...p);
  if (!still) ui.toast(`Arbeitsplan vom Bauteil geladen (${p.length} Arbeitsgänge)`, 'ok');
}
watch(() => [props.kundeId, props.teilenummer], () => {
  if (!props.arbeitsgaenge.length && gespeichert.value) {
    ausBauteilLaden(true);
    ui.toast('Arbeitsplan vom Bauteil übernommen', 'ok');
  }
}, { immediate: true });

async function bauteilSpeichern() {
  const info = props.teil ?? props.teilInfo ?? {};
  if (await stamm.planSpeichern(props.kundeId, props.teilenummer, props.arbeitsgaenge, info)) ui.toast('Arbeitsplan am Bauteil gespeichert', 'ok');
}

function hinzu(typ) { props.arbeitsgaenge.push(leererArbeitsgang(typ, uid)); }
function weg(i) { props.arbeitsgaenge.splice(i, 1); }
function schieben(i, d) {
  const j = i + d;
  if (j < 0 || j >= props.arbeitsgaenge.length) return;
  const [a] = props.arbeitsgaenge.splice(i, 1);
  props.arbeitsgaenge.splice(j, 0, a);
}
function vorlageAnwenden(id, el) {
  if (!id) return;
  const kopie = stamm.vorlageKopie(id);
  props.arbeitsgaenge.push(...kopie);
  if (el) el.value = '';
  ui.toast(`${kopie.length} Arbeitsgänge aus der Vorlage hinzugefügt`, 'ok');
}
function maschineWechsel(ag, name) {
  ag.maschine = name;
  const m = maschinen.value.find((x) => x.name === name);
  if (m) ag.satz = m.satz;
}
const arten = (typ) => stamm.arten.filter((a) => a.typ === typ);

function anfragenZu(ag) { return anfragen.fuerArbeitsgang(ag.id); }
function preisUebernehmen(ag, a) {
  const pos = a.positionen.find((x) => x.agId === ag.id);
  const menge = props.teil ? (props.teil.staffel?.aktiv && props.teil.staffel.stufen.length ? Math.min(...props.teil.staffel.stufen.map((s) => Number(s.menge) || Infinity)) : props.teil.menge) : pos?.mengen[0];
  const p = preisFuerMenge(a.antwort, menge, pos?.key);
  if (!p) return;
  ag.fremdProStk = p.proStk;
  ag.fremdEinmal = p.einmalig;
  ag.lieferant = a.lieferantName;
  ag.anfrageId = a.id;
  ui.toast(`Preis aus ${a.id} übernommen (${p.menge} Stk)`, 'ok');
}
const farbe = { Gesendet: 'text-warn', 'Angebot erhalten': 'text-ok', Abgesagt: 'text-mute' };
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <select v-if="!ohneBauteil" class="field !w-auto" @change="vorlageAnwenden($event.target.value, $event.target)">
        <option value="">Vorlage anwenden …</option>
        <option v-for="v in vorlagen" :key="v.id" :value="v.id">{{ v.name }}{{ v.kundeId ? ' (Kunde)' : '' }}</option>
      </select>
      <button class="btn" @click="hinzu('intern')"><Plus :size="15" /> Arbeitsgang</button>
      <button class="btn" @click="hinzu('fremd')"><Truck :size="15" /> Fremdvergabe</button>
      <div v-if="!ohneBauteil && !ohneSpeichern" class="ml-auto flex flex-wrap items-center gap-2">
        <button v-if="gespeichert && !arbeitsgaenge.length" class="btn" @click="ausBauteilLaden()"><DownloadCloud :size="15" /> Vom Bauteil laden</button>
        <button class="btn" :disabled="!schluesselOk" :class="!schluesselOk ? 'pointer-events-none opacity-40' : ''" :title="schluesselOk ? '' : 'Dafür braucht das Bauteil einen Kunden und eine Teilenummer'" @click="bauteilSpeichern"><Save :size="15" /> Am Bauteil speichern</button>
      </div>
    </div>
    <p v-if="!ohneBauteil && !ohneSpeichern && !schluesselOk" class="mb-3 text-xs text-mute">Zum Speichern am Bauteil braucht es einen gewählten Kunden und eine Teilenummer.</p>
    <p v-else-if="!ohneBauteil && !ohneSpeichern && gespeichert" class="mb-3 text-xs text-ok">Dieses Bauteil hat einen gespeicherten Arbeitsplan. Änderungen hier gelten erst nach „Am Bauteil speichern“.</p>

    <div v-auto-animate class="space-y-2.5">
      <div v-for="(ag, i) in arbeitsgaenge" :key="ag.id" class="rounded-xl border border-line bg-surface2 p-3">
        <div class="flex items-center gap-2">
          <span class="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold text-mute tnum">{{ i + 1 }}</span>
          <span class="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-surface text-mute"><Truck v-if="ag.typ === 'fremd'" :size="13" /><Cog v-else :size="13" /></span>
          <input v-model="ag.name" :list="'arten-' + ag.typ" class="field !py-1.5 font-medium" :placeholder="ag.typ === 'fremd' ? 'Name der Fremdvergabe, z. B. Oberflächenbehandlung' : 'Name, z. B. Drehen'" />
          <datalist :id="'arten-' + ag.typ"><option v-for="a in arten(ag.typ)" :key="a.id" :value="a.name" /></datalist>
          <div class="flex shrink-0">
            <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface hover:text-ink" title="Nach oben" @click="schieben(i, -1)"><ChevronUp :size="15" /></button>
            <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface hover:text-ink" title="Nach unten" @click="schieben(i, 1)"><ChevronDown :size="15" /></button>
            <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-accent-soft hover:text-accent" title="Entfernen" @click="weg(i)"><Trash2 :size="15" /></button>
          </div>
        </div>

        <div v-if="ag.typ === 'intern'" class="mt-2.5 grid gap-2 sm:grid-cols-4">
          <label class="block"><span class="label mb-1 block">Maschine</span>
            <select class="field" :value="ag.maschine" @change="maschineWechsel(ag, $event.target.value)"><option value="">– wählen –</option><option v-for="m in maschinen" :key="m.name" :value="m.name">{{ m.name }}</option></select>
          </label>
          <NumField v-model="ag.satz" label="Satz" unit="€/h" />
          <NumField v-model="ag.ruestMin" label="Rüstzeit" unit="min" :step="5" />
          <NumField v-model="ag.stueckMin" label="Stückzeit" unit="min" :step="0.5" />
        </div>

        <div v-else class="mt-2.5 space-y-2.5">
          <div class="grid gap-2 sm:grid-cols-3">
            <label class="block"><span class="label mb-1 block">Lieferant</span>
              <select v-model="ag.lieferant" class="field"><option value="">– wählen –</option><option v-for="l in lieferanten" :key="l.id" :value="l.name">{{ l.name }}</option></select>
            </label>
            <NumField v-model="ag.fremdProStk" label="Preis je Stück" unit="€" />
            <NumField v-model="ag.fremdEinmal" label="Einmalig" unit="€" />
          </div>
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <button v-if="teil" class="btn !py-1 !text-xs" @click="emit('anfrage', ag)"><Send :size="13" /> Anfrage an Lieferanten</button>
            <template v-for="a in anfragenZu(ag)" :key="a.id">
              <RouterLink :to="`/anfragen/${a.id}`" class="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 hover:border-accent/50">
                <FileText :size="12" class="text-mute" /><span class="tnum">{{ a.id }}</span><span :class="farbe[a.status]">{{ a.status }}</span>
              </RouterLink>
              <button v-if="a.antwort" class="btn !py-1 !text-xs" @click="preisUebernehmen(ag, a)"><Euro :size="13" /> Preis übernehmen</button>
            </template>
            <span v-if="ag.anfrageId" class="text-mute">Preis aus {{ ag.anfrageId }}</span>
          </div>
        </div>
      </div>
    </div>

    <p v-if="!arbeitsgaenge.length" class="rounded-xl border border-dashed border-line px-4 py-8 text-center text-sm text-mute">
      Noch keine Arbeitsgänge. Vorlage anwenden oder Arbeitsgänge hinzufügen. Das geht auch später in der Fertigung.
    </p>
  </div>
</template>
