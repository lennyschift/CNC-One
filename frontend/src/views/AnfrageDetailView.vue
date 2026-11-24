<script setup>
import { computed, reactive, ref, watch, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft, Mail, Copy, Save, XCircle, FileText, Send, Scale, Award, Inbox, Paperclip, ChevronDown, ScanText, CheckCircle2, AlertTriangle, CircleHelp } from '@lucide/vue';
import AnfrageMailDialog from '../components/AnfrageMailDialog.vue';
import LieferangebotDialog from '../components/LieferangebotDialog.vue';
import { abgleich } from '../lib/lieferangebot.js';
import { eur, zahl } from '../lib/format.js';
import MailHtml from '../components/MailHtml.vue';
import BelegLink from '../components/BelegLink.vue';
import ZuschlagDialog from '../components/ZuschlagDialog.vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import NumField from '../components/NumField.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';
import { useBelege } from '../stores/belege.js';
import { mailText, istFrei } from '../lib/anfrage.js';

const route = useRoute();
const store = useAnfragen();
const ui = useUi();
const belege = useBelege();
const a = computed(() => store.anfrage(route.params.id));
const mail = computed(() => (a.value ? mailText(a.value) : null));
const frei = computed(() => (a.value ? istFrei(a.value) : false));
const router = useRouter();
// Alle Anfragen, die mit dieser zusammen verschickt wurden (Vergleich)
const imVorgang = computed(() => (a.value ? store.vorgang(a.value.vorgang) : []));
const mailDialog = ref(false);
const zuschlagOffen = ref(false);
// Angebot aus PDF einlesen (aus dem Posteingang direkt mit ?einlesen=1)
const einlesen = ref(false);
const vonPosteingang = computed(() => route.query.von === 'posteingang');
onMounted(() => {
  if (route.query.senden) { mailDialog.value = true; router.replace({ query: {} }); }
});
// auch beim Wechsel von einer Anfrage zur nächsten (die Seite bleibt dieselbe)
watch(() => [route.params.id, route.query.einlesen], ([, e]) => {
  if (e) { einlesen.value = true; router.replace({ query: { ...route.query, einlesen: undefined } }); }
}, { immediate: true });
// PDFs in den Mails des Lieferanten
const pdfAnzahl = computed(() => (a.value?.nachrichten ?? []).filter((n) => n.richtung === 'Eingang').flatMap((n) => n.anhaenge).filter((x) => /\.pdf$/i.test(x.name)).length);
// Abgleich: je Position unserer Anfrage, was der Lieferant angeboten hat (aus dem eingelesenen PDF)
const daten = computed(() => a.value?.antwort?.daten ?? null);
const abgleichZeilen = computed(() => (daten.value ? a.value.positionen.map((p, i) => {
  const os = (daten.value.positionen ?? []).filter((o) => o.zuordnung === p.key);
  return { p, nr: i + 1, os, je: daten.value.je?.[p.key] ?? null, pruefung: os.flatMap((o) => abgleich(o, p)) };
}) : []));
const optionen = computed(() => (daten.value?.positionen ?? []).filter((o) => !o.zuordnung));
const mengenText = (o) => [o.stueck != null && `${zahl(o.stueck, 0)} Stk`, o.kg != null && `${zahl(o.kg, 2)} kg`, o.meter != null && `${zahl(o.meter, 3)} m`].filter(Boolean).join(' · ');
watch(() => a.value?.neueAntwort, (neu) => { if (neu) store.gelesen(a.value.id); }, { immediate: true });
const offen = ref({});
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const groesse = (b) => (!b ? '' : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);

// Formular für das Angebot des Lieferanten: je Position eine Zeile pro angefragter Menge
const form = reactive({ angebotsnr: '', gueltigBis: '', lieferzeit: '', nebenkosten: 0, nebenkostenText: '', preise: [] });
watch(a, (x) => {
  if (!x) return;
  form.angebotsnr = x.antwort?.angebotsnr ?? '';
  form.nebenkosten = x.antwort?.nebenkosten ?? 0;
  form.nebenkostenText = x.antwort?.nebenkostenText ?? '';
  form.lieferzeit = x.antwort?.lieferzeit ?? '';
  form.gueltigBis = x.antwort?.gueltigBis ?? '';
  form.preise = x.positionen.flatMap((p) => p.mengen.map((m) => {
    const alt = x.antwort?.preise.find((q) => q.posKey === p.key && q.menge === m);
    return { posKey: p.key, menge: m, proStk: alt?.proStk ?? 0, einmalig: alt?.einmalig ?? 0 };
  }));
}, { immediate: true });
const zeilenFuer = (key) => form.preise.filter((p) => p.posKey === key);

async function kopieren() {
  try { await navigator.clipboard.writeText(`${mail.value.betreff}\n\n${mail.value.text}`); ui.toast('Anschreiben kopiert', 'ok'); } catch { ui.toast('Kopieren nicht möglich', 'warn'); }
}
function speichern() {
  if (!form.preise.some((p) => p.proStk > 0 || p.einmalig > 0)) { ui.toast('Bitte mindestens einen Preis eintragen', 'warn'); return; }
  store.antwortErfassen(a.value.id, { angebotsnr: form.angebotsnr, gueltigBis: form.gueltigBis, lieferzeit: form.lieferzeit, nebenkosten: form.nebenkosten, nebenkostenText: form.nebenkostenText, preise: form.preise.map((p) => ({ ...p })) });
}
const de = (iso) => new Date(iso).toLocaleDateString('de-DE');
</script>

<template>
  <div v-if="a" class="mx-auto max-w-[1200px] space-y-4">
    <div class="flex flex-wrap items-center gap-4">
      <RouterLink v-if="vonPosteingang" to="/posteingang" class="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"><ArrowLeft :size="15" /> Zurück zum Posteingang</RouterLink>
      <RouterLink to="/anfragen" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft v-if="!vonPosteingang" :size="15" /> Alle Anfragen</RouterLink>
    </div>

    <section class="card p-6">
      <div class="flex flex-wrap items-start gap-5">
        <div class="flex -space-x-3">
          <PartImage v-for="p in a.positionen.slice(0, 3)" :key="p.key" :teil="p.teil" :groesse="64" class="ring-2 ring-surface" />
        </div>
        <div class="min-w-[240px] flex-1">
          <div class="flex items-center gap-3"><h2 class="text-xl font-semibold tnum">{{ a.id }}</h2><StatusBadge :status="a.status" /></div>
          <p class="mt-1 text-sm">an {{ a.lieferantName }} · {{ a.positionen.length }} Position{{ a.positionen.length === 1 ? '' : 'en' }}</p>
          <p class="text-sm text-mute">angelegt am {{ de(a.erstellt) }}</p>
          <p v-if="!a.angebotId" class="mt-2 text-sm"><span class="rounded-full bg-surface2 px-3 py-1 text-mute">Freie Anfrage · {{ a.art }}</span></p>
          <p v-else class="mt-2 text-sm">
            <RouterLink :to="`/angebote/${a.angebotId}`" class="inline-flex items-center gap-1.5 rounded-full bg-surface2 px-3 py-1 text-accent hover:underline"><FileText :size="13" /> Zum Angebot <span class="tnum">{{ a.angebotId }}</span><span v-if="a.kundeName || belege.angebot(a.angebotId)" class="text-mute"> · {{ a.kundeName || belege.angebot(a.angebotId)?.kopf.kundeName }}</span></RouterLink>
          </p>
          <p v-if="a.notiz" class="mt-2 rounded-lg bg-surface2 px-3 py-2 text-sm">Hinweis: {{ a.notiz }}</p>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <button class="btn" :class="a.versendetAm ? '' : 'btn-primary'" @click="mailDialog = true"><Send :size="15" /> {{ a.versendetAm ? 'Erneut per Mail senden' : 'Per Mail senden' }}</button>
            <button class="btn" :class="pdfAnzahl && !a.antwort?.daten ? 'btn-primary' : ''" @click="einlesen = true"><ScanText :size="15" /> Angebot aus PDF einlesen<span v-if="pdfAnzahl" class="opacity-70"> ({{ pdfAnzahl }} PDF)</span></button>
            <RouterLink :to="{ path: `/anfragen/vergleich/${a.vorgang}`, query: vonPosteingang ? { von: 'posteingang' } : {} }" class="btn"><Scale :size="15" /> Angebote vergleichen<span v-if="imVorgang.length > 1" class="text-mute"> ({{ imVorgang.length }} Lieferanten)</span></RouterLink>
            <button v-if="a.antwort" class="btn" :class="a.zuschlag ? '!border-ok !text-ok' : ''" @click="zuschlagOffen = true"><Award :size="15" /> {{ a.zuschlag ? (a.zuschlagPositionen?.length >= a.positionen.length && !a.zuschlagAlternativen?.length ? 'Zuschlag erteilt' : `Zuschlag: ${a.zuschlagPositionen?.length ?? 0} von ${a.positionen.length}`) : 'Zuschlag erteilen' }}</button>
            <ZuschlagDialog v-if="zuschlagOffen" :anfrage="a" :andere="imVorgang" @schliessen="zuschlagOffen = false" />
            <span v-if="a.versendetAm" class="text-xs text-mute">per Mail verschickt am {{ zeit(a.versendetAm) }}</span>
          </div>
          <p v-if="imVorgang.length > 1" class="mt-2 text-xs text-mute">Zusammen verschickt (Vorgang {{ a.vorgang }}) mit:
            <template v-for="(x, i) in imVorgang.filter((y) => y.id !== a.id)" :key="x.id"><span v-if="i">, </span><RouterLink :to="`/anfragen/${x.id}`" class="text-accent hover:underline">{{ x.lieferantName }}</RouterLink></template>
          </p>
        </div>
        <div class="rounded-2xl bg-accent-soft px-5 py-3 text-center">
          <div class="label !text-accent">Unsere Anfragenummer</div>
          <div class="mt-0.5 text-lg font-semibold text-accent tnum">{{ a.id }}</div>
          <div class="text-[11px] text-mute">der Lieferant nennt sie im Angebot</div>
        </div>
      </div>
    </section>

    <!-- Abgleich: angefragt gegen angeboten (aus dem eingelesenen PDF) -->
    <section v-if="daten" class="card overflow-x-auto p-5">
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <h3 class="flex items-center gap-2 text-sm font-semibold"><Scale :size="16" class="text-accent" /> Angefragt und angeboten</h3>
        <span class="text-xs text-mute">aus {{ daten.datei || 'dem PDF' }}<template v-if="a.antwort?.angebotsnr"> · Angebot {{ a.antwort.angebotsnr }}</template></span>
        <BelegLink v-if="a.antwort?.pdf" :url="a.antwort.pdf" :name="`Angebot ${a.antwort.angebotsnr || ''}`" :titel="a.lieferantName" class="ml-auto inline-flex items-center gap-1 text-xs text-accent hover:underline"><FileText :size="13" /> PDF öffnen</BelegLink>
      </div>
      <table class="w-full min-w-[760px] text-sm">
        <thead><tr class="border-b border-line text-left text-xs text-mute"><th class="py-2 pr-3 font-medium">Unsere Anfrage</th><th class="py-2 pr-3 font-medium">Angebot des Lieferanten</th><th class="py-2 pr-3 font-medium">Prüfung</th><th class="py-2 text-right font-medium">Preis</th></tr></thead>
        <tbody>
          <tr v-for="z in abgleichZeilen" :key="z.p.key" class="border-b border-line/60 align-top">
            <td class="py-2.5 pr-3">
              <div class="font-medium"><span class="mr-1 text-mute">{{ z.nr }}</span>{{ z.p.teil.name }}</div>
              <div class="text-xs text-mute">{{ [z.p.teil.material, z.p.abmessung].filter(Boolean).join(' · ') }}</div>
              <div class="text-xs">{{ z.p.mengen.join(' / ') }} {{ z.p.einheit }}<template v-if="z.p.anforderungen"> · <span class="text-mute">{{ z.p.anforderungen }}</span></template></div>
            </td>
            <td class="py-2.5 pr-3">
              <div v-for="(o, k) in z.os" :key="k" :class="k ? 'mt-1.5' : ''">
                <div><span v-if="o.pos" class="mr-1 text-xs text-mute">Pos {{ o.pos }}</span>{{ [o.werkstoff, o.zustand].filter(Boolean).join(' ') }} <span class="text-mute">{{ [o.form, o.abmessung].filter(Boolean).join(' · ') }}</span></div>
                <div class="text-xs tnum">{{ mengenText(o) }}<template v-if="o.preis != null"> · {{ eur(o.preis) }} / {{ o.preisJe }}</template><template v-if="o.liefertermin"> · <span class="text-mute">{{ o.liefertermin }}</span></template></div>
              </div>
              <span v-if="!z.os.length" class="text-xs text-warn">nicht angeboten</span>
            </td>
            <td class="py-2.5 pr-3">
              <div class="flex flex-wrap gap-1">
                <span v-for="(c, k) in z.pruefung" :key="k" class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]" :class="c.ok === true ? 'bg-ok/10 text-ok' : c.ok === false ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'" :title="`angefragt: ${c.angefragt} · angeboten: ${c.angeboten}`">
                  <CheckCircle2 v-if="c.ok === true" :size="12" /><AlertTriangle v-else-if="c.ok === false" :size="12" /><CircleHelp v-else :size="12" />{{ c.feld }}<template v-if="c.ok === false">: {{ c.angeboten }}</template>
                </span>
                <span v-if="z.je?.abweichung" class="inline-flex items-center gap-1 rounded-full bg-warn/15 px-2 py-0.5 text-[11px] text-warn"><AlertTriangle :size="12" /> Menge: {{ zahl(z.je.angeboten, 2) }} {{ z.p.einheit }} angeboten</span>
              </div>
            </td>
            <td class="whitespace-nowrap py-2.5 text-right tnum">
              <template v-if="z.je"><div class="font-semibold">{{ eur(z.je.einzel) }} / {{ z.p.einheit }}</div><div class="text-xs text-mute">{{ eur(z.je.betrag) }}</div></template>
              <span v-else class="text-mute">–</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs">
        <span v-if="a.antwort?.nebenkosten">Nebenkosten <strong class="tnum">{{ eur(a.antwort.nebenkosten) }}</strong><template v-if="a.antwort.nebenkostenText"> <span class="text-mute">({{ a.antwort.nebenkostenText.split('\n').join(', ') }})</span></template></span>
        <span v-if="optionen.length" class="text-mute">Nicht übernommen: {{ optionen.map((o) => `${o.option ? 'Option ' : ''}Pos ${o.pos || '?'} (${o.betrag != null ? eur(o.betrag) : '–'})`).join(', ') }}</span>
        <span v-if="daten.netto != null" :class="daten.stimmt ? 'text-ok' : 'text-warn'">Netto laut PDF {{ eur(daten.netto) }}{{ daten.stimmt ? ', Summe stimmt' : ', Summe weicht ab' }}</span>
      </div>
    </section>

    <div class="grid items-start gap-4 lg:grid-cols-2">
      <section class="card p-5">
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><Mail :size="16" class="text-accent" /> Mails</h3>
        <div v-if="a.nachrichten.length" class="space-y-2">
          <div v-for="(n, i) in [...a.nachrichten].reverse()" :key="i" class="rounded-xl border border-line">
            <button class="flex w-full items-start gap-3 px-3.5 py-2.5 text-left" @click="offen[i] = !offen[i]">
              <Send v-if="n.richtung === 'Ausgang'" :size="15" class="mt-0.5 shrink-0 text-mute" /><Inbox v-else :size="15" class="mt-0.5 shrink-0 text-accent" />
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium">{{ n.betreff }}</span>
                <span class="block truncate text-xs text-mute">{{ n.richtung === 'Ausgang' ? 'an die Lieferanten (BCC)' : `von ${n.vonName || n.vonEmail}` }} · {{ zeit(n.datum) }}<template v-if="n.anhaenge.length"> · <Paperclip :size="11" class="inline" /> {{ n.anhaenge.length }}</template></span>
              </span>
              <ChevronDown :size="15" class="mt-0.5 shrink-0 text-mute transition" :class="offen[i] ? 'rotate-180' : ''" />
            </button>
            <div v-if="offen[i] || (i === 0 && n.richtung === 'Eingang')" class="border-t border-line px-3.5 py-3">
              <div v-if="n.anhaenge.length" class="mb-2 flex flex-wrap gap-1.5">
                <template v-for="x in n.anhaenge" :key="x.name">
                  <BelegLink v-if="x.url && /\.pdf$/i.test(x.name)" :url="x.url" :name="x.name" :titel="a.lieferantName" class="inline-flex items-center gap-1 rounded-lg border border-line bg-surface2 px-2 py-1 text-xs hover:border-accent/50 hover:text-accent"><Paperclip :size="12" /> {{ x.name }} <span class="text-mute">{{ groesse(x.groesse) }}</span></BelegLink>
                  <a v-else :href="x.url" :class="x.url ? 'hover:border-accent/50 hover:text-accent' : 'pointer-events-none'" target="_blank" rel="noopener" class="inline-flex items-center gap-1 rounded-lg border border-line bg-surface2 px-2 py-1 text-xs"><Paperclip :size="12" /> {{ x.name }} <span class="text-mute">{{ groesse(x.groesse) }}</span></a>
                </template>
              </div>
              <div class="max-h-80 overflow-auto"><MailHtml v-if="n.html" :html="n.html" /><pre v-else class="whitespace-pre-wrap font-sans text-[13px] text-mute">{{ n.text }}</pre></div>
            </div>
          </div>
        </div>
        <template v-else>
          <p class="mb-3 text-sm text-mute">Noch nicht per Mail verschickt. „Per Mail senden“ schickt eine Mail an alle Lieferanten des Vorgangs (in BCC); Antworten mit der Nummer {{ a.vorgang }} erscheinen dann hier.</p>
          <details class="text-sm">
            <summary class="cursor-pointer text-mute hover:text-ink">Anschreiben zum Kopieren (z. B. für andere Wege)</summary>
            <div class="mt-2 rounded-xl border border-line bg-surface2 p-4 text-[13px] leading-relaxed">
              <div class="mb-2 font-medium">{{ mail.betreff }}</div>
              <pre class="whitespace-pre-wrap font-sans text-mute">{{ mail.text }}</pre>
            </div>
            <button class="btn mt-2" @click="kopieren"><Copy :size="15" /> Kopieren</button>
          </details>
        </template>
      </section>

      <section class="card p-5">
        <h3 class="mb-3 text-sm font-semibold">Angebot des Lieferanten</h3>
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="label mb-1 block">Angebotsnummer des Lieferanten</span><input v-model="form.angebotsnr" class="field" placeholder="z. B. AN-5521" /></label>
          <label class="block"><span class="label mb-1 block">Gültig bis</span><input v-model="form.gueltigBis" type="date" class="field" /></label>
          <label class="col-span-2 block"><span class="label mb-1 block">Lieferzeit</span><input v-model="form.lieferzeit" class="field" placeholder="z. B. 2 Wochen, KW 50, ab Lager" /></label>
          <label class="block"><span class="label mb-1 block">Nebenkosten (einmal je Angebot)</span><NumField v-model="form.nebenkosten" unit="€" /></label>
          <label class="block"><span class="label mb-1 block">wofür</span><input v-model="form.nebenkostenText" class="field" placeholder="z. B. Verpackung, Fracht" /></label>
        </div>

        <div class="mt-4 space-y-4">
          <div v-for="p in a.positionen" :key="p.key" class="rounded-xl border border-line p-3">
            <div class="mb-3 flex items-center gap-3">
              <PartImage :teil="p.teil" :groesse="38" />
              <div v-if="frei" class="min-w-0"><div class="truncate text-sm font-medium">{{ p.teil.name }}</div><div class="truncate text-xs text-mute">{{ [p.teil.material, p.abmessung].filter(Boolean).join(' · ') || '–' }}</div></div>
              <div v-else class="min-w-0"><div class="truncate text-sm font-medium">{{ p.agName || 'Fremdvergabe' }}</div><div class="truncate text-xs text-mute">{{ p.teil.name }}<template v-if="p.teil.teilenummer"> · {{ p.teil.teilenummer }}</template></div></div>
            </div>
            <div class="grid grid-cols-[80px_1fr_1fr] gap-2 pb-1 text-xs"><span class="label">Menge</span><span class="label">Preis je {{ p.einheit === 'Stk' || !p.einheit ? 'Stück' : p.einheit === 'Stangen' ? 'Stange' : p.einheit === 'Platten' ? 'Platte' : p.einheit === 'Zuschnitte' ? 'Zuschnitt' : p.einheit }}</span><span class="label">Einmalig</span></div>
            <div class="space-y-2">
              <div v-for="z in zeilenFuer(p.key)" :key="z.menge" class="grid grid-cols-[80px_1fr_1fr] items-center gap-2">
                <span class="text-sm font-semibold tnum">{{ z.menge }} {{ p.einheit || 'Stk' }}</span>
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
        <p v-if="a.antwort && !frei" class="mt-3 text-xs text-mute">Der Preis lässt sich jetzt in der Workbench am jeweiligen Arbeitsgang mit „Preis übernehmen“ in die Kalkulation holen.</p>
      </section>
    </div>
  </div>
  <AnfrageMailDialog v-if="a && mailDialog" :vorgang="a.vorgang" @schliessen="mailDialog = false" @gesendet="mailDialog = false" />
  <LieferangebotDialog v-if="a && einlesen" :anfrage="a" @schliessen="einlesen = false" @erfasst="einlesen = false" />
  <div v-else-if="!a" class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Anfrage nicht gefunden</p>
    <RouterLink to="/anfragen" class="btn mt-4">Zur Übersicht</RouterLink>
  </div>
</template>
