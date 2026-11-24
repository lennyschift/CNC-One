<script setup>
// Angebote vergleichen, auch ohne Anfrage aus CNC One (Anfrage lief per Telefon, Mail außerhalb, oder vor der Einführung):
// mehrere Angebots-PDFs auf einmal einlesen. Je PDF wird der Lieferant erkannt (oder neu angelegt), gleiche Positionen
// verschiedener Lieferanten (gleicher Werkstoff, gleiche Form und Maße) werden zu einer Position zusammengefasst. Daraus
// entsteht ein Vorgang mit einer Lieferantenanfrage je Lieferant, mit den Preisen aus dem PDF und den PDFs als Anhang,
// danach öffnet sich der Angebotsvergleich.
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { X, FileUp, FileText, Loader, Trash2, CheckCircle2, AlertTriangle, Scale, Truck, ChevronDown } from '@lucide/vue';
import { call, hochladen } from '../data/api.js';
import { repo, stammdatenRoh } from '../data/repo.js';
import { pdfjs } from '../lib/pdf.js';
import { textAusSeite } from '../lib/zeichnungText.js';
import { angebotLesen, lieferantErkennen, lieferantVorschlag, positionsGruppen, preiseFuer } from '../lib/lieferangebot.js';
import { eur, zahl } from '../lib/format.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

const emit = defineEmits(['schliessen']);
const router = useRouter();
const store = useAnfragen();
const ui = useUi();

const lieferanten = ref([]);
repo.lieferanten.liste().then((l) => { lieferanten.value = (l ?? []).filter((x) => x.aktiv !== false); }).catch(() => {});
// die eigene Firma steht auch im PDF (als Empfänger): nie als Lieferant vorschlagen
const eigene = String(stammdatenRoh().firma?.firmenname ?? '').split(/\s+/).filter((w) => w.length >= 4 && !/^(gmbh|mbh)$/i.test(w));

// je PDF: { name, file, seiten, r, lieferantId, neuName, offen }
const angebote = ref([]);
const liest = ref(0);
const legtAn = ref(false);

async function seitenAus(file) {
  const aufgabe = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
  const doc = await aufgabe.promise;
  const s = [];
  for (let i = 1; i <= Math.min(doc.numPages, 10); i++) s.push(await textAusSeite(await doc.getPage(i)));
  aufgabe.destroy();
  return s;
}

async function vorlageFuer(id) {
  return id ? ((await store.angebotsvorlage(id)) ?? {}) : {};
}

async function dateienDazu(files) {
  for (const file of [...files].filter((f) => /\.pdf$/i.test(f.name) || f.type === 'application/pdf')) {
    liest.value++;
    try {
      const seiten = await seitenAus(file);
      let r = angebotLesen(seiten);
      const lieferantId = lieferantErkennen(r.text, lieferanten.value);
      if (lieferantId) r = angebotLesen(seiten, await vorlageFuer(lieferantId));
      angebote.value.push({ name: file.name, file, seiten, r, lieferantId, neuName: lieferantVorschlag(r.text, eigene), offen: false });
    } catch (e) {
      ui.toast(`${file.name}: ${e?.message || 'nicht lesbar'}`, 'warn');
    } finally {
      liest.value--;
    }
  }
  zuordnungNeu();
}
function gewaehlt(e) { dateienDazu(e.target.files ?? []); e.target.value = ''; }
function abgelegt(e) { dateienDazu(e.dataTransfer?.files ?? []); }
async function lieferantGeaendert(a) {
  a.r = angebotLesen(a.seiten, await vorlageFuer(a.lieferantId));
  zuordnungNeu();
}
function entfernen(i) { angebote.value.splice(i, 1); zuordnungNeu(); }

// ------------------------------------------------------------------ gemeinsame Positionen
const gruppen = ref([]); // [{ name, material, abmessungText, einheit, menge }]
const zu = ref([]); // [[gruppe|-1 je Angebotsposition] je Angebot]
function zuordnungNeu() {
  const g = positionsGruppen(angebote.value.map((a) => a.r));
  gruppen.value = g.gruppen.map((x) => ({ ...x }));
  zu.value = g.zuordnung;
}
// nur Positionen, die mindestens ein Angebot hat, in der Reihenfolge der Liste
const benutzt = computed(() => gruppen.value.map((g, i) => i).filter((i) => zu.value.some((z) => z.includes(i))));
const zelle = (ai, gi) => {
  const os = (angebote.value[ai]?.r.positionen ?? []).filter((_o, k) => zu.value[ai]?.[k] === gi);
  return os.length ? { betrag: os.reduce((s, o) => s + (o.betrag ?? 0), 0), o: os[0], n: os.length } : null;
};
const mengen = (o) => [o.stueck != null && `${zahl(o.stueck, 0)} Stk`, o.kg != null && `${zahl(o.kg, 2)} kg`, o.meter != null && `${zahl(o.meter, 3)} m`].filter(Boolean).join(' · ');
const lieferantText = (a) => (a.lieferantId ? lieferanten.value.find((l) => l.id === a.lieferantId)?.name ?? a.lieferantId : a.neuName ? `${a.neuName} (neu)` : 'Lieferant fehlt');

const fehler = computed(() => {
  if (!angebote.value.length) return 'Bitte mindestens ein Angebot einlesen.';
  if (angebote.value.some((a) => !a.lieferantId && !a.neuName.trim())) return 'Bitte bei jedem Angebot den Lieferanten wählen oder einen Namen eintragen.';
  const namen = angebote.value.map((a) => (a.lieferantId || a.neuName.trim()).toLowerCase());
  if (new Set(namen).size !== namen.length) return 'Ein Lieferant kommt doppelt vor: je Lieferant ein Angebot.';
  if (!benutzt.value.length) return 'Keine Position mit Preis erkannt.';
  if (benutzt.value.some((i) => !(Number(gruppen.value[i].menge) > 0) || !gruppen.value[i].name.trim())) return 'Jede Position braucht eine Bezeichnung und eine Menge.';
  return '';
});

async function anlegen() {
  if (fehler.value || legtAn.value) return;
  legtAn.value = true;
  try {
    // neue Lieferanten anlegen
    for (const a of angebote.value) {
      if (a.lieferantId) continue;
      const vorhanden = lieferanten.value.find((l) => l.name.toLowerCase() === a.neuName.trim().toLowerCase());
      a.lieferantId = vorhanden?.id ?? (await call('cnc_one.api.stammdaten.speichern', { art: 'lieferant', daten: { name: a.neuName.trim(), aktiv: true } })).id;
    }
    const positionen = benutzt.value.map((i) => {
      const g = gruppen.value[i];
      return { teil: { name: g.name.trim(), material: g.material }, abmessung: g.abmessungText, einheit: g.einheit, mengen: [Math.ceil(Number(g.menge))] };
    });
    const neu = await store.freiAnlegen({
      art: 'Material', lieferanten: angebote.value.map((a) => ({ name: a.lieferantId })), positionen,
      notiz: 'Aus eingelesenen Angeboten (Anfrage lief außerhalb von CNC One)',
    });
    if (!neu?.length) return;
    // je Lieferant: PDF anhängen und die Preise erfassen
    for (const [ai, a] of angebote.value.entries()) {
      const la = neu[ai];
      const keys = (zu.value[ai] ?? []).map((gi) => (gi >= 0 && benutzt.value.includes(gi) ? `frei:${benutzt.value.indexOf(gi) + 1}` : ''));
      const { preise, je } = preiseFuer(la, a.r.positionen, keys);
      if (!preise.length) continue;
      let pdf = '';
      try { pdf = (await hochladen(a.file, { doctype: 'Lieferantenanfrage', docname: la.id }))?.file_url ?? ''; } catch (e) { ui.toast(`${a.name}: ${e.message}`, 'warn'); }
      const n = a.r.nebenkosten;
      await store.antwortErfassen(la.id, {
        angebotsnr: a.r.kopf.angebotsnr || '', gueltigBis: a.r.kopf.gueltigBis || '',
        lieferzeit: (a.r.positionen.map((o) => o.liefertermin).find(Boolean) ?? '').slice(0, 140),
        preise, nebenkosten: Math.round(n.reduce((s, x) => s + x.betrag, 0) * 100) / 100,
        nebenkostenText: n.map((x) => `${x.text || 'Nebenkosten'}: ${eur(x.betrag)}`).join('\n'), pdf,
        daten: {
          datei: a.name, kopf: a.r.kopf, netto: a.r.netto, stimmt: a.r.stimmt, nebenkosten: n, je,
          positionen: a.r.positionen.map((o, k) => ({ ...o, zuordnung: keys[k] })),
        },
      });
    }
    emit('schliessen');
    router.push(`/anfragen/vergleich/${neu[0].vorgang}`);
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    legtAn.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <!-- Ablegen selbst behandeln: sonst landen die PDFs zusätzlich in der Workbench (globales Ablegen im Fenster) -->
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-3 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')" @dragover.prevent @drop.prevent.stop="abgelegt">
      <Transition name="pop" appear>
        <div class="card flex max-h-[95vh] w-[min(1300px,98vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
            <div>
              <h2 class="text-base font-semibold">Angebote einlesen und vergleichen</h2>
              <p class="text-xs text-mute">Auch ohne Anfrage aus CNC One: PDFs der Lieferanten hierher ziehen. Gleiche Positionen werden zusammengefasst, danach öffnet sich der Vergleich.</p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="min-h-0 flex-1 space-y-4 overflow-auto p-5">
            <label class="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line px-4 py-5 text-sm text-mute hover:border-accent/50 hover:text-ink">
              <Loader v-if="liest" :size="17" class="animate-spin" /><FileUp v-else :size="17" />
              {{ liest ? 'PDFs werden gelesen …' : angebote.length ? 'Weitere Angebots-PDFs hinzufügen' : 'Angebots-PDFs wählen oder hierher ziehen (mehrere auf einmal)' }}
              <input type="file" accept="application/pdf,.pdf" multiple class="hidden" @change="gewaehlt" />
            </label>

            <!-- je Angebot: Lieferant und Erkanntes -->
            <section v-for="(a, ai) in angebote" :key="ai" class="rounded-xl border border-line">
              <div class="flex flex-wrap items-center gap-3 px-3 py-2.5">
                <FileText :size="17" class="shrink-0 text-accent" />
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-medium">{{ a.name }}</div>
                  <div class="text-xs text-mute tnum">
                    Angebot {{ a.r.kopf.angebotsnr || '?' }} · {{ a.r.positionen.filter((o) => !o.option).length }} Position{{ a.r.positionen.filter((o) => !o.option).length === 1 ? '' : 'en' }}<template v-if="a.r.positionen.some((o) => o.option)"> + Optionen</template>
                    <template v-if="a.r.summeNebenkosten"> · Nebenkosten {{ eur(a.r.summeNebenkosten) }}</template>
                    <span v-if="a.r.netto != null" class="ml-1" :class="a.r.stimmt ? 'text-ok' : 'text-warn'"><CheckCircle2 v-if="a.r.stimmt" :size="12" class="inline" /><AlertTriangle v-else :size="12" class="inline" /> Netto {{ eur(a.r.netto) }}</span>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <Truck :size="15" class="text-mute" />
                  <select v-model="a.lieferantId" class="field !w-52 !py-1 text-sm" @change="lieferantGeaendert(a)">
                    <option value="">Neuer Lieferant …</option>
                    <option v-for="l in lieferanten" :key="l.id" :value="l.id">{{ l.name }}</option>
                  </select>
                  <input v-if="!a.lieferantId" v-model="a.neuName" class="field !w-52 !py-1 text-sm" placeholder="Name des Lieferanten" />
                </div>
                <button class="grid h-7 w-7 place-items-center rounded-md text-mute hover:bg-surface2" :title="a.offen ? 'Positionen zuklappen' : 'Positionen zeigen und zuordnen'" @click="a.offen = !a.offen"><ChevronDown :size="15" class="transition" :class="a.offen ? 'rotate-180' : ''" /></button>
                <button class="grid h-7 w-7 place-items-center rounded-md text-mute hover:bg-surface2" title="Angebot entfernen" @click="entfernen(ai)"><Trash2 :size="14" /></button>
              </div>
              <div v-if="a.offen" class="space-y-1.5 border-t border-line px-3 py-2.5">
                <p v-if="!a.r.positionen.length" class="text-xs text-warn">Keine Positionen erkannt. Das Angebot lässt sich später bei der Lieferantenanfrage mit „Angebot aus PDF einlesen“ anlernen.</p>
                <div v-for="(o, k) in a.r.positionen" :key="k" class="grid items-center gap-2 text-xs sm:grid-cols-[1fr_auto_220px]">
                  <span class="min-w-0 truncate"><span v-if="o.option" class="mr-1 rounded-full bg-warn/15 px-1.5 text-warn">Option</span><span class="text-mute">Pos {{ o.pos || '–' }}</span> {{ [o.werkstoff, o.zustand].filter(Boolean).join(' ') }} {{ [o.form, o.abmessung].filter(Boolean).join(' ') }} · {{ mengen(o) }}</span>
                  <span class="tnum">{{ o.betrag != null ? eur(o.betrag) : '–' }}</span>
                  <select v-model="zu[ai][k]" class="field !py-0.5 !text-xs">
                    <option :value="-1">– nicht übernehmen –</option>
                    <option v-for="(g, gi) in gruppen" :key="gi" :value="gi">{{ g.name }}</option>
                  </select>
                </div>
              </div>
            </section>

            <!-- gemeinsame Positionen: was wir (gedanklich) angefragt haben -->
            <section v-if="benutzt.length" class="overflow-x-auto rounded-xl border border-line">
              <div class="border-b border-line px-3 py-2 text-sm font-semibold">Positionen für den Vergleich <span class="font-normal text-mute">· wie angefragt; je Lieferant der Betrag laut PDF</span></div>
              <table class="w-full min-w-[720px] text-sm">
                <thead><tr class="text-left text-xs text-mute"><th class="min-w-[340px] px-3 py-1.5 font-medium">Bezeichnung</th><th class="px-2 py-1.5 font-medium">Menge</th><th v-for="(a, ai) in angebote" :key="ai" class="px-2 py-1.5 text-right font-medium">{{ lieferantText(a) }}</th></tr></thead>
                <tbody>
                  <tr v-for="gi in benutzt" :key="gi" class="border-t border-line/60 align-top">
                    <td class="px-3 py-1.5"><input v-model="gruppen[gi].name" class="field !py-1 text-sm" :title="gruppen[gi].name" /></td>
                    <td class="px-2 py-1.5">
                      <div class="flex gap-1">
                        <input v-model.number="gruppen[gi].menge" type="number" min="1" class="field !w-20 !py-1 text-sm tnum" />
                        <select v-model="gruppen[gi].einheit" class="field !w-20 !py-1 text-sm"><option>Stk</option><option>kg</option><option>m</option></select>
                      </div>
                    </td>
                    <td v-for="(a, ai) in angebote" :key="ai" class="px-2 py-1.5 text-right tnum">
                      <template v-if="zelle(ai, gi)"><div class="font-medium">{{ eur(zelle(ai, gi).betrag) }}</div><div class="text-[11px] text-mute">{{ mengen(zelle(ai, gi).o) }}</div></template>
                      <span v-else class="text-mute">–</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="px-3 py-2 text-xs text-mute">Der Vergleich rechnet je Lieferant den Preis je Einheit (Betrag ÷ angebotene Menge) auf die Menge hier hoch; abweichende Mengen werden markiert.</p>
            </section>
          </div>

          <footer class="flex flex-wrap items-center justify-end gap-2 border-t border-line px-6 py-3">
            <span v-if="fehler && angebote.length" class="mr-auto text-xs text-warn">{{ fehler }}</span>
            <button class="btn" @click="emit('schliessen')">Abbrechen</button>
            <button class="btn btn-primary" :disabled="!!fehler || legtAn || liest > 0" @click="anlegen"><Scale :size="15" /> {{ legtAn ? 'Wird angelegt …' : 'Anlegen und vergleichen' }}</button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
