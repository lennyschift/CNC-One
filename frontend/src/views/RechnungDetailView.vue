<script setup>
import { computed, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft, Printer, Lock, Trash2, Banknote, BellRing, Undo2, FileText, Truck, ShieldCheck, FileDown, FileCode, TriangleAlert } from '@lucide/vue';
import RechnungDokument from '../components/RechnungDokument.vue';
import StatusBadge from '../components/StatusBadge.vue';
import NumField from '../components/NumField.vue';
import { useRechnung } from '../stores/rechnung.js';
import { useFirma } from '../stores/firma.js';
import { benutzer } from '../data/repo.js';
import { eur } from '../lib/format.js';

const route = useRoute();
const router = useRouter();
const store = useRechnung();
const firma = useFirma();
const r = computed(() => store.rechnung(route.params.id));
const darfBuchen = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'CNC Buchhaltung', 'System Manager'].includes(x)));
const festgeschrieben = computed(() => ['Offen', 'Teilbezahlt', 'Bezahlt'].includes(r.value?.status));
const mitNummer = computed(() => !!r.value?.nummer && r.value.status !== 'Entwurf');
const zahlbar = computed(() => ['Offen', 'Teilbezahlt'].includes(r.value?.status));

// ---- Entwurf bearbeiten
const form = reactive({ rechnungsdatum: '', zahlungszielTage: 0, kundenbestellnr: '', einleitung: '', bemerkung: '' });
watch(r, (x) => {
  if (!x) return;
  Object.assign(form, { rechnungsdatum: x.rechnungsdatum, zahlungszielTage: x.zahlungszielTage, kundenbestellnr: x.kundenbestellnr, einleitung: x.einleitung, bemerkung: x.bemerkung });
}, { immediate: true });
const speichert = ref(false);
async function speichern() { speichert.value = true; await store.speichern(r.value.id, { ...form }); speichert.value = false; }

// zweite Bestätigung bei Aktionen, die sich nicht zurücknehmen lassen
const frage = ref('');
function bestaetigt(name, fn) {
  if (frage.value !== name) { frage.value = name; setTimeout(() => { if (frage.value === name) frage.value = ''; }, 5000); return; }
  frage.value = '';
  fn();
}
async function verwerfen() { if (await store.verwerfen(r.value.id)) router.push('/rechnungen'); }

// ---- Zahlung
const zahlung = reactive({ betrag: 0, datum: new Date().toISOString().slice(0, 10), referenz: '', konto: '' });
watch(() => r.value?.offen, (o) => { zahlung.betrag = o || 0; }, { immediate: true });
const konten = computed(() => [...(r.value?.firma?.banken ?? firma.firma.banken).map((b) => b.bezeichnung), 'Bar', 'Sonstiges']);
async function zahlen() {
  const rec = await store.zahlungErfassen(r.value.id, { betrag: Number(zahlung.betrag), zahlungsdatum: zahlung.datum, referenz: zahlung.referenz, konto: zahlung.konto });
  if (rec) Object.assign(zahlung, { referenz: '', konto: '' });
}
const stornoGrund = reactive({ rechnung: '', zahlung: '' });
const zahlungWeg = ref('');
async function zahlungStorno(id) {
  if (!stornoGrund.zahlung.trim()) return;
  if (await store.zahlungStornieren(id, stornoGrund.zahlung)) { zahlungWeg.value = ''; stornoGrund.zahlung = ''; }
}

// ---- Storno und Mahnung
async function stornieren() { await store.stornieren(r.value.id, stornoGrund.rechnung); stornoGrund.rechnung = ''; }
const naechsteStufe = computed(() => {
  const aktive = (r.value?.mahnungen ?? []).filter((m) => m.status !== 'Zurückgezogen').map((m) => m.stufe);
  return ['Zahlungserinnerung', '1. Mahnung', '2. Mahnung'].find((s) => !aktive.includes(s)) ?? null;
});
async function mahnen() { const m = await store.mahnungAnlegen(r.value.id); if (m) router.push(`/mahnungen/${m.id}`); }

const lieferscheine = computed(() => [...new Set((r.value?.positionen ?? []).flatMap((p) => (p.lieferungen ?? []).map((l) => l.lieferschein)))]);
// ---- E-Rechnung
const laedt = ref(false);
const datei = (art) => `/api/method/cnc_one.api.erechnung.herunterladen?id=${encodeURIComponent(r.value.id)}&art=${art}`;
async function eRechnungNeu() { laedt.value = true; await store.eRechnungNeu(r.value.id); laedt.value = false; }
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const drucken = () => window.print();
</script>

<template>
  <div v-if="r" class="mx-auto grid max-w-[1300px] items-start gap-6 xl:grid-cols-[1fr_360px]">
    <RechnungDokument :rechnung="r" />

    <aside class="no-print space-y-4 xl:sticky xl:top-0">
      <RouterLink to="/rechnungen" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Rechnungen</RouterLink>

      <section class="card p-5">
        <div class="flex items-center justify-between"><h2 class="font-semibold tnum">{{ r.nummer || 'Entwurf' }}</h2><StatusBadge :status="r.status" /></div>
        <p class="mt-1 text-sm text-mute">{{ r.kundeName }} · <RouterLink :to="`/auftraege/${r.auftragId}`" class="text-accent hover:underline tnum">{{ r.auftragId }}</RouterLink></p>
        <dl class="mt-4 grid grid-cols-3 gap-2 text-center">
          <div class="rounded-xl bg-surface2 px-2 py-2"><dt class="text-[11px] text-mute">Brutto</dt><dd class="text-sm font-semibold tnum">{{ eur(r.brutto) }}</dd></div>
          <div class="rounded-xl bg-surface2 px-2 py-2"><dt class="text-[11px] text-mute">Bezahlt</dt><dd class="text-sm font-semibold tnum text-ok">{{ eur(r.bezahlt) }}</dd></div>
          <div class="rounded-xl px-2 py-2" :class="r.offen > 0 && r.tageUeberfaellig > 0 ? 'bg-accent-soft text-accent' : 'bg-surface2'"><dt class="text-[11px]" :class="r.tageUeberfaellig > 0 ? '' : 'text-mute'">Offen</dt><dd class="text-sm font-semibold tnum">{{ eur(r.offen) }}</dd></div>
        </dl>
        <p v-if="r.tageUeberfaellig > 0" class="mt-3 rounded-lg bg-accent-soft px-3 py-2 text-xs text-accent">{{ r.tageUeberfaellig }} Tage überfällig (fällig am {{ de(r.faelligAm) }}).</p>

        <div class="mt-4 space-y-2">
          <template v-if="r.status === 'Entwurf'">
            <button v-if="darfBuchen" class="btn w-full justify-center" :class="frage === 'fest' ? 'btn-primary' : 'btn-primary'" @click="bestaetigt('fest', () => store.festschreiben(r.id))"><Lock :size="16" /> {{ frage === 'fest' ? 'Wirklich festschreiben?' : 'Festschreiben' }}</button>
            <p v-else class="text-xs text-mute">Festschreiben darf nur die Buchhaltung.</p>
            <p class="text-xs text-mute">Beim Festschreiben bekommt die Rechnung ihre lückenlose Nummer und das heutige Datum. Danach lässt sie sich nur noch stornieren.</p>
            <button class="btn w-full justify-center !text-mute" @click="bestaetigt('weg', verwerfen)"><Trash2 :size="16" /> {{ frage === 'weg' ? 'Wirklich verwerfen?' : 'Entwurf verwerfen' }}</button>
          </template>
          <button class="btn w-full justify-center" @click="drucken"><Printer :size="16" /> Drucken / als PDF speichern</button>
        </div>
      </section>

      <!-- E-Rechnung -->
      <section v-if="mitNummer && r.eRechnung" class="card p-5">
        <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold"><FileDown :size="16" class="text-accent" /> E-Rechnung</h3>
        <p class="mb-3 text-xs text-mute">Die Rechnung als PDF mit eingebetteten Rechnungsdaten (ZUGFeRD, PDF/A-3) und als XRechnung-XML, zum Versenden per E-Mail oder an Behörden.</p>
        <div class="space-y-2">
          <a v-if="r.eRechnung.pdf" :href="datei('pdf')" target="_blank" rel="noopener" class="btn w-full justify-center"><FileDown :size="16" /> {{ r.eRechnung.zugferd ? 'PDF mit ZUGFeRD' : 'PDF (ohne ZUGFeRD)' }}</a>
          <a v-if="r.eRechnung.xrechnung" :href="datei('xml')" download class="btn w-full justify-center"><FileCode :size="16" /> XRechnung (XML)</a>
        </div>
        <p v-if="r.eRechnung.hinweis" class="mt-3 flex items-start gap-1.5 rounded-lg bg-accent-soft px-3 py-2 text-xs text-accent"><TriangleAlert :size="14" class="mt-0.5 shrink-0" /><span>{{ r.eRechnung.hinweis }} Die Angaben stehen in den <RouterLink to="/stammdaten/firma" class="underline">Firmendaten</RouterLink> und beim Kunden (Kontakt mit E-Mail).</span></p>
        <p v-else-if="r.eRechnung.status === 'Fehler'" class="mt-3 text-xs text-accent">Die E-Rechnung ließ sich nicht erzeugen.</p>
        <button v-if="darfBuchen" class="btn mt-2 w-full justify-center !text-mute" :disabled="laedt" @click="eRechnungNeu">{{ r.eRechnung.status ? 'E-Rechnung neu erzeugen' : 'E-Rechnung erzeugen' }}</button>
      </section>

      <!-- Entwurf bearbeiten -->
      <section v-if="r.status === 'Entwurf'" class="card p-5">
        <h3 class="mb-3 text-sm font-semibold">Angaben</h3>
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="label mb-1 block">Rechnungsdatum</span><input v-model="form.rechnungsdatum" type="date" class="field" /></label>
          <NumField v-model="form.zahlungszielTage" label="Zahlungsziel" unit="Tage" :decimals="0" />
          <label class="col-span-2 block"><span class="label mb-1 block">Bestellnummer des Kunden</span><input v-model="form.kundenbestellnr" class="field" /></label>
          <label class="col-span-2 block"><span class="label mb-1 block">Einleitungstext</span><textarea v-model="form.einleitung" rows="2" class="field resize-y" /></label>
          <label class="col-span-2 block"><span class="label mb-1 block">Bemerkung</span><textarea v-model="form.bemerkung" rows="2" class="field resize-y" /></label>
        </div>
        <button class="btn mt-3 w-full justify-center" :disabled="speichert" @click="speichern">Angaben speichern</button>
      </section>

      <!-- Zahlung -->
      <section v-if="zahlbar && darfBuchen" class="card p-5">
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><Banknote :size="16" class="text-accent" /> Zahlung erfassen</h3>
        <div class="grid grid-cols-2 gap-3">
          <NumField v-model="zahlung.betrag" label="Betrag" unit="€" />
          <label class="block"><span class="label mb-1 block">Datum</span><input v-model="zahlung.datum" type="date" class="field" /></label>
          <label class="block"><span class="label mb-1 block">Eingegangen auf</span><select v-model="zahlung.konto" class="field"><option value="">–</option><option v-for="k in konten" :key="k">{{ k }}</option></select></label>
          <label class="block"><span class="label mb-1 block">Verwendungszweck</span><input v-model="zahlung.referenz" class="field" /></label>
        </div>
        <button class="btn btn-primary mt-3 w-full justify-center" :disabled="!(zahlung.betrag > 0)" @click="zahlen">Zahlung buchen</button>
      </section>
      <section v-if="r.zahlungen.length" class="card p-5">
        <h3 class="mb-3 text-sm font-semibold">Zahlungen</h3>
        <ul class="space-y-2">
          <li v-for="z in r.zahlungen" :key="z.id" class="rounded-xl border border-line p-3 text-sm" :class="z.storniert ? 'opacity-50' : ''">
            <div class="flex items-center justify-between gap-3"><span class="tnum" :class="z.storniert ? 'line-through' : 'font-semibold'">{{ eur(z.betrag) }}</span><span class="text-xs text-mute">{{ de(z.datum) }}</span></div>
            <div class="text-xs text-mute">{{ z.konto }}<template v-if="z.referenz"> · {{ z.referenz }}</template><template v-if="z.storniert"> · storniert: {{ z.stornoGrund }}</template></div>
            <template v-if="!z.storniert && darfBuchen">
              <button v-if="zahlungWeg !== z.id" class="mt-1 text-xs text-mute hover:text-accent" @click="zahlungWeg = z.id">Stornieren …</button>
              <div v-else class="mt-2 flex gap-2"><input v-model="stornoGrund.zahlung" class="field !py-1.5" placeholder="Grund (Pflicht)" /><button class="btn !py-1.5" :disabled="!stornoGrund.zahlung.trim()" @click="zahlungStorno(z.id)">OK</button></div>
            </template>
          </li>
        </ul>
      </section>

      <!-- Mahnung -->
      <section v-if="zahlbar && darfBuchen && r.tageUeberfaellig > 0 && naechsteStufe" class="card p-5">
        <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold"><BellRing :size="16" class="text-accent" /> Mahnwesen</h3>
        <button class="btn w-full justify-center" @click="mahnen">{{ naechsteStufe }} anlegen</button>
      </section>
      <section v-if="r.mahnungen.length" class="card p-5">
        <h3 class="mb-2 text-sm font-semibold">Mahnungen zu dieser Rechnung</h3>
        <ul class="space-y-1.5 text-sm"><li v-for="m in r.mahnungen" :key="m.id" class="flex items-center justify-between gap-2"><RouterLink :to="`/mahnungen/${m.id}`" class="text-accent hover:underline">{{ m.stufe }}</RouterLink><span class="flex items-center gap-2 text-xs text-mute">{{ de(m.datum) }} <StatusBadge :status="m.status" /></span></li></ul>
      </section>

      <!-- Storno -->
      <section v-if="festgeschrieben && darfBuchen" class="card p-5">
        <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold"><Undo2 :size="16" class="text-accent" /> Stornieren</h3>
        <p class="mb-2 text-xs text-mute">Erzeugt eine Stornorechnung mit eigener Nummer. Menge und Sonderkosten sind danach im Auftrag wieder frei.</p>
        <input v-model="stornoGrund.rechnung" class="field" placeholder="Grund (Pflicht)" />
        <button class="btn mt-2 w-full justify-center" :class="frage === 'storno' ? '!border-accent !bg-accent-soft !text-accent' : '!text-mute'" :disabled="!stornoGrund.rechnung.trim()" @click="bestaetigt('storno', stornieren)">{{ frage === 'storno' ? 'Wirklich stornieren?' : 'Rechnung stornieren' }}</button>
      </section>
      <section v-if="r.stornoZu || r.storniertDurch" class="card p-5 text-sm">
        <p v-if="r.stornoZu">Stornorechnung zu <RouterLink :to="`/rechnungen/${r.stornoZu}`" class="text-accent hover:underline tnum">{{ store.rechnung(r.stornoZu)?.nummer || r.stornoZu }}</RouterLink>. Grund: {{ r.stornoGrund }}</p>
        <p v-if="r.storniertDurch">Storniert durch <RouterLink :to="`/rechnungen/${r.storniertDurch}`" class="text-accent hover:underline tnum">{{ store.rechnung(r.storniertDurch)?.nummer || r.storniertDurch }}</RouterLink>.</p>
      </section>

      <section class="card p-5">
        <h3 class="mb-2 text-sm font-semibold">Herkunft</h3>
        <ul class="space-y-1 text-sm">
          <li class="flex items-center gap-2"><FileText :size="14" class="text-mute" /> Auftrag <RouterLink :to="`/auftraege/${r.auftragId}`" class="text-accent hover:underline tnum">{{ r.auftragId }}</RouterLink></li>
          <li v-for="l in lieferscheine" :key="l" class="flex items-center gap-2"><Truck :size="14" class="text-mute" /> Lieferschein <RouterLink :to="`/lieferscheine/${l}`" class="text-accent hover:underline tnum">{{ l }}</RouterLink></li>
        </ul>
        <p v-if="r.inhaltHash" class="mt-3 flex items-start gap-1.5 break-all text-[11px] text-mute"><ShieldCheck :size="13" class="mt-0.5 shrink-0" /> Prüfsumme (SHA-256) {{ r.inhaltHash }}<br />festgeschrieben {{ de(r.festgeschriebenAm) }} von {{ r.festgeschriebenVon }}</p>
      </section>
    </aside>
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Rechnung nicht gefunden</p>
    <RouterLink to="/rechnungen" class="btn mt-4">Zur Liste</RouterLink>
  </div>
</template>
