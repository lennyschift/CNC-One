<script setup>
// Posteingang: Anfragen aus dem gemeinsamen Postfach (nur Mails mit Stichwort im Betreff). Links die Liste, rechts die Mail
// mit Anhängen und der Zuordnung zu Kunde und Kontakt.
import { ref, computed, watch, onMounted, defineAsyncComponent } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Inbox, RefreshCw, Paperclip, FileText, Box, Table2, File, Building2, UserPlus, Check, Ban, Reply, Settings, MailWarning } from '@lucide/vue';
import StatusBadge from '../components/StatusBadge.vue';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import { useMail } from '../stores/mail.js';
import { benutzer } from '../data/repo.js';
import { zahl } from '../lib/format.js';

const DrawingViewer = defineAsyncComponent(() => import('../components/DrawingViewer.vue'));
const ModelViewer = defineAsyncComponent(() => import('../components/ModelViewer.vue'));

const route = useRoute();
const router = useRouter();
const mail = useMail();
const istAdmin = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'System Manager'].includes(x)));

const filter = ref('offen');
const FILTER = [
  { id: 'offen', label: 'Offen', passt: (x) => ['Neu', 'In Bearbeitung'].includes(x.status) || x.neueAntwort },
  { id: 'beantwortet', label: 'Beantwortet', passt: (x) => x.status === 'Beantwortet' },
  { id: 'alle', label: 'Alle', passt: () => true },
];
const zeilen = computed(() => mail.liste.filter(FILTER.find((f) => f.id === filter.value).passt));
const zaehler = (id) => mail.liste.filter(FILTER.find((f) => f.id === id).passt).length;

const id = computed(() => route.params.id || '');
const d = computed(() => (id.value ? mail.details[id.value] : null));
onMounted(async () => {
  await mail.laden();
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

// ---- Keine Anfrage (mit Rückfrage im Knopf)
const bestaetigen = ref(false);
async function verwerfen() {
  if (!bestaetigen.value) { bestaetigen.value = true; return; }
  const naechste = zeilen.value[zeilen.value.findIndex((x) => x.id === d.value.id) + 1]?.id;
  if (await mail.keineAnfrage(d.value.id)) router.replace(naechste ? `/posteingang/${naechste}` : '/posteingang');
}

// ---- Anhänge
const vorschau = ref(null);
const ICON = { Zeichnung: FileText, STEP: Box, Tabelle: Table2, Datei: File };
const groesse = (b) => (!b ? '' : b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);
const ansehbar = (a) => a.art === 'Zeichnung' || a.art === 'STEP';
// Beim Wechsel der Anfrage: laden, Vorschau und Rückfrage zurücksetzen
watch(id, (neu) => { if (neu) mail.detail(neu); vorschau.value = null; bestaetigen.value = false; }, { immediate: true });
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const kurzZeit = (iso) => {
  if (!iso) return '';
  const t = new Date(iso);
  return t.toDateString() === new Date().toDateString() ? t.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : t.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
};
</script>

<template>
  <div class="mx-auto max-w-[1500px]">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1">
        <button v-for="f in FILTER" :key="f.id" class="rounded-lg px-3 py-1.5 text-sm transition" :class="filter === f.id ? 'bg-surface text-ink shadow-sm' : 'text-mute hover:text-ink'" @click="filter = f.id">
          {{ f.label }} <span class="ml-1 text-xs text-mute tnum">{{ zaehler(f.id) }}</span>
        </button>
      </div>
      <RouterLink v-if="istAdmin" to="/stammdaten/mail" class="ml-auto inline-flex items-center gap-1.5 text-xs text-mute hover:text-ink"><Settings :size="14" /> Mail-Anbindung</RouterLink>
      <button class="btn" :class="istAdmin ? '' : 'ml-auto'" :disabled="mail.ruft" @click="mail.abrufen()"><RefreshCw :size="15" :class="mail.ruft ? 'animate-spin' : ''" /> Jetzt abrufen</button>
    </div>

    <div class="grid items-start gap-4 lg:grid-cols-[380px_1fr]">
      <!-- Liste -->
      <section class="card overflow-hidden" :class="id ? 'hidden lg:block' : ''">
        <div v-if="!mail.geladen" class="p-6 text-sm text-mute">Wird geladen …</div>
        <div v-else-if="!zeilen.length" class="flex flex-col items-center px-6 py-14 text-center text-sm text-mute">
          <Inbox :size="34" :stroke-width="1.4" class="mb-3" />
          <span class="font-medium text-ink">Keine Anfragen</span>
          <span class="mt-1 text-xs">Geholt werden Mails aus dem Postfach mit einem Stichwort im Betreff, z. B. „Anfrage“.</span>
        </div>
        <div v-auto-animate class="divide-y divide-line">
          <RouterLink v-for="x in zeilen" :key="x.id" :to="`/posteingang/${x.id}`" class="block px-4 py-3 transition hover:bg-surface2" :class="x.id === id ? 'bg-accent-soft/60' : ''">
            <div class="flex items-center gap-2">
              <span v-if="x.status === 'Neu' || x.neueAntwort" class="h-2 w-2 shrink-0 rounded-full bg-accent" />
              <span class="min-w-0 flex-1 truncate text-sm" :class="x.status === 'Neu' ? 'font-semibold' : 'font-medium'">{{ x.vonName || x.vonEmail }}</span>
              <span class="shrink-0 text-xs text-mute tnum">{{ kurzZeit(x.letzteNachricht) }}</span>
            </div>
            <div class="mt-0.5 truncate text-sm">{{ x.betreff || '(ohne Betreff)' }}</div>
            <div class="mt-1 flex items-center gap-2 text-xs text-mute">
              <span v-if="x.kundeName" class="inline-flex items-center gap-1 truncate"><Building2 :size="12" /> {{ x.kundeName }}</span>
              <span v-else class="text-warn">Kunde zuordnen</span>
              <span v-if="x.neueAntwort" class="text-accent">neue Antwort</span>
              <StatusBadge v-if="x.status !== 'Neu'" :status="x.status" class="ml-auto" />
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- Mail -->
      <div v-if="id && !d" class="card p-6 text-sm text-mute">Wird geladen …</div>
      <div v-else-if="d" class="space-y-4">
        <section class="card p-5">
          <RouterLink to="/posteingang" class="mb-2 inline-block text-xs text-mute hover:text-ink lg:hidden">← Alle Anfragen</RouterLink>
          <div class="flex flex-wrap items-start gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2"><span class="text-xs text-mute tnum">{{ d.id }}</span><StatusBadge :status="d.status" /></div>
              <h2 class="mt-1 text-xl font-semibold tracking-tight">{{ d.betreff || '(ohne Betreff)' }}</h2>
              <p class="mt-0.5 text-sm text-mute">{{ d.vonName }} <span class="tnum">&lt;{{ d.vonEmail }}&gt;</span> · {{ zeit(d.datum) }}</p>
            </div>
            <button class="btn !py-1.5 text-sm" :class="bestaetigen ? '!border-accent !text-accent' : '!text-mute'" :title="'Aus CNC One entfernen, im Postfach bleibt die Mail'" @click="verwerfen" @blur="bestaetigen = false">
              <Ban :size="15" /> {{ bestaetigen ? 'Wirklich entfernen?' : 'Keine Anfrage' }}
            </button>
          </div>

          <!-- Kunde und Kontakt -->
          <div v-if="d.kundeId" class="mt-4 flex items-center gap-2 rounded-xl bg-surface2 px-3.5 py-2.5 text-sm">
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
          <div class="max-h-[420px] overflow-auto whitespace-pre-wrap break-words text-sm leading-relaxed">{{ n.text || '(kein Text)' }}</div>
          <div v-if="n.anhaenge.length" class="mt-4 flex flex-wrap gap-2 border-t border-line pt-3">
            <span class="mr-1 inline-flex items-center gap-1 text-xs text-mute"><Paperclip :size="13" /> {{ n.anhaenge.length }}</span>
            <component
              :is="ansehbar(a) ? 'button' : 'a'" v-for="a in n.anhaenge" :key="a.url" :href="ansehbar(a) ? undefined : a.url" :target="ansehbar(a) ? undefined : '_blank'"
              class="datei" :class="vorschau?.url === a.url ? 'datei-aktiv' : ''" @click="ansehbar(a) && (vorschau = vorschau?.url === a.url ? null : a)"
            >
              <component :is="ICON[a.art]" :size="14" class="shrink-0" /><span class="truncate">{{ a.name }}</span><span class="text-[10px] opacity-70 tnum">{{ groesse(a.groesse) }}</span>
            </component>
          </div>
          <p v-if="n.hinweis" class="mt-2 flex items-start gap-1.5 text-xs text-warn"><MailWarning :size="13" class="mt-0.5 shrink-0" /> {{ n.hinweis }}</p>
          <div v-if="vorschau && n.anhaenge.some((a) => a.url === vorschau.url)" class="mt-3 h-[520px]">
            <DrawingViewer v-if="vorschau.art === 'Zeichnung'" :key="vorschau.url" :url="vorschau.url" :name="vorschau.name" />
            <ModelViewer v-else :key="vorschau.url" :url="vorschau.url" :name="vorschau.name" nur-ansehen />
          </div>
        </section>
      </div>
      <div v-else class="card hidden flex-col items-center justify-center p-14 text-sm text-mute lg:flex"><Inbox :size="30" :stroke-width="1.4" class="mb-2" /> Anfrage links auswählen</div>
    </div>
  </div>
</template>

<style scoped>
.datei { display: inline-flex; max-width: 18rem; align-items: center; gap: 0.4rem; border-radius: 0.6rem; background: var(--surface-2); padding: 0.3rem 0.6rem; font-size: 0.75rem; color: var(--ink); transition: background 0.15s; }
.datei:hover { background: color-mix(in srgb, var(--accent) 10%, var(--surface-2)); }
.datei-aktiv { background: var(--accent-soft); color: var(--accent); }
</style>
