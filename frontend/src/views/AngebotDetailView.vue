<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Pencil, Send, Printer, ShoppingCart, XCircle, Trash2, ArrowLeft, Mail, Inbox, ClipboardList } from '@lucide/vue';
import AngebotMailDialog from '../components/AngebotMailDialog.vue';
import { useUi } from '../stores/ui.js';
import BelegPdf from '../components/BelegPdf.vue';
import { belegPdfUrl, pdfDrucken } from '../lib/belegpdf.js';
import AuftragDialog from '../components/AuftragDialog.vue';
import AngebotAnfragen from '../components/AngebotAnfragen.vue';
import WorkflowSteps from '../components/WorkflowSteps.vue';
import StatusBadge from '../components/StatusBadge.vue';
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
const geladen = Date.now();
const pdfUrl = computed(() => (angebot.value ? belegPdfUrl('Angebot', angebot.value.id, `${angebot.value.status}-${geladen}`) : ''));
async function drucken() {
  try { await pdfDrucken(pdfUrl.value); } catch (e) { ui.toast(e.message, 'warn'); }
}

function bearbeiten() {
  draft.ausAngebot(angebot.value);
  router.push('/workbench');
}
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
    <BelegPdf v-if="angebot.kopf?.kundeId" :url="pdfUrl" :name="`Angebot ${angebot.id}.pdf`" />
    <div v-else class="card grid min-h-[300px] place-items-center p-10 text-sm text-mute">Ohne Kunden gibt es noch kein PDF. Bitte das Angebot in der Workbench vervollständigen.</div>

    <aside class="no-print space-y-4 xl:sticky xl:top-0">
      <RouterLink to="/angebote" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Angebote</RouterLink>

      <section class="card p-5">
        <div class="flex items-center justify-between"><h2 class="font-semibold tnum">{{ angebot.id }}</h2><StatusBadge :status="status" /></div>
        <div class="mt-5"><WorkflowSteps :stand="stand" :schritte="['Angebot', 'Auftrag']" /></div>
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
          <template v-else-if="angebot.status === 'Gesendet'">
            <RouterLink v-if="auftraegeDazu.length === 1" :to="`/auftraege/${auftraegeDazu[0].id}`" class="btn btn-primary w-full justify-center"><ClipboardList :size="16" /> Zum Auftrag {{ auftraegeDazu[0].id }}</RouterLink>
            <button v-if="status === 'Teilweise bestellt'" class="btn w-full justify-center" :class="auftraegeDazu.length === 1 ? '' : 'btn-primary'" @click="dialog = true"><ShoppingCart :size="16" /> Weitere Bauteile in Auftrag übernehmen</button>
            <button v-else class="btn w-full justify-center" title="Dasselbe Angebot noch einmal beauftragen, z. B. für einen Abruf" @click="dialog = true"><ShoppingCart :size="16" /> Weiteren Auftrag (Abruf) anlegen</button>
          </template>
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
