<script setup>
// Was das System für einen Kunden angelernt hat, lesbar und einzeln löschbar:
// Zeichnungserkennung (je Angabe bis zu vier Regeln, die erste passende gilt) und die Spalten der Tabellen in Anfrage-Mails
// (je Absender, dazu der Standard des Kunden).
import { ref, onMounted } from 'vue';
import { Brain, ScanText, Table2, Trash2, Loader } from '@lucide/vue';
import { call } from '../data/api.js';
import { FELDER } from '../lib/erkennung.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ kunde: { type: String, required: true }, darf: { type: Boolean, default: false } });
const ui = useUi();
const d = ref(null);

async function laden() {
  try { d.value = await call('cnc_one.api.mail.angelernt', { kunde: props.kunde }); } catch (e) { ui.toast(e.message, 'warn'); }
}
onMounted(laden);

const ROLLEN = { teilenummer: 'Teilenummer', menge: 'Menge', liefertermin: 'Liefertermin' };
const pz = (x) => `${Math.round(x * 100)} %`;
// Eine Regel in Worten
function regelText(r) {
  if (r.bereich) return `feste Stelle auf der Seite: ${pz(r.bereich.x)} von links, ${pz(r.bereich.y)} von oben`;
  if (r.dx !== undefined && r.dx !== null) {
    const wo = Math.abs(r.dy) < 0.004 ? 'rechts daneben' : r.dy > 0 && Math.abs(r.dx) < 0.03 ? 'darunter' : 'versetzt daneben';
    return `beim Stichwort „${r.stichwort}“, Wert ${wo} (gemerkter Abstand)`;
  }
  return `beim Stichwort „${r.stichwort}“, Wert rechts daneben oder darunter`;
}

async function zeichnungVergessen(feld) {
  if (!confirm(feld ? `Angelernte Regeln für „${FELDER[feld]?.label ?? feld}“ löschen?` : 'Alle angelernten Regeln der Zeichnungserkennung dieses Kunden löschen?')) return;
  try { await call('cnc_one.api.zeichnung.vergessen', { kunde: props.kunde, feld: feld || null }); await laden(); ui.toast('Gelöscht', 'ok'); } catch (e) { ui.toast(e.message, 'warn'); }
}
async function tabelleVergessen(kontakt = '') {
  if (!confirm(kontakt ? `Angelernte Spalten für ${kontakt} löschen?` : 'Standard-Spalten des Kunden löschen?')) return;
  try { d.value = await call('cnc_one.api.mail.tabellenvorlage_entfernen', { kunde: props.kunde, kontakt }); ui.toast('Gelöscht', 'ok'); } catch (e) { ui.toast(e.message, 'warn'); }
}
const spaltenText = (s) => Object.entries(s ?? {}).map(([r, k]) => `${ROLLEN[r] ?? r} = „${k}“`).join(' · ');
const geaendert = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
</script>

<template>
  <section>
    <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold"><Brain :size="15" class="text-accent" /> Angelernt</h3>
    <div v-if="!d" class="flex items-center gap-2 text-sm text-mute"><Loader :size="14" class="animate-spin" /> Lädt …</div>
    <div v-else class="space-y-3 text-sm">
      <div class="rounded-xl border border-line p-3">
        <div class="mb-2 flex items-center gap-2">
          <ScanText :size="15" class="text-mute" /><span class="font-medium">Zeichnungserkennung</span>
          <span v-if="d.zeichnung.geaendert" class="text-xs text-mute">zuletzt {{ geaendert(d.zeichnung.geaendert) }}</span>
          <button v-if="darf && Object.keys(d.zeichnung.felder).length" type="button" class="ml-auto text-xs text-mute hover:text-ink" @click="zeichnungVergessen('')">alle löschen</button>
        </div>
        <p v-if="!Object.keys(d.zeichnung.felder).length" class="text-xs text-mute">Nichts angelernt – es gilt die allgemeine Erkennung.</p>
        <div v-for="(regeln, feld) in d.zeichnung.felder" :key="feld" class="flex items-start gap-3 border-t border-line py-2 first:border-0">
          <span class="w-36 shrink-0 font-medium">{{ FELDER[feld]?.label ?? feld }}</span>
          <ol class="min-w-0 flex-1 list-decimal space-y-0.5 pl-4 text-xs text-mute"><li v-for="(r, i) in regeln" :key="i">{{ regelText(r) }}</li></ol>
          <button v-if="darf" type="button" class="text-mute hover:text-ink" title="Regeln dieser Angabe löschen" @click="zeichnungVergessen(feld)"><Trash2 :size="14" /></button>
        </div>
      </div>
      <div class="rounded-xl border border-line p-3">
        <div class="mb-2 flex items-center gap-2"><Table2 :size="15" class="text-mute" /><span class="font-medium">Tabellen in Anfrage-Mails</span></div>
        <p v-if="!Object.keys(d.tabellen.kunde).length && !Object.keys(d.tabellen.kontakte).length" class="text-xs text-mute">Nichts angelernt – Spalten werden an den Überschriften erkannt.</p>
        <div v-for="(spalten, adresse) in d.tabellen.kontakte" :key="adresse" class="flex items-start gap-3 border-t border-line py-2 first:border-0">
          <span class="w-36 shrink-0 truncate font-medium" :title="adresse">{{ adresse }}</span>
          <span class="min-w-0 flex-1 text-xs text-mute">{{ spaltenText(spalten) }}</span>
          <button v-if="darf" type="button" class="text-mute hover:text-ink" title="Löschen" @click="tabelleVergessen(adresse)"><Trash2 :size="14" /></button>
        </div>
        <div v-if="Object.keys(d.tabellen.kunde).length" class="flex items-start gap-3 border-t border-line py-2">
          <span class="w-36 shrink-0 font-medium">Standard des Kunden</span>
          <span class="min-w-0 flex-1 text-xs text-mute">{{ spaltenText(d.tabellen.kunde) }} <span class="block">(gilt für Absender ohne eigene Spalten)</span></span>
          <button v-if="darf" type="button" class="text-mute hover:text-ink" title="Löschen" @click="tabelleVergessen('')"><Trash2 :size="14" /></button>
        </div>
      </div>
    </div>
  </section>
</template>
