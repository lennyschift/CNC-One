<script setup>
// Druckvorlagen der Belege (HTML mit Jinja-Platzhaltern, CSS) ändern, mit PDF-Vorschau an einem echten Beleg.
// Ohne Änderung gilt der Stand im Code. Geänderte Stände liegen in der Datenbank; auf dem Testsystem lassen sie sich
// „in den Code übernehmen“ (Datei unter templates/), damit sie mit Git ins Produktivsystem kommen. Jeder Stand steht
// im Verlauf und lässt sich zurückholen.
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { FileCode2, Save, Eye, RotateCcw, History, GitCommitHorizontal, AlertTriangle, Check, Code2, X } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';

const ui = useUi();
const HINWEIS = 'HTML mit Platzhaltern wie {{ a.id }} und {% if … %}';
const stand = ref(null); // { vorlagen, inDenCode, darfAendern }
const gewaehlt = ref('');
const v = ref(null); // geladene Vorlage (holen)
const text = ref('');
const notiz = ref('');
const arbeitet = ref('');
const codeZeigen = ref(false);
const verlaufOffen = ref(false);

const geaendertImEditor = computed(() => v.value && text.value !== v.value.inhalt);
const zeilen = computed(() => text.value.split('\n').length);

async function laden() {
  try { stand.value = await call('cnc_one.api.druckvorlage.liste'); } catch (e) { ui.toast(e.message, 'warn'); }
}
onMounted(async () => {
  await laden();
  if (stand.value?.vorlagen.length) waehlen(stand.value.vorlagen[0].datei);
});

async function waehlen(datei) {
  if (geaendertImEditor.value && !confirm('Die Änderungen an dieser Vorlage sind nicht gespeichert. Verwerfen?')) return;
  gewaehlt.value = datei;
  codeZeigen.value = false;
  verlaufOffen.value = false;
  fehler.value = '';
  try {
    v.value = await call('cnc_one.api.druckvorlage.holen', { datei });
    text.value = v.value.inhalt;
    await belegeLaden(v.value.beleg);
    vorschau();
  } catch (e) { ui.toast(e.message, 'warn'); }
}

function uebernehmen(r, meldung) {
  v.value = r;
  text.value = r.inhalt;
  const i = stand.value.vorlagen.findIndex((x) => x.datei === r.datei);
  if (i >= 0) stand.value.vorlagen[i] = { ...stand.value.vorlagen[i], geaendert: r.geaendert, codeNeuer: r.codeNeuer, geaendertAm: r.geaendertAm, geaendertVon: r.geaendertVon };
  if (meldung) ui.toast(meldung, 'ok');
}

async function ausfuehren(art, fn) {
  arbeitet.value = art;
  try { await fn(); } catch (e) { ui.toast(e.message, 'warn'); } finally { arbeitet.value = ''; }
}
const speichern = () => ausfuehren('speichern', async () => {
  uebernehmen(await call('cnc_one.api.druckvorlage.speichern', { datei: gewaehlt.value, inhalt: text.value, notiz: notiz.value }), 'Vorlage gespeichert, gilt ab sofort für neue PDFs');
  notiz.value = '';
});
const zuruecksetzen = () => {
  if (!confirm('Wieder den Stand im Code verwenden? Der geänderte Stand bleibt im Verlauf.')) return;
  ausfuehren('zuruecksetzen', async () => { uebernehmen(await call('cnc_one.api.druckvorlage.zuruecksetzen', { datei: gewaehlt.value }), 'Stand im Code gilt wieder'); vorschau(); });
};
const inDenCode = () => {
  if (!confirm('Den gespeicherten Stand in die Datei im Code schreiben? Er kommt mit dem nächsten Commit nach GitHub und ins Produktivsystem.')) return;
  ausfuehren('code', async () => uebernehmen(await call('cnc_one.api.druckvorlage.in_den_code', { datei: gewaehlt.value }), 'In den Code übernommen'));
};
async function standLaden(s) {
  try {
    text.value = await call('cnc_one.api.druckvorlage.stand_inhalt', { id: s.id });
    verlaufOffen.value = false;
    codeZeigen.value = false;
    ui.toast('Früherer Stand im Editor; zum Übernehmen speichern', 'ok');
    vorschau();
  } catch (e) { ui.toast(e.message, 'warn'); }
}

// ---- Vorschau an einem Beleg
const belege = ref([]);
const belegId = ref('');
const pdfUrl = ref('');
const fehler = ref('');
const laedt = ref(false);
async function belegeLaden(art) {
  if (art === 'Firma') { belege.value = []; belegId.value = ''; return; }
  try { belege.value = await call('cnc_one.api.druckvorlage.belege', { beleg: art }); } catch { belege.value = []; }
  if (!belege.value.some((b) => b.id === belegId.value)) belegId.value = belege.value[0]?.id ?? '';
}
let laufNr = 0;
async function vorschau() {
  if (!v.value) return;
  const nr = ++laufNr;
  laedt.value = true;
  try {
    const r = await call('cnc_one.api.druckvorlage.vorschau', { datei: gewaehlt.value, inhalt: text.value, beleg: v.value.beleg, id: belegId.value });
    if (nr !== laufNr) return;
    fehler.value = r.fehler || '';
    if (r.pdf) {
      const bytes = Uint8Array.from(atob(r.pdf), (c) => c.charCodeAt(0));
      if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
      pdfUrl.value = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
    }
  } catch (e) {
    if (nr === laufNr) fehler.value = e.message;
  } finally {
    if (nr === laufNr) laedt.value = false;
  }
}
watch(belegId, (neu, alt) => { if (alt !== undefined && neu !== alt) vorschau(); });
onBeforeUnmount(() => { if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); });

// ---- Editor: Tab rückt ein, Strg+S speichert, Strg+Enter zeigt die Vorschau
const feld = ref(null);
const rinne = ref(null);
function taste(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); if (stand.value?.darfAendern && geaendertImEditor.value) speichern(); return; }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); vorschau(); return; }
  if (e.key === 'Tab') {
    e.preventDefault();
    const t = e.target;
    const [a, b] = [t.selectionStart, t.selectionEnd];
    text.value = text.value.slice(0, a) + '  ' + text.value.slice(b);
    requestAnimationFrame(() => { t.selectionStart = t.selectionEnd = a + 2; });
  }
}
const mitlaufen = (e) => { if (rinne.value) rinne.value.scrollTop = e.target.scrollTop; };
const zeit = (iso) => (iso ? new Date(iso.replace(' ', 'T')).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
</script>

<template>
  <div class="mx-auto max-w-[1800px]">
    <StammNav />
    <p class="mb-4 max-w-4xl text-sm text-mute">
      Hier lassen sich die PDF-Vorlagen der Belege ändern. Ohne Änderung gilt der Stand im Code. Gespeicherte Änderungen gelten sofort für neue PDFs;
      bereits verschickte Belege bleiben, wie sie sind.<template v-if="stand?.inDenCode"> Auf diesem Testsystem schreibt „In den Code übernehmen“ den Stand in die Datei, damit er mit dem nächsten Commit nach GitHub und ins Produktivsystem kommt.</template>
    </p>

    <div v-if="!stand" class="card p-5 text-sm text-mute">Wird geladen …</div>
    <div v-else class="grid items-start gap-4 xl:grid-cols-[250px_minmax(0,1fr)_minmax(0,1fr)]">
      <!-- Vorlagen -->
      <nav class="card p-2">
        <button
          v-for="x in stand.vorlagen" :key="x.datei" type="button" class="flex w-full items-start gap-2.5 rounded-xl px-3 py-2 text-left transition"
          :class="gewaehlt === x.datei ? 'bg-accent-soft' : 'hover:bg-surface2'" @click="waehlen(x.datei)"
        >
          <FileCode2 :size="16" class="mt-0.5 shrink-0" :class="gewaehlt === x.datei ? 'text-accent' : 'text-mute'" />
          <span class="min-w-0 flex-1">
            <span class="block text-sm" :class="gewaehlt === x.datei ? 'font-medium text-accent' : ''">{{ x.bezeichnung }}</span>
            <span class="block truncate font-mono text-[10px] text-mute">{{ x.datei }}</span>
            <span v-if="x.geaendert" class="mt-0.5 inline-flex items-center gap-1 rounded-full bg-warn/15 px-1.5 text-[10px] font-medium text-warn">geändert</span>
            <span v-if="x.codeNeuer" class="ml-1 mt-0.5 inline-flex items-center gap-1 rounded-full bg-accent-soft px-1.5 text-[10px] font-medium text-accent" title="Die Datei im Code ist neuer als die Änderung">Code neuer</span>
          </span>
        </button>
      </nav>

      <!-- Editor -->
      <section v-if="v" class="card flex min-w-0 flex-col p-4">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <h2 class="mr-auto text-sm font-semibold">{{ v.bezeichnung }}
            <span v-if="v.geaendert" class="ml-1 text-xs font-normal text-mute">geändert {{ zeit(v.geaendertAm) }}{{ v.geaendertVon ? ` von ${v.geaendertVon}` : '' }}</span>
            <span v-else class="ml-1 text-xs font-normal text-mute">Stand im Code</span>
          </h2>
          <button type="button" class="btn !py-1.5 !text-sm" :class="codeZeigen ? 'border-accent text-accent' : ''" title="Stand im Code daneben ansehen" @click="codeZeigen = !codeZeigen"><Code2 :size="15" /> Code</button>
          <div class="relative">
            <button type="button" class="btn !py-1.5 !text-sm" :class="verlaufOffen ? 'border-accent text-accent' : ''" @click="verlaufOffen = !verlaufOffen"><History :size="15" /> Verlauf <span class="text-mute tnum">{{ v.staende.length }}</span></button>
            <div v-if="verlaufOffen" class="absolute right-0 top-full z-40 mt-1.5 w-80 rounded-xl border border-line bg-surface p-2 shadow-xl">
              <p v-if="!v.staende.length" class="px-2 py-2 text-xs text-mute">Noch keine Änderungen.</p>
              <button v-for="s in v.staende" :key="s.id" type="button" class="block w-full rounded-lg px-2.5 py-1.5 text-left hover:bg-surface2" title="In den Editor laden" @click="standLaden(s)">
                <span class="block text-sm">{{ s.aktion }}<span v-if="s.notiz" class="text-mute"> · {{ s.notiz }}</span></span>
                <span class="block text-[11px] text-mute">{{ zeit(s.zeit) }} · {{ s.von }}</span>
              </button>
            </div>
          </div>
        </div>

        <div v-if="v.codeNeuer" class="mb-3 flex items-start gap-2 rounded-xl bg-accent-soft/60 px-3 py-2 text-xs text-accent">
          <AlertTriangle :size="14" class="mt-0.5 shrink-0" />
          <span>Die Datei im Code wurde geändert, nachdem diese Vorlage hier geändert wurde (z. B. durch ein Update). Es gilt weiter die Änderung von hier. Über „Code“ lässt sich der neue Stand ansehen.</span>
        </div>

        <div v-if="codeZeigen" class="relative mb-3">
          <button type="button" class="absolute right-2 top-2 text-mute hover:text-ink" @click="codeZeigen = false"><X :size="14" /></button>
          <div class="label mb-1">Stand im Code (nur lesen)</div>
          <pre class="max-h-[320px] overflow-auto rounded-xl bg-surface2 p-3 font-mono text-[11.5px] leading-[1.55]">{{ v.code }}</pre>
        </div>

        <div class="flex min-h-[560px] flex-1 overflow-hidden rounded-xl border border-line bg-surface2 focus-within:border-accent">
          <div ref="rinne" class="select-none overflow-hidden py-3 pl-2 pr-2 text-right font-mono text-[11.5px] leading-[1.55] text-mute/70" aria-hidden="true">
            <div v-for="n in zeilen" :key="n">{{ n }}</div>
          </div>
          <textarea
            ref="feld" v-model="text" spellcheck="false" wrap="off" :readonly="!stand.darfAendern"
            class="min-h-[560px] flex-1 resize-none bg-transparent py-3 pr-3 font-mono text-[11.5px] leading-[1.55] outline-none"
            @keydown="taste" @scroll="mitlaufen"
          />
        </div>
        <p class="mt-2 text-[11px] text-mute">
          {{ v.art === 'css' ? 'CSS' : HINWEIS }} ·
          <span class="kbd">Strg</span>+<span class="kbd">Enter</span> Vorschau · <span class="kbd">Strg</span>+<span class="kbd">S</span> speichern
        </p>

        <div v-if="stand.darfAendern" class="mt-3 flex flex-wrap items-center gap-2">
          <input v-model="notiz" class="field !w-auto min-w-0 flex-1 !py-1.5 !text-sm" placeholder="Notiz zur Änderung (optional)" @keydown.enter.prevent="geaendertImEditor && speichern()" />
          <button type="button" class="btn btn-primary !py-1.5 !text-sm" :disabled="!geaendertImEditor || !!arbeitet" @click="speichern"><Save :size="15" /> Speichern</button>
          <button v-if="geaendertImEditor" type="button" class="btn !py-1.5 !text-sm" @click="text = v.inhalt; vorschau()"><X :size="15" /> Verwerfen</button>
          <button v-if="v.geaendert" type="button" class="btn !py-1.5 !text-sm" :disabled="!!arbeitet" title="Wieder den Stand im Code verwenden" @click="zuruecksetzen"><RotateCcw :size="15" /> Auf Code-Stand</button>
          <button v-if="v.geaendert && stand.inDenCode" type="button" class="btn !py-1.5 !text-sm" :disabled="!!arbeitet || geaendertImEditor" :title="geaendertImEditor ? 'Erst speichern' : 'Stand in die Datei unter templates/ schreiben'" @click="inDenCode"><GitCommitHorizontal :size="15" /> In den Code übernehmen</button>
        </div>
        <p v-else class="mt-3 text-xs text-mute">Ändern dürfen nur Administratoren.</p>
      </section>

      <!-- Vorschau -->
      <section v-if="v" class="card flex min-w-0 flex-col p-4 xl:sticky xl:top-4">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <h2 class="mr-auto flex items-center gap-2 text-sm font-semibold"><Eye :size="16" class="text-accent" /> Vorschau
            <span v-if="laedt" class="text-xs font-normal text-mute">wird erzeugt …</span>
            <span v-else-if="!fehler && pdfUrl" class="inline-flex items-center gap-1 text-xs font-normal text-ok"><Check :size="12" /> {{ geaendertImEditor ? 'ungespeicherter Stand' : 'aktueller Stand' }}</span>
          </h2>
          <select v-if="v.beleg !== 'Firma'" v-model="belegId" class="field !w-auto max-w-[260px] !py-1.5 !text-sm" :title="`${v.beleg} für die Vorschau`">
            <option v-if="!belege.length" value="">Kein {{ v.beleg }} vorhanden</option>
            <option v-for="b in belege" :key="b.id" :value="b.id">{{ b.text }}</option>
          </select>
          <button type="button" class="btn !py-1.5 !text-sm" :disabled="laedt" @click="vorschau"><Eye :size="15" /> Aktualisieren</button>
        </div>
        <div v-if="fehler" class="mb-3 flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-xs text-warn">
          <AlertTriangle :size="14" class="mt-0.5 shrink-0" /><span class="whitespace-pre-wrap break-words font-mono">{{ fehler }}</span>
        </div>
        <iframe v-if="pdfUrl" :src="pdfUrl" class="h-[78vh] w-full rounded-xl border border-line bg-white" title="Vorschau" />
        <p v-else-if="!laedt" class="px-4 py-16 text-center text-sm text-mute">Keine Vorschau.</p>
      </section>
    </div>
  </div>
</template>
