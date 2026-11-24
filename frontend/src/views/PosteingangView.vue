<script setup>
// Posteingang: Mails aus dem gemeinsamen Postfach (bekannte Absender und Mails mit Stichwort im Betreff), eingeordnet als
// Anfrage, Bestellung, Rechnung, Lieferant oder Sonstiges. Links die Liste, rechts die Mail mit Anhängen und der Zuordnung
// zu Kunde oder Lieferant; je Art die passende Aktion (Workbench, Auftrag aus Bestellung, Eingangsrechnung).
import { ref, computed, watch, onMounted, defineAsyncComponent } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Inbox, RefreshCw, Paperclip, FileText, Box, Table2, File, FileArchive, Building2, UserPlus, Check, Ban, Reply, Settings, MailWarning, Calculator, ArrowRight, Search, X, MessagesSquare, ShoppingCart, Receipt, Truck, Shapes, ShieldAlert, CheckCircle2, RotateCcw, FileCode2, AlertCircle } from '@lucide/vue';
import BestellungDialog from '../components/BestellungDialog.vue';
import { repo } from '../data/repo.js';
import FilterLeiste from '../components/FilterLeiste.vue';
import { useAngebot } from '../stores/angebot.js';
import StatusBadge from '../components/StatusBadge.vue';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import MailHtml from '../components/MailHtml.vue';
import TabelleDialog from '../components/TabelleDialog.vue';
import { useMail } from '../stores/mail.js';
import { benutzer } from '../data/repo.js';
import { zahl } from '../lib/format.js';
import { bauteilGruppen } from '../lib/anhaenge.js';

const DrawingViewer = defineAsyncComponent(() => import('../components/DrawingViewer.vue'));
const ModelViewer = defineAsyncComponent(() => import('../components/ModelViewer.vue'));

const route = useRoute();
const router = useRouter();
const mail = useMail();
const draft = useAngebot();
const istAdmin = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'System Manager'].includes(x)));

const filter = ref('offen');
const FILTER = [
  { id: 'offen', label: 'Offen', passt: (x) => ['Neu', 'In Bearbeitung'].includes(x.status) || x.neueAntwort },
  { id: 'beantwortet', label: 'Erledigt', passt: (x) => ['Beantwortet', 'Erledigt'].includes(x.status) },
  { id: 'alle', label: 'Alle', passt: () => true },
];
// Register je Art der Mail (vom Server beim Abholen eingeordnet, hier umsortierbar)
const ARTEN = [
  { id: 'Anfrage', label: 'Anfragen', icon: Calculator },
  { id: 'Bestellung', label: 'Bestellungen', icon: ShoppingCart },
  { id: 'Rechnung', label: 'Rechnungen', icon: Receipt },
  { id: 'Lieferant', label: 'Lieferanten', icon: Truck },
  { id: 'Sonstiges', label: 'Sonstiges', icon: Shapes },
];
const artIcon = (k) => ARTEN.find((a) => a.id === k)?.icon ?? Shapes;
const kategorie = ref('');
const nachArt = (k) => mail.liste.filter((x) => (!k || (x.kategorie || 'Anfrage') === k) && FILTER.find((f) => f.id === filter.value).passt(x)).length;
// Schnellfilter (kombinierbar) und Suche über Betreff, Absender, Kunde, Text und Nummern
const SCHNELL = [
  { id: 'wichtig', label: 'Wichtig', icon: AlertCircle, passt: (x) => x.wichtig },
  { id: 'ohneKunde', label: 'Kunde fehlt', icon: UserPlus, passt: (x) => !x.kundeId },
  { id: 'antwort', label: 'Neue Antwort', icon: MessagesSquare, passt: (x) => x.neueAntwort },
  { id: 'zeichnung', label: 'Mit Zeichnung', icon: FileText, passt: (x) => !!x.anhangArten?.Zeichnung },
  { id: 'step', label: 'Mit 3D-Modell', icon: Box, passt: (x) => !!x.anhangArten?.STEP },
  { id: 'ohneAngebot', label: 'Ohne Angebot', icon: Calculator, passt: (x) => !x.angebotId },
];
const schnell = ref([]);
const schnellUm = (k) => { schnell.value = schnell.value.includes(k) ? schnell.value.filter((x) => x !== k) : [...schnell.value, k]; };
const suche = ref('');
const norm = (t) => String(t ?? '').toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
const vorgefiltert = computed(() => {
  const woerter = norm(suche.value).split(/\s+/).filter(Boolean);
  const aktiv = SCHNELL.filter((q) => schnell.value.includes(q.id));
  return mail.liste.filter((x) => FILTER.find((f) => f.id === filter.value).passt(x)
    && (!kategorie.value || (x.kategorie || 'Anfrage') === kategorie.value)
    && aktiv.every((q) => q.passt(x))
    && (!woerter.length || woerter.every((w) => norm([x.id, x.betreff, x.vonName, x.vonEmail, x.kundeName, x.kundeId, x.angebotId, x.vorschau].join(' ')).includes(w))));
});
const zeilen = ref([]);
const beschriftungen = { status: 'Status', kundeName: 'Kunde', vonEmail: 'Absender', letzteNachricht: 'Letzte Nachricht', datum: 'Eingegangen', angebotId: 'Angebot' };
const zaehler = (id) => mail.liste.filter((x) => (!kategorie.value || (x.kategorie || 'Anfrage') === kategorie.value) && FILTER.find((f) => f.id === id).passt(x)).length;
const sucheAktiv = computed(() => !!suche.value.trim() || schnell.value.length > 0);
function zuruecksetzen() { suche.value = ''; schnell.value = []; }

// Liste nach Tagen gruppiert: Heute, Gestern, Diese Woche, dann je Monat
function gruppeVon(iso) {
  if (!iso) return 'Ohne Datum';
  const t = new Date(iso);
  const heute = new Date(); heute.setHours(0, 0, 0, 0);
  const tage = Math.floor((heute - new Date(t.getFullYear(), t.getMonth(), t.getDate())) / 864e5);
  if (tage <= 0) return 'Heute';
  if (tage === 1) return 'Gestern';
  if (tage < 7) return 'Diese Woche';
  return t.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
}
const gruppen = computed(() => {
  const g = [];
  for (const x of zeilen.value) {
    const name = gruppeVon(x.letzteNachricht);
    if (g.at(-1)?.name !== name) g.push({ name, zeilen: [] });
    g.at(-1).zeilen.push(x);
  }
  // wichtige Mails zuerst, sonst wie sortiert
  for (const x of g) x.zeilen = [...x.zeilen.filter((z) => z.wichtig), ...x.zeilen.filter((z) => !z.wichtig)];
  return g;
});
const hervor = (text) => {
  const w = suche.value.trim();
  if (!w || !text) return [{ t: text ?? '', m: false }];
  // ohne NFD: Positionen müssen zum Originaltext passen
  const n = text.toLowerCase();
  const teile = [];
  let i = 0;
  const ws = w.toLowerCase().split(/\s+/).filter(Boolean);
  while (i < text.length) {
    let treffer = null;
    for (const x of ws) { const j = n.indexOf(x, i); if (j >= 0 && (!treffer || j < treffer[0])) treffer = [j, x.length]; }
    if (!treffer) { teile.push({ t: text.slice(i), m: false }); break; }
    if (treffer[0] > i) teile.push({ t: text.slice(i, treffer[0]), m: false });
    teile.push({ t: text.slice(treffer[0], treffer[0] + treffer[1]), m: true });
    i = treffer[0] + treffer[1];
  }
  return teile;
};

const id = computed(() => route.params.id || '');
const d = computed(() => (id.value ? mail.details[id.value] : null));
onMounted(async () => {
  await mail.laden();
  await Promise.resolve();
  if (!id.value && zeilen.value.length && window.innerWidth >= 1024) router.replace(`/posteingang/${zeilen.value[0].id}`);
});

// ---- Zuordnung zu Kunde und Kontakt
const art = ref('bestehend');
const kunde = ref('');
const neuerKunde = ref('');
const kontakt = ref({ anrede: '', vorname: '', nachname: '' });
const ordnet = ref(false);
watch(d, (x) => {
  if (!x || x.kundeId) return;
  kunde.value = x.kundeVorschlag?.id ?? '';
  art.value = 'bestehend';
  neuerKunde.value = '';
  kontakt.value = { ...x.kontaktVorschlag, nachname: x.kontaktVorschlag.nachname || x.vonEmail.split('@')[0] };
}, { immediate: true });
const kannZuordnen = computed(() => (art.value === 'neu' ? !!neuerKunde.value.trim() : !!kunde.value) && !!kontakt.value.nachname.trim());
async function zuordnen() {
  ordnet.value = true;
  await mail.kundeZuordnen(d.value.id, art.value === 'neu' ? { neuerKunde: neuerKunde.value, kontakt: kontakt.value } : { kunde: kunde.value, kontakt: kontakt.value });
  ordnet.value = false;
}

// ---- In die Workbench: Angebotsentwurf mit Kunde, Bauteile aus Zeichnungen und Modellen, Mengen aus dem Mailtext
// Steht eine Tabelle in der Mail, werden Menge und Liefertermin vorher in der Tabellen-Maske bestätigt.
const uebernimmt = ref(false);
const tabelleOffen = ref(false);
function inWorkbench() {
  if (!d.value.angebotId && d.value.tabellen?.length) { tabelleOffen.value = true; return; }
  uebernehmen();
}
async function uebernehmen({ zeilen = [], spalten = null } = {}) {
  tabelleOffen.value = false;
  uebernimmt.value = true;
  if (spalten) await mail.tabellenvorlageLernen(d.value.id, spalten);
  const r = await mail.angebotAnlegen(d.value.id);
  uebernimmt.value = false;
  if (!r) return;
  if (r.angebot.status !== 'Entwurf') { router.push(`/angebote/${r.angebot.id}`); return; }
  await draft.ausMailAnfrage({ ...r, zeilen });
  router.push('/workbench');
}

// ---- Einordnen: Art ändern, erledigt, Lieferant zuordnen
const istKunde = computed(() => ['Anfrage', 'Bestellung', 'Sonstiges'].includes(d.value?.kategorie || 'Anfrage') && !d.value?.lieferantId);
const lieferanten = ref([]);
const lieferantWahl = ref('');
onMounted(async () => { try { lieferanten.value = (await repo.lieferanten.liste()).filter((l) => l.aktiv !== false); } catch { /* Auswahl bleibt leer */ } });
const lieferantName = (lid) => lieferanten.value.find((l) => l.id === lid)?.name ?? lid;
async function naechsteNachErledigt() {
  const naechste = zeilen.value[zeilen.value.findIndex((x) => x.id === d.value.id) + 1]?.id;
  if (await mail.erledigt(d.value.id, 1) && filter.value === 'offen') router.replace(naechste ? `/posteingang/${naechste}` : '/posteingang');
}

// ---- Bestellung: Auftrag aus dem Bestell-PDF (Bestell-Import mit Abgleich gegen das Angebot)
const bestellung = ref(null);
async function bestellungOeffnen(a) {
  try {
    const blob = await (await fetch(a.url, { credentials: 'same-origin' })).blob();
    bestellung.value = new File([blob], a.name, { type: 'application/pdf' });
  } catch (e) { mail.ui?.toast?.(e.message, 'warn'); }
}
async function bestellungFertig(rec) {
  const auftragId = rec?.id ?? rec?.auftrag?.id ?? '';
  bestellung.value = null;
  await mail.erledigt(d.value.id, 1, auftragId);
  if (auftragId) router.push(`/auftraege/${auftragId}`);
}

// ---- Rechnung: Eingangsrechnung aus einem Anhang
const pdfOderXml = (a) => /\.(pdf|xml)$/i.test(a.name);
async function alsRechnung(a) {
  const r = await mail.eingangsrechnung(d.value.id, a.url);
  if (r) router.push(`/eingangsrechnungen/${r.id}`);
}

// ---- Keine Anfrage (mit Rückfrage im Knopf)
const bestaetigen = ref(false);
async function verwerfen(sperren = false) {
  if (!bestaetigen.value) { bestaetigen.value = true; return; }
  const naechste = zeilen.value[zeilen.value.findIndex((x) => x.id === d.value.id) + 1]?.id;
  if (await mail.keineAnfrage(d.value.id, sperren)) router.replace(naechste ? `/posteingang/${naechste}` : '/posteingang');
}

// ---- Anhänge
const vorschau = ref(null);
const ICON = { Zeichnung: FileText, STEP: Box, Tabelle: Table2, ZIP: FileArchive, Datei: File };
const groesse = (b) => (!b ? '' : b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);
const ansehbar = (a) => a.art === 'Zeichnung' || a.art === 'STEP';
const anhangGruppen = (n) => bauteilGruppen(n.anhaenge);
// Je Nachricht: HTML (wie im Mailprogramm) oder reiner Text
const alsText = ref({});
// Beim Wechsel der Anfrage: laden, Vorschau und Rückfrage zurücksetzen
watch(id, (neu) => { if (neu) mail.detail(neu); vorschau.value = null; bestaetigen.value = false; alsText.value = {}; }, { immediate: true });
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const kurzZeit = (iso) => {
  if (!iso) return '';
  const t = new Date(iso);
  return t.toDateString() === new Date().toDateString() ? t.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : t.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
};
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <!-- Register je Art -->
    <div class="mb-3 flex flex-wrap gap-1.5">
      <button class="register" :class="!kategorie ? 'register-aktiv' : ''" @click="kategorie = ''"><Inbox :size="14" /> Alle <span class="tnum opacity-70">{{ nachArt('') }}</span></button>
      <button v-for="a in ARTEN" :key="a.id" class="register" :class="kategorie === a.id ? 'register-aktiv' : ''" @click="kategorie = a.id"><component :is="a.icon" :size="14" /> {{ a.label }} <span class="tnum opacity-70">{{ nachArt(a.id) }}</span></button>
    </div>
    <!-- Kopf: Status, Suche, Abrufen -->
    <div class="mb-3 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface p-1">
        <button v-for="f in FILTER" :key="f.id" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f.id ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="filter = f.id">
          {{ f.label }} <span class="ml-1 text-xs tnum opacity-70">{{ zaehler(f.id) }}</span>
        </button>
      </div>
      <label class="relative min-w-[220px] flex-1 sm:max-w-sm">
        <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !pl-9 !pr-8" placeholder="Betreff, Absender, Kunde, Text …" />
        <button v-if="suche" class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-mute hover:text-ink" title="Suche leeren" @click="suche = ''"><X :size="14" /></button>
      </label>
      <RouterLink v-if="istAdmin" to="/stammdaten/mail" class="ml-auto inline-flex items-center gap-1.5 text-xs text-mute hover:text-ink"><Settings :size="14" /> Mail-Anbindung</RouterLink>
      <button class="btn" :class="istAdmin ? '' : 'ml-auto'" :disabled="mail.ruft" @click="mail.abrufen()"><RefreshCw :size="15" :class="mail.ruft ? 'animate-spin' : ''" /> Jetzt abrufen</button>
    </div>
    <!-- Schnellfilter und anpassbare Filter -->
    <div class="mb-4 flex flex-wrap items-center gap-2">
      <button v-for="q in SCHNELL" :key="q.id" type="button" class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition" :class="schnell.includes(q.id) ? 'border-accent/50 bg-accent-soft text-accent' : 'border-line bg-surface text-mute hover:text-ink'" @click="schnellUm(q.id)">
        <component :is="q.icon" :size="13" /> {{ q.label }}
      </button>
      <span class="ml-auto text-xs text-mute tnum">{{ zeilen.length }} von {{ mail.liste.length }}</span>
      <button v-if="sucheAktiv" class="text-xs text-mute underline-offset-2 hover:text-ink hover:underline" @click="zuruecksetzen">Zurücksetzen</button>
    </div>
    <FilterLeiste v-model="zeilen" class="mb-4" :liste="vorgefiltert" modul="posteingang" :beschriftungen="beschriftungen" :ausblenden="['vorschau', 'id', 'betreff', 'vonName']" />

    <div class="grid items-start gap-4 lg:grid-cols-[400px_1fr]">
      <!-- Liste -->
      <section class="card overflow-hidden lg:sticky lg:top-0 lg:max-h-[calc(100vh-9rem)] lg:overflow-y-auto" :class="id ? 'hidden lg:block' : ''">
        <div v-if="!mail.geladen" class="p-6 text-sm text-mute">Wird geladen …</div>
        <div v-else-if="!zeilen.length" class="flex flex-col items-center px-6 py-14 text-center text-sm text-mute">
          <Inbox :size="34" :stroke-width="1.4" class="mb-3" />
          <template v-if="mail.liste.length">
            <span class="font-medium text-ink">Nichts gefunden</span>
            <span class="mt-1 text-xs">Andere Suche oder weniger Filter probieren.</span>
            <button class="btn mt-3 !py-1 text-xs" @click="zuruecksetzen(); filter = 'alle'">Alle zeigen</button>
          </template>
          <template v-else>
            <span class="font-medium text-ink">Keine Mails</span>
            <span class="mt-1 text-xs">Geholt werden Mails bekannter Absender (Kunden, Lieferanten) und Mails mit einem Stichwort im Betreff, z. B. „Anfrage“.</span>
          </template>
        </div>
        <div v-for="g in gruppen" :key="g.name">
          <div class="sticky top-0 z-10 border-b border-line bg-surface2/95 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-mute backdrop-blur">{{ g.name }}</div>
          <div v-auto-animate class="divide-y divide-line">
            <RouterLink v-for="x in g.zeilen" :key="x.id" :to="`/posteingang/${x.id}`" class="relative block px-4 py-3 transition hover:bg-surface2" :class="x.id === id ? 'bg-accent-soft/60' : ''">
              <span v-if="x.id === id" class="absolute inset-y-0 left-0 w-0.5 bg-accent" />
              <div class="flex items-center gap-2">
                <button type="button" class="wichtig" :class="x.wichtig ? 'wichtig-an' : ''" :title="x.wichtig ? 'Wichtig – Kennzeichen entfernen' : 'Als wichtig kennzeichnen'" @click.prevent.stop="mail.wichtigSetzen(x.id, !x.wichtig)">!</button>
                <span v-if="x.status === 'Neu' || x.neueAntwort" class="h-2 w-2 shrink-0 rounded-full bg-accent" />
                <ShieldAlert v-if="x.absenderWarnung" :size="13" class="shrink-0 text-warn" title="Absender nicht bestätigt" />
                <component :is="artIcon(x.kategorie)" v-if="!kategorie" :size="13" class="shrink-0 text-mute" :title="x.kategorie" />
                <span class="min-w-0 flex-1 truncate text-sm" :class="x.status === 'Neu' ? 'font-semibold' : 'font-medium'"><template v-for="(t, i) in hervor(x.vonName || x.vonEmail)" :key="i"><mark v-if="t.m" class="rounded bg-warn/25 text-ink">{{ t.t }}</mark><template v-else>{{ t.t }}</template></template></span>
                <span class="shrink-0 text-xs text-mute tnum">{{ kurzZeit(x.letzteNachricht) }}</span>
              </div>
              <div class="mt-0.5 truncate text-sm"><template v-for="(t, i) in hervor(x.betreff || '(ohne Betreff)')" :key="i"><mark v-if="t.m" class="rounded bg-warn/25 text-ink">{{ t.t }}</mark><template v-else>{{ t.t }}</template></template></div>
              <div v-if="x.vorschau" class="mt-0.5 line-clamp-1 text-xs text-mute"><template v-for="(t, i) in hervor(x.vorschau)" :key="i"><mark v-if="t.m" class="rounded bg-warn/25 text-ink">{{ t.t }}</mark><template v-else>{{ t.t }}</template></template></div>
              <div class="mt-1.5 flex items-center gap-2 text-xs text-mute">
                <span v-if="x.kundeName" class="inline-flex min-w-0 items-center gap-1 truncate"><Building2 :size="12" class="shrink-0" /> {{ x.kundeName }}</span>
                <span v-else-if="x.lieferantId" class="inline-flex min-w-0 items-center gap-1 truncate"><Truck :size="12" class="shrink-0" /> {{ x.lieferantId }}</span>
                <span v-else-if="(x.kategorie || 'Anfrage') === 'Anfrage'" class="inline-flex items-center gap-1 text-warn"><UserPlus :size="12" /> Kunde zuordnen</span>
                <span v-if="x.eingangsrechnungen?.length" class="inline-flex items-center gap-0.5 text-ok" title="Eingangsrechnung angelegt"><Receipt :size="12" /><span class="tnum">{{ x.eingangsrechnungen.length }}</span></span>
                <span v-if="x.anhangArten?.Zeichnung" class="inline-flex items-center gap-0.5" :title="`${x.anhangArten.Zeichnung} Zeichnung(en)`"><FileText :size="12" /><span class="tnum">{{ x.anhangArten.Zeichnung }}</span></span>
                <span v-if="x.anhangArten?.STEP" class="inline-flex items-center gap-0.5" :title="`${x.anhangArten.STEP} 3D-Modell(e)`"><Box :size="12" /><span class="tnum">{{ x.anhangArten.STEP }}</span></span>
                <span v-if="x.anzahlNachrichten > 1" class="inline-flex items-center gap-0.5" :title="`${x.anzahlNachrichten} Nachrichten im Verlauf`"><MessagesSquare :size="12" /><span class="tnum">{{ x.anzahlNachrichten }}</span></span>
                <span v-if="x.neueAntwort" class="text-accent">neue Antwort</span>
                <span class="ml-auto flex shrink-0 items-center gap-1.5">
                  <span v-if="x.angebotId" class="tnum">{{ x.angebotId }}</span>
                  <StatusBadge v-if="x.status !== 'Neu'" :status="x.status" />
                </span>
              </div>
            </RouterLink>
          </div>
        </div>
      </section>

      <!-- Mail -->
      <div v-if="id && !d" class="card p-6 text-sm text-mute">Wird geladen …</div>
      <div v-else-if="d" class="space-y-4">
        <TabelleDialog v-if="tabelleOffen" :anfrage="d" @schliessen="tabelleOffen = false" @uebernehmen="uebernehmen" />
        <BestellungDialog v-if="bestellung" :datei="bestellung" :kunde-id="d.kundeId" @schliessen="bestellung = null" @fertig="bestellungFertig" />
        <section class="card p-5">
          <RouterLink to="/posteingang" class="mb-2 inline-block text-xs text-mute hover:text-ink lg:hidden">← Alle Anfragen</RouterLink>
          <div class="flex flex-wrap items-start gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <button type="button" class="wichtig !h-6 !w-6 !text-sm" :class="d.wichtig ? 'wichtig-an' : ''" :title="d.wichtig ? 'Wichtig – Kennzeichen entfernen' : 'Als wichtig kennzeichnen'" @click="mail.wichtigSetzen(d.id, !d.wichtig)">!</button>
                <span class="text-xs text-mute tnum">{{ d.id }}</span><StatusBadge :status="d.status" />
                <label class="inline-flex items-center gap-1 rounded-full border border-line bg-surface2 py-0.5 pl-2 pr-1 text-xs" title="Art der Mail (umsortieren)">
                  <component :is="artIcon(d.kategorie)" :size="12" class="text-mute" />
                  <select :value="d.kategorie" class="bg-transparent pr-1 outline-none" @change="mail.kategorieSetzen(d.id, $event.target.value)"><option v-for="a in ARTEN" :key="a.id" :value="a.id">{{ a.id }}</option></select>
                </label>
              </div>
              <h2 class="mt-1 text-xl font-semibold tracking-tight">{{ d.betreff || '(ohne Betreff)' }}</h2>
              <p class="mt-0.5 text-sm text-mute">{{ d.vonName }} <span class="tnum">&lt;{{ d.vonEmail }}&gt;</span> · {{ zeit(d.datum) }}</p>
            </div>
            <button v-if="d.kundeId && (d.kategorie || 'Anfrage') === 'Anfrage'" class="btn btn-primary !py-1.5 text-sm" :disabled="uebernimmt" @click="inWorkbench">
              <template v-if="d.angebotId"><ArrowRight :size="15" /> Angebot {{ d.angebotId }} öffnen</template>
              <template v-else><Calculator :size="15" /> {{ uebernimmt ? 'Wird übernommen …' : 'In Workbench übernehmen' }}</template>
            </button>
            <RouterLink v-if="d.auftragId" :to="`/auftraege/${d.auftragId}`" class="btn !py-1.5 text-sm"><ArrowRight :size="15" /> Auftrag {{ d.auftragId }}</RouterLink>
            <button v-if="d.kategorie !== 'Anfrage' && d.status !== 'Erledigt'" class="btn !py-1.5 text-sm" title="Erledigt: verschwindet aus „Offen“, der Inhalt bleibt" @click="naechsteNachErledigt"><CheckCircle2 :size="15" /> Erledigt</button>
            <button v-else-if="d.status === 'Erledigt'" class="btn !py-1.5 text-sm" @click="mail.erledigt(d.id, 0)"><RotateCcw :size="15" /> Wieder öffnen</button>
            <button v-if="!d.angebotId && !d.eingangsrechnungen?.length" class="btn !py-1.5 text-sm" :class="bestaetigen ? '!border-accent !text-accent' : '!text-mute'" :title="'Aus CNC One entfernen, im Postfach bleibt die Mail'" @click="verwerfen(false)" @blur="bestaetigen = false">
              <Ban :size="15" /> {{ bestaetigen ? 'Wirklich entfernen?' : d.kategorie === 'Anfrage' ? 'Keine Anfrage' : 'Entfernen' }}
            </button>
            <!-- mousedown.prevent: der erste Knopf behält den Fokus, sonst verschwindet dieser vor dem Klick -->
            <button v-if="bestaetigen && d.vonEmail" class="btn !border-accent !py-1.5 text-sm !text-accent" :title="`${d.vonEmail} kommt in den Mail-Einstellungen auf die Liste „Absender nie abholen“`" @mousedown.prevent @click="verwerfen(true)">
              <Ban :size="15" /> Entfernen und Absender sperren
            </button>
          </div>

          <div v-if="d.absenderWarnung" class="mt-4 flex items-start gap-2 rounded-xl border border-warn/40 bg-warn/10 px-3.5 py-2.5 text-sm">
            <ShieldAlert :size="16" class="mt-0.5 shrink-0 text-warn" />
            <div><strong>Absender nicht bestätigt.</strong> Die Prüfung des Postfachs ist fehlgeschlagen ({{ d.absenderPruefung }}); die Mail könnte gefälscht sein.
              Sie wurde deshalb keinem Kunden oder Lieferanten zugeordnet. Anhänge nur öffnen, wenn sie erwartet werden.</div>
          </div>
          <div v-if="d.eingangsrechnungen?.length" class="mt-4 flex flex-wrap items-center gap-2 rounded-xl bg-ok/10 px-3.5 py-2.5 text-sm">
            <Receipt :size="15" class="text-ok" /> Eingangsrechnung
            <RouterLink v-for="r in d.eingangsrechnungen" :key="r" :to="`/eingangsrechnungen/${r}`" class="font-medium text-accent hover:underline tnum">{{ r }}</RouterLink>
          </div>
          <div v-if="d.bestellung" />
          <!-- Lieferant -->
          <div v-if="d.lieferantId" class="mt-4 flex items-center gap-2 rounded-xl bg-surface2 px-3.5 py-2.5 text-sm">
            <Truck :size="15" class="text-accent" /> Lieferant <strong>{{ lieferantName(d.lieferantId) }}</strong>
            <span class="ml-auto text-xs text-mute">{{ d.vonEmail }}</span>
          </div>
          <div v-else-if="!istKunde && !d.kundeId" class="mt-4 rounded-2xl border border-warn/40 bg-warn/5 p-4">
            <div class="mb-3 flex items-center gap-2 text-sm font-medium"><Truck :size="16" class="text-warn" /> {{ d.vonEmail }} ist noch keinem Lieferanten zugeordnet</div>
            <div class="flex flex-wrap gap-2">
              <select v-model="lieferantWahl" class="field !w-72"><option value="" disabled>Lieferant wählen …</option><option v-for="l in lieferanten" :key="l.id" :value="l.id">{{ l.name }}</option></select>
              <button class="btn btn-primary !py-1.5" :disabled="!lieferantWahl" :class="!lieferantWahl ? 'pointer-events-none opacity-40' : ''" @click="mail.lieferantZuordnen(d.id, lieferantWahl)"><Check :size="15" /> Zuordnen · Adresse merken</button>
            </div>
            <p class="mt-2 text-xs text-mute">Die Adresse kommt zu den weiteren Adressen des Lieferanten; seine nächsten Mails und Rechnungen landen dann von selbst hier.</p>
          </div>
          <!-- Kunde und Kontakt -->
          <div v-if="!istKunde" />
          <div v-else-if="d.kundeId" class="mt-4 flex items-center gap-2 rounded-xl bg-surface2 px-3.5 py-2.5 text-sm">
            <Building2 :size="15" class="text-accent" /> Kunde <strong>{{ d.kundeName }}</strong> <span class="text-xs text-mute tnum">{{ d.kundeId }}</span>
            <span class="ml-auto text-xs text-mute">{{ d.vonEmail }} ist dort als Kontakt hinterlegt</span>
          </div>
          <div v-else class="mt-4 rounded-2xl border border-warn/40 bg-warn/5 p-4">
            <div class="mb-3 flex items-center gap-2 text-sm font-medium"><UserPlus :size="16" class="text-warn" /> {{ d.vonEmail }} ist noch bei keinem Kunden als Kontakt hinterlegt</div>
            <div class="mb-3 flex gap-1 rounded-xl border border-line bg-surface p-1 text-sm sm:w-fit">
              <button class="rounded-lg px-3 py-1" :class="art === 'bestehend' ? 'bg-accent-soft text-accent' : 'text-mute'" @click="art = 'bestehend'">Bestehender Kunde</button>
              <button class="rounded-lg px-3 py-1" :class="art === 'neu' ? 'bg-accent-soft text-accent' : 'text-mute'" @click="art = 'neu'">Neuer Kunde</button>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <div v-if="art === 'bestehend'" class="sm:col-span-2">
                <CustomerCombobox v-model="kunde" />
                <p v-if="d.kundeVorschlag && kunde === d.kundeVorschlag.id" class="mt-1 text-xs text-mute">Vorschlag: gleiche Domain wie ein Kontakt von {{ d.kundeVorschlag.name }}</p>
              </div>
              <label v-else class="block sm:col-span-2"><span class="label mb-1 block">Name des neuen Kunden</span><input v-model="neuerKunde" class="field" placeholder="z. B. Muster GmbH" /></label>
              <div class="grid grid-cols-[100px_1fr_1fr] gap-3 sm:col-span-2">
                <label class="block"><span class="label mb-1 block">Anrede</span><select v-model="kontakt.anrede" class="field"><option value="">–</option><option>Herr</option><option>Frau</option></select></label>
                <label class="block"><span class="label mb-1 block">Vorname</span><input v-model="kontakt.vorname" class="field" /></label>
                <label class="block"><span class="label mb-1 block">Nachname</span><input v-model="kontakt.nachname" class="field" /></label>
              </div>
            </div>
            <button class="btn btn-primary mt-3 !py-1.5" :disabled="!kannZuordnen || ordnet" :class="!kannZuordnen ? 'pointer-events-none opacity-40' : ''" @click="zuordnen">
              <Check :size="15" /> {{ art === 'neu' ? 'Kunden anlegen und zuordnen' : 'Zuordnen' }} · Kontakt {{ d.vonEmail }} anlegen
            </button>
          </div>
        </section>

        <!-- Nachrichten im Verlauf -->
        <section v-for="(n, i) in d.nachrichten" :key="i" class="card p-5" :class="n.richtung === 'Ausgang' ? 'border-accent/30' : ''">
          <div class="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
            <Reply v-if="n.richtung === 'Ausgang'" :size="14" class="self-center text-accent" />
            <span class="font-medium">{{ n.vonName || n.vonEmail }}</span>
            <span class="text-xs text-mute">an {{ n.an }}<template v-if="n.cc"> · CC {{ n.cc }}</template></span>
            <span class="ml-auto text-xs text-mute tnum">{{ zeit(n.datum) }}</span>
          </div>
          <p v-if="i > 0 && n.betreff !== d.betreff" class="mb-2 text-xs text-mute">Betreff: {{ n.betreff }}</p>
          <!-- Text links, Anhänge rechts: je Bauteil Zeichnung und 3D-Modell nebeneinander, darunter die übrigen Dateien -->
          <div class="grid gap-5" :class="n.anhaenge.length || n.hinweis ? 'lg:grid-cols-[minmax(0,1fr)_300px]' : ''">
            <div class="min-w-0">
              <template v-if="n.html && !alsText[i]">
                <MailHtml :html="n.html" />
                <button class="mt-1 text-[11px] text-mute hover:text-ink" @click="alsText[i] = true">Als Text anzeigen</button>
              </template>
              <template v-else>
                <div class="max-h-[520px] overflow-auto whitespace-pre-wrap break-words text-sm leading-relaxed">{{ n.text || '(kein Text)' }}</div>
                <button v-if="n.html" class="mt-1 text-[11px] text-mute hover:text-ink" @click="alsText[i] = false">Wie im Mailprogramm anzeigen</button>
              </template>
            </div>

            <aside v-if="n.anhaenge.length || n.hinweis" class="space-y-3 lg:border-l lg:border-line lg:pl-5">
              <template v-for="ag in [anhangGruppen(n)]" :key="'ag'">
                <div v-if="ag.gruppen.length">
                  <div class="mb-1.5 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-mute">
                    <span class="inline-flex items-center gap-1"><Paperclip :size="12" /> Bauteile</span>
                    <span class="normal-case tracking-normal">{{ ag.gruppen.filter((g) => g.pdf && g.step).length }}/{{ ag.gruppen.length }} vollständig</span>
                  </div>
                  <div class="space-y-1.5">
                    <div v-for="g in ag.gruppen" :key="g.schluessel + (g.pdf?.url || g.step?.url)" class="rounded-xl bg-surface2/70 p-1.5">
                      <div class="truncate px-1 pb-1 text-xs font-medium" :title="g.name">{{ g.name }}</div>
                      <div class="grid grid-cols-2 gap-1.5">
                        <template v-for="(x, art) in { pdf: g.pdf, step: g.step }" :key="art">
                          <button v-if="x" type="button" class="kachel" :class="vorschau?.url === x.url ? 'kachel-aktiv' : ''" :title="x.aus ? `${x.name}\naus ${x.aus}` : x.name" @click="vorschau = vorschau?.url === x.url ? null : x">
                            <component :is="art === 'pdf' ? FileText : Box" :size="15" class="shrink-0" />
                            <span class="min-w-0"><span class="block text-[11px] font-semibold">{{ art === 'pdf' ? 'Zeichnung' : '3D-Modell' }}</span><span class="block truncate text-[10px] opacity-70 tnum">{{ groesse(x.groesse) }}{{ x.aus ? ' · ZIP' : '' }}</span></span>
                          </button>
                          <div v-else class="kachel kachel-fehlt" :title="art === 'pdf' ? 'Keine Zeichnung zu diesem Bauteil' : 'Kein 3D-Modell zu diesem Bauteil'">
                            <component :is="art === 'pdf' ? FileText : Box" :size="15" class="shrink-0" />
                            <span class="text-[11px]">{{ art === 'pdf' ? 'Zeichnung fehlt' : '3D fehlt' }}</span>
                          </div>
                        </template>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="ag.sonstige.length">
                  <div class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-mute">Weitere Dateien</div>
                  <div class="flex flex-col gap-1.5">
                    <a v-for="a in ag.sonstige" :key="a.url" :href="a.url" target="_blank" rel="noopener" class="datei !max-w-none" :title="a.aus ? `${a.name}\naus ${a.aus}` : a.name">
                      <component :is="ICON[a.art]" :size="14" class="shrink-0" /><span class="min-w-0 flex-1 truncate">{{ a.name }}</span><span class="text-[10px] opacity-70 tnum">{{ groesse(a.groesse) }}</span>
                    </a>
                  </div>
                </div>
              </template>
              <div v-if="n.richtung === 'Eingang' && ['Bestellung', 'Rechnung', 'Lieferant'].includes(d.kategorie) && n.anhaenge.some((a) => !a.aus && pdfOderXml(a))" class="flex flex-col gap-1.5">
                <template v-for="a in n.anhaenge.filter((x) => !x.aus && pdfOderXml(x))" :key="`akt-${a.url}`">
                  <button v-if="d.kategorie === 'Bestellung' && /\.pdf$/i.test(a.name) && !d.auftragId" class="btn justify-start !py-1 text-xs" :disabled="!d.kundeId" :title="d.kundeId ? 'Bestellung einlesen, mit dem Angebot abgleichen und als Auftrag anlegen' : 'Bitte zuerst den Kunden zuordnen'" @click="bestellungOeffnen(a)"><ShoppingCart :size="13" /> <span class="truncate">Auftrag aus {{ a.name }}</span></button>
                  <button v-if="d.kategorie !== 'Bestellung'" class="btn justify-start !py-1 text-xs" title="Als Eingangsrechnung übernehmen (E-Rechnung wird gelesen, PDF zum Ausfüllen)" @click="alsRechnung(a)"><component :is="/\.xml$/i.test(a.name) ? FileCode2 : Receipt" :size="13" /> <span class="truncate">Rechnung aus {{ a.name }}</span></button>
                </template>
              </div>
              <p v-if="n.hinweis" class="flex items-start gap-1.5 whitespace-pre-line text-xs text-warn"><MailWarning :size="13" class="mt-0.5 shrink-0" /> {{ n.hinweis }}</p>
            </aside>
          </div>
          <!-- Vorschau über die volle Breite -->
          <div v-if="vorschau && n.anhaenge.some((a) => a.url === vorschau.url)" class="mt-4 h-[560px]">
            <DrawingViewer v-if="vorschau.art === 'Zeichnung'" :key="vorschau.url" :url="vorschau.url" :name="vorschau.name" />
            <ModelViewer v-else :key="vorschau.url" :url="vorschau.url" :name="vorschau.name" nur-ansehen />
          </div>
        </section>
      </div>
      <div v-else class="card hidden flex-col items-center justify-center p-14 text-sm text-mute lg:flex"><Inbox :size="30" :stroke-width="1.4" class="mb-2" /> Mail links auswählen</div>
    </div>
  </div>
</template>

<style scoped>
.register { display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 0.75rem; border: 1px solid var(--line); background: var(--surface); padding: 0.35rem 0.75rem; font-size: 0.8125rem; color: var(--mute); transition: all 0.15s; }
.register:hover { color: var(--ink); }
.register-aktiv { border-color: color-mix(in srgb, var(--accent) 45%, transparent); background: var(--accent-soft); color: var(--accent); font-weight: 500; }
.datei { display: inline-flex; max-width: 18rem; align-items: center; gap: 0.4rem; border-radius: 0.6rem; background: var(--surface-2); padding: 0.3rem 0.6rem; font-size: 0.75rem; color: var(--ink); transition: background 0.15s; }
.datei:hover { background: color-mix(in srgb, var(--accent) 10%, var(--surface-2)); }
.datei-aktiv { background: var(--accent-soft); color: var(--accent); }
.wichtig { display: grid; height: 1.15rem; width: 1.15rem; flex: none; place-items: center; border-radius: 9999px; font-size: 0.75rem; font-weight: 800; line-height: 1; color: color-mix(in srgb, var(--mute) 55%, transparent); border: 1px solid color-mix(in srgb, var(--mute) 30%, transparent); transition: all 0.15s; }
.wichtig:hover { color: #dc2626; background: color-mix(in srgb, #dc2626 10%, transparent); }
.wichtig-an { background: #dc2626; border-color: #dc2626; color: #fff; }
.wichtig-an:hover { background: #b91c1c; color: #fff; }
.kachel { display: flex; min-width: 0; align-items: center; gap: 0.4rem; border-radius: 0.55rem; border: 1px solid var(--line); background: var(--surface); padding: 0.35rem 0.5rem; text-align: left; color: var(--ink); transition: all 0.15s; }
button.kachel:hover { border-color: color-mix(in srgb, var(--accent) 45%, transparent); color: var(--accent); }
.kachel-aktiv { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
.kachel-fehlt { border-style: dashed; background: transparent; color: var(--mute); opacity: 0.8; }
</style>
