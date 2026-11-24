<script setup>
// Teilefamilie anlegen oder bearbeiten: Bezeichnung, Unterschied der Varianten und die Bauteile mit ihrer Variante
// (z. B. „Gewindelänge 16“). Jedes Bauteil bleibt einzeln bestellbar; ein Bauteil gehört zu höchstens einer Familie.
import { ref, reactive, computed, onMounted } from 'vue';
import { X, Save, Trash2, Network, Search, Plus, Unlink } from '@lucide/vue';
import PartImage from './PartImage.vue';
import { call } from '../data/api.js';
import { useStammdaten } from '../stores/stammdaten.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({
  familie: { type: Object, default: null }, // bestehende Familie (familie_ui) oder null
  vorschlag: { type: Object, default: null }, // { bezeichnung, zeichnungsnr, bauteile: [{ id, teilenummer, name, variante, … }] }
});
const emit = defineEmits(['schliessen', 'gespeichert']);
const ui = useUi();
const stamm = useStammdaten();
onMounted(() => stamm.laden('bauteil'));

const start = props.familie ?? props.vorschlag ?? {};
const f = reactive({
  id: props.familie?.id ?? '', bezeichnung: start.bezeichnung ?? '', merkmal: start.merkmal ?? '', zeichnungsnr: start.zeichnungsnr ?? '', notiz: start.notiz ?? '',
  bauteile: (start.varianten ?? start.bauteile ?? []).map((b) => ({ ...b })),
});
// Bauteile hinzufügen: Suche über Teilenummer, Bezeichnung, Zeichnung
const suche = ref('');
const treffer = computed(() => {
  const q = suche.value.trim().toLowerCase();
  if (q.length < 2) return [];
  const drin = new Set(f.bauteile.map((b) => b.id));
  return (stamm.listen.bauteil ?? []).filter((b) => !drin.has(b.id) && `${b.teilenummer} ${b.name} ${b.zeichnungsnr}`.toLowerCase().includes(q)).slice(0, 8);
});
function hinzu(b) { f.bauteile.push({ id: b.id, teilenummer: b.teilenummer, name: b.name, vorschaubild: b.vorschaubild, variante: '', anderswo: b.teilefamilie && b.teilefamilie !== f.id ? b.teilefamilie : '' }); suche.value = ''; }
const gueltig = computed(() => f.bezeichnung.trim() && f.bauteile.length >= 2);

const speichert = ref(false);
async function speichern() {
  speichert.value = true;
  try {
    const r = await call('cnc_one.api.teilefamilie.speichern', { daten: JSON.parse(JSON.stringify({ ...f, bauteile: f.bauteile.map((b) => ({ id: b.id, variante: b.variante })) })) });
    ui.toast(`Teilefamilie „${r.bezeichnung}“ gespeichert`, 'ok');
    stamm.laden('bauteil', true);
    emit('gespeichert', r);
  } catch (e) { ui.toast(e.message, 'warn'); } finally { speichert.value = false; }
}
const frage = ref(false);
async function aufloesen() {
  if (!frage.value) { frage.value = true; setTimeout(() => { frage.value = false; }, 4000); return; }
  try {
    await call('cnc_one.api.teilefamilie.aufloesen', { id: f.id });
    ui.toast('Teilefamilie aufgelöst, die Bauteile bleiben', 'ok');
    stamm.laden('bauteil', true);
    emit('gespeichert', null);
  } catch (e) { ui.toast(e.message, 'warn'); }
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <div class="card flex max-h-[92vh] w-[min(820px,96vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center justify-between border-b border-line px-6 py-4">
          <div><h2 class="flex items-center gap-2 text-base font-semibold"><Network :size="16" class="text-accent" /> {{ f.id ? `Teilefamilie ${f.id}` : 'Neue Teilefamilie' }}</h2><p class="text-xs text-mute">Varianten eines Teils verknüpfen. Jede Variante bleibt ein eigenes Bauteil und einzeln bestellbar.</p></div>
          <button type="button" class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
        </header>
        <div class="min-h-0 flex-1 space-y-4 overflow-auto px-6 py-5">
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block"><span class="label mb-1 block">Bezeichnung</span><input v-model="f.bezeichnung" class="field" placeholder="z. B. Gewindebolzen M8" /></label>
            <label class="block"><span class="label mb-1 block">Unterschied der Varianten</span><input v-model="f.merkmal" class="field" placeholder="z. B. Gewindelänge" /></label>
            <label class="block"><span class="label mb-1 block">Gemeinsame Zeichnung</span><input v-model="f.zeichnungsnr" class="field" placeholder="optional" /></label>
            <label class="block"><span class="label mb-1 block">Notiz</span><input v-model="f.notiz" class="field" placeholder="optional" /></label>
          </div>
          <section>
            <div class="label mb-2">Varianten ({{ f.bauteile.length }})</div>
            <div class="divide-y divide-line rounded-xl border border-line">
              <div v-for="(b, i) in f.bauteile" :key="b.id" class="flex items-center gap-3 px-3 py-2">
                <PartImage :teil="b" :groesse="36" />
                <div class="min-w-0 flex-1"><div class="truncate text-sm font-medium tnum">{{ b.teilenummer }}</div><div class="truncate text-xs text-mute">{{ b.name || '–' }}<span v-if="b.anderswo" class="text-warn"> · wechselt aus {{ b.anderswo }}</span></div></div>
                <input v-model="b.variante" class="field !w-44 !py-1.5 text-sm" :placeholder="f.merkmal ? `${f.merkmal} …` : 'Variante, z. B. L = 16'" />
                <button type="button" class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:text-accent" title="Aus der Familie nehmen" @click="f.bauteile.splice(i, 1)"><Trash2 :size="14" /></button>
              </div>
              <p v-if="!f.bauteile.length" class="px-3 py-3 text-xs text-mute">Noch keine Bauteile.</p>
            </div>
            <div class="relative mt-2">
              <Search :size="14" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
              <input v-model="suche" class="field !pl-8 text-sm" placeholder="Bauteil hinzufügen: Teilenummer, Bezeichnung oder Zeichnung …" />
              <div v-if="treffer.length" class="absolute inset-x-0 top-full z-10 mt-1 max-h-64 overflow-auto rounded-xl border border-line bg-surface shadow-xl">
                <button v-for="b in treffer" :key="b.id" type="button" class="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-surface2" @click="hinzu(b)">
                  <PartImage :teil="b" :groesse="28" /><span class="tnum font-medium">{{ b.teilenummer }}</span><span class="min-w-0 flex-1 truncate text-mute">{{ b.name }}</span><span v-if="b.teilefamilie" class="text-[11px] text-mute">in {{ b.teilefamilie }}</span><Plus :size="14" class="text-accent" />
                </button>
              </div>
            </div>
            <p class="mt-1.5 text-[11px] text-mute">Ein Bauteil gehört zu höchstens einer Familie: kommt es aus einer anderen, wechselt es hierher.</p>
          </section>
        </div>
        <footer class="flex items-center gap-2 border-t border-line bg-surface2 px-6 py-4">
          <button v-if="f.id" type="button" class="btn" :class="frage ? '!border-accent !bg-accent-soft !text-accent' : '!text-mute'" @click="aufloesen"><Unlink :size="15" /> {{ frage ? 'Wirklich auflösen?' : 'Familie auflösen' }}</button>
          <span class="ml-auto text-xs text-mute">{{ f.bauteile.length < 2 ? 'mindestens zwei Bauteile' : '' }}</span>
          <button type="button" class="btn" @click="emit('schliessen')">Abbrechen</button>
          <button type="button" class="btn btn-primary" :disabled="!gueltig || speichert" :class="!gueltig || speichert ? 'pointer-events-none opacity-40' : ''" @click="speichern"><Save :size="15" /> Speichern</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
