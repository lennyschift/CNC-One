<script setup>
// Freie Lieferantenanfrage ohne Angebot, z. B. für Material: Bezeichnung, Werkstoff, Abmessung, Einheit und Mengen
// selbst eintragen. Pro Lieferant entsteht eine Anfrage mit eigener Nummer und allen Positionen.
// Mit `aendern` (die Anfragen eines Vorgangs) wird eine bestehende Anfrage geändert: es entsteht eine neue Fassung
// (gleiche Nummer mit -1, -2 …), die bisherige bleibt unverändert und gilt als ersetzt.
import { ref, reactive, computed, onMounted } from 'vue';
import { X, Send, Plus, Trash2, Layers, ShieldCheck, PencilLine } from '@lucide/vue';
import RohmaterialPopup from './RohmaterialPopup.vue';
import FormSymbol from './FormSymbol.vue';
import MailMuster from './MailMuster.vue';
import { isoGruppe } from '../lib/iso.js';
import { useWerkstoff } from '../stores/werkstoff.js';
import NumField from './NumField.vue';
import VorlagenChips from './VorlagenChips.vue';
import { repo } from '../data/repo.js';
import { EINHEITEN, materialAbmessung } from '../lib/anfrage.js';
import { useAnfragen } from '../stores/anfragen.js';

const props = defineProps({ aendern: { type: Array, default: null } });
const emit = defineEmits(['schliessen', 'angelegt']);
const anfragen = useAnfragen();
const erste = props.aendern?.[0] ?? null;

const ARTEN = ['Material', 'Fremdvergabe', 'Sonstiges'];
const art = ref(erste?.art ?? 'Material');
const lieferanten = ref([]);
const materialien = ref([]);
const gewaehlt = reactive(Object.fromEntries((props.aendern ?? []).map((x) => [x.lieferantId, true])));
const notiz = ref(erste?.notiz ?? '');
const grund = ref('');
const leer = () => ({ name: '', material: '', abmessung: '', anforderungen: '', einheit: 'Stk', mengen: [1], roh: null, laenge: 0, breite: 0, orig: null });
// Position einer bestehenden Anfrage zum Ändern; Bezug zu Bauteil/Arbeitsgang (Workbench) bleibt in `orig`
const ausAnfrage = (p) => ({
  name: p.teil.name, material: p.teil.material, abmessung: p.abmessung, anforderungen: p.anforderungen, einheit: p.einheit || 'Stk',
  mengen: [...p.mengen], roh: p.roh ? { ...p.roh } : null, laenge: p.roh?.laenge ?? 0, breite: p.roh?.breite ?? 0,
  orig: { teilId: p.teilId, agId: p.agId, agName: p.agName, teil: { teilenummer: p.teil.teilenummer, zeichnungsnr: p.teil.zeichnungsnr } },
});
const ws = useWerkstoff();

// Material: Rohmaterial aus dem Baum wählen statt frei schreiben; Werkstoff, Abmessung und Anforderungen ergeben sich daraus
const wahlFuer = ref(null);
function materialText(p) {
  const r = p.roh;
  if (!r) return;
  p.material = [r.werkstoff, r.zustand].filter(Boolean).join(' ');
  p.abmessung = materialAbmessung(r, p.einheit, p.laenge, p.breite);
  const a = r.anforderungen ?? {};
  p.anforderungen = [a.zeugnis && `Zeugnis ${a.zeugnis}`, ...(a.pruefungen ?? [])].filter(Boolean).join(', ');
}
function rohUebernehmen(p, r) {
  const vorher = p.roh?.artikel;
  p.roh = r;
  if (!p.name.trim() || p.name === vorher) p.name = r.artikel;
  if (p.einheit === 'Stk') p.einheit = r.form === 'Platte' ? 'Zuschnitte' : 'Stangen';
  materialText(p);
  wahlFuer.value = null;
}
const isoVon = (p) => (p.roh ? isoGruppe(p.roh.werkstoff, ws.werkstoff(p.roh.werkstoff)?.isoGruppe ?? '') : null);
const positionen = reactive(erste ? erste.positionen.map(ausAnfrage) : [leer()]);
const istPlatte = (p) => p.roh?.form === 'Platte';
// Beschriftung der Längenfelder je Einheit
const laengeLabel = (p) => (istPlatte(p) ? 'Länge' : p.einheit === 'Stangen' ? 'Stangenlänge' : p.einheit === 'Zuschnitte' ? 'Zuschnittlänge' : 'Länge');
const brauchtLaenge = (p) => ['Stangen', 'Zuschnitte', 'Platten', 'Stk'].includes(p.einheit);
// für die Vorlagen: woran man erkennt, was angefragt wird
const kontext = computed(() => ({ art: art.value, texte: positionen.flatMap((p) => [p.material, p.name]) }));

onMounted(async () => {
  [lieferanten.value, materialien.value] = await Promise.all([repo.lieferanten.liste(), repo.materialien.liste()]);
});

const auswahl = computed(() => lieferanten.value.filter((l) => gewaehlt[l.id]));
const sauber = (p) => [...new Set(p.mengen.map((m) => Math.floor(Number(m)) || 0).filter((m) => m > 0))].sort((a, b) => a - b);
const gueltig = computed(() => positionen.filter((p) => p.name.trim() && sauber(p).length));
const bereit = computed(() => auswahl.value.length && gueltig.value.length === positionen.length);
// Position so, wie sie an den Server geht (Anlegen, Ändern und Vorschau)
const ausgabe = (p) => ({
  ...(p.orig ?? {}),
  teil: { ...(p.orig?.teil ?? {}), name: p.name.trim(), material: p.material.trim() },
  abmessung: p.abmessung.trim(), anforderungen: p.anforderungen, einheit: p.einheit, mengen: sauber(p),
  roh: p.roh ? { ...p.roh, laenge: Number(p.laenge) || 0, breite: Number(p.breite) || 0 } : null,
});

// Vorschau der Mail genau wie beim Senden (Text und Tabelle vom Server)
const vorschauPositionen = computed(() => gueltig.value.map(ausgabe));

function mengeHinzu(p) { p.mengen.push((Math.max(0, ...p.mengen) || 1) * 2); }
function mengeWeg(p, i) { if (p.mengen.length > 1) p.mengen.splice(i, 1); }

const speichert = ref(false);
async function anlegen() {
  if (speichert.value || !bereit.value) return;
  speichert.value = true;
  const daten = { lieferanten: auswahl.value, art: art.value, notiz: notiz.value, positionen: positionen.map(ausgabe) };
  const neu = erste ? await anfragen.aendern({ ...daten, vorgang: erste.vorgang, grund: grund.value }) : await anfragen.freiAnlegen(daten);
  speichert.value = false;
  if (neu) emit('angelegt', neu);
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[94vh] w-[min(1240px,97vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div v-if="erste"><h2 class="flex items-center gap-2 text-base font-semibold"><PencilLine :size="16" class="text-accent" /> Anfrage {{ erste.vorgang }} ändern</h2><p class="text-xs text-mute">Es entsteht eine neue Fassung mit -1, -2 … Die bisherige Anfrage bleibt mit Mails und Antworten erhalten und gilt als ersetzt.</p></div>
            <div v-else><h2 class="text-base font-semibold">Neue Lieferantenanfrage</h2><p class="text-xs text-mute">Frei erfasst, z. B. für Material. Eine Anfrage pro Lieferant.</p></div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="grid min-h-0 flex-1 gap-6 overflow-auto px-6 py-5 lg:grid-cols-[1.15fr_1fr]">
            <div class="space-y-5">
              <div v-if="!erste" class="flex gap-1 rounded-xl border border-line bg-surface p-1">
                <button v-for="x in ARTEN" :key="x" class="flex-1 rounded-lg px-3 py-1.5 text-sm transition" :class="art === x ? 'bg-accent-soft font-medium text-accent' : 'text-mute hover:text-ink'" @click="art = x">{{ x }}</button>
              </div>
              <label v-else class="block"><span class="label mb-1 block">Was hat sich geändert? (intern, steht nicht in der Mail)</span><input v-model="grund" class="field" placeholder="z. B. Menge erhöht, Länge geändert" /></label>

              <div>
                <div class="label mb-2">Positionen</div>
                <datalist id="freie-anfrage-werkstoffe"><option v-for="m in materialien" :key="m.name" :value="m.name" /></datalist>
                <div class="space-y-2">
                  <div v-for="(p, n) in positionen" :key="n" class="rounded-xl border border-line p-3">
                    <div class="flex items-start gap-2">
                      <span class="mt-2 w-5 shrink-0 text-sm text-mute tnum">{{ n + 1 }}</span>
                      <div class="grid min-w-0 flex-1 gap-2">
                        <template v-if="art === 'Material'">
                          <button type="button" class="flex items-center gap-2.5 rounded-xl border border-dashed px-3 py-2 text-left text-sm transition" :class="p.roh ? 'border-line hover:border-accent' : 'border-accent text-accent hover:bg-accent-soft'" @click="wahlFuer = n">
                            <template v-if="p.roh">
                              <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-sm font-bold" :style="isoVon(p) ? { background: isoVon(p).farbe, color: isoVon(p).schrift } : {}">{{ isoVon(p)?.code ?? '?' }}</span>
                              <FormSymbol :form="p.roh.form" :groesse="24" :farbe="isoVon(p)?.farbe || ''" />
                              <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ p.roh.artikel }}</span><span v-if="p.anforderungen" class="block truncate text-[11px] text-mute"><ShieldCheck :size="10" class="inline" /> {{ p.anforderungen }}</span></span>
                              <span class="text-xs text-mute">ändern</span>
                            </template>
                            <template v-else-if="p.abmessung"><Layers :size="16" /> <span class="min-w-0 flex-1 truncate text-ink">{{ p.material }} · {{ p.abmessung }}</span><span class="text-xs">Rohmaterial wählen …</span></template>
                            <template v-else><Layers :size="16" /> Rohmaterial wählen …</template>
                          </button>
                          <label class="block"><span class="label mb-1 block">Bezeichnung</span><input v-model="p.name" class="field" placeholder="Bezeichnung" /></label>
                          <div v-if="p.roh && brauchtLaenge(p)" class="flex flex-wrap items-end gap-2">
                            <div class="w-40"><NumField v-model="p.laenge" :label="laengeLabel(p)" unit="mm" :decimals="0" @update:model-value="materialText(p)" /></div>
                            <template v-if="istPlatte(p)"><span class="pb-2 text-mute">×</span><div class="w-40"><NumField v-model="p.breite" label="Breite" unit="mm" :decimals="0" @update:model-value="materialText(p)" /></div></template>
                            <span class="pb-2 text-[11px] text-mute">{{ istPlatte(p) ? 'Plattendicke kommt aus der Abmessung' : Number(p.laenge) > 0 ? '' : 'leer = Lagerlänge des Lieferanten' }}</span>
                          </div>
                          <p v-if="p.abmessung" class="text-[11px] text-mute">In der Anfrage: <span class="text-ink">{{ p.abmessung }}</span></p>
                        </template>
                        <template v-else>
                          <input v-model="p.name" class="field" placeholder="Bezeichnung der Leistung" />
                          <div class="grid gap-2 sm:grid-cols-2">
                            <input v-model="p.material" class="field" list="freie-anfrage-werkstoffe" placeholder="Werkstoff, z. B. 1.4305" />
                            <input v-model="p.abmessung" class="field" placeholder="Abmessung, z. B. Ø 50 x 3000 mm" />
                          </div>
                        </template>
                      </div>
                      <button v-if="positionen.length > 1" class="mt-1.5 grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2 hover:text-ink" title="Position entfernen" @click="positionen.splice(n, 1)"><Trash2 :size="15" /></button>
                    </div>
                    <div class="mt-2 flex flex-wrap items-end gap-2 pl-7">
                      <select v-model="p.einheit" class="field !w-auto" @change="materialText(p)">
                        <option v-for="e in EINHEITEN" :key="e" :value="e">{{ e }}</option>
                      </select>
                      <div v-for="(m, i) in p.mengen" :key="i" class="relative"><NumField v-model="p.mengen[i]" :unit="p.einheit" :decimals="0" :min="1" class="w-32" />
                        <button v-if="p.mengen.length > 1" class="absolute -right-1.5 -top-1.5 grid h-4 w-4 place-items-center rounded-full bg-line text-mute hover:bg-accent hover:text-white" @click="mengeWeg(p, i)"><X :size="10" /></button>
                      </div>
                      <button class="btn !px-2.5" title="Weitere Menge (Staffel) anfragen" @click="mengeHinzu(p)"><Plus :size="15" /></button>
                    </div>
                  </div>
                </div>
                <button class="btn mt-2" @click="positionen.push(leer())"><Plus :size="15" /> Position hinzufügen</button>
              </div>

              <div>
                <div class="label mb-2">An welche Lieferanten?</div>
                <VorlagenChips v-model:notiz="notiz" class="mb-2" :kontext="kontext" :lieferanten="lieferanten" :gewaehlt="gewaehlt" />
                <div class="grid gap-1.5 sm:grid-cols-2">
                  <label v-for="l in lieferanten" :key="l.id" class="flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm transition" :class="gewaehlt[l.id] ? 'border-accent bg-accent-soft' : 'border-line hover:border-mute'">
                    <input v-model="gewaehlt[l.id]" type="checkbox" class="accent-[var(--accent)]" />
                    <span class="min-w-0 flex-1 truncate">{{ l.name }}</span><span class="truncate text-xs text-mute">{{ l.leistung }}</span>
                  </label>
                </div>
                <p v-if="!lieferanten.length" class="text-sm text-mute">Noch keine Lieferanten angelegt (Stammdaten → Lieferanten).</p>
              </div>

              <label class="block"><span class="label mb-1 block">Hinweis an die Lieferanten</span><textarea v-model="notiz" rows="2" class="field resize-y" placeholder="z. B. mit Abnahmeprüfzeugnis 3.1, Liefertermin …" /></label>
            </div>

            <MailMuster :art="art" :notiz="notiz" :positionen="vorschauPositionen" :vorgang="erste?.vorgang ?? ''" />
          </div>

          <footer class="flex items-center justify-between gap-4 border-t border-line bg-surface2 px-6 py-4">
            <span class="text-sm text-mute">{{ positionen.length }} Position{{ positionen.length === 1 ? '' : 'en' }} · {{ auswahl.length }} Lieferant{{ auswahl.length === 1 ? '' : 'en' }}</span>
            <div class="flex gap-2">
              <button class="btn" @click="emit('schliessen')">Abbrechen</button>
              <button class="btn btn-primary" :disabled="!bereit || speichert" :class="!bereit || speichert ? 'pointer-events-none opacity-40' : ''" @click="anlegen"><Send :size="16" /> {{ erste ? 'Neue Fassung anlegen und Mail schreiben' : 'Anlegen und Mail schreiben' }}</button>
            </div>
          </footer>
        </div>
      </Transition>
    </div>
    <RohmaterialPopup v-if="wahlFuer !== null" :wert="positionen[wahlFuer].roh" @uebernehmen="rohUebernehmen(positionen[wahlFuer], $event)" @schliessen="wahlFuer = null" />
  </Teleport>
</template>
