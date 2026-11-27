<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Pencil, Send, Printer, ShoppingCart, XCircle, Trash2, ArrowLeft, Mail, Inbox, ClipboardList, Calculator, FilePen, History, ArrowRight } from '@lucide/vue';
import AngebotMailDialog from '../components/AngebotMailDialog.vue';
import { useUi } from '../stores/ui.js';
import BelegPdf from '../components/BelegPdf.vue';
import BilderSchalter from '../components/BilderSchalter.vue';
import { belegPdfUrl, pdfDrucken } from '../lib/belegpdf.js';
import AuftragDialog from '../components/AuftragDialog.vue';
import AngebotAnfragen from '../components/AngebotAnfragen.vue';
import WorkflowSteps from '../components/WorkflowSteps.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektFeld from '../components/ProjektFeld.vue';
import PartImage from '../components/PartImage.vue';
import { useBelege } from '../stores/belege.js';
import { useAngebot } from '../stores/angebot.js';

const route = useRoute();
const router = useRouter();
const b = useBelege();
const draft = useAngebot();
const ui = useUi();
const mailDialog = ref(false);

const angebot = computed(() => b.angebot(route.params.id));
const status = computed(() => (angebot.value ? b.statusVon(angebot.value) : ''));
const bestellt = computed(() => (angebot.value ? b.bestelltFuer(angebot.value.id) : {}));
const dialog = ref(false);
// Nur zwei Schritte: Angebot und Auftrag. Ein Haken beim Angebot, sobald etwas bestellt ist, beim Auftrag erst wenn alles bestellt ist.
const stand = computed(() => (status.value === 'Bestellt' ? 2 : status.value === 'Teilweise bestellt' ? 1 : 0));
// Mit einem Auftrag ist das Angebot angenommen: nicht mehr senden oder ablehnen. Weitere Aufträge (Abrufe) gehen weiterhin.
const beauftragt = computed(() => stand.value > 0);
const auftraegeDazu = computed(() => b.auftraege.filter((x) => x.angebotId === angebot.value?.id && x.status !== 'Storniert'));

// Angezeigt und gedruckt wird das PDF, wie es verschickt wird (beim Entwurf frisch erzeugt, nach dem Senden das verschickte)
const geladen = ref(Date.now()); // neu laden, wenn z. B. die Bauteilbilder umgeschaltet werden
const pdfUrl = computed(() => (angebot.value ? belegPdfUrl('Angebot', angebot.value.id, `${angebot.value.status}-${geladen.value}`) : ''));
async function drucken() {
  try { await pdfDrucken(pdfUrl.value); } catch (e) { ui.toast(e.message, 'warn'); }
}

// Entwurf: in der Workbench weiterbearbeiten. Gesendet: dort nur ansehen, wie kalkuliert wurde.
async function bearbeiten() {
  await draft.ausAngebot(angebot.value);
  router.push('/workbench');
}
// Überarbeiten: neue Fassung (gleiche Nummer mit -1, -2 …) als Entwurf, das Original bleibt unverändert
const ueberarbeiten = ref(false);
const grund = ref('');
const offeneFassung = computed(() => (angebot.value?.fassungen ?? []).find((f) => f.status === 'Entwurf' && f.id !== angebot.value.id) ?? null);
async function neueFassung() {
  const rec = await b.angebotUeberarbeiten(angebot.value.id, grund.value);
  if (!rec) return;
  ueberarbeiten.value = false;
  grund.value = '';
  await draft.ausAngebot(rec);
  router.push('/workbench');
}
const datum = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');

async function loeschen() {
  if (await b.angebotLoeschen(angebot.value.id)) router.push('/angebote');
}
function angelegt(auftrag) {
  dialog.value = false;
  router.push(`/auftraege/${auftrag.id}`);
}
</script>

<template>
  <div v-if="angebot" class="mx-auto grid max-w-[1300px] items-start gap-6 xl:grid-cols-[1fr_340px]">
    <BilderSchalter :doctype="'Angebot'" :beleg-id="angebot.id" class="mx-auto mb-3 max-w-[820px] justify-end" @geaendert="geladen = Date.now()" />
    <BelegPdf v-if="angebot.kopf?.kundeId" :url="pdfUrl" :name="`Angebot ${angebot.id}.pdf`" />
    <div v-else class="card grid min-h-[300px] place-items-center p-10 text-sm text-mute">Ohne Kunden gibt es noch kein PDF. Bitte das Angebot in der Workbench vervollständigen.</div>

    <aside class="no-print space-y-4 xl:sticky xl:top-0">
      <RouterLink to="/angebote" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Angebote</RouterLink>

      <section class="card p-5">
        <div class="flex items-center justify-between"><h2 class="font-semibold tnum">{{ angebot.id }}</h2><StatusBadge :status="status" /></div>
        <ProjektFeld class="mt-4" :projekt="angebot.kopf.projekt" :kontakt-name="angebot.kopf.kontaktName" :kontakt-email="angebot.kopf.kontaktEmail" @speichern="b.projektSetzen('Angebot', angebot.id, $event)" />
        <div class="mt-5"><WorkflowSteps :stand="stand" :schritte="['Angebot', 'Auftrag']" /></div>
        <RouterLink v-if="angebot.ersetztDurch" :to="`/angebote/${angebot.ersetztDurch}`" class="mt-4 flex items-center gap-2 rounded-xl bg-warn/10 px-3 py-2 text-xs text-warn hover:underline">
          <History :size="14" class="shrink-0" /><span>Ersetzt durch die neue Fassung <strong class="tnum">{{ angebot.ersetztDurch }}</strong>. Dieses Angebot gilt nicht mehr.</span><ArrowRight :size="13" class="ml-auto shrink-0" />
        </RouterLink>
        <div v-if="angebot.vorgaenger" class="mt-4 rounded-xl bg-surface2 px-3 py-2 text-xs">
          <div class="flex items-center gap-2"><FilePen :size="14" class="shrink-0 text-accent" /> Fassung {{ angebot.fassung }}, ersetzt <RouterLink :to="`/angebote/${angebot.vorgaenger}`" class="tnum text-accent hover:underline">{{ angebot.vorgaenger }}</RouterLink></div>
          <div v-if="angebot.aenderungsgrund" class="mt-1 text-mute">Grund: {{ angebot.aenderungsgrund }}</div>
        </div>
        <RouterLink v-if="angebot.mailAnfrage" :to="`/posteingang/${angebot.mailAnfrage.id}`" class="mt-4 flex items-center gap-2 rounded-xl bg-surface2 px-3 py-2 text-xs hover:text-accent">
          <Inbox :size="14" class="shrink-0 text-accent" /><span class="truncate">Anfrage per Mail von {{ angebot.mailAnfrage.vonName || angebot.mailAnfrage.vonEmail }}</span>
        </RouterLink>

        <div class="mt-5 space-y-2">
          <template v-if="angebot.status === 'Entwurf'">
            <button class="btn btn-primary w-full justify-center" @click="mailDialog = true"><Mail :size="16" /> Per Mail senden</button>
            <button class="btn w-full justify-center" @click="b.angebotSenden(angebot.id)"><Send :size="16" /> Als gesendet markieren</button>
            <button class="btn w-full justify-center" @click="bearbeiten"><Pencil :size="16" /> In Workbench bearbeiten</button>
          </template>
          <template v-else-if="angebot.status === 'Gesendet' && !beauftragt">
            <button class="btn btn-primary w-full justify-center" @click="dialog = true"><ShoppingCart :size="16" /> In Auftrag übernehmen</button>
            <button class="btn w-full justify-center" @click="mailDialog = true"><Mail :size="16" /> Erneut per Mail senden</button>
          </template>
          <!-- Nachverhandlung, Position entfällt …: neue Fassung statt das gesendete Angebot zu ändern -->
          <template v-if="['Gesendet', 'Abgelehnt'].includes(angebot.status) && !beauftragt && !angebot.ersetztDurch">
            <RouterLink v-if="offeneFassung" :to="`/angebote/${offeneFassung.id}`" class="btn w-full justify-center"><FilePen :size="16" /> Überarbeitung {{ offeneFassung.id }} öffnen</RouterLink>
            <button v-else-if="!ueberarbeiten" class="btn w-full justify-center" title="Neue Fassung als Entwurf (gleiche Nummer mit -1, -2 …). Dieses Angebot bleibt unverändert und gilt als ersetzt, sobald die neue Fassung gesendet ist." @click="ueberarbeiten = true"><FilePen :size="16" /> Überarbeiten (neue Fassung)</button>
            <div v-else class="rounded-xl border border-line p-3">
              <label class="label mb-1 block">Grund (intern)</label>
              <textarea v-model="grund" rows="2" class="field resize-y text-sm" placeholder="z. B. Position entfällt, Preis nachverhandelt" />
              <div class="mt-2 flex gap-2">
                <button class="btn btn-primary flex-1 justify-center !py-1.5 text-sm" @click="neueFassung"><FilePen :size="15" /> Neue Fassung anlegen</button>
                <button class="btn !py-1.5 text-sm" @click="ueberarbeiten = false">Abbrechen</button>
              </div>
            </div>
          </template>
          <template v-else-if="angebot.status === 'Gesendet'">
            <RouterLink v-if="auftraegeDazu.length === 1" :to="`/auftraege/${auftraegeDazu[0].id}`" class="btn btn-primary w-full justify-center"><ClipboardList :size="16" /> Zum Auftrag {{ auftraegeDazu[0].id }}</RouterLink>
            <button v-if="status === 'Teilweise bestellt'" class="btn w-full justify-center" :class="auftraegeDazu.length === 1 ? '' : 'btn-primary'" @click="dialog = true"><ShoppingCart :size="16" /> Weitere Bauteile in Auftrag übernehmen</button>
            <button v-else class="btn w-full justify-center" title="Dasselbe Angebot noch einmal beauftragen, z. B. für einen Abruf" @click="dialog = true"><ShoppingCart :size="16" /> Weiteren Auftrag (Abruf) anlegen</button>
          </template>
          <button v-if="angebot.status !== 'Entwurf'" class="btn w-full justify-center" title="Kalkulation, Zeichnung und 3D-Modell in der Workbench ansehen (ohne Änderungen)" @click="bearbeiten"><Calculator :size="16" /> In Workbench ansehen</button>
          <button class="btn w-full justify-center" @click="drucken"><Printer :size="16" /> Drucken</button>
          <button v-if="angebot.status === 'Gesendet' && !beauftragt" class="btn w-full justify-center !text-mute" @click="b.angebotAblehnen(angebot.id)"><XCircle :size="16" /> Als abgelehnt markieren</button>
          <button v-if="angebot.status === 'Entwurf'" class="btn w-full justify-center !text-mute" @click="loeschen"><Trash2 :size="16" /> Entwurf löschen</button>
        </div>
      </section>

      <section class="card p-5">
        <h3 class="mb-3 text-sm font-semibold">Bestellfortschritt</h3>
        <ul class="space-y-3">
          <li v-for="p in angebot.positionen" :key="p.key" class="flex items-center gap-3">
            <PartImage :teil="p.teil" :groesse="38" />
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium">{{ p.teil.name }}</div>
              <div class="text-xs text-mute">{{ bestellt[p.key] ? `${bestellt[p.key]} Stk bestellt` : 'noch nicht bestellt' }}</div>
            </div>
            <span class="h-2 w-2 rounded-full" :class="bestellt[p.key] ? 'bg-ok' : 'bg-line'" />
          </li>
        </ul>
        <ul v-if="b.auftraege.some((x) => x.angebotId === angebot.id)" class="mt-4 space-y-1.5 border-t border-line pt-3 text-sm">
          <li class="label">Aufträge aus diesem Angebot</li>
          <li v-for="x in b.auftraege.filter((a) => a.angebotId === angebot.id)" :key="x.id"><RouterLink :to="`/auftraege/${x.id}`" class="text-accent hover:underline tnum">{{ x.id }}</RouterLink></li>
        </ul>
      </section>
      <section v-if="angebot.fassungen?.length > 1" class="card p-5">
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><History :size="15" class="text-accent" /> Fassungen</h3>
        <ul class="space-y-1.5">
          <li v-for="f in angebot.fassungen" :key="f.id">
            <RouterLink :to="`/angebote/${f.id}`" class="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface2" :class="f.id === angebot.id ? 'bg-surface2 font-medium' : ''">
              <span class="tnum">{{ f.id }}</span><StatusBadge :status="f.status" class="scale-90" /><span class="ml-auto text-xs text-mute">{{ datum(f.versandt) }}</span>
            </RouterLink>
            <div v-if="f.grund" class="truncate px-2 text-xs text-mute" :title="f.grund">{{ f.grund }}</div>
          </li>
        </ul>
      </section>
      <AngebotAnfragen :ziel="{ angebotId: angebot.id }" variante="karte" />
    </aside>

    <AngebotMailDialog v-if="mailDialog" :angebot="angebot" @schliessen="mailDialog = false" @gesendet="mailDialog = false" />
    <AuftragDialog v-if="dialog" :angebot="angebot" @schliessen="dialog = false" @angelegt="angelegt" />
  </div>

  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Angebot nicht gefunden</p>
    <RouterLink to="/angebote" class="btn mt-4">Zur Angebotsliste</RouterLink>
  </div>
</template>
