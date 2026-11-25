<script setup>
// Regeln fürs Schwärzen der Kundenzeichnungen: ein Standard für alle Kunden und je Kunde ein eigener Regelsatz (der
// Standard gilt immer mit). Dazu kommen automatisch die Begriffe aus den Stammdaten des Kunden (Name, Kürzel,
// Ansprechpartner, Mail-Domain). Alles nur Vorschläge — vor dem Versand prüft immer ein Mensch.
import { ref, computed, onMounted, watch } from 'vue';
import { ShieldCheck, Plus, Save, Trash2, Upload, Info, Image as ImageIcon } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import Toggle from '../components/Toggle.vue';
import { call, hochladen } from '../data/api.js';
import { useUi } from '../stores/ui.js';
import { useSchwaerzen } from '../stores/schwaerzen.js';

const ui = useUi();
const sw = useSchwaerzen();
const saetze = ref([]);
const gewaehlt = ref(null);
const f = ref(null); // Bearbeitungsstand
const kundenBegriffe = ref([]);
const speichert = ref(false);

const LISTEN = [
  { key: 'directKeywords', label: 'Stichwörter', text: 'werden selbst geschwärzt (Projektnamen, Werksbezeichnungen …)' },
  { key: 'labelRightKeywords', label: 'Beschriftung → Werte rechts daneben', text: 'z. B. „Gez.“, „Gepr.“: Name und Datum daneben' },
  { key: 'headerKeywords', label: 'Kopfzeile → Text darunter', text: 'z. B. „Name“, „Abt.“ im Schriftfeld' },
  { key: 'changeTableKeywords', label: 'Änderungstabelle: ganze Spalte darunter', text: 'muss auch als Kopfzeile eingetragen sein; obere 35 % der Seite' },
  { key: 'columnAboveKeywords', label: 'Änderungstabelle: Spalte darüber', text: 'für Tabellen, die nach oben wachsen; untere 35 % der Seite' },
];
const ZONEN = { all: 'überall', top: 'oben', bottom: 'unten', left: 'links', right: 'rechts', corners: 'Ecken' };

async function laden() {
  saetze.value = await call('cnc_one.api.schwaerzen.regelsaetze');
  if (!gewaehlt.value) gewaehlt.value = saetze.value[0]?.id ?? null;
  oeffnen(saetze.value.find((s) => s.id === gewaehlt.value) ?? saetze.value[0]);
}
function oeffnen(s) {
  if (!s) return;
  gewaehlt.value = s.id;
  f.value = { ...JSON.parse(JSON.stringify(s)), texte: Object.fromEntries(LISTEN.map((l) => [l.key, (s.regeln[l.key] ?? []).join('\n')])) };
}
onMounted(laden);
watch(() => f.value?.kundeId, async (k) => {
  kundenBegriffe.value = k ? (await call('cnc_one.api.schwaerzen.regeln_fuer', { kunde: k })).kundenBegriffe : [];
}, { immediate: true });

function neu() {
  f.value = { id: '', bezeichnung: '', kundeId: '', aktiv: true, standard: false, regeln: { logos: [], logoOptions: {}, detectEmail: true, detectPhone: false, logoThreshold: 0.45 }, texte: Object.fromEntries(LISTEN.map((l) => [l.key, ''])) };
  gewaehlt.value = null;
}
async function speichern() {
  speichert.value = true;
  try {
    const regeln = { ...f.value.regeln };
    for (const l of LISTEN) regeln[l.key] = f.value.texte[l.key].split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    const r = await call('cnc_one.api.schwaerzen.regelsatz_speichern', { daten: { id: f.value.id, bezeichnung: f.value.bezeichnung, kundeId: f.value.kundeId, aktiv: f.value.aktiv, regeln } });
    gewaehlt.value = r.id;
    sw.regelnVergessen();
    ui.toast(`Regelsatz „${r.bezeichnung}“ gespeichert`, 'ok');
    await laden();
  } catch (e) { ui.toast(e.message, 'warn'); } finally { speichert.value = false; }
}
async function loeschen() {
  if (!confirm(`Regelsatz „${f.value.bezeichnung}“ löschen?`)) return;
  try { await call('cnc_one.api.schwaerzen.regelsatz_loeschen', { id: f.value.id }); gewaehlt.value = null; sw.regelnVergessen(); await laden(); } catch (e) { ui.toast(e.message, 'warn'); }
}

// Logos: Bild (PNG/JPEG, am besten mit 300 dpi ausgeschnitten) als private Datei am Regelsatz
const datei = ref(null);
async function logoHochladen(e) {
  const file = e.target.files?.[0];
  e.target.value = '';
  if (!file || !f.value.id) return;
  if (!/image\/(png|jpeg)/.test(file.type)) { ui.toast('Bitte ein PNG- oder JPEG-Bild wählen', 'warn'); return; }
  try {
    const up = await hochladen(file, { doctype: 'Schwaerzregelsatz', docname: f.value.id });
    const groesse = await new Promise((res, rej) => { const img = new Image(); img.onload = () => res([img.naturalWidth, img.naturalHeight]); img.onerror = rej; img.src = up.file_url; });
    f.value.regeln.logos = [...(f.value.regeln.logos ?? []), { id: up.name, name: file.name.replace(/\.\w+$/, ''), dataUrl: up.file_url, width: groesse[0], height: groesse[1], enabled: true }];
    ui.toast('Logo hinzugefügt – bitte speichern', 'ok');
  } catch (err) { ui.toast(err.message || 'Logo ließ sich nicht hochladen', 'warn'); }
}
const opt = (id) => (f.value.regeln.logoOptions[id] ??= {});
const titel = computed(() => (f.value?.id ? f.value.bezeichnung : 'Neuer Regelsatz'));
</script>

<template>
  <div class="mx-auto max-w-[1200px]">
    <StammNav />
    <div class="mb-4 flex flex-wrap items-start gap-3">
      <p class="mr-auto max-w-[760px] text-sm text-mute">Was beim Schwärzen der Kundenzeichnungen automatisch vorgeschlagen wird. Der Standard gilt für alle Kunden, ein Regelsatz je Kunde kommt dazu. Name, Kürzel, Ansprechpartner und Mail-Domain des Kunden werden immer gesucht. Vor dem Versand an Partner prüft immer ein Mensch das Ergebnis.</p>
      <button class="btn btn-primary" @click="neu"><Plus :size="16" /> Regelsatz für einen Kunden</button>
    </div>
    <div class="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <div class="card h-fit p-2">
        <button v-for="s in saetze" :key="s.id" type="button" class="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm" :class="gewaehlt === s.id ? 'bg-accent-soft text-accent' : 'hover:bg-surface2'" @click="oeffnen(s)">
          <ShieldCheck :size="15" /><span class="min-w-0 flex-1 truncate"><span class="font-medium">{{ s.bezeichnung }}</span><span class="block truncate text-[11px] text-mute">{{ s.standard ? 'für alle Kunden' : s.kundeName || 'ohne Kunde' }}{{ s.aktiv ? '' : ' · inaktiv' }}</span></span>
        </button>
      </div>

      <div v-if="f" class="card space-y-5 p-5">
        <div class="flex flex-wrap items-end gap-3">
          <label class="block min-w-[220px] flex-1"><span class="label mb-1 block">Bezeichnung</span><input v-model="f.bezeichnung" class="field" :disabled="!!f.id" :placeholder="titel" /></label>
          <div v-if="!f.standard" class="min-w-[260px] flex-1"><CustomerCombobox v-model="f.kundeId" /></div>
          <Toggle v-model="f.aktiv" klein label="Aktiv" />
        </div>
        <p v-if="f.standard" class="flex items-start gap-1.5 rounded-xl bg-surface2 px-3 py-2 text-xs text-mute"><Info :size="13" class="mt-0.5 shrink-0" /> Der Standard gilt immer, auch zusätzlich zum Regelsatz eines Kunden. Kundennamen gehören nicht hierher, sondern in den Regelsatz des Kunden (oder sie kommen von selbst aus den Stammdaten).</p>
        <div v-if="kundenBegriffe.length" class="rounded-xl border border-line px-3 py-2 text-xs"><span class="font-medium">Automatisch aus den Stammdaten des Kunden:</span> <span class="text-mute">{{ kundenBegriffe.join(' · ') }}</span></div>

        <div class="grid gap-4 md:grid-cols-2">
          <label v-for="l in LISTEN" :key="l.key" class="block"><span class="label block">{{ l.label }}</span><span class="mb-1 block text-[11px] text-mute">{{ l.text }} · eins je Zeile</span>
            <textarea v-model="f.texte[l.key]" rows="5" class="field resize-y font-mono text-xs" />
          </label>
          <div class="space-y-2">
            <Toggle v-model="f.regeln.detectEmail" klein label="E-Mail-Adressen schwärzen" />
            <Toggle v-model="f.regeln.detectPhone" klein label="Telefonnummern schwärzen (Teilenummern können ähnlich aussehen)" />
          </div>
        </div>

        <section>
          <div class="mb-2 flex items-center gap-2"><ImageIcon :size="15" class="text-accent" /><span class="text-sm font-semibold">Logos</span>
            <label class="btn ml-auto !py-1 text-xs" :class="f.id ? '' : 'pointer-events-none opacity-40'" :title="f.id ? 'PNG oder JPEG, am besten mit 300 dpi aus einer Zeichnung ausgeschnitten' : 'Erst speichern'"><Upload :size="13" /> Logo hinzufügen<input ref="datei" type="file" accept="image/png,image/jpeg" class="hidden" @change="logoHochladen" /></label>
          </div>
          <div class="space-y-2">
            <div v-for="(l, i) in f.regeln.logos" :key="l.id" class="flex flex-wrap items-center gap-3 rounded-xl border border-line p-2">
              <img :src="l.dataUrl" alt="" class="h-12 max-w-[120px] rounded bg-white object-contain" />
              <input v-model="l.name" class="field !w-40 !py-1 text-xs" />
              <label class="flex items-center gap-1 text-xs text-mute">Schwelle <input v-model.number="opt(l.id).threshold" type="number" min="0.3" max="0.95" step="0.05" class="field !w-20 !py-1 text-xs" :placeholder="String(f.regeln.logoThreshold)" /></label>
              <label class="flex items-center gap-1 text-xs text-mute">Suchen <select v-model="opt(l.id).zone" class="field !w-auto !py-1 text-xs"><option v-for="(t, z) in ZONEN" :key="z" :value="z">{{ t }}</option></select></label>
              <label class="flex items-center gap-1 text-xs text-mute">höchstens <input v-model.number="opt(l.id).maxHits" type="number" min="1" max="10" class="field !w-16 !py-1 text-xs" placeholder="3" /> je Seite</label>
              <Toggle v-model="l.enabled" klein label="aktiv" />
              <button type="button" class="ml-auto text-mute hover:text-accent" title="Logo entfernen" @click="f.regeln.logos.splice(i, 1)"><Trash2 :size="14" /></button>
            </div>
            <p v-if="!f.regeln.logos?.length" class="text-xs text-mute">Keine Logos. Logos werden auf jeder Seite gesucht (auch in A1), Treffer sind Vorschläge.</p>
          </div>
        </section>

        <div class="flex gap-2 border-t border-line pt-4">
          <button v-if="f.id && !f.standard" type="button" class="btn !text-mute" @click="loeschen"><Trash2 :size="15" /> Löschen</button>
          <button type="button" class="btn btn-primary ml-auto" :disabled="speichert || (!f.id && !f.bezeichnung.trim())" @click="speichern"><Save :size="15" /> Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>
