<script setup>
// Arbeitsplan eines Bauteils. Wird in der Workbench, beim Beauftragen und in der Fertigung genutzt.
// Der Plan lässt sich am Bauteil speichern (Kunde + Teilenummer), damit spätere Angebote und Aufträge ihn schon haben.
import { useArbeitsplan } from '../lib/arbeitsplan.js';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Hash, Plus, Truck, Cog, ChevronUp, ChevronDown, Trash2, Save, DownloadCloud, FileText, Send, Euro, Clock } from '@lucide/vue';
import NumField from './NumField.vue';
import { eur } from '../lib/format.js';

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

const { stamm, anfragen, ui, maschinen, lieferanten, vorlagen, gespeichert, schluesselOk, ausBauteilLaden, bauteilSpeichern, serienArbeitsgang, hinzu, typSetzen, maschinenFuerAg, unbekannteArt, weg, schieben, vorlageAnwenden, maschineWechsel, arten, anfragenZu, preisUebernehmen, farbe, SPALTEN, umschalten, zeitNoetig, summe, fremdSumme } = useArbeitsplan(props);
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <select v-if="!ohneBauteil" class="field !w-auto" @change="vorlageAnwenden($event.target.value, $event.target)">
        <option value="">Vorlage anwenden …</option>
        <option v-for="v in vorlagen" :key="v.id" :value="v.id">{{ v.name }}{{ v.kundeId ? ' (Kunde)' : '' }}</option>
      </select>
      <select class="field !w-auto" aria-label="Arbeitsgang hinzufügen" @change="hinzu($event.target.value, $event.target)">
        <option value="">+ Arbeitsgang hinzufügen …</option>
        <option v-for="a in stamm.arten" :key="a.id" :value="a.name">{{ a.name }}{{ a.typ === 'fremd' ? ' (extern)' : '' }}</option>
      </select>
      <div v-if="!ohneBauteil && !ohneSpeichern" class="ml-auto flex flex-wrap items-center gap-2">
        <button v-if="gespeichert && !arbeitsgaenge.length" class="btn" @click="ausBauteilLaden()"><DownloadCloud :size="15" /> Vom Bauteil laden</button>
        <button class="btn" :disabled="!schluesselOk" :class="!schluesselOk ? 'pointer-events-none opacity-40' : ''" :title="schluesselOk ? '' : 'Dafür braucht das Bauteil einen Kunden und eine Teilenummer'" @click="bauteilSpeichern"><Save :size="15" /> Am Bauteil speichern</button>
      </div>
    </div>
    <p v-if="!ohneBauteil && !ohneSpeichern && !schluesselOk" class="mb-3 text-xs text-mute">Zum Speichern am Bauteil braucht es einen gewählten Kunden und eine Teilenummer.</p>
    <p v-else-if="!ohneBauteil && !ohneSpeichern && gespeichert" class="mb-3 text-xs text-ok">Dieses Bauteil hat einen gespeicherten Arbeitsplan. Änderungen hier gelten erst nach „Am Bauteil speichern“.</p>

    <div v-if="teil?.seriennummern && !arbeitsgaenge.some((a) => stamm.istSerienart(a.name))" class="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-accent-soft px-3.5 py-2.5 text-xs text-accent">
      <Hash :size="14" /> Seriennummern sind aktiv, im Arbeitsplan fehlt der Arbeitsgang „{{ stamm.serienart }}“.
      <button class="btn !py-1 !text-xs" @click="serienArbeitsgang"><Plus :size="13" /> Arbeitsgang „{{ stamm.serienart }}“ ergänzen</button>
    </div>

    <div v-auto-animate class="space-y-2.5">
      <div v-for="(ag, i) in arbeitsgaenge" :key="ag.id" class="rounded-xl border border-line bg-surface2 p-3">
        <div class="flex items-center gap-2">
          <span class="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold text-mute tnum">{{ i + 1 }}</span>
                    <select v-model="ag.name" class="field !py-1.5 font-medium" :class="!ag.name || unbekannteArt(ag) ? '!border-warn' : ''" aria-label="Arbeitsgang">
            <option value="" disabled>Arbeitsgang wählen …</option>
            <option v-if="unbekannteArt(ag)" :value="ag.name">{{ ag.name }} (nicht in den Stammdaten)</option>
            <option v-for="a in stamm.arten" :key="a.id" :value="a.name">{{ a.name }}</option>
          </select>
          <span class="flex shrink-0 rounded-lg border border-line bg-surface p-0.5 text-[11px]" role="radiogroup" aria-label="Intern oder extern">
            <button type="button" class="umschalter" :class="ag.typ === 'intern' ? 'aktiv' : ''" @click="typSetzen(ag, 'intern')"><Cog :size="11" /> Intern</button>
            <button type="button" class="umschalter" :class="ag.typ === 'fremd' ? 'aktiv' : ''" @click="typSetzen(ag, 'fremd')"><Truck :size="11" /> Extern</button>
          </span>
          <div class="flex shrink-0">
            <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface hover:text-ink" title="Nach oben" @click="schieben(i, -1)"><ChevronUp :size="15" /></button>
            <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface hover:text-ink" title="Nach unten" @click="schieben(i, 1)"><ChevronDown :size="15" /></button>
            <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-accent-soft hover:text-accent" title="Entfernen" @click="weg(i)"><Trash2 :size="15" /></button>
          </div>
        </div>

        <!-- Intern: Maschine und Satz, daneben Rüsten und je Stück (Zeit oder direkt Euro) -->
        <div v-if="ag.typ === 'intern'" class="mt-2.5 grid gap-2.5 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <div class="grid grid-cols-[minmax(0,1fr)_96px] gap-2">
            <label class="block"><span class="label mb-1 block">Maschine</span>
              <select class="field" :value="ag.maschine" @change="maschineWechsel(ag, $event.target.value)"><option value="">– optional –</option><option v-for="m in maschinenFuerAg(ag)" :key="m.name" :value="m.name">{{ m.name }}</option></select>
            </label>
            <NumField v-model="ag.satz" label="Satz" unit="€/h" :class="zeitNoetig(ag) ? '' : 'opacity-50'" />
          </div>
          <div v-for="sp in SPALTEN" :key="sp.art" class="kosten">
            <div class="mb-1 flex items-center justify-between gap-2">
              <span class="label">{{ sp.label }}</span>
              <span class="flex rounded-lg border border-line bg-surface p-0.5 text-[11px]" role="radiogroup" :aria-label="`${sp.label}: Zeit oder Euro`">
                <button type="button" role="radio" :aria-checked="!ag[sp.direkt]" class="umschalter" :class="!ag[sp.direkt] ? 'aktiv' : ''" title="Zeit × Satz" @click="umschalten(ag, sp, false)"><Clock :size="11" /> Zeit</button>
                <button type="button" role="radio" :aria-checked="!!ag[sp.direkt]" class="umschalter" :class="ag[sp.direkt] ? 'aktiv' : ''" title="Kosten direkt eintragen" @click="umschalten(ag, sp, true)"><Euro :size="11" /> Betrag</button>
              </span>
            </div>
            <div class="flex items-center gap-2">
              <NumField v-if="ag[sp.direkt]" v-model="ag[sp.euro]" unit="€" class="min-w-0 flex-1" />
              <NumField v-else v-model="ag[sp.zeit]" unit="min" :step="sp.schritt" class="min-w-0 flex-1" />
              <span class="w-24 shrink-0 text-right text-sm font-semibold tnum" :title="ag[sp.direkt] ? 'direkt eingetragen' : 'Zeit × Satz'">{{ eur(sp.kosten(ag)) }}<span class="block text-[10px] font-normal text-mute">{{ sp.art === 'ruest' ? 'einmalig' : 'je Stück' }}</span></span>
            </div>
          </div>
          <p v-if="stamm.istSerienart(ag.name)" class="flex items-center gap-2 text-xs text-accent md:col-span-3"><Hash :size="12" /> Dieser Arbeitsgang bringt die Seriennummern an. In der Fertigung ist dann zu sehen, welche Nummern schon fertig sind.</p>
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

    <div v-if="arbeitsgaenge.length" class="mt-3 flex flex-wrap items-center justify-end gap-x-6 gap-y-1 rounded-xl bg-surface2 px-4 py-2.5 text-sm">
      <span class="text-mute">Summe</span>
      <span>Rüsten <strong class="tnum">{{ eur(summe.ruest) }}</strong><template v-if="fremdSumme.ruest"> <span class="text-xs text-mute">+ Fremd einmalig {{ eur(fremdSumme.ruest) }}</span></template></span>
      <span>Je Stück <strong class="tnum">{{ eur(summe.stueck + fremdSumme.stueck) }}</strong><template v-if="fremdSumme.stueck"> <span class="text-xs text-mute">davon Fremd {{ eur(fremdSumme.stueck) }}</span></template></span>
    </div>
    <p v-if="!arbeitsgaenge.length" class="rounded-xl border border-dashed border-line px-4 py-8 text-center text-sm text-mute">
      Noch keine Arbeitsgänge. Vorlage anwenden oder Arbeitsgang hinzufügen. Die Maschine ist hier optional, festgelegt wird sie spätestens in der Fertigung.
    </p>
  </div>
</template>

<style scoped>
.kosten { border-radius: 0.75rem; background: var(--surface); padding: 0.5rem 0.65rem; border: 1px solid var(--line); }
.umschalter { display: inline-flex; align-items: center; gap: 0.2rem; border-radius: 0.4rem; padding: 0.1rem 0.4rem; color: var(--mute); }
.umschalter.aktiv { background: var(--accent-soft); color: var(--accent); font-weight: 500; }
</style>
