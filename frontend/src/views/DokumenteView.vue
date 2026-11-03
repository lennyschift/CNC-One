<script setup>
// Dokumente: alle Dateien der App an einer Stelle (Zeichnungen, Modelle, Angebote, Rechnungen, Mail-Anhänge …).
// Suche auch im Text der Dateien, Filter nach Art und Kunde, Vorschau, Bezüge zu den Belegen, Schlagworte und Notiz.
import { ref, computed, watch, onMounted, defineAsyncComponent } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { watchDebounced } from '@vueuse/core';
import { Search, FolderOpen, FileText, Box, Receipt, FileCode2, Mail, File, ScrollText, RefreshCw, Download, Tag, Link2, Truck, Bell, ShoppingBag } from '@lucide/vue';
import CustomerCombobox from '../components/CustomerCombobox.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';
import { zahl } from '../lib/format.js';

const DrawingViewer = defineAsyncComponent(() => import('../components/DrawingViewer.vue'));
const ModelViewer = defineAsyncComponent(() => import('../components/ModelViewer.vue'));

const route = useRoute();
const router = useRouter();
const ui = useUi();

const ARTEN = ['Zeichnung', '3D-Modell', 'Angebot', 'Rechnung', 'E-Rechnung (XML)', 'Lieferschein', 'Mahnung', 'Bestellung', 'Mail-Anhang', 'Sonstiges'];
const ICON = { Zeichnung: FileText, '3D-Modell': Box, Angebot: ScrollText, Rechnung: Receipt, 'E-Rechnung (XML)': FileCode2, Lieferschein: Truck, Mahnung: Bell, Bestellung: ShoppingBag, 'Mail-Anhang': Mail, Sonstiges: File };
const BELEG = {
  Bauteil: { label: 'Bauteil', weg: () => '/stammdaten/bauteile' },
  Angebot: { label: 'Angebot', weg: (id) => `/angebote/${id}` },
  Auftrag: { label: 'Auftrag', weg: (id) => `/auftraege/${id}` },
  Rechnung: { label: 'Rechnung', weg: (id) => `/rechnungen/${id}` },
  Lieferschein: { label: 'Lieferschein', weg: (id) => `/lieferscheine/${id}` },
  Mahnung: { label: 'Mahnung', weg: (id) => `/mahnungen/${id}` },
  'Mail Anfrage': { label: 'Mail', weg: (id) => `/posteingang/${id}` },
  Kunde: { label: 'Kunde', weg: () => '/stammdaten/kunden' },
};

const suche = ref(route.query.q ?? '');
const art = ref(route.query.art ?? '');
const kunde = ref(route.query.kunde ?? '');
const liste = ref([]);
const arten = ref({});
const laedt = ref(false);

async function laden() {
  laedt.value = true;
  try {
    const r = await call('cnc_one.api.dokumente.liste', { suche: suche.value, art: art.value, kunde: kunde.value });
    liste.value = r.dokumente;
    arten.value = r.arten;
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    laedt.value = false;
  }
}
onMounted(laden);
watchDebounced(suche, laden, { debounce: 300 });
watch([art, kunde], laden);
watch([suche, art, kunde], () => router.replace({ query: { ...route.query, q: suche.value || undefined, art: art.value || undefined, kunde: kunde.value || undefined } }));

async function aktualisieren() {
  try {
    const r = await call('cnc_one.api.dokumente.abgleichen');
    ui.toast(`Abgeglichen: ${r.neu} neu, ${r.geaendert} geändert, ${r.entfernt} entfernt`, 'ok');
    laden();
  } catch (e) { ui.toast(e.message, 'warn'); }
}

const id = computed(() => route.params.id || '');
const gewaehlt = computed(() => liste.value.find((d) => d.id === id.value) ?? null);
function waehlen(d) { router.replace({ path: `/dokumente/${d.id}`, query: route.query }); }

// Schlagworte und Notiz: beim Verlassen des Feldes speichern
const pflege = ref({ schlagworte: '', notiz: '' });
watch(gewaehlt, (d) => { pflege.value = { schlagworte: d?.schlagworte ?? '', notiz: d?.notiz ?? '' }; }, { immediate: true });
async function speichern(feld) {
  const d = gewaehlt.value;
  if (!d || pflege.value[feld] === d[feld]) return;
  try {
    const neu = await call('cnc_one.api.dokumente.pflegen', { id: d.id, [feld]: pflege.value[feld] });
    Object.assign(d, neu);
    pflege.value[feld] = neu[feld];
  } catch (e) { ui.toast(e.message, 'warn'); }
}

const anzahl = computed(() => Object.values(arten.value).reduce((a, b) => a + b, 0));
const groesse = (b) => (!b ? '' : b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`);
const datum = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const vorschau = (d) => (d.endung === 'pdf' ? 'pdf' : ['stp', 'step'].includes(d.endung) ? '3d' : ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(d.endung) ? 'bild' : '');
</script>

<template>
  <div class="mx-auto max-w-[1600px]">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <label class="relative min-w-[280px] flex-1">
        <Search :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
        <input v-model="suche" class="field !pl-9" placeholder="Suchen: Teilenummer, Kunde, Beleg, Schlagwort oder Text im Dokument …" />
      </label>
      <div class="w-64"><CustomerCombobox v-model="kunde" /></div>
      <button v-if="kunde" class="text-xs text-mute hover:text-ink" @click="kunde = ''">alle Kunden</button>
      <button class="btn" title="Register mit den Dateien abgleichen" @click="aktualisieren"><RefreshCw :size="15" :class="laedt ? 'animate-spin' : ''" /> Aktualisieren</button>
    </div>

    <div class="mb-4 flex flex-wrap gap-1.5">
      <button class="chip" :class="!art ? 'chip-an' : ''" @click="art = ''">Alle <span class="tnum opacity-70">{{ anzahl }}</span></button>
      <button v-for="a in ARTEN.filter((x) => arten[x] || art === x)" :key="a" class="chip" :class="art === a ? 'chip-an' : ''" @click="art = art === a ? '' : a">
        <component :is="ICON[a]" :size="13" /> {{ a }} <span class="tnum opacity-70">{{ arten[a] ?? 0 }}</span>
      </button>
    </div>

    <div class="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_560px]">
      <section class="card overflow-hidden">
        <div v-if="!liste.length && !laedt" class="flex flex-col items-center px-6 py-14 text-center text-sm text-mute">
          <FolderOpen :size="34" :stroke-width="1.4" class="mb-3" />
          <span class="font-medium text-ink">Keine Dokumente gefunden</span>
          <span class="mt-1 text-xs">Andere Suche oder Filter versuchen.</span>
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="border-b border-line text-left text-[11px] uppercase tracking-wide text-mute">
              <th class="px-4 py-2 font-medium">Dokument</th>
              <th class="hidden px-2 py-2 font-medium md:table-cell">Kunde</th>
              <th class="hidden px-2 py-2 font-medium lg:table-cell">Bezüge</th>
              <th class="px-4 py-2 text-right font-medium">Datum</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in liste" :key="d.id" class="cursor-pointer border-b border-line last:border-0 hover:bg-surface2" :class="d.id === id ? 'bg-accent-soft/60' : ''" @click="waehlen(d)">
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-2.5">
                  <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface2 text-accent"><component :is="ICON[d.art] ?? File" :size="16" /></span>
                  <div class="min-w-0">
                    <div class="truncate font-medium">{{ d.titel }}</div>
                    <div class="truncate text-xs text-mute">
                      {{ d.art }}<template v-if="d.teilenummer"> · {{ d.teilenummer }}</template><template v-if="d.revision"> · Rev. {{ d.revision }}</template><template v-if="d.fassung === 'Ältere Fassung'"> · ältere Fassung</template> · {{ groesse(d.groesse) }}
                    </div>
                    <div v-if="d.treffer" class="mt-0.5 line-clamp-2 text-[11px] text-mute">„{{ d.treffer }}“</div>
                  </div>
                </div>
              </td>
              <td class="hidden truncate px-2 py-2.5 text-xs md:table-cell">{{ d.kundeName }}</td>
              <td class="hidden px-2 py-2.5 lg:table-cell">
                <div class="flex flex-wrap gap-1">
                  <span v-for="b in d.bezuege.slice(0, 3)" :key="b.typ + b.id" class="rounded-full bg-surface2 px-2 py-0.5 text-[11px] text-mute">{{ BELEG[b.typ]?.label ?? b.typ }} {{ b.typ === 'Bauteil' ? b.bezeichnung.split(' · ')[1] ?? b.id : b.bezeichnung.split(' · ')[0] }}</span>
                  <span v-if="d.bezuege.length > 3" class="text-[11px] text-mute">+{{ d.bezuege.length - 3 }}</span>
                </div>
              </td>
              <td class="whitespace-nowrap px-4 py-2.5 text-right text-xs text-mute tnum">{{ datum(d.datum) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <aside v-if="gewaehlt" class="space-y-4 xl:sticky xl:top-0">
        <section class="card p-4">
          <div class="mb-3 flex items-start gap-3">
            <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><component :is="ICON[gewaehlt.art] ?? File" :size="19" /></span>
            <div class="min-w-0 flex-1">
              <h2 class="break-words text-sm font-semibold">{{ gewaehlt.titel }}</h2>
              <p class="text-xs text-mute">{{ gewaehlt.art }} · {{ datum(gewaehlt.datum) }} · {{ groesse(gewaehlt.groesse) }}<template v-if="gewaehlt.revision"> · Rev. {{ gewaehlt.revision }} ({{ gewaehlt.fassung === 'Aktuell' ? 'aktuell' : 'ältere Fassung' }})</template></p>
            </div>
            <a :href="gewaehlt.url" :download="gewaehlt.titel" class="btn !py-1 text-xs" title="Herunterladen"><Download :size="14" /></a>
          </div>
          <div class="h-[420px]">
            <DrawingViewer v-if="vorschau(gewaehlt) === 'pdf'" :key="gewaehlt.url" :url="gewaehlt.url" :name="gewaehlt.titel" />
            <ModelViewer v-else-if="vorschau(gewaehlt) === '3d'" :key="gewaehlt.url" :url="gewaehlt.url" :name="gewaehlt.titel" nur-ansehen />
            <img v-else-if="vorschau(gewaehlt) === 'bild'" :src="gewaehlt.url" :alt="gewaehlt.titel" class="h-full w-full rounded-xl object-contain" />
            <div v-else class="grid h-full place-items-center rounded-xl border-2 border-dashed border-line text-sm text-mute">Keine Vorschau für .{{ gewaehlt.endung }}, bitte herunterladen</div>
          </div>
        </section>

        <section class="card space-y-3 p-4">
          <div>
            <h3 class="mb-1.5 flex items-center gap-1.5 text-xs font-semibold"><Link2 :size="13" class="text-accent" /> Gehört zu</h3>
            <div class="flex flex-wrap gap-1.5">
              <RouterLink v-for="b in gewaehlt.bezuege" :key="b.typ + b.id" :to="BELEG[b.typ]?.weg(b.id) ?? '#'" class="rounded-lg bg-surface2 px-2.5 py-1 text-xs hover:text-accent">
                <span class="text-mute">{{ BELEG[b.typ]?.label ?? b.typ }}</span> {{ b.bezeichnung }}
              </RouterLink>
            </div>
            <p v-if="gewaehlt.kundeName" class="mt-1.5 text-xs text-mute">Kunde: <span class="text-ink">{{ gewaehlt.kundeName }}</span></p>
          </div>
          <label class="block"><span class="label mb-1 flex items-center gap-1"><Tag :size="12" /> Schlagworte</span><input v-model="pflege.schlagworte" class="field" placeholder="z. B. Erstmuster, eilig" @blur="speichern('schlagworte')" @keydown.enter="speichern('schlagworte')" /></label>
          <label class="block"><span class="label mb-1 block">Notiz</span><textarea v-model="pflege.notiz" rows="3" class="field" placeholder="Hinweis zum Dokument" @blur="speichern('notiz')" /></label>
        </section>
      </aside>
      <div v-else class="card hidden flex-col items-center justify-center p-14 text-sm text-mute xl:flex"><FolderOpen :size="30" :stroke-width="1.4" class="mb-2" /> Dokument links auswählen</div>
    </div>
  </div>
</template>

<style scoped>
.chip { display: inline-flex; align-items: center; gap: 0.35rem; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); padding: 0.25rem 0.7rem; font-size: 0.78rem; color: var(--mute); transition: all 0.15s; }
.chip:hover { color: var(--ink); }
.chip-an { border-color: transparent; background: var(--accent-soft); color: var(--accent); }
</style>
