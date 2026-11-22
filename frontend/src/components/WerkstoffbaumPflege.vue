<script setup>
// Pflege einer Stufe des Rohmaterial-Baums in den Stammdaten: Zustände, Ausführungen (je Form), Abmessungen (Reihe je Form)
// oder Materialanforderungen. Anlegen, aktiv/inaktiv, löschen. Inaktive Einträge erscheinen nicht mehr in der Auswahl.
import { ref, computed, onMounted } from 'vue';
import { Plus, Trash2, Check, Eye, EyeOff } from '@lucide/vue';
import FormSymbol from './FormSymbol.vue';
import NumField from './NumField.vue';
import { FORMEN } from '../lib/werkstoffbaum.js';
import { ISO_GRUPPEN } from '../lib/iso.js';
import { useWerkstoff } from '../stores/werkstoff.js';

const props = defineProps({ art: { type: String, required: true }, darf: { type: Boolean, default: false } });
const ws = useWerkstoff();
const alle = ref(null);
async function laden() { alle.value = await ws.neuLaden(true); }
onMounted(laden);

const liste = computed(() => (alle.value ?? { zustaende: [], ausfuehrungen: [], abmessungen: [], anforderungen: [] })[{ zustand: 'zustaende', ausfuehrung: 'ausfuehrungen', abmessung: 'abmessungen', anforderung: 'anforderungen' }[props.art]]);
const nachForm = computed(() => FORMEN.map((f) => ({ ...f, eintraege: liste.value.filter((x) => x.form === f.id) })));
const idVon = (x) => (props.art === 'zustand' ? x.code : props.art === 'anforderung' ? x.name : x.id);

async function setzen(x, werte) { const b = await ws.eintragSetzen(props.art, idVon(x), werte); if (b) alle.value = b; }
async function loeschen(x) { const b = await ws.eintragLoeschen(props.art, idVon(x)); if (b) alle.value = b; }
const umschalten = (x) => setzen(x, { aktiv: x.aktiv ? 0 : 1 });

// ---- Anlegen
const neu = ref({ code: '', text: '', name: '', form: 'Rund', m1: 0, m2: 0, iso: [] });
const formInfo = computed(() => FORMEN.find((f) => f.id === neu.value.form));
async function anlegen() {
  const n = neu.value;
  let ok = null;
  if (props.art === 'zustand') {
    ok = await ws.zustandHinzuOhneWerkstoff(n.code, n.text);
  } else if (props.art === 'ausfuehrung') ok = await ws.ausfuehrungHinzu(n.form, n.name, n.iso.join(' '));
  else if (props.art === 'abmessung') ok = await ws.abmessungHinzu(n.form, n.m1, n.m2);
  else ok = await ws.anforderungHinzu(n.name);
  if (ok) { neu.value = { ...n, code: '', text: '', name: '', m1: 0, m2: 0 }; await laden(); }
}
const gueltig = computed(() => {
  const n = neu.value;
  if (props.art === 'zustand') return !!n.code.trim();
  if (props.art === 'abmessung') return n.m1 > 0 && (!formInfo.value?.m2 || n.m2 > 0);
  return !!n.name.trim();
});
const isoUmschalten = (l, g) => (l.includes(g) ? l.filter((x) => x !== g) : [...l, g]);
</script>

<template>
  <div class="space-y-4">
    <!-- Anlegen -->
    <div v-if="darf" class="card flex flex-wrap items-end gap-3 p-4" @keydown.enter="gueltig && anlegen()">
      <template v-if="art === 'zustand'">
        <label class="w-32"><span class="label mb-1 block">Zustand</span><input v-model="neu.code" class="field" placeholder="z. B. T6511" /></label>
        <label class="min-w-[220px] flex-1"><span class="label mb-1 block">Beschreibung</span><input v-model="neu.text" class="field" placeholder="z. B. lösungsgeglüht, gereckt, warmausgelagert" /></label>
      </template>
      <template v-else-if="art === 'anforderung'">
        <label class="min-w-[260px] flex-1"><span class="label mb-1 block">Anforderung / Nachweis</span><input v-model="neu.name" class="field" placeholder="z. B. Röntgengeprüft" /></label>
      </template>
      <template v-else>
        <div><span class="label mb-1 block">Form</span>
          <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1">
            <button v-for="f in FORMEN" :key="f.id" type="button" class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs" :class="neu.form === f.id ? 'bg-surface font-medium shadow-sm' : 'text-mute hover:text-ink'" @click="neu.form = f.id"><FormSymbol :form="f.id" :groesse="18" /> {{ f.label }}</button>
          </div>
        </div>
        <template v-if="art === 'ausfuehrung'">
          <label class="min-w-[200px] flex-1"><span class="label mb-1 block">Ausführung</span><input v-model="neu.name" class="field" placeholder="z. B. geschliffen h6" /></label>
          <div><span class="label mb-1 block">Nur für ISO-Gruppen (leer = alle)</span>
            <div class="flex gap-1"><button v-for="g in ISO_GRUPPEN" :key="g.code" type="button" class="grid h-8 w-8 place-items-center rounded-lg text-xs font-bold transition" :style="neu.iso.includes(g.code) ? { background: g.farbe, color: g.schrift } : {}" :class="neu.iso.includes(g.code) ? '' : 'border border-line text-mute'" @click="neu.iso = isoUmschalten(neu.iso, g.code)">{{ g.code }}</button></div>
          </div>
        </template>
        <template v-else>
          <div class="w-32"><NumField v-model="neu.m1" :label="formInfo.m1" unit="mm" :decimals="1" /></div>
          <div v-if="formInfo.m2" class="w-32"><NumField v-model="neu.m2" :label="formInfo.m2" unit="mm" :decimals="1" /></div>
        </template>
      </template>
      <button type="button" class="btn btn-primary" :disabled="!gueltig" @click="anlegen"><Plus :size="15" /> Anlegen</button>
    </div>

    <p v-if="alle === null" class="py-8 text-center text-sm text-mute">Lädt …</p>

    <!-- Zustände / Anforderungen als Liste -->
    <div v-else-if="art === 'zustand' || art === 'anforderung'" class="card divide-y divide-line overflow-hidden">
      <div v-for="x in liste" :key="idVon(x)" class="flex items-center gap-3 px-4 py-2" :class="x.aktiv ? '' : 'opacity-50'">
        <span class="w-40 shrink-0 font-semibold">{{ idVon(x) }}</span>
        <input v-if="art === 'zustand'" :value="x.beschreibung" class="field !py-1 text-sm" :disabled="!darf" placeholder="Beschreibung" @change="setzen(x, { beschreibung: $event.target.value })" />
        <span v-else class="flex-1" />
        <template v-if="darf">
          <button type="button" class="text-mute hover:text-ink" :title="x.aktiv ? 'Deaktivieren (nicht mehr auswählbar)' : 'Wieder aktivieren'" @click="umschalten(x)"><Eye v-if="x.aktiv" :size="16" /><EyeOff v-else :size="16" /></button>
          <button type="button" class="text-mute hover:text-accent" title="Löschen" @click="loeschen(x)"><Trash2 :size="15" /></button>
        </template>
      </div>
      <p v-if="!liste.length" class="px-4 py-8 text-center text-sm text-mute">Noch keine Einträge.</p>
    </div>

    <!-- Ausführungen / Abmessungen je Form -->
    <div v-else class="grid gap-3 md:grid-cols-2">
      <section v-for="f in nachForm" :key="f.id" class="card p-4">
        <h3 class="mb-2.5 flex items-center gap-2 text-sm font-semibold"><FormSymbol :form="f.id" :groesse="22" class="text-accent" /> {{ f.label }} <span class="font-normal text-mute">· {{ f.eintraege.length }}</span></h3>
        <div class="flex flex-wrap gap-1.5">
          <span v-for="x in f.eintraege" :key="x.id" class="group inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs tnum" :class="x.aktiv ? '' : 'opacity-40 line-through'">
            {{ art === 'abmessung' ? x.text : x.name }}
            <template v-if="art === 'ausfuehrung' && x.iso.length"><span v-for="g in x.iso" :key="g" class="grid h-4 w-4 place-items-center rounded text-[9px] font-bold" :style="{ background: ISO_GRUPPEN[g]?.farbe, color: ISO_GRUPPEN[g]?.schrift }">{{ g }}</span></template>
            <template v-if="darf">
              <button type="button" class="hidden text-mute hover:text-ink group-hover:inline" :title="x.aktiv ? 'Deaktivieren' : 'Aktivieren'" @click="umschalten(x)"><EyeOff v-if="x.aktiv" :size="12" /><Check v-else :size="12" /></button>
              <button type="button" class="hidden text-mute hover:text-accent group-hover:inline" title="Löschen" @click="loeschen(x)"><Trash2 :size="12" /></button>
            </template>
          </span>
          <span v-if="!f.eintraege.length" class="text-xs text-mute">Noch keine.</span>
        </div>
      </section>
    </div>
  </div>
</template>
