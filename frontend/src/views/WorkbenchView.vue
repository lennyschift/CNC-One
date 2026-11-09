<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { MapPin, UserRound, Hash, Eye, FilePlus2, Send, Check, Loader, AlertTriangle, Inbox } from '@lucide/vue';
import AnfrageDialog from '../components/AnfrageDialog.vue';
import BauteilWahlDialog from '../components/BauteilWahlDialog.vue';
import AngebotAnfragen from '../components/AngebotAnfragen.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { fremdPositionen } from '../lib/anfrage.js';
import { useUi } from '../stores/ui.js';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import PartList from '../components/PartList.vue';
import PartEditor from '../components/PartEditor.vue';
import AnimatedNumber from '../components/AnimatedNumber.vue';
import NumField from '../components/NumField.vue';
import { repo } from '../data/repo.js';
import { eur } from '../lib/format.js';
import { useAngebot } from '../stores/angebot.js';
import { onMounted } from 'vue';

const a = useAngebot();
const anfragenStore = useAnfragen();
const ui = useUi();
const router = useRouter();

// Der Entwurf wird laufend gespeichert. Der Knopf speichert sofort und öffnet die Ansicht des Angebots.
async function ansehen() {
  if (!kunde.value) { ui.toast('Bitte zuerst einen Kunden wählen', 'warn'); return; }
  if (!a.teile.length) { ui.toast('Das Angebot enthält noch kein Bauteil', 'warn'); return; }
  await a.speichern();
  if (a.speicherStand === 'gespeichert' && a.angebotId) router.push(`/angebote/${a.angebotId}`);
}
const ziel = computed(() => ({ angebotId: a.angebotId }));
const bezug = computed(() => ({ angebotId: a.angebotId ?? '' }));
const anzahlAnfragen = computed(() => anfragenStore.fuerAngebot(ziel.value).length);
const anfrageOffen = ref(false);
const anfrageAg = ref('');
const anzahlFremd = computed(() => fremdPositionen(a.teile).length);
// Eine Anfrage gehört zu einem gespeicherten Angebot: der Entwurf wird vorher gespeichert.
async function anfrageOeffnen(ag) {
  await a.speichern();
  if (!a.angebotId) { ui.toast('Das Angebot konnte nicht gespeichert werden', 'warn'); return; }
  anfrageAg.value = ag?.id ?? '';
  anfrageOffen.value = true;
}
async function neuesAngebot() {
  await a.neu();
  ui.toast('Neues, leeres Angebot');
}
const kunden = ref([]);
onMounted(async () => { kunden.value = await repo.kunden.liste(); });
const kunde = computed(() => kunden.value.find((k) => k.id === a.kopf.kundeId) ?? null);
// Ansprechpartner (Einkäufer) je Angebot aus den Kontakten des Kunden; leer = Rechnungskontakt des Kunden
const kontakte = computed(() => kunde.value?.kontakte ?? []);
const kontaktWahl = computed({
  get: () => {
    if (!a.kopf.kontaktName && !a.kopf.kontaktEmail) return '';
    const i = kontakte.value.findIndex((k) => (a.kopf.kontaktEmail ? k.email === a.kopf.kontaktEmail : k.name === a.kopf.kontaktName));
    return i >= 0 ? String(i) : 'eigen';
  },
  set: (v) => {
    if (v === 'eigen') return;
    const k = v === '' ? null : kontakte.value[Number(v)];
    a.kopf.kontaktName = k?.name ?? '';
    a.kopf.kontaktEmail = k?.email ?? '';
  },
});
const mwst = computed(() => a.netto * 0.19);
</script>

<template>
  <div class="mx-auto flex max-w-[1500px] flex-col gap-4">
    <!-- Angebotskopf -->
    <section class="card p-5">
      <RouterLink v-if="a.mailAnfrage" :to="`/posteingang/${a.mailAnfrage.id}`" class="mb-4 flex items-center gap-2 rounded-xl bg-accent-soft/60 px-3.5 py-2 text-sm hover:bg-accent-soft">
        <Inbox :size="15" class="shrink-0 text-accent" />
        <span class="min-w-0 truncate">Aus der Mail-Anfrage von <strong>{{ a.mailAnfrage.vonName || a.mailAnfrage.vonEmail }}</strong>: {{ a.mailAnfrage.betreff }}</span>
        <span class="ml-auto shrink-0 text-xs text-accent">Mail ansehen</span>
      </RouterLink>
      <div class="grid gap-5 lg:grid-cols-[1fr_auto]">
        <div class="grid gap-4 md:grid-cols-[minmax(240px,1.2fr)_1fr_120px_1fr]">
          <CustomerCombobox v-model="a.kopf.kundeId" />
          <label class="block"><span class="label mb-1 block">Anfrage-Nr. des Kunden</span><input v-model="a.kopf.anfrageNr" class="field" placeholder="z. B. RFQ-2026-118" /></label>
          <NumField v-model="a.kopf.gueltigWochen" label="Gültig" unit="Wo." :decimals="0" :min="1" />
          <label class="block"><span class="label mb-1 block">Lieferzeit</span><input v-model="a.kopf.lieferzeit" class="field" :disabled="!!a.fruehesterTermin" :title="a.fruehesterTermin ? 'Frühester Liefertermin der Bauteile' : ''" /></label>
          <label class="block md:col-span-2"><span class="label mb-1 block">Projekt <span class="font-normal normal-case text-mute">(optional, nur intern)</span></span><input v-model="a.kopf.projekt" class="field" placeholder="z. B. Prüfstand 2027" /></label>
          <label class="block md:col-span-2"><span class="label mb-1 block">Ansprechpartner (Einkäufer)</span>
            <select v-model="kontaktWahl" class="field" :disabled="!kunde">
              <option value="">{{ kunde?.kontakt ? `Rechnungskontakt: ${kunde.kontakt.name}` : '– wie beim Kunden –' }}</option>
              <option v-for="(k, i) in kontakte" :key="i" :value="String(i)">{{ k.name || k.email }}{{ k.name && k.email ? ` · ${k.email}` : '' }}</option>
              <option v-if="kontaktWahl === 'eigen'" value="eigen">{{ a.kopf.kontaktName || a.kopf.kontaktEmail }}{{ a.kopf.kontaktName && a.kopf.kontaktEmail ? ` · ${a.kopf.kontaktEmail}` : '' }}</option>
            </select>
          </label>

          <Transition name="fade">
            <div v-if="kunde" class="grid gap-3 text-sm md:col-span-4 md:grid-cols-3">
              <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><MapPin :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div v-for="z in kunde.adresse" :key="z">{{ z }}</div></div></div>
              <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><UserRound :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div>{{ a.kopf.kontaktName || kunde.kontakt?.name || '–' }}</div><div class="text-xs text-mute">{{ a.kopf.kontaktName || a.kopf.kontaktEmail ? a.kopf.kontaktEmail : kunde.kontakt?.email }}</div></div></div>
              <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><Hash :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div class="text-xs text-mute">Lieferanten-Nr. bei Kunde</div><div>{{ kunde.lieferantennr || '–' }}</div></div></div>
            </div>
          </Transition>
        </div>

        <!-- Summe -->
        <div class="min-w-[250px] rounded-2xl bg-ink px-5 py-4 text-bg">
          <div class="text-xs opacity-60">Angebotssumme netto · {{ a.teile.length }} Position{{ a.teile.length === 1 ? '' : 'en' }}</div>
          <div class="mt-1 text-3xl font-semibold tracking-tight"><AnimatedNumber :value="a.netto" :format="eur" /></div>
          <div class="mt-1 text-xs opacity-60 tnum">zzgl. 19 % MwSt. {{ eur(mwst) }}</div>
          <div class="mt-3 flex h-1.5 overflow-hidden rounded-full bg-white/15">
            <div v-for="(t, i) in a.teile" :key="t.id" class="h-full transition-all duration-500" :style="{ width: (a.netto > 0 ? (a.ergebnisse[t.id].gesamt / a.netto) * 100 : 0) + '%', background: 'var(--accent)', opacity: 1 - (i % 4) * 0.22 }" :title="t.name" />
          </div>
          <button v-if="anzahlFremd" class="btn mt-4 w-full justify-center !border-white/20 !bg-white/10 !text-bg hover:!bg-white/20" @click="anfrageOeffnen()"><Send :size="15" /> Lieferantenanfrage ({{ anzahlFremd }} Fremdvergabe{{ anzahlFremd === 1 ? '' : 'n' }}<template v-if="anzahlAnfragen">, {{ anzahlAnfragen }} gesendet</template>)</button>
          <div class="mt-2 flex gap-2">
            <button class="btn btn-primary flex-1 justify-center" @click="ansehen"><Eye :size="16" /> Angebot ansehen</button>
            <button class="btn !border-white/20 !bg-white/10 !text-bg hover:!bg-white/20" title="Neues, leeres Angebot beginnen" @click="neuesAngebot"><FilePlus2 :size="16" /></button>
          </div>
          <div class="mt-3 flex items-center justify-center gap-1.5 text-xs opacity-70">
            <Loader v-if="a.speicherStand === 'speichert' || a.speicherStand === 'offen'" :size="12" class="animate-spin" />
            <AlertTriangle v-else-if="a.speicherStand === 'fehler'" :size="12" />
            <Check v-else :size="12" />
            {{ a.speicherStand === 'fehler' ? 'Speichern fehlgeschlagen' : a.speicherStand === 'gespeichert' ? (a.angebotId ? `${a.angebotId} gespeichert` : 'Noch nichts zu speichern') : 'Speichert …' }}
          </div>
        </div>
      </div>
    </section>

    <AngebotAnfragen :ziel="ziel" variante="leiste" />

    <!-- Arbeitsbereich -->
    <div class="grid items-start gap-4 lg:grid-cols-[340px_1fr]">
      <PartList class="max-h-[calc(100vh-9rem)] lg:sticky lg:top-0" />
      <Transition name="slide" mode="out-in">
        <PartEditor v-if="a.auswahl" :key="a.auswahl.id" :teil="a.auswahl" :ergebnis="a.ergebnisse[a.auswahl.id]" @anfrage="anfrageOeffnen" />
        <div v-else class="card grid place-items-center p-16 text-center text-mute">
          <p class="text-sm">Bauteil auswählen oder mit <span class="kbd">N</span> ein neues anlegen.</p>
        </div>
      </Transition>
    </div>

    <BauteilWahlDialog v-if="ui.bauteilWahlOffen" @schliessen="ui.bauteilWahlOffen = false" />
    <AnfrageDialog v-if="anfrageOffen" :teile="a.teile" :vorgewaehlt="anfrageAg" :bezug="bezug" @schliessen="anfrageOffen = false" />
  </div>
</template>
