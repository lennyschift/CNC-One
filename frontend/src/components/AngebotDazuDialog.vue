<script setup>
// Ein weiteres Angebot kommt zu einem laufenden Vergleich dazu (Angebote kommen zeitlich versetzt): PDF wählen, der
// Lieferant wird erkannt (oder gewählt bzw. neu angelegt). Ist er noch nicht im Vorgang, bekommt er dort eine Anfrage mit
// denselben Positionen (ohne Mail). Danach geht das bekannte „Angebot aus PDF einlesen“ mit dieser Datei auf.
import { ref, computed } from 'vue';
import { X, FileUp, FileText, Loader, Truck, ArrowRight } from '@lucide/vue';
import { call } from '../data/api.js';
import { repo, stammdatenRoh } from '../data/repo.js';
import { pdfjs } from '../lib/pdf.js';
import { textAusSeite } from '../lib/zeichnungText.js';
import { angebotLesen, lieferantErkennen, lieferantVorschlag } from '../lib/lieferangebot.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ vorgang: { type: String, required: true }, anfragen: { type: Array, required: true } });
const emit = defineEmits(['schliessen', 'weiter']);
const store = useAnfragen();
const ui = useUi();

const lieferanten = ref([]);
repo.lieferanten.liste().then((l) => { lieferanten.value = (l ?? []).filter((x) => x.aktiv !== false); }).catch(() => {});
const eigene = String(stammdatenRoh().firma?.firmenname ?? '').split(/\s+/).filter((w) => w.length >= 4 && !/^(gmbh|mbh)$/i.test(w));

const datei = ref(null); // { name, file }
const lieferantId = ref('');
const neuName = ref('');
const liest = ref(false);
const legtAn = ref(false);

async function lesen(file) {
  if (!file || liest.value) return;
  liest.value = true;
  try {
    const aufgabe = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
    const doc = await aufgabe.promise;
    const s = [];
    for (let i = 1; i <= Math.min(doc.numPages, 10); i++) s.push(await textAusSeite(await doc.getPage(i)));
    aufgabe.destroy();
    const r = angebotLesen(s);
    datei.value = { name: file.name, file };
    lieferantId.value = lieferantErkennen(r.text, lieferanten.value) || '';
    neuName.value = lieferantId.value ? '' : lieferantVorschlag(r.text, eigene);
  } catch (e) {
    ui.toast(`${file.name}: ${e?.message || 'nicht lesbar'}`, 'warn');
  } finally {
    liest.value = false;
  }
}
const istPdf = (f) => /\.pdf$/i.test(f.name) || f.type === 'application/pdf';
function gewaehlt(e) { lesen([...(e.target.files ?? [])].find(istPdf)); e.target.value = ''; }
function abgelegt(e) { lesen([...(e.dataTransfer?.files ?? [])].find(istPdf)); }

// schon im Vorgang? Dann geht das Angebot zu seiner bestehenden Anfrage
const bestehend = computed(() => props.anfragen.find((a) => a.lieferantId === lieferantId.value) ?? null);
const fehler = computed(() => (!datei.value ? 'Bitte das Angebots-PDF wählen.' : !lieferantId.value && !neuName.value.trim() ? 'Bitte den Lieferanten wählen oder einen Namen eintragen.' : ''));

async function weiter() {
  if (fehler.value || legtAn.value) return;
  legtAn.value = true;
  try {
    let id = lieferantId.value;
    if (!id) {
      const vorhanden = lieferanten.value.find((l) => l.name.toLowerCase() === neuName.value.trim().toLowerCase());
      id = vorhanden?.id ?? (await call('cnc_one.api.stammdaten.speichern', { art: 'lieferant', daten: { name: neuName.value.trim(), aktiv: true } })).id;
    }
    const anfrage = bestehend.value ?? (await store.lieferantDazu(props.vorgang, id));
    if (anfrage) emit('weiter', { anfrage, datei: datei.value });
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    legtAn.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <!-- Ablegen selbst behandeln: sonst landet das PDF zusätzlich in der Workbench (globales Ablegen im Fenster) -->
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-3 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')" @dragover.prevent @drop.prevent.stop="abgelegt">
      <Transition name="pop" appear>
        <div class="card flex w-[min(560px,96vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
            <div>
              <h2 class="text-base font-semibold">Weiteres Angebot zum Vergleich</h2>
              <p class="text-xs text-mute">Vorgang {{ vorgang }} · die Positionen bleiben wie angefragt</p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="space-y-4 p-5">
            <label class="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-line px-4 py-4 text-sm hover:border-accent/50">
              <Loader v-if="liest" :size="18" class="animate-spin text-mute" /><FileText v-else-if="datei" :size="18" class="shrink-0 text-accent" /><FileUp v-else :size="18" class="text-mute" />
              <span class="min-w-0 flex-1 truncate" :class="datei ? 'font-medium' : 'text-mute'">{{ liest ? 'PDF wird gelesen …' : datei ? datei.name : 'Angebots-PDF wählen oder hierher ziehen' }}</span>
              <span v-if="datei && !liest" class="text-xs text-accent">andere Datei</span>
              <input type="file" accept="application/pdf,.pdf" class="hidden" @change="gewaehlt" />
            </label>

            <div v-if="datei" class="space-y-2">
              <div class="label">Lieferant</div>
              <div class="flex flex-wrap items-center gap-2">
                <Truck :size="15" class="text-mute" />
                <select v-model="lieferantId" class="field !w-60 !py-1.5 text-sm">
                  <option value="">Neuer Lieferant …</option>
                  <option v-for="l in lieferanten" :key="l.id" :value="l.id">{{ l.name }}</option>
                </select>
                <input v-if="!lieferantId" v-model="neuName" class="field !w-56 !py-1.5 text-sm" placeholder="Name des Lieferanten" />
              </div>
              <p class="text-xs text-mute">
                <template v-if="bestehend">{{ bestehend.lieferantName }} ist schon im Vergleich: das Angebot kommt zu seiner Anfrage {{ bestehend.id }}<template v-if="bestehend.antwort"> und ersetzt die bisher erfassten Preise</template>.</template>
                <template v-else>Der Lieferant kommt mit denselben Positionen zum Vorgang dazu. Es wird keine Mail verschickt.</template>
              </p>
            </div>
          </div>

          <footer class="flex flex-wrap items-center justify-end gap-2 border-t border-line px-6 py-3">
            <span v-if="fehler && datei" class="mr-auto text-xs text-warn">{{ fehler }}</span>
            <button class="btn" @click="emit('schliessen')">Abbrechen</button>
            <button class="btn btn-primary" :disabled="!!fehler || legtAn || liest" @click="weiter"><ArrowRight :size="15" /> {{ legtAn ? 'Einen Moment …' : 'Weiter: Preise zuordnen' }}</button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
