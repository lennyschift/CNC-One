<script setup>
// Material des ganzen Angebots anfragen: das Rohmaterial aller Positionen, zusammengefasst je Artikel (Werkstoff, Zustand,
// Abmessung, Ausführung) mit Bedarf, Anforderungen und Abgleich mit dem Rohmaterial-Lager. Was ganz im Lager liegt, ist
// nicht vorgewählt. Gewählte Zeilen gehen an die gewählten Lieferanten (je Lieferant eine Anfrage); danach lassen sich
// weitere Zeilen an andere Lieferanten schicken.
import { ref, reactive, computed, onMounted } from 'vue';
import { X, Send, Mail, Warehouse, ShieldCheck, AlertTriangle, Check, Plus } from '@lucide/vue';
import NumField from './NumField.vue';
import FormSymbol from './FormSymbol.vue';
import VorlagenChips from './VorlagenChips.vue';
import AnfrageMailDialog from './AnfrageMailDialog.vue';
import { repo } from '../data/repo.js';
import { EINHEITEN, mailText } from '../lib/anfrage.js';
import { materialBedarf, artikelText } from '../lib/werkstoffbaum.js';
import { isoGruppe } from '../lib/iso.js';
import { zahl } from '../lib/format.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useWerkstoff } from '../stores/werkstoff.js';

const props = defineProps({ teile: { type: Array, required: true }, angebotId: { type: String, default: '' } });
const emit = defineEmits(['schliessen']);
const anfragen = useAnfragen();
const ws = useWerkstoff();

const chargen = ref([]);
const lieferanten = ref([]);
const gewaehlt = reactive({});
const notiz = ref('');
onMounted(async () => {
  [lieferanten.value, chargen.value] = await Promise.all([repo.lieferanten.liste(), ws.chargenLaden(true)]);
  zeilenAufbauen();
});

const bedarf = computed(() => materialBedarf(props.teile, chargen.value));
const iso = (g) => isoGruppe(g.werkstoff, ws.werkstoff(g.werkstoff)?.isoGruppe ?? '');
const anfText = (a) => [a.zeugnis && `Zeugnis ${a.zeugnis}`, ...(a.pruefungen ?? [])].filter(Boolean).join(', ');
const artikel = (g) => artikelText(g.werkstoff, g);
// schon zu diesem Angebot angefragt (Material-Anfrage mit gleicher Bezeichnung)
const schon = (g) => anfragen.fuerAngebot({ angebotId: props.angebotId }).filter((x) => x.art === 'Material' && x.positionen.some((p) => p.teil.name === artikel(g)));

// Je Zeile: an/aus, Einheit und Mengen (Grundmenge, ggf. größte Staffel). Stangen in Metern, Platten in kg.
const zeilen = ref([]);
const runden = (v, schritt) => Math.max(schritt, Math.ceil(v / schritt) * schritt);
function vorschlag(g) {
  if (g.form === 'Platte') return { einheit: 'kg', mengen: [...new Set([runden(g.kg, 1), runden(g.kgMax, 1)])] };
  // was nach Abzug des Lagers fehlt (für Grundmenge und größte Staffel); liegt alles im Lager, der volle Bedarf
  const offen = g.fehlt || g.bedarf;
  const offenMax = Math.max(g.bedarfMax - g.vorrat, 0) || g.bedarfMax;
  return { einheit: 'm', mengen: [...new Set([runden(offen / 1000, 1), runden(offenMax / 1000, 1)])] };
}
function zeilenAufbauen() {
  zeilen.value = bedarf.value.liste.map((g) => ({ g, an: g.status !== 'lager' && !schon(g).length, ...vorschlag(g) }));
}
const aktiv = computed(() => zeilen.value.filter((z) => z.an));
const auswahl = computed(() => lieferanten.value.filter((l) => gewaehlt[l.id]));
const kontext = computed(() => ({ art: 'Material', texte: aktiv.value.flatMap((z) => [z.g.werkstoff]) }));
const sauber = (m) => [...new Set(m.map((x) => Math.ceil(Number(x)) || 0).filter((x) => x > 0))].sort((a, b) => a - b);
const positionen = computed(() => aktiv.value.map((z) => ({
  teil: { name: artikel(z.g), material: [z.g.werkstoff, z.g.zustand].filter(Boolean).join(' ') },
  abmessung: [`${z.g.form} ${z.g.abmessung}`, z.g.ausfuehrung, `für ${z.g.teile.map((t) => `${t.menge} × ${t.zuschnitt} mm`).join(', ')}`].filter(Boolean).join(' · '),
  anforderungen: anfText(z.g.anforderungen),
  einheit: z.einheit,
  mengen: sauber(z.mengen),
})));
const vorschau = computed(() => mailText({ id: `LA-${new Date().getFullYear()}-NNNN`, art: 'Material', notiz: notiz.value, positionen: positionen.value.map((p, i) => ({ ...p, key: `mat:${i + 1}`, agName: '' })) }));
const bereit = computed(() => auswahl.value.length && positionen.value.length && positionen.value.every((p) => p.mengen.length));

const mailVorgang = ref('');
const speichert = ref(false);
async function senden() {
  if (speichert.value || !bereit.value) return;
  speichert.value = true;
  const neu = await anfragen.freiAnlegen({ art: 'Material', angebotId: props.angebotId, notiz: notiz.value, lieferanten: auswahl.value, positionen: positionen.value });
  speichert.value = false;
  if (neu) mailVorgang.value = neu[0].vorgang;
}
// Nach dem Versand: zurück zur Liste, um weitere Zeilen an andere Lieferanten zu schicken
function weiter() {
  mailVorgang.value = '';
  for (const k of Object.keys(gewaehlt)) delete gewaehlt[k];
  zeilenAufbauen();
}

const mengeText = (g, mm) => (g.form === 'Platte' ? `${zahl(mm / 1e6, 2)} m²` : `${zahl(mm / 1000, 2)} m`);
const STATUS = { lager: ['im Lager', 'bg-ok/15 text-ok'], teilweise: ['teilweise im Lager', 'bg-warn/15 text-warn'], bestellen: ['bestellen', 'bg-accent-soft text-accent'] };
</script>

<template>
  <Teleport to="body">
    <AnfrageMailDialog v-if="mailVorgang" :vorgang="mailVorgang" @schliessen="weiter" @gesendet="weiter" />
    <div v-else class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[94vh] w-[min(1240px,97vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div><h2 class="text-base font-semibold">Material anfragen</h2><p class="text-xs text-mute">Rohmaterial aller Positionen, je Artikel zusammengefasst, mit Abgleich gegen das Rohmaterial-Lager</p></div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="grid min-h-0 flex-1 gap-6 overflow-auto px-6 py-5 xl:grid-cols-[1.45fr_1fr]">
            <div class="space-y-5">
              <div class="space-y-2">
                <div v-for="z in zeilen" :key="z.g.key" class="rounded-xl border p-3 transition" :class="z.an ? 'border-accent/60 bg-accent-soft/30' : 'border-line'">
                  <div class="flex items-start gap-3">
                    <input v-model="z.an" type="checkbox" class="mt-2.5 h-4 w-4 accent-[var(--accent)]" />
                    <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-base font-bold" :style="iso(z.g) ? { background: iso(z.g).farbe, color: iso(z.g).schrift } : {}">{{ iso(z.g)?.code ?? '?' }}</span>
                    <FormSymbol :form="z.g.form" :groesse="30" :farbe="iso(z.g)?.farbe || ''" class="mt-0.5 shrink-0" />
                    <div class="min-w-0 flex-1">
                      <div class="flex flex-wrap items-center gap-2"><span class="font-semibold">{{ artikel(z.g) }}</span>
                        <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="STATUS[z.g.status][1]">{{ STATUS[z.g.status][0] }}</span></div>
                      <div class="mt-0.5 text-xs text-mute">
                        {{ z.g.teile.map((t) => `${t.name || t.teilenummer || 'Bauteil'} (${t.menge}${t.mengeMax !== t.menge ? `–${t.mengeMax}` : ''} × ${t.zuschnitt} mm)`).join(' · ') }}
                      </div>
                      <div class="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs tnum">
                        <span>Bedarf <strong>{{ mengeText(z.g, z.g.bedarf) }}</strong><template v-if="z.g.bedarfMax !== z.g.bedarf"> (größte Staffel {{ mengeText(z.g, z.g.bedarfMax) }})</template> · {{ zahl(z.g.kg, 1) }} kg</span>
                        <span class="flex items-center gap-1"><Warehouse :size="12" class="text-mute" /> Lager {{ z.g.vorrat ? mengeText(z.g, z.g.vorrat) : '–' }}<template v-if="z.g.chargen.length"> ({{ z.g.chargen.map((c) => c.id).join(', ') }})</template></span>
                        <span v-if="z.g.fehlt" class="text-accent">fehlt {{ mengeText(z.g, z.g.fehlt) }}</span>
                        <span v-else-if="z.g.bedarfMax > z.g.vorrat" class="text-warn">für die größte Staffel fehlen {{ mengeText(z.g, z.g.bedarfMax - z.g.vorrat) }}</span>
                      </div>
                      <div v-if="anfText(z.g.anforderungen)" class="mt-0.5 text-[11px] text-mute"><ShieldCheck :size="11" class="inline" /> {{ anfText(z.g.anforderungen) }}</div>
                      <div v-if="z.g.ohneNachweis" class="mt-0.5 text-[11px] text-warn">{{ z.g.ohneNachweis }} Charge{{ z.g.ohneNachweis === 1 ? '' : 'n' }} im Lager ohne die geforderten Nachweise</div>
                      <div v-if="schon(z.g).length" class="mt-0.5 text-[11px] text-warn">schon angefragt: {{ schon(z.g).map((s) => `${s.id} (${s.lieferantName})`).join('; ') }}</div>
                      <div v-if="z.an" class="mt-2 flex flex-wrap items-end gap-2">
                        <select v-model="z.einheit" class="field !w-auto !py-1.5 text-sm"><option v-for="e in EINHEITEN" :key="e" :value="e">{{ e }}</option></select>
                        <div v-for="(m, i) in z.mengen" :key="i" class="relative"><NumField v-model="z.mengen[i]" :unit="z.einheit" :decimals="0" :min="1" class="w-28" />
                          <button v-if="z.mengen.length > 1" class="absolute -right-1.5 -top-1.5 grid h-4 w-4 place-items-center rounded-full bg-line text-mute hover:bg-accent hover:text-white" @click="z.mengen.splice(i, 1)"><X :size="10" /></button>
                        </div>
                        <button class="btn !px-2.5" title="Weitere Menge anfragen" @click="z.mengen.push(Math.max(1, ...z.mengen) * 2)"><Plus :size="15" /></button>
                      </div>
                    </div>
                  </div>
                </div>
                <p v-if="!zeilen.length" class="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-mute">Noch keine Position hat ein vollständiges Rohmaterial (Werkstoff, Abmessung und Zuschnitt).</p>
                <p v-if="bedarf.unvollstaendig.length" class="flex items-start gap-1.5 text-xs text-warn"><AlertTriangle :size="13" class="mt-0.5 shrink-0" /> Ohne vollständiges Rohmaterial (Abmessung oder Zuschnitt fehlt): {{ bedarf.unvollstaendig.map((t) => t.name || t.teilenummer || 'Bauteil').join(', ') }}</p>
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
                <p class="mt-1.5 text-xs text-mute">Jeder gewählte Lieferant bekommt die gewählten Zeilen. Für andere Lieferanten danach einfach andere Zeilen wählen.</p>
              </div>
              <label class="block"><span class="label mb-1 block">Hinweis an die Lieferanten</span><textarea v-model="notiz" rows="2" class="field resize-y" placeholder="z. B. Liefertermin, Fixlängen, gesägt auf Maß …" /></label>
            </div>

            <div>
              <div class="label mb-2 flex items-center gap-1.5"><Mail :size="13" /> Vorschau des Anschreibens</div>
              <div class="rounded-xl border border-line bg-surface2 p-4 text-[13px] leading-relaxed">
                <div class="mb-2 font-medium">{{ positionen.length ? vorschau.betreff : '–' }}</div>
                <pre v-if="positionen.length" class="whitespace-pre-wrap font-sans text-mute">{{ vorschau.text }}</pre>
                <p v-else class="text-mute">Bitte mindestens eine Zeile wählen.</p>
              </div>
            </div>
          </div>

          <footer class="flex items-center justify-between gap-4 border-t border-line bg-surface2 px-6 py-4">
            <span class="text-sm text-mute">{{ aktiv.length }} Artikel · {{ auswahl.length }} Lieferant{{ auswahl.length === 1 ? '' : 'en' }}</span>
            <div class="flex gap-2">
              <button class="btn" @click="emit('schliessen')"><Check :size="15" /> Fertig</button>
              <button class="btn btn-primary" :disabled="!bereit || speichert" :class="!bereit || speichert ? 'pointer-events-none opacity-40' : ''" @click="senden"><Send :size="16" /> Anlegen und Mail schreiben</button>
            </div>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
