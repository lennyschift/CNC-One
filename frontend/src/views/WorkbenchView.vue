<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { MapPin, UserRound, Hash, Save, FilePlus2, Send } from '@lucide/vue';
import AnfrageDialog from '../components/AnfrageDialog.vue';
import AngebotAnfragen from '../components/AngebotAnfragen.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { fremdPositionen } from '../lib/anfrage.js';
import { useBelege } from '../stores/belege.js';
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
const belege = useBelege();
const anfragenStore = useAnfragen();
const ui = useUi();
const router = useRouter();

function speichern() {
  if (!kunde.value) { ui.toast('Bitte zuerst einen Kunden wählen', 'warn'); return; }
  if (!a.teile.length) { ui.toast('Das Angebot enthält noch kein Bauteil', 'warn'); return; }
  const rec = belege.angebotSpeichern({ angebotId: a.angebotId, kopf: a.kopf, teile: a.teile }, kunde.value);
  a.angebotId = rec.id;
  anfragenStore.verknuepfen(a.entwurfId, rec.id);
  ui.toast(`${rec.id} gespeichert`, 'ok');
  router.push(`/angebote/${rec.id}`);
}
const ziel = computed(() => ({ entwurfId: a.entwurfId, angebotId: a.angebotId }));
const bezug = computed(() => ({ entwurfId: a.entwurfId, angebotId: a.angebotId ?? '', kundeName: kunde.value?.name ?? '' }));
const anzahlAnfragen = computed(() => anfragenStore.fuerAngebot(ziel.value).length);
const anfrageOffen = ref(false);
const anfrageAg = ref('');
const anzahlFremd = computed(() => fremdPositionen(a.teile).length);
function anfrageOeffnen(ag) {
  anfrageAg.value = ag?.id ?? '';
  anfrageOffen.value = true;
}
function neuesAngebot() {
  a.neu();
  ui.toast('Neues, leeres Angebot');
}
const kunden = ref([]);
onMounted(async () => { kunden.value = await repo.kunden.liste(); });
const kunde = computed(() => kunden.value.find((k) => k.id === a.kopf.kundeId) ?? null);
const mwst = computed(() => a.netto * 0.19);
</script>

<template>
  <div class="mx-auto flex max-w-[1500px] flex-col gap-4">
    <!-- Angebotskopf -->
    <section class="card p-5">
      <div class="grid gap-5 lg:grid-cols-[1fr_auto]">
        <div class="grid gap-4 md:grid-cols-[minmax(240px,1.2fr)_1fr_120px_1fr]">
          <CustomerCombobox v-model="a.kopf.kundeId" />
          <label class="block"><span class="label mb-1 block">Anfrage-Nr. des Kunden</span><input v-model="a.kopf.anfrageNr" class="field" placeholder="z. B. RFQ-2026-118" /></label>
          <NumField v-model="a.kopf.gueltigWochen" label="Gültig" unit="Wo." :decimals="0" :min="1" />
          <label class="block"><span class="label mb-1 block">Lieferzeit</span><input v-model="a.kopf.lieferzeit" class="field" /></label>

          <Transition name="fade">
            <div v-if="kunde" class="grid gap-3 text-sm md:col-span-4 md:grid-cols-3">
              <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><MapPin :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div v-for="z in kunde.adresse" :key="z">{{ z }}</div></div></div>
              <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><UserRound :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div>{{ kunde.kontakt.name }}</div><div class="text-xs text-mute">{{ kunde.kontakt.email }}</div></div></div>
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
            <button class="btn btn-primary flex-1 justify-center" @click="speichern"><Save :size="16" /> {{ a.angebotId ? 'Speichern' : 'Als Angebot speichern' }}</button>
            <button class="btn !border-white/20 !bg-white/10 !text-bg hover:!bg-white/20" title="Neues, leeres Angebot beginnen" @click="neuesAngebot"><FilePlus2 :size="16" /></button>
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

    <AnfrageDialog v-if="anfrageOffen" :teile="a.teile" :vorgewaehlt="anfrageAg" :bezug="bezug" @schliessen="anfrageOffen = false" />
  </div>
</template>
