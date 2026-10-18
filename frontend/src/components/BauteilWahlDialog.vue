<script setup>
// Bestandsbauteil aus den Stammdaten ins Angebot übernehmen. Zeigt die Bauteile des gewählten Kunden.
import { ref, computed, onMounted } from 'vue';
import { X, Search, Workflow, Hash, Check } from '@lucide/vue';
import PartImage from './PartImage.vue';
import CustomerCombobox from './CustomerCombobox.vue';
import { repo } from '../data/repo.js';
import { call } from '../data/api.js';
import { useAngebot } from '../stores/angebot.js';
import { useUi } from '../stores/ui.js';

const emit = defineEmits(['schliessen']);
const a = useAngebot();
const ui = useUi();

const liste = ref(null);
const materialien = ref([]);
const suche = ref('');
const suchfeld = ref(null);
onMounted(async () => {
  materialien.value = await repo.materialien.liste();
  try { liste.value = await call('cnc_one.api.stammdaten.liste', { art: 'bauteil' }); } catch (e) { ui.toast(e.message, 'warn'); liste.value = []; }
  setTimeout(() => suchfeld.value?.focus(), 0);
});

// Schon im Angebot enthaltene Bestandsbauteile sind nicht noch einmal wählbar
const imAngebot = computed(() => new Set(Object.values(a.zuordnung).map((z) => z.bauteilId)));
const treffer = computed(() => {
  const q = suche.value.trim().toLowerCase();
  return (liste.value ?? []).filter((b) => b.kundeId === a.kopf.kundeId && b.status === 'Aktiv'
    && (!q || `${b.name} ${b.teilenummer} ${b.zeichnungsnr} ${b.material}`.toLowerCase().includes(q)));
});

function waehlen(b) {
  if (imAngebot.value.has(b.id)) return;
  a.ausBauteilHinzufuegen(b, materialien.value);
  emit('schliessen');
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')" @keydown.esc="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[88vh] w-[min(720px,96vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div><h2 class="text-base font-semibold">Bestandsbauteil wählen</h2><p class="text-xs text-mute">Bauteile des Kunden aus den Stammdaten, mit Arbeitsplan</p></div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>
          <div class="space-y-3 border-b border-line px-6 py-4">
            <CustomerCombobox v-model="a.kopf.kundeId" />
            <label class="relative block">
              <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
              <input ref="suchfeld" v-model="suche" class="field !pl-9" placeholder="Bezeichnung, Teilenummer, Zeichnung …" :disabled="!a.kopf.kundeId" />
            </label>
          </div>
          <div class="min-h-0 flex-1 space-y-1.5 overflow-auto p-3">
            <p v-if="!a.kopf.kundeId" class="px-4 py-10 text-center text-sm text-mute">Bitte zuerst den Kunden wählen, dann erscheinen seine Bauteile.</p>
            <p v-else-if="liste === null" class="px-4 py-10 text-center text-sm text-mute">Lädt …</p>
            <p v-else-if="!treffer.length" class="px-4 py-10 text-center text-sm text-mute">{{ suche ? 'Keine Treffer.' : 'Dieser Kunde hat noch keine Bauteile in den Stammdaten. Lege ein neues Bauteil an, es steht danach automatisch dort.' }}</p>
            <button v-for="b in treffer" :key="b.id" class="flex w-full items-center gap-3 rounded-xl border border-line p-3 text-left transition" :class="imAngebot.has(b.id) ? 'cursor-not-allowed opacity-50' : 'hover:border-accent/50 hover:bg-surface2'" @click="waehlen(b)">
              <PartImage :teil="b" :groesse="44" />
              <div class="min-w-0 flex-1">
                <div class="truncate font-medium">{{ b.name || 'Ohne Bezeichnung' }}</div>
                <div class="truncate text-xs text-mute">{{ b.teilenummer }}<template v-if="b.zeichnungsnr"> · Zeichnung {{ b.zeichnungsnr }}</template><template v-if="b.material"> · {{ b.material }}</template></div>
              </div>
              <span v-if="b.seriennummern" class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute"><Hash :size="11" /> Serie</span>
              <span class="inline-flex shrink-0 items-center gap-1 rounded-full bg-surface2 px-2.5 py-1 text-xs text-mute"><Workflow :size="12" /> {{ b.arbeitsgaenge.length ? `${b.arbeitsgaenge.length} Arbeitsgänge` : 'kein Plan' }}</span>
              <span v-if="imAngebot.has(b.id)" class="inline-flex items-center gap-1 text-xs text-ok"><Check :size="13" /> im Angebot</span>
            </button>
          </div>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
