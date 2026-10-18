<script setup>
import { computed, reactive, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, Mail, Copy, Save, XCircle, FileText } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import NumField from '../components/NumField.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';
import { useBelege } from '../stores/belege.js';
import { mailText } from '../lib/anfrage.js';

const route = useRoute();
const store = useAnfragen();
const ui = useUi();
const belege = useBelege();
const a = computed(() => store.anfrage(route.params.id));
const mail = computed(() => (a.value ? mailText(a.value) : null));

// Formular für das Angebot des Lieferanten: je Position eine Zeile pro angefragter Menge
const form = reactive({ angebotsnr: '', gueltigBis: '', preise: [] });
watch(a, (x) => {
  if (!x) return;
  form.angebotsnr = x.antwort?.angebotsnr ?? '';
  form.gueltigBis = x.antwort?.gueltigBis ?? '';
  form.preise = x.positionen.flatMap((p) => p.mengen.map((m) => {
    const alt = x.antwort?.preise.find((q) => q.posKey === p.key && q.menge === m);
    return { posKey: p.key, menge: m, proStk: alt?.proStk ?? 0, einmalig: alt?.einmalig ?? 0 };
  }));
}, { immediate: true });
const zeilenFuer = (key) => form.preise.filter((p) => p.posKey === key);

const mailto = computed(() => (mail.value ? `mailto:?subject=${encodeURIComponent(mail.value.betreff)}&body=${encodeURIComponent(mail.value.text)}` : '#'));
async function kopieren() {
  try { await navigator.clipboard.writeText(`${mail.value.betreff}\n\n${mail.value.text}`); ui.toast('Anschreiben kopiert', 'ok'); } catch { ui.toast('Kopieren nicht möglich', 'warn'); }
}
function speichern() {
  if (!form.preise.some((p) => p.proStk > 0 || p.einmalig > 0)) { ui.toast('Bitte mindestens einen Preis eintragen', 'warn'); return; }
  store.antwortErfassen(a.value.id, { angebotsnr: form.angebotsnr, gueltigBis: form.gueltigBis, preise: form.preise.map((p) => ({ ...p })) });
}
const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
</script>

<template>
  <div v-if="a" class="mx-auto max-w-[1200px] space-y-4">
    <RouterLink to="/anfragen" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Anfragen</RouterLink>

    <section class="card p-6">
      <div class="flex flex-wrap items-start gap-5">
        <div class="flex -space-x-3">
          <PartImage v-for="p in a.positionen.slice(0, 3)" :key="p.key" :teil="p.teil" :groesse="64" class="ring-2 ring-surface" />
        </div>
        <div class="min-w-[240px] flex-1">
          <div class="flex items-center gap-3"><h2 class="text-xl font-semibold tnum">{{ a.id }}</h2><StatusBadge :status="a.status" /></div>
          <p class="mt-1 text-sm">an {{ a.lieferantName }} · {{ a.positionen.length }} Position{{ a.positionen.length === 1 ? '' : 'en' }}</p>
          <p class="text-sm text-mute">angelegt am {{ de(a.erstellt) }}</p>
          <p class="mt-2 text-sm">
            <RouterLink :to="`/angebote/${a.angebotId}`" class="inline-flex items-center gap-1.5 rounded-full bg-surface2 px-3 py-1 text-accent hover:underline"><FileText :size="13" /> Zum Angebot <span class="tnum">{{ a.angebotId }}</span><span v-if="a.kundeName || belege.angebot(a.angebotId)" class="text-mute"> · {{ a.kundeName || belege.angebot(a.angebotId)?.kopf.kundeName }}</span></RouterLink>
          </p>
          <p v-if="a.notiz" class="mt-2 rounded-lg bg-surface2 px-3 py-2 text-sm">Hinweis: {{ a.notiz }}</p>
        </div>
        <div class="rounded-2xl bg-accent-soft px-5 py-3 text-center">
          <div class="label !text-accent">Unsere Anfragenummer</div>
          <div class="mt-0.5 text-lg font-semibold text-accent tnum">{{ a.id }}</div>
          <div class="text-[11px] text-mute">der Lieferant nennt sie im Angebot</div>
        </div>
      </div>
    </section>

    <div class="grid items-start gap-4 lg:grid-cols-2">
      <section class="card p-5">
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><Mail :size="16" class="text-accent" /> Anschreiben</h3>
        <div class="rounded-xl border border-line bg-surface2 p-4 text-[13px] leading-relaxed">
          <div class="mb-2 font-medium">{{ mail.betreff }}</div>
          <pre class="whitespace-pre-wrap font-sans text-mute">{{ mail.text }}</pre>
        </div>
        <div class="mt-3 flex gap-2">
          <a :href="mailto" class="btn btn-primary"><Mail :size="15" /> In Mailprogramm öffnen</a>
          <button class="btn" @click="kopieren"><Copy :size="15" /> Kopieren</button>
        </div>
        <p class="mt-2 text-xs text-mute">Später verschickt Frappe die Mail direkt mit Zeichnungen und Modellen im Anhang.</p>
      </section>

      <section class="card p-5">
        <h3 class="mb-3 text-sm font-semibold">Angebot des Lieferanten</h3>
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="label mb-1 block">Angebotsnummer des Lieferanten</span><input v-model="form.angebotsnr" class="field" placeholder="z. B. AN-5521" /></label>
          <label class="block"><span class="label mb-1 block">Gültig bis</span><input v-model="form.gueltigBis" type="date" class="field" /></label>
        </div>

        <div class="mt-4 space-y-4">
          <div v-for="p in a.positionen" :key="p.key" class="rounded-xl border border-line p-3">
            <div class="mb-3 flex items-center gap-3">
              <PartImage :teil="p.teil" :groesse="38" />
              <div class="min-w-0"><div class="truncate text-sm font-medium">{{ p.agName || 'Fremdvergabe' }}</div><div class="truncate text-xs text-mute">{{ p.teil.name }}<template v-if="p.teil.teilenummer"> · {{ p.teil.teilenummer }}</template></div></div>
            </div>
            <div class="grid grid-cols-[64px_1fr_1fr] gap-2 pb-1 text-xs"><span class="label">Menge</span><span class="label">Preis je Stück</span><span class="label">Einmalig</span></div>
            <div class="space-y-2">
              <div v-for="z in zeilenFuer(p.key)" :key="z.menge" class="grid grid-cols-[64px_1fr_1fr] items-center gap-2">
                <span class="text-sm font-semibold tnum">{{ z.menge }} Stk</span>
                <NumField v-model="z.proStk" unit="€" />
                <NumField v-model="z.einmalig" unit="€" />
              </div>
            </div>
          </div>
        </div>

        <div class="mt-4 flex gap-2">
          <button class="btn btn-primary" @click="speichern"><Save :size="15" /> {{ a.antwort ? 'Angebot aktualisieren' : 'Angebot erfassen' }}</button>
          <button v-if="a.status === 'Gesendet'" class="btn !text-mute" @click="store.absagen(a.id)"><XCircle :size="15" /> Als abgesagt markieren</button>
        </div>
        <p v-if="a.antwort" class="mt-3 text-xs text-mute">Der Preis lässt sich jetzt in der Workbench am jeweiligen Arbeitsgang mit „Preis übernehmen“ in die Kalkulation holen.</p>
      </section>
    </div>
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Anfrage nicht gefunden</p>
    <RouterLink to="/anfragen" class="btn mt-4">Zur Übersicht</RouterLink>
  </div>
</template>
