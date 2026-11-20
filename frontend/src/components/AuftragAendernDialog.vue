<script setup>
// Laufenden Auftrag ändern: Menge (0 = Position entfällt), Stückpreis, Liefertermin und Sonderkosten je Position, dazu
// neue Positionen aus einem gesendeten Angebot. Die Nummer bleibt; der Server hält jede Änderung mit Grund fest, zieht
// die Fertigung mit und verlangt eine neue Auftragsbestätigung („Änderung 1“ …). Grenzen prüft der Server
// (nicht unter geliefert/berechnet, Preis nur ohne Rechnung).
import { ref, reactive, computed } from 'vue';
import { Plus, Trash2, Ban, RotateCcw, Lock } from '@lucide/vue';
import StammDialog from './StammDialog.vue';
import PartImage from './PartImage.vue';
import NumField from './NumField.vue';
import { call } from '../data/api.js';
import { eur } from '../lib/format.js';
import { useBelege } from '../stores/belege.js';
import { useFertigung } from '../stores/fertigung.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ auftrag: { type: Object, required: true } });
const emit = defineEmits(['schliessen', 'geaendert']);
const b = useBelege();
const f = useFertigung();
const ui = useUi();

const grund = ref('');
const speichert = ref(false);
const zeilen = reactive(props.auftrag.positionen.map((p) => ({
  key: p.key, teil: p.teil, alt: p,
  menge: p.menge, einzelpreis: p.einzelpreis, termin: p.termin || '',
  untergrenze: Math.max(p.geliefert || 0, p.berechnet || 0),
  preisFest: (p.berechnet || 0) > 0,
  kosten: p.kosten.map((k) => ({ label: k.label, betrag: k.betrag, fest: !!p.kostenAbgerechnet?.[k.label] })),
})));
const neu = reactive([]);

const kostenText = (liste) => JSON.stringify(liste.map((k) => [k.label.trim(), Math.round(k.betrag * 100)]));
function geaendert(z) {
  return z.menge !== z.alt.menge || Math.round(z.einzelpreis * 100) !== Math.round(z.alt.einzelpreis * 100) || (z.termin || '') !== (z.alt.termin || '')
    || kostenText(z.kosten) !== kostenText(z.alt.kosten);
}
const summe = (z) => z.menge * z.einzelpreis + (z.menge ? z.kosten.reduce((s, k) => s + (Number(k.betrag) || 0), 0) : 0);
const nettoNeu = computed(() => zeilen.reduce((s, z) => s + summe(z), 0));
const fehler = computed(() => zeilen.filter((z) => z.menge < z.untergrenze).map((z) => `${z.teil.name}: mindestens ${z.untergrenze} Stk (schon geliefert oder berechnet)`));
const etwas = computed(() => zeilen.some(geaendert) || neu.some((n) => n.angebotKey && n.menge > 0));
const gueltig = computed(() => !!grund.value.trim() && etwas.value && !fehler.value.length);

// neue Positionen: aus gesendeten Angeboten desselben Kunden
const angebote = computed(() => b.angebote.filter((a) => a.status === 'Gesendet' && a.kopf.kundeId === props.auftrag.kunde?.id));
const positionenVon = (id) => b.angebot(id)?.positionen ?? [];
function neuHinzu() {
  neu.push({ angebotId: props.auftrag.angebotId && angebote.value.some((a) => a.id === props.auftrag.angebotId) ? props.auftrag.angebotId : angebote.value[0]?.id ?? '', angebotKey: '', menge: 1, termin: '', serienStart: '' });
}

async function speichern() {
  if (!gueltig.value) return;
  speichert.value = true;
  try {
    const rec = await call('cnc_one.api.auftrag.aendern', {
      id: props.auftrag.id, grund: grund.value,
      positionen: zeilen.filter(geaendert).map((z) => ({ key: z.key, menge: z.menge, einzelpreis: z.einzelpreis, termin: z.termin || null, kosten: z.kosten.filter((k) => k.label.trim()).map((k) => ({ label: k.label.trim(), betrag: k.betrag })) })),
      neu: neu.filter((n) => n.angebotKey && n.menge > 0).map((n) => ({ ...n, termin: n.termin || null })),
    });
    b.auftragEinsetzen(rec);
    await f.neuLaden();
    ui.toast(`Änderung ${rec.aenderungNr} gespeichert – bitte die geänderte Auftragsbestätigung senden`, 'ok');
    emit('geaendert', rec);
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    speichert.value = false;
  }
}
</script>

<template>
  <StammDialog :titel="`Auftrag ${auftrag.id} ändern`" :untertitel="auftrag.kundeName" breite="980px" neu speichern-text="Änderung speichern" :speichert="speichert" :gueltig="gueltig" @schliessen="emit('schliessen')" @speichern="speichern">
    <p class="rounded-xl bg-surface2 px-4 py-3 text-sm text-mute">
      Die Auftragsnummer bleibt. Jede Änderung wird mit Grund festgehalten, die Fertigung wird angepasst, und danach geht eine geänderte
      Auftragsbestätigung („Änderung {{ (auftrag.aenderungNr || 0) + 1 }}“) an den Kunden. Menge 0 heißt: Position entfällt.
    </p>

    <label class="block"><span class="label mb-1 block">Grund der Änderung <span class="text-accent">*</span></span>
      <input v-model="grund" class="field" placeholder="z. B. Nachverhandlung am 20.11., Position 2 entfällt laut Kunde" /></label>

    <section class="space-y-2">
      <div v-for="z in zeilen" :key="z.key" class="rounded-xl border p-3 transition" :class="z.menge === 0 ? 'border-line/60 bg-surface2' : geaendert(z) ? 'border-accent/50 bg-accent-soft/30' : 'border-line'">
        <div class="flex items-start gap-3">
          <PartImage :teil="z.teil" :groesse="44" />
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate font-medium" :class="z.menge === 0 ? 'text-mute line-through' : ''">{{ z.teil.name }}</span>
              <span class="text-xs text-mute">{{ z.teil.teilenummer }}</span>
              <span v-if="z.menge === 0" class="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">entfällt</span>
              <span class="ml-auto text-xs text-mute tnum">bisher {{ z.alt.menge }} × {{ eur(z.alt.einzelpreis) }}</span>
            </div>
            <div class="mt-2 grid items-end gap-3 sm:grid-cols-[110px_130px_150px_1fr_auto]">
              <label class="block"><span class="label mb-1 block">Menge</span><NumField v-model="z.menge" :decimals="0" unit="Stk" :min="0" /></label>
              <label class="block" :title="z.preisFest ? 'Es ist schon etwas berechnet: der Stückpreis bleibt' : ''"><span class="label mb-1 flex items-center gap-1">Stückpreis <Lock v-if="z.preisFest" :size="11" /></span>
                <NumField v-model="z.einzelpreis" unit="€" :class="z.preisFest ? 'pointer-events-none opacity-50' : ''" /></label>
              <label class="block"><span class="label mb-1 block">Liefertermin</span><input v-model="z.termin" type="date" class="field" /></label>
              <div class="text-xs text-mute">
                <div v-if="z.untergrenze">geliefert {{ z.alt.geliefert }} · berechnet {{ z.alt.berechnet }} → mindestens {{ z.untergrenze }} Stk</div>
                <div class="tnum">Summe neu <strong class="text-ink">{{ eur(summe(z)) }}</strong></div>
              </div>
              <button v-if="z.menge > 0" type="button" class="btn !py-1.5 text-xs" :disabled="z.untergrenze > 0" :title="z.untergrenze ? 'Schon geliefert oder berechnet' : 'Position streichen (Menge 0)'" @click="z.menge = 0"><Ban :size="13" /> Entfällt</button>
              <button v-else type="button" class="btn !py-1.5 text-xs" @click="z.menge = z.alt.menge || 1"><RotateCcw :size="13" /> Wieder aufnehmen</button>
            </div>
            <!-- Sonderkosten der Position -->
            <div v-if="z.menge > 0" class="mt-2 space-y-1">
              <div v-for="(k, i) in z.kosten" :key="i" class="flex items-center gap-2 pl-1 text-sm">
                <span class="text-mute">↳</span>
                <input v-model="k.label" class="field !w-56 !py-1 text-sm" :disabled="k.fest" />
                <NumField v-model="k.betrag" unit="€" class="w-32" :class="k.fest ? 'pointer-events-none opacity-50' : ''" />
                <span v-if="k.fest" class="text-xs text-mute">schon berechnet</span>
                <button v-else type="button" class="text-mute hover:text-accent" title="Kosten entfernen" @click="z.kosten.splice(i, 1)"><Trash2 :size="14" /></button>
              </div>
              <button type="button" class="inline-flex items-center gap-1 pl-5 text-xs text-accent hover:underline" @click="z.kosten.push({ label: '', betrag: 0, fest: false })"><Plus :size="12" /> Kosten</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section>
      <div class="mb-2 flex items-center justify-between">
        <h3 class="text-sm font-semibold">Neue Positionen</h3>
        <button type="button" class="btn !py-1 text-xs" :disabled="!angebote.length" :title="angebote.length ? '' : 'Es gibt kein gesendetes Angebot dieses Kunden'" @click="neuHinzu"><Plus :size="13" /> Aus Angebot</button>
      </div>
      <p v-if="!neu.length" class="text-xs text-mute">Weitere Bauteile kommen aus einem gesendeten Angebot desselben Kunden (Preise wie angeboten).</p>
      <div v-for="(n, i) in neu" :key="i" class="mb-2 grid items-end gap-2 rounded-xl border border-line p-3 sm:grid-cols-[170px_1fr_100px_140px_120px_auto]">
        <label class="block"><span class="label mb-1 block">Angebot</span>
          <select v-model="n.angebotId" class="field" @change="n.angebotKey = ''"><option v-for="a in angebote" :key="a.id" :value="a.id">{{ a.id }}</option></select></label>
        <label class="block"><span class="label mb-1 block">Bauteil</span>
          <select v-model="n.angebotKey" class="field"><option value="" disabled>wählen …</option><option v-for="p in positionenVon(n.angebotId)" :key="p.key" :value="p.key">{{ p.teil.name }} {{ p.teil.teilenummer ? `(${p.teil.teilenummer})` : '' }}</option></select></label>
        <label class="block"><span class="label mb-1 block">Menge</span><NumField v-model="n.menge" :decimals="0" unit="Stk" :min="1" /></label>
        <label class="block"><span class="label mb-1 block">Liefertermin</span><input v-model="n.termin" type="date" class="field" /></label>
        <label class="block" title="Nur bei Bauteilen mit Seriennummern"><span class="label mb-1 block">1. Seriennr.</span><input v-model="n.serienStart" class="field" placeholder="falls nötig" /></label>
        <button type="button" class="mb-2 text-mute hover:text-accent" title="Entfernen" @click="neu.splice(i, 1)"><Trash2 :size="15" /></button>
      </div>
    </section>

    <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface2 px-4 py-3 text-sm">
      <div v-if="fehler.length" class="text-warn"><div v-for="x in fehler" :key="x">{{ x }}</div></div>
      <div v-else-if="!grund.trim() && etwas" class="text-warn">Bitte den Grund der Änderung angeben.</div>
      <div v-else class="text-mute">{{ etwas ? 'Geänderte Positionen sind markiert.' : 'Noch nichts geändert.' }}</div>
      <div class="tnum">Auftragswert {{ eur(auftrag.netto) }} → <strong>{{ eur(nettoNeu) }}</strong><span v-if="neu.some((n) => n.angebotKey)" class="text-mute"> + neue Positionen</span></div>
    </div>
  </StammDialog>
</template>
