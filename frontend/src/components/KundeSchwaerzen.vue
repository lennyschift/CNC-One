<script setup>
// Schwärzen je Kunde, direkt in der Kundenmaske: Stichwörter, Beschriftungen, Kopfzeilen, Änderungstabelle und Logos
// (Bild hochladen, hierher ziehen oder mit Strg+V aus einem Ausschnitt einfügen). Gespeichert als Regelsatz des Kunden
// (api/schwaerzen.py); der Standard gilt immer zusätzlich, Name/Kürzel/Ansprechpartner/Mail-Domain kommen von selbst dazu.
import { ref, onMounted } from 'vue';
import { Save, Trash2, Upload, Image as ImageIcon, Info, ChevronDown, ClipboardPaste } from '@lucide/vue';
import Toggle from './Toggle.vue';
import { call, hochladen } from '../data/api.js';
import { useUi } from '../stores/ui.js';
import { useSchwaerzen } from '../stores/schwaerzen.js';

const props = defineProps({
  kundeId: { type: String, required: true },
  kundeName: { type: String, default: '' },
  darf: { type: Boolean, default: true },
});
const ui = useUi();
const sw = useSchwaerzen();

const LISTEN = [
  { key: 'directKeywords', label: 'Stichwörter', text: 'werden selbst geschwärzt: Projektnamen, Werke, Abteilungen, interne Kürzel …', haupt: true },
  { key: 'labelRightKeywords', label: 'Beschriftung → Wert rechts daneben', text: 'z. B. „Gez.“, „Gepr.“, „Datum“: der Name daneben wird geschwärzt' },
  { key: 'headerKeywords', label: 'Kopfzeile → Text darunter', text: 'z. B. „Name“, „Abt.“ im Schriftfeld' },
  { key: 'changeTableKeywords', label: 'Änderungstabelle: Spalte darunter', text: 'auch als Kopfzeile eintragen; obere 35 % der Seite' },
  { key: 'columnAboveKeywords', label: 'Änderungstabelle: Spalte darüber', text: 'für Tabellen, die nach oben wachsen; untere 35 % der Seite' },
];
const ZONEN = { all: 'überall', top: 'oben', bottom: 'unten', left: 'links', right: 'rechts', corners: 'Ecken' };

const f = ref(null);
const begriffe = ref([]);
const speichert = ref(false);
const mehr = ref(false);
const geaendert = ref(false);

function ausSatz(s) {
  return { ...JSON.parse(JSON.stringify(s)), texte: Object.fromEntries(LISTEN.map((l) => [l.key, (s.regeln[l.key] ?? []).join('\n')])) };
}
async function laden() {
  const saetze = await call('cnc_one.api.schwaerzen.regelsaetze');
  const s = saetze.find((x) => x.kundeId === props.kundeId);
  f.value = s ? ausSatz(s) : ausSatz({ id: '', bezeichnung: props.kundeName || props.kundeId, kundeId: props.kundeId, aktiv: true, regeln: { logos: [], logoOptions: {}, detectEmail: true, detectPhone: false, logoThreshold: 0.45 } });
  mehr.value = LISTEN.some((l) => !l.haupt && f.value.texte[l.key]);
  begriffe.value = (await call('cnc_one.api.schwaerzen.regeln_fuer', { kunde: props.kundeId })).kundenBegriffe ?? [];
  geaendert.value = false;
}
onMounted(() => laden().catch((e) => ui.toast(e.message, 'warn')));

async function speichern(still = false) {
  speichert.value = true;
  try {
    const regeln = { ...f.value.regeln };
    for (const l of LISTEN) regeln[l.key] = f.value.texte[l.key].split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    const r = await call('cnc_one.api.schwaerzen.regelsatz_speichern', { daten: { id: f.value.id, bezeichnung: f.value.bezeichnung || props.kundeName || props.kundeId, kundeId: props.kundeId, aktiv: f.value.aktiv, regeln } });
    f.value.id = r.id;
    f.value.bezeichnung = r.bezeichnung;
    sw.regelnVergessen();
    geaendert.value = false;
    if (!still) ui.toast('Schwärz-Regeln des Kunden gespeichert', 'ok');
    return true;
  } catch (e) { ui.toast(e.message, 'warn'); return false; } finally { speichert.value = false; }
}

// Logos: Datei wählen, hierher ziehen oder einfügen (Strg+V eines Bildschirm-Ausschnitts)
async function logoDazu(file) {
  if (!file || !props.darf) return;
  if (!/image\/(png|jpeg)/.test(file.type)) { ui.toast('Bitte ein PNG- oder JPEG-Bild', 'warn'); return; }
  if (!f.value.id && !(await speichern(true))) return;
  try {
    const name = file.name && file.name !== 'image.png' ? file.name : `Logo ${props.kundeName || ''}.png`.trim();
    const up = await hochladen(new File([file], name, { type: file.type }), { doctype: 'Schwaerzregelsatz', docname: f.value.id });
    const groesse = await new Promise((res, rej) => { const img = new Image(); img.onload = () => res([img.naturalWidth, img.naturalHeight]); img.onerror = rej; img.src = up.file_url; });
    f.value.regeln.logos = [...(f.value.regeln.logos ?? []), { id: up.name, name: name.replace(/\.\w+$/, ''), dataUrl: up.file_url, width: groesse[0], height: groesse[1], enabled: true }];
    await speichern(true);
    ui.toast('Logo hinzugefügt', 'ok');
  } catch (err) { ui.toast(err.message || 'Logo ließ sich nicht hochladen', 'warn'); }
}
function gewaehlt(e) { const file = e.target.files?.[0]; e.target.value = ''; logoDazu(file); }
function abgelegt(e) { logoDazu([...(e.dataTransfer?.files ?? [])].find((x) => x.type.startsWith('image/'))); }
function eingefuegt(e) {
  const item = [...(e.clipboardData?.items ?? [])].find((x) => x.type.startsWith('image/'));
  if (!item) return;
  e.preventDefault();
  logoDazu(item.getAsFile());
}
const opt = (id) => (f.value.regeln.logoOptions[id] ??= {});
function logoWeg(i) { f.value.regeln.logos.splice(i, 1); geaendert.value = true; }
// Die Kundenmaske speichert die Schwärz-Regeln mit, wenn sie geändert wurden
defineExpose({ speichernWennGeaendert: async () => (geaendert.value ? speichern(true) : true) });
</script>

<template>
  <div v-if="f" class="space-y-4" @input="geaendert = true" @change="geaendert = true">
    <p class="flex items-start gap-1.5 rounded-xl bg-surface2 px-3 py-2 text-xs text-mute"><Info :size="13" class="mt-0.5 shrink-0" /> Vorschläge fürs Schwärzen der Zeichnungen dieses Kunden, bevor sie an Partner gehen. Der Standard (Stammdaten → Schwärzen) gilt immer zusätzlich. Vor dem Versand prüft immer ein Mensch.</p>
    <div v-if="begriffe.length" class="rounded-xl border border-line px-3 py-2 text-xs"><span class="font-medium">Wird immer gesucht (aus den Stammdaten):</span> <span class="text-mute">{{ begriffe.join(' · ') }}</span></div>

    <div class="grid gap-4 md:grid-cols-2">
      <label class="block"><span class="label block">{{ LISTEN[0].label }}</span><span class="mb-1 block text-[11px] text-mute">{{ LISTEN[0].text }} · eins je Zeile</span>
        <textarea v-model="f.texte.directKeywords" rows="6" class="field resize-y font-mono text-xs" :disabled="!darf" />
      </label>
      <label class="block"><span class="label block">{{ LISTEN[1].label }}</span><span class="mb-1 block text-[11px] text-mute">{{ LISTEN[1].text }} · eins je Zeile</span>
        <textarea v-model="f.texte.labelRightKeywords" rows="6" class="field resize-y font-mono text-xs" :disabled="!darf" />
      </label>
    </div>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-accent hover:underline" @click="mehr = !mehr"><ChevronDown :size="13" class="transition" :class="mehr ? 'rotate-180' : ''" /> Kopfzeilen und Änderungstabelle</button>
    <div v-if="mehr" class="grid gap-4 md:grid-cols-3">
      <label v-for="l in LISTEN.slice(2)" :key="l.key" class="block"><span class="label block">{{ l.label }}</span><span class="mb-1 block text-[11px] text-mute">{{ l.text }}</span>
        <textarea v-model="f.texte[l.key]" rows="4" class="field resize-y font-mono text-xs" :disabled="!darf" />
      </label>
    </div>
    <div class="flex flex-wrap gap-5">
      <Toggle v-model="f.regeln.detectEmail" klein label="E-Mail-Adressen schwärzen" />
      <Toggle v-model="f.regeln.detectPhone" klein label="Telefonnummern schwärzen" />
    </div>

    <section tabindex="0" class="rounded-xl border border-dashed border-line p-3 outline-none focus:border-accent" @paste="eingefuegt" @dragover.prevent @drop.prevent.stop="abgelegt">
      <div class="mb-2 flex flex-wrap items-center gap-2">
        <ImageIcon :size="15" class="text-accent" /><span class="text-sm font-semibold">Logos des Kunden</span>
        <span class="text-[11px] text-mute"><ClipboardPaste :size="11" class="inline" /> Ausschnitt hier anklicken und Strg+V, Bild hierher ziehen oder</span>
        <label v-if="darf" class="btn ml-auto !py-1 text-xs"><Upload :size="13" /> Bild wählen<input type="file" accept="image/png,image/jpeg" class="hidden" @change="gewaehlt" /></label>
      </div>
      <div class="space-y-2">
        <div v-for="(l, i) in f.regeln.logos" :key="l.id" class="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-2">
          <img :src="l.dataUrl" alt="" class="h-12 max-w-[140px] rounded bg-white object-contain" />
          <input v-model="l.name" class="field !w-40 !py-1 text-xs" :disabled="!darf" />
          <label class="flex items-center gap-1 text-xs text-mute" title="Wie ähnlich ein Fund sein muss (höher = strenger)">Schwelle <input v-model.number="opt(l.id).threshold" type="number" min="0.3" max="0.95" step="0.05" class="field !w-20 !py-1 text-xs" :placeholder="String(f.regeln.logoThreshold ?? 0.45)" /></label>
          <label class="flex items-center gap-1 text-xs text-mute">Suchen <select v-model="opt(l.id).zone" class="field !w-auto !py-1 text-xs"><option v-for="(t, z) in ZONEN" :key="z" :value="z">{{ t }}</option></select></label>
          <Toggle v-model="l.enabled" klein label="aktiv" />
          <button v-if="darf" type="button" class="ml-auto text-mute hover:text-accent" title="Logo entfernen" @click="logoWeg(i)"><Trash2 :size="14" /></button>
        </div>
        <p v-if="!f.regeln.logos?.length" class="text-xs text-mute">Noch kein Logo. Am besten das Logo aus einer Zeichnung des Kunden ausschneiden (Windows: Win+Umschalt+S) und hier einfügen.</p>
      </div>
    </section>

    <div v-if="darf" class="flex items-center gap-2">
      <span v-if="geaendert" class="text-xs text-warn">Nicht gespeichert</span>
      <button type="button" class="btn btn-primary ml-auto" :disabled="speichert" @click="speichern()"><Save :size="15" /> Schwärz-Regeln speichern</button>
    </div>
  </div>
</template>
