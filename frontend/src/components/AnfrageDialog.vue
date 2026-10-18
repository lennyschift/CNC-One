<script setup>
// Lieferantenanfrage für Fremdvergaben aus der Workbench. Pro Lieferant entsteht eine Anfrage mit eigener Nummer
// und beliebig vielen Positionen, damit ein Lieferant mehrere Bauteile in einer Anfrage bekommt.
import { ref, reactive, computed, onMounted } from 'vue';
import { X, Send, Plus, Mail } from '@lucide/vue';
import PartImage from './PartImage.vue';
import NumField from './NumField.vue';
import { repo } from '../data/repo.js';
import { fremdPositionen, mailText, nummer } from '../lib/anfrage.js';
import { useAnfragen } from '../stores/anfragen.js';

const props = defineProps({
  teile: { type: Array, required: true },
  // optional: Position (Arbeitsgang-Id), die vorab angehakt ist
  vorgewaehlt: { type: String, default: '' },
  // Bezug zum Angebot bzw. Entwurf: { entwurfId, angebotId, kundeName }
  bezug: { type: Object, default: () => ({}) },
});
const emit = defineEmits(['schliessen']);
const anfragen = useAnfragen();

const lieferanten = ref([]);
const gewaehlt = reactive({});
const notiz = ref('');

// Alle Fremdvergaben des Angebots als wählbare Positionen
// Schon angefragte Fremdvergaben sind nicht vorgewählt, damit nichts doppelt rausgeht.
const positionen = reactive(fremdPositionen(props.teile).map((p) => {
  const schon = anfragen.fuerArbeitsgang(p.ag.id);
  return {
    key: p.key, teil: p.teil, ag: p.ag, mengen: [...p.mengen], schon,
    an: props.vorgewaehlt ? p.ag.id === props.vorgewaehlt : !schon.length,
  };
}));

onMounted(async () => {
  lieferanten.value = await repo.lieferanten.liste();
  for (const p of positionen.filter((x) => x.an)) {
    const l = lieferanten.value.find((x) => x.name === p.ag.lieferant);
    if (l) gewaehlt[l.id] = true;
  }
});

const aktiv = computed(() => positionen.filter((p) => p.an));
const auswahl = computed(() => lieferanten.value.filter((l) => gewaehlt[l.id]));
const vorschau = computed(() => mailText({
  id: nummer(anfragen.liste.length + 1),
  notiz: notiz.value,
  positionen: aktiv.value.map((p) => ({ key: p.key, agName: p.ag.name, mengen: p.mengen, teil: p.teil })),
}));

function mengeHinzu(p) { p.mengen.push((Math.max(0, ...p.mengen) || 5) * 2); }
function mengeWeg(p, i) { if (p.mengen.length > 1) p.mengen.splice(i, 1); }
const bereit = computed(() => auswahl.value.length && aktiv.value.length);

function senden() {
  anfragen.anlegen({
    lieferanten: auswahl.value,
    notiz: notiz.value,
    bezug: props.bezug,
    positionen: aktiv.value.map((p) => ({
      teil: p.teil,
      agId: p.ag.id,
      agName: p.ag.name,
      mengen: [...new Set(p.mengen.map((m) => Math.floor(Number(m)) || 0).filter((m) => m > 0))].sort((a, b) => a - b),
    })),
  });
  emit('schliessen');
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[92vh] w-[min(1040px,96vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div><h2 class="text-base font-semibold">Lieferantenanfrage</h2><p class="text-xs text-mute">Eine Anfrage pro Lieferant, mit allen gewählten Bauteilen</p></div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="grid min-h-0 flex-1 gap-6 overflow-auto px-6 py-5 lg:grid-cols-[1.15fr_1fr]">
            <div class="space-y-5">
              <div>
                <div class="label mb-2">Was soll angefragt werden?</div>
                <div class="space-y-2">
                  <div v-for="p in positionen" :key="p.key" class="rounded-xl border p-3 transition" :class="p.an ? 'border-accent/60 bg-accent-soft/40' : 'border-line'">
                    <div class="flex items-center gap-3">
                      <input v-model="p.an" type="checkbox" class="h-4 w-4 accent-[var(--accent)]" />
                      <PartImage :teil="p.teil" :groesse="40" />
                      <div class="min-w-0 flex-1">
                        <div class="truncate text-sm font-medium">{{ p.ag.name || 'Fremdvergabe' }}</div>
                        <div class="truncate text-xs text-mute">{{ p.teil.name }} · {{ p.teil.teilenummer || 'ohne Teilenummer' }}</div>
                        <div v-if="p.schon.length" class="mt-0.5 truncate text-[11px] text-warn">schon angefragt: {{ p.schon.map((s) => `${s.id} (${s.lieferantName}, ${s.status})`).join('; ') }}</div>
                      </div>
                    </div>
                    <div v-if="p.an" class="mt-3 flex flex-wrap items-end gap-2 pl-7">
                      <div v-for="(m, i) in p.mengen" :key="i" class="relative"><NumField v-model="p.mengen[i]" unit="Stk" :decimals="0" :min="1" class="w-28" />
                        <button v-if="p.mengen.length > 1" class="absolute -right-1.5 -top-1.5 grid h-4 w-4 place-items-center rounded-full bg-line text-mute hover:bg-accent hover:text-white" @click="mengeWeg(p, i)"><X :size="10" /></button>
                      </div>
                      <button class="btn !px-2.5" title="Menge hinzufügen" @click="mengeHinzu(p)"><Plus :size="15" /></button>
                    </div>
                  </div>
                  <p v-if="!positionen.length" class="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-mute">Kein Bauteil hat eine Fremdvergabe. Lege am Bauteil einen Arbeitsgang „Fremdvergabe“ an.</p>
                </div>
              </div>

              <div>
                <div class="label mb-2">An welche Lieferanten?</div>
                <div class="space-y-1.5">
                  <label v-for="l in lieferanten" :key="l.id" class="flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm transition" :class="gewaehlt[l.id] ? 'border-accent bg-accent-soft' : 'border-line hover:border-mute'">
                    <input v-model="gewaehlt[l.id]" type="checkbox" class="accent-[var(--accent)]" />
                    <span class="flex-1">{{ l.name }}</span><span class="text-xs text-mute">{{ l.leistung }}</span>
                  </label>
                </div>
                <p class="mt-1.5 text-xs text-mute">Jeder Lieferant bekommt eine eigene Anfragenummer mit allen gewählten Positionen.</p>
              </div>

              <label class="block"><span class="label mb-1 block">Hinweis an die Lieferanten</span><textarea v-model="notiz" rows="2" class="field resize-y" placeholder="z. B. Farbe, Maskierung, Termin …" /></label>
            </div>

            <div>
              <div class="label mb-2 flex items-center gap-1.5"><Mail :size="13" /> Vorschau des Anschreibens</div>
              <div class="rounded-xl border border-line bg-surface2 p-4 text-[13px] leading-relaxed">
                <div class="mb-2 font-medium">{{ aktiv.length ? vorschau.betreff : '–' }}</div>
                <pre v-if="aktiv.length" class="whitespace-pre-wrap font-sans text-mute">{{ vorschau.text }}</pre>
                <p v-else class="text-mute">Bitte mindestens eine Position wählen.</p>
              </div>
              <p class="mt-2 text-xs text-mute">Die Anfragenummer steht im Betreff und im Text. Der Lieferant nennt sie in seinem Angebot, so lässt es sich später zuordnen.</p>
            </div>
          </div>

          <footer class="flex items-center justify-between gap-4 border-t border-line bg-surface2 px-6 py-4">
            <span class="text-sm text-mute">{{ aktiv.length }} Position{{ aktiv.length === 1 ? '' : 'en' }} · {{ auswahl.length }} Lieferant{{ auswahl.length === 1 ? '' : 'en' }}</span>
            <div class="flex gap-2">
              <button class="btn" @click="emit('schliessen')">Abbrechen</button>
              <button class="btn btn-primary" :disabled="!bereit" :class="!bereit ? 'pointer-events-none opacity-40' : ''" @click="senden"><Send :size="16" /> Anfrage{{ auswahl.length > 1 ? 'n' : '' }} anlegen</button>
            </div>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
