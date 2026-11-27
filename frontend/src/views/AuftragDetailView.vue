<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, MapPin, UserRound, Hash, CalendarDays, Factory, Truck, Receipt, FileText, Calculator, Send, FileCheck2, FileUp, ShoppingCart, PencilLine, History, AlertTriangle, Pencil, Check, X } from '@lucide/vue';
import AuftragAendernDialog from '../components/AuftragAendernDialog.vue';
import BestellungDialog from '../components/BestellungDialog.vue';
import { useRouter } from 'vue-router';
import LieferscheinDialog from '../components/LieferscheinDialog.vue';
import RechnungDialog from '../components/RechnungDialog.vue';
import AngebotMailDialog from '../components/AngebotMailDialog.vue';
import PdfVorschauDialog from '../components/PdfVorschauDialog.vue';
import { belegPdfUrl } from '../lib/belegpdf.js';
import { auftragStand } from '../lib/auftragstand.js';
import { useRechnung } from '../stores/rechnung.js';
import { bereichText } from '../lib/serien.js';
import WorkflowSteps from '../components/WorkflowSteps.vue';
import StatusBadge from '../components/StatusBadge.vue';
import ProjektMarke from '../components/ProjektMarke.vue';
import ProjektFeld from '../components/ProjektFeld.vue';
import PartImage from '../components/PartImage.vue';
import { useBelege } from '../stores/belege.js';
import { useAngebot } from '../stores/angebot.js';
import { useFertigung } from '../stores/fertigung.js';
import { produziert, fortschritt } from '../lib/fertigung.js';
import { eur } from '../lib/format.js';

const route = useRoute();
const b = useBelege();
const f = useFertigung();
const auftrag = computed(() => b.auftrag(route.params.id));
onMounted(() => b.auftraegeNeuLaden());
const lieferDialog = ref(false);
// Bestellnummer des Kunden: auch bei laufendem Auftrag änderbar
const bestellnrEdit = ref(false);
const bestellnrWert = ref('');
function bestellnrStart() { bestellnrWert.value = auftrag.value?.kundenbestellnr ?? ''; bestellnrEdit.value = true; }
function bestellnrFertig() {
  bestellnrEdit.value = false;
  if (bestellnrWert.value.trim() !== (auftrag.value.kundenbestellnr ?? '')) b.bestellnrSetzen(auftrag.value.id, bestellnrWert.value.trim());
}
const rechnungDialog = ref(false);
// Auftragsbestätigung: ansehen (frisch erzeugt) und per Mail senden
const abDialog = ref(false);
const abPdf = ref(null);
function abAnsehen() { abPdf.value = { url: belegPdfUrl('Auftrag', auftrag.value.id, Date.now()), name: `Auftragsbestätigung ${auftrag.value.id}${auftrag.value.aenderungNr ? ` Änderung ${auftrag.value.aenderungNr}` : ''}.pdf` }; }
// Auftrag ändern (Menge, Preis, Termin, Kosten, neue Positionen); danach muss eine neue AB raus
const aendernDialog = ref(false);
const abOffen = computed(() => (auftrag.value?.aenderungNr || 0) > (auftrag.value?.ab?.aenderung || 0));
const zeitpunkt = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const router = useRouter();
const re = useRechnung();
const fbs = computed(() => (auftrag.value ? f.fuerAuftrag(auftrag.value.id) : []));
// Ein Haken gibt es erst, wenn der Schritt wirklich fertig ist. Ein Lieferschein vor der Fertigung hakt die Fertigung nicht ab.
const stand = computed(() => auftragStand({
  fertigungsbauteile: fbs.value, lieferung: auftrag.value?.lieferung, abrechnung: auftrag.value?.abrechnung, rechnungen: auftrag.value ? re.fuerAuftrag(auftrag.value.id) : [],
}));
const rechnungen = computed(() => (auftrag.value ? re.fuerAuftrag(auftrag.value.id) : []));
function rechnungAngelegt(rec) { rechnungDialog.value = false; router.push(`/rechnungen/${rec.id}`); }
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
const fbZu = (key) => fbs.value.find((x) => x.auftragPosKey === key);
// Kalkulation des Angebots in der Workbench ansehen (nur lesen), auf Wunsch gleich mit dieser Position
const draft = useAngebot();
const angebotDazu = computed(() => (auftrag.value?.angebotId ? b.angebot(auftrag.value.angebotId) : null));
// Positionen aus einer Bestellung können aus verschiedenen (auch früheren) Angeboten stammen
const angebotZu = (p) => (p.angebotId ? b.angebot(p.angebotId) : null);
async function inWorkbench(posKey = '', ang = angebotDazu.value) {
  await draft.ausAngebot(ang, { auswahl: posKey, auftragId: auftrag.value.id });
  router.push('/workbench');
}
// Bestellung des Kunden (PDF) an den Auftrag koppeln und abgleichen
const bestellungDialog = ref(false);
</script>

<template>
  <div v-if="auftrag" class="mx-auto max-w-[1200px] space-y-4">
    <RouterLink to="/auftraege" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Aufträge</RouterLink>

    <section class="card p-6">
      <div class="flex flex-wrap items-start justify-between gap-6">
        <div>
          <div class="flex items-center gap-3"><h2 class="text-xl font-semibold tnum">{{ auftrag.id }}</h2><StatusBadge :status="auftrag.status" /><ProjektMarke :projekt="auftrag.projekt" /></div>
          <p class="mt-1 text-sm text-mute">
            <template v-if="auftrag.angebote.length">aus <template v-for="(a, i) in auftrag.angebote" :key="a"><template v-if="i">, </template><RouterLink :to="`/angebote/${a}`" class="text-accent hover:underline tnum">{{ a }}</RouterLink></template></template>
            <template v-else>aus der Bestellung des Kunden</template>
            · angelegt am {{ de(auftrag.datum) }}
          </p>
          <div class="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <button class="btn" title="Auftragsbestätigung als PDF ansehen und drucken" @click="abAnsehen"><FileCheck2 :size="16" /> Auftragsbestätigung</button>
            <button v-if="auftrag.status !== 'Storniert'" class="btn" :class="auftrag.ab?.gesendetAm && !abOffen ? '' : 'btn-primary'" @click="abDialog = true"><Send :size="15" /> {{ abOffen ? `AB Änderung ${auftrag.aenderungNr} senden` : auftrag.ab?.gesendetAm ? 'AB erneut senden' : 'AB per Mail senden' }}</button>
            <span v-if="abOffen" class="inline-flex items-center gap-1 text-xs text-warn"><AlertTriangle :size="13" /> Änderung {{ auftrag.aenderungNr }} ist noch nicht bestätigt</span>
            <span v-else-if="auftrag.ab?.gesendetAm" class="text-xs text-ok">gesendet am {{ zeitpunkt(auftrag.ab.gesendetAm) }} an {{ auftrag.ab.gesendetAn }}</span>
            <span v-else class="text-xs text-mute">noch nicht bestätigt</span>
            <button v-if="auftrag.status !== 'Storniert'" class="btn" title="Menge, Preis, Liefertermin oder Kosten ändern, Positionen streichen oder dazunehmen (Nachverhandlung)" @click="aendernDialog = true"><PencilLine :size="15" /> Auftrag ändern</button>
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <a v-if="auftrag.bestellungDatei" :href="auftrag.bestellungDatei" target="_blank" rel="noopener" class="btn"><ShoppingCart :size="15" /> Bestellung des Kunden</a>
            <button v-if="auftrag.status !== 'Storniert'" class="btn" title="PDF der Bestellung einlesen: Bestellnummer, Positionen und Liefertermine übernehmen und die Preise abgleichen" @click="bestellungDialog = true"><FileUp :size="15" /> {{ auftrag.bestellungDatei ? 'Bestellung erneut abgleichen' : 'Bestellung (PDF) koppeln' }}</button>
          </div>
          <button v-if="!fbs.length" class="btn btn-primary mt-4" @click="f.ausAuftrag(auftrag.id)"><Factory :size="16" /> Fertigung starten</button>
          <RouterLink v-else :to="{ path: '/fertigung', query: { auftrag: auftrag.id } }" class="btn mt-4" title="Fertigung mit allen Positionen dieses Auftrags"><Factory :size="16" /> Zur Fertigung</RouterLink>
          <button v-if="angebotDazu" class="btn mt-4 ml-2" title="Kalkulation, Zeichnung und 3D-Modell des Angebots in der Workbench ansehen (ohne Änderungen)" @click="inWorkbench()"><Calculator :size="16" /> Kalkulation ansehen</button>
          <button v-if="auftrag.lieferung.status !== 'Geliefert'" class="btn mt-4 ml-2" @click="lieferDialog = true"><Truck :size="16" /> Lieferschein erstellen</button>
          <span class="ml-2 mt-4 inline-block align-middle"><StatusBadge :status="auftrag.lieferung.status" /></span>
          <button v-if="auftrag.abrechnung.status !== 'Berechnet'" class="btn mt-4 ml-2" @click="rechnungDialog = true"><Receipt :size="16" /> Rechnung erstellen</button>
          <span v-if="auftrag.abrechnung.berechnet" class="ml-2 mt-4 inline-block align-middle"><StatusBadge :status="auftrag.abrechnung.status" /></span>
          <div v-if="rechnungen.length" class="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
            <span class="text-mute">Rechnungen:</span>
            <RouterLink v-for="x in rechnungen" :key="x.id" :to="`/rechnungen/${x.id}`" class="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface2 px-2.5 py-0.5 hover:border-accent/50"><span class="font-semibold text-accent tnum">{{ x.nummer || 'Entwurf' }}</span><StatusBadge :status="x.status" /></RouterLink>
          </div>
        </div>
        <div class="w-full max-w-xl"><WorkflowSteps :stand="stand" /></div>
      </div>
      <div class="mt-5 grid gap-3 text-sm md:grid-cols-4">
        <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><MapPin :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div class="font-medium">{{ auftrag.kundeName }}</div><div v-for="z in auftrag.kunde.adresse" :key="z" class="text-mute">{{ z }}</div></div></div>
        <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><UserRound :size="16" class="mt-0.5 shrink-0 text-mute" /><div><div class="text-xs text-mute">Ansprechpartner</div><div>{{ auftrag.kontaktName || auftrag.kunde.kontakt?.name || '–' }}</div><div class="text-xs text-mute">{{ auftrag.kontaktName || auftrag.kontaktEmail ? auftrag.kontaktEmail : auftrag.kunde.kontakt?.email }}</div></div></div>
        <div class="flex gap-2.5 rounded-xl bg-surface2 px-3.5 py-2.5"><Hash :size="16" class="mt-0.5 shrink-0 text-mute" />
          <div class="min-w-0 flex-1"><div class="text-xs text-mute">Bestellnummer des Kunden</div>
            <div v-if="bestellnrEdit" class="mt-0.5 flex items-center gap-1.5">
              <input v-model="bestellnrWert" class="field !py-1 text-sm" placeholder="Bestellnummer" autofocus @keydown.enter="bestellnrFertig" @keydown.esc="bestellnrEdit = false" />
              <button class="text-ok" title="Übernehmen" @click="bestellnrFertig"><Check :size="16" /></button>
              <button class="text-mute hover:text-ink" title="Abbrechen" @click="bestellnrEdit = false"><X :size="16" /></button>
            </div>
            <div v-else class="flex items-center gap-2"><span class="min-w-0 flex-1 truncate">{{ auftrag.kundenbestellnr || '–' }}</span><button v-if="auftrag.status !== 'Storniert'" class="text-mute hover:text-ink" title="Bestellnummer ändern" @click="bestellnrStart"><Pencil :size="13" /></button></div>
            <div v-if="auftrag.bestelldatum" class="text-xs text-mute">vom {{ de(auftrag.bestelldatum) }}</div></div></div>
        <ProjektFeld :projekt="auftrag.projekt" @speichern="b.projektSetzen('Auftrag', auftrag.id, $event)" />
      </div>
    </section>

    <section class="card overflow-hidden">
      <header class="flex items-center justify-between border-b border-line px-6 py-4">
        <h3 class="text-sm font-semibold">Positionen</h3>
        <div class="text-right"><div class="text-xs text-mute">Auftragswert netto</div><div class="text-lg font-semibold tnum">{{ eur(auftrag.netto) }}</div></div>
      </header>
      <div v-for="(p, i) in auftrag.positionen" :key="p.key" class="flex gap-4 border-b border-line px-6 py-4 last:border-0" :class="p.entfallen ? 'opacity-60' : ''">
        <PartImage iso :teil="p.teil" :groesse="64" />
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline justify-between gap-4">
            <div><span class="mr-2 text-mute">{{ i + 1 }}</span><span class="font-medium" :class="p.entfallen ? 'line-through' : ''">{{ p.teil.name }}</span><span v-if="p.entfallen" class="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">entfällt</span><span v-else-if="p.mengeUrspruenglich && p.mengeUrspruenglich !== p.menge" class="ml-2 text-xs text-warn">bisher {{ p.mengeUrspruenglich }} Stk</span><span v-if="p.teil.teilenummer" class="ml-2 text-xs text-mute">{{ p.teil.teilenummer }}</span><span v-if="p.teil.revision" class="ml-1.5 text-xs text-mute">Rev. {{ p.teil.revision }}</span></div>
            <div class="text-sm tnum">{{ p.menge }} Stk × {{ eur(p.einzelpreis) }} = <span class="font-semibold">{{ eur(p.einzelpreis * p.menge) }}</span></div>
          </div>
          <div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-mute">
            <span v-if="p.teil.material">{{ p.teil.material }}</span>
            <span v-if="p.bestellposition" class="text-ink">Pos. {{ p.bestellposition }} der Bestellung</span>
            <span v-if="p.preisform === 'Bestellung'" class="rounded-full bg-surface2 px-2 py-0.5" title="Stückpreis wie bestellt, die Kosten des Angebots sind darin enthalten">Preis laut Bestellung</span>
            <span v-else-if="p.bestellpreis && Math.abs(p.bestellpreis - p.einzelpreis) >= 0.005" class="tnum" title="Stückpreis in der Bestellung des Kunden">bestellt zu {{ eur(p.bestellpreis) }} je Stück</span>
            <button v-if="angebotZu(p) && p.angebotKey" class="inline-flex items-center gap-1 text-accent hover:underline" title="Kalkulation dieses Bauteils in der Workbench ansehen" @click="inWorkbench(p.angebotKey, angebotZu(p))"><Calculator :size="12" /> Kalkulation</button>
            <a v-if="p.teil.zeichnung" :href="p.teil.zeichnung" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-accent hover:underline"><FileText :size="12" /> Zeichnung</a>
            <span v-if="p.teil.revision && p.teil.aktuelleRevision && p.teil.revision.toLowerCase() !== p.teil.aktuelleRevision.toLowerCase()" class="text-warn">am Bauteil inzwischen Rev. {{ p.teil.aktuelleRevision }}</span>
            <span v-if="p.staffelMenge">Staffel {{ p.staffelMenge }} Stk</span>
            <span class="inline-flex items-center gap-1" :class="p.geliefert >= p.menge ? 'text-ok' : p.geliefert ? 'text-warn' : ''"><Truck :size="12" /> geliefert {{ p.geliefert }} / {{ p.menge }}</span>
            <span v-if="p.gefertigt || fbZu(p.key)">gefertigt {{ p.gefertigt }}</span>
            <RouterLink v-for="ls in p.lieferscheine" :key="ls.id" :to="`/lieferscheine/${ls.id}`" class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-accent hover:underline"><span class="tnum">{{ ls.id }}</span><span class="text-mute">{{ ls.menge }} Stk</span></RouterLink>
            <span class="inline-flex items-center gap-1" :class="p.berechnet >= p.menge ? 'text-ok' : p.berechnet ? 'text-warn' : ''"><Receipt :size="12" /> berechnet {{ p.berechnet }} / {{ p.menge }}</span>
            <RouterLink v-for="x in p.rechnungen" :key="x.id" :to="`/rechnungen/${x.id}`" class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-accent hover:underline"><span class="tnum">{{ x.nummer || 'Entwurf' }}</span><span class="text-mute">{{ x.menge }} Stk</span></RouterLink>
            <span v-if="p.serienVon" class="inline-flex items-center gap-1 text-ink"><Hash :size="12" /> Seriennummern {{ bereichText(p.serienVon, p.serienBis, p.serienStellen) }}</span>
            <span class="inline-flex items-center gap-1"><CalendarDays :size="12" /> Liefertermin {{ p.termin ? new Date(p.termin).toLocaleDateString('de-DE') : 'offen' }}</span>
          </div>
          <!-- was in der Bestellung des Kunden zu dieser Position steht -->
          <div v-if="p.bestellung" class="mt-2 rounded-xl border border-line px-3 py-2 text-xs">
            <div class="flex flex-wrap items-center gap-x-4 gap-y-0.5">
              <span class="font-medium">Laut Bestellung</span>
              <span v-if="p.bestellung.zeichnungsdatum" :title="'Datum bzw. Stand der Zeichnung laut Bestellung'">Zeichnung vom {{ de(p.bestellung.zeichnungsdatum) }}</span>
              <span v-if="p.bestellung.betrag != null" class="tnum">{{ p.bestellung.menge }} {{ p.bestellung.einheit || 'Stk' }} × {{ eur(p.bestellung.preis) }} = {{ eur(p.bestellung.betrag) }}</span>
              <span v-if="p.bestellung.betrag != null && Math.abs(p.bestellung.betrag - p.einzelpreis * p.menge - p.kosten.reduce((s, k) => s + k.betrag, 0)) > 0.05" class="text-warn tnum">Auftrag: {{ eur(p.einzelpreis * p.menge + p.kosten.reduce((s, k) => s + k.betrag, 0)) }}</span>
            </div>
            <dl v-if="p.bestellung.angaben?.length" class="mt-1 grid gap-x-4 gap-y-0.5 text-mute sm:grid-cols-[auto_1fr]">
              <template v-for="a in p.bestellung.angaben" :key="a.spalte"><dt>{{ a.spalte }}</dt><dd class="text-ink tnum">{{ a.wert }}</dd></template>
            </dl>
          </div>
          <div v-for="k in p.kosten" :key="k.label" class="mt-1 flex justify-between pl-4 text-xs text-mute"><span>↳ {{ k.label }}<template v-if="p.kostenAbgerechnet[k.label]"> · abgerechnet in <RouterLink :to="`/rechnungen/${p.kostenAbgerechnet[k.label]}`" class="text-accent hover:underline">{{ re.rechnung(p.kostenAbgerechnet[k.label])?.nummer || 'Entwurf' }}</RouterLink></template></span><span class="tnum">{{ eur(k.betrag) }}</span></div>

          <RouterLink v-if="fbZu(p.key)" :to="`/fertigung/${fbZu(p.key).id}`" class="mt-3 flex items-center gap-3 rounded-xl bg-surface2 px-3.5 py-2.5 text-sm transition hover:bg-accent-soft">
            <Factory :size="15" class="text-accent" />
            <span class="tnum">{{ fbZu(p.key).id }}</span><StatusBadge :status="fbZu(p.key).status" />
            <span class="ml-auto text-xs text-mute tnum">{{ produziert(fbZu(p.key)) }} / {{ fbZu(p.key).menge }} Stk</span>
            <span class="h-1.5 w-24 overflow-hidden rounded-full bg-line"><span class="block h-full rounded-full" :class="fortschritt(fbZu(p.key)) >= 1 ? 'bg-ok' : 'bg-accent'" :style="{ width: fortschritt(fbZu(p.key)) * 100 + '%' }" /></span>
          </RouterLink>
        </div>
      </div>
    </section>
    <!-- Änderungen mit Grund, neueste zuerst -->
    <section v-if="auftrag.aenderungen?.length" class="card p-6">
      <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><History :size="16" class="text-accent" /> Änderungen</h3>
      <ol class="space-y-3">
        <li v-for="z in [...auftrag.aenderungen].reverse()" :key="z.nr" class="rounded-xl bg-surface2 px-4 py-3 text-sm">
          <div class="flex flex-wrap items-center gap-2"><span class="font-semibold">Änderung {{ z.nr }}</span><span class="text-xs text-mute">{{ zeitpunkt(z.datum) }} · {{ z.benutzer }}</span>
            <span class="ml-auto text-xs" :class="(auftrag.ab?.aenderung || 0) >= z.nr ? 'text-ok' : 'text-warn'">{{ (auftrag.ab?.aenderung || 0) >= z.nr ? 'bestätigt' : 'AB ausstehend' }}</span></div>
          <div class="mt-0.5 text-mute">{{ z.grund }}</div>
          <ul class="mt-1.5 list-inside list-disc text-xs"><li v-for="x in z.details" :key="x" :class="x.startsWith('Fertigung:') ? 'text-mute' : ''">{{ x }}</li></ul>
        </li>
      </ol>
    </section>
    <AuftragAendernDialog v-if="aendernDialog" :auftrag="auftrag" @schliessen="aendernDialog = false" @geaendert="aendernDialog = false" />
    <BestellungDialog v-if="bestellungDialog" :auftrag="auftrag" @schliessen="bestellungDialog = false" @fertig="bestellungDialog = false" />
    <AngebotMailDialog v-if="abDialog" :auftrag="auftrag" @schliessen="abDialog = false" @gesendet="abDialog = false" />
    <PdfVorschauDialog v-if="abPdf" :url="abPdf.url" :name="abPdf.name" doctype="Auftrag" :beleg-id="auftrag.id" @schliessen="abPdf = null" />
    <RechnungDialog v-if="rechnungDialog" :auftrag-id="auftrag.id" @schliessen="rechnungDialog = false" @angelegt="rechnungAngelegt" />
    <LieferscheinDialog v-if="lieferDialog" :auftrag-id="auftrag.id" @schliessen="lieferDialog = false" @angelegt="lieferDialog = false" />
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Auftrag nicht gefunden</p>
    <RouterLink to="/auftraege" class="btn mt-4">Zur Auftragsliste</RouterLink>
  </div>
</template>
