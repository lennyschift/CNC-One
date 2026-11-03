<script setup>
// Archiv: Aufbewahrungsfristen je Dokumentart. Abgeschlossene Dokumente sind bis zum Fristende nicht löschbar.
import { ref, onMounted } from 'vue';
import { Archive, Check, RotateCcw } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';

const ui = useUi();
const fristen = ref([]);
const darf = ref(false);
const speichert = ref(false);

onMounted(async () => {
  try {
    const r = await call('cnc_one.api.dokumente.fristen');
    fristen.value = r.fristen;
    darf.value = r.darf;
  } catch (e) { ui.toast(e.message, 'warn'); }
});

async function speichern() {
  speichert.value = true;
  try {
    const r = await call('cnc_one.api.dokumente.fristen_speichern', { fristen: fristen.value });
    fristen.value = r.fristen;
    ui.toast('Aufbewahrungsfristen gespeichert', 'ok');
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    speichert.value = false;
  }
}
const ABSCHLUSS = {
  Rechnung: 'festgeschrieben', 'E-Rechnung (XML)': 'festgeschrieben', Angebot: 'gesendet', Lieferschein: 'geliefert oder storniert',
  Mahnung: 'versendet oder zurückgezogen', 'Mail-Anhang': 'Angebot zur Anfrage erstellt', Zeichnung: 'Revision bestellt', '3D-Modell': 'Revision bestellt',
  Bestellung: 'mit dem Auftrag', Sonstiges: '',
};
</script>

<template>
  <div class="mx-auto max-w-[1000px]">
    <StammNav />
    <p class="mb-4 text-sm text-mute">
      Abgeschlossene Dokumente lassen sich bis zum Ende ihrer Aufbewahrungsfrist nicht löschen. Die Frist beginnt mit dem Schluss des Kalenderjahres,
      in dem das Dokument entstanden ist (§ 147 Abs. 4 AO). Die Vorbelegung bitte mit dem Steuerberater abstimmen.
    </p>
    <section class="card overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-line text-left text-[11px] uppercase tracking-wide text-mute">
            <th class="px-4 py-2 font-medium">Dokumentart</th>
            <th class="px-2 py-2 font-medium">Abgeschlossen, wenn</th>
            <th class="w-28 px-2 py-2 font-medium">Jahre</th>
            <th class="px-4 py-2 font-medium">Grundlage</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in fristen" :key="f.art" class="border-b border-line last:border-0">
            <td class="px-4 py-2 font-medium"><Archive :size="13" class="mr-1.5 inline text-accent" />{{ f.art }}</td>
            <td class="px-2 py-2 text-xs text-mute">{{ ABSCHLUSS[f.art] }}</td>
            <td class="px-2 py-2">
              <div class="flex items-center gap-1">
                <input v-model.number="f.jahre" type="number" min="0" max="50" class="field !w-16 !py-1 tnum" :disabled="!darf" />
                <button v-if="darf && f.jahre !== f.vorbelegt" class="text-mute hover:text-ink" :title="`Vorbelegung: ${f.vorbelegt} Jahre`" @click="f.jahre = f.vorbelegt"><RotateCcw :size="13" /></button>
              </div>
              <div v-if="!f.jahre" class="mt-0.5 text-[10px] text-mute">keine Pflicht</div>
            </td>
            <td class="px-4 py-2"><input v-model="f.grundlage" class="field !py-1 text-xs" :disabled="!darf" /></td>
          </tr>
        </tbody>
      </table>
    </section>
    <div class="mt-4 flex justify-end">
      <span v-if="!darf" class="mr-auto text-xs text-mute">Ändern dürfen Administratoren und die Buchhaltung.</span>
      <button v-if="darf" class="btn btn-primary" :disabled="speichert" @click="speichern"><Check :size="15" /> Speichern</button>
    </div>
  </div>
</template>
