<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { X, AlertTriangle, ShoppingCart, ChevronDown, Workflow, Truck, Hash } from '@lucide/vue';
import PartImage from './PartImage.vue';
import NumField from './NumField.vue';
import Toggle from './Toggle.vue';
import ArbeitsplanEditor from './ArbeitsplanEditor.vue';
import { optionen, auftragsPosition } from '../lib/beleg.js';
import { useBelege } from '../stores/belege.js';
import { planAus } from '../lib/fertigung.js';
import { useStamm } from '../stores/stamm.js';
import { eur, uid } from '../lib/format.js';
import { bereich, bereichText, formatNr, hoechste } from '../lib/serien.js';
import SerienFeld from './SerienFeld.vue';
import { call } from '../data/api.js';

const props = defineProps({ angebot: { type: Object, required: true } });
const emit = defineEmits(['schliessen', 'angelegt']);
const b = useBelege();
const stamm = useStamm();
const kundeId = props.angebot.kopf.kundeId;

const bestellt = computed(() => b.bestelltFuer(props.angebot.id));
const bestellnr = reactive({ wert: '' });

// pro Angebotsposition: Auswahl der Staffel, Menge, Liefertermin und welche Kosten berechnet werden
const zustand = reactive(props.angebot.positionen.map((p) => {
  const opt = optionen(p.teil, p.ergebnis);
  // Arbeitsplan: am Bauteil gespeichert hat Vorrang, sonst der aus dem Angebot, sonst leer
  const plan = stamm.planFuer(kundeId, p.teil.teilenummer) ?? JSON.parse(JSON.stringify(p.teil.arbeitsgaenge ?? []));
  return { key: p.key, aktiv: (bestellt.value[p.key] ?? 0) === 0, optId: opt[0].id, menge: opt[0].menge, termin: '', serienStart: '', kostenAus: {}, plan, planSpeichern: true, planOffen: false };
}));

// Seriennummern: Stammdaten des Bauteils (Kennzeichen und letzte vergebene Nummer) frisch holen
const bauteile = ref({});
onMounted(async () => {
  try {
    const l = await call('cnc_one.api.stammdaten.liste', { art: 'bauteil' });
    bauteile.value = Object.fromEntries(l.map((b) => [b.id, b]));
    // Startnummer vorbelegen: die letzte vergebene Nummer des Bauteils plus eins
    props.angebot.positionen.forEach((p, i) => {
      const b = bauteile.value[p.bauteilId];
      if (b?.seriennummern && b.letzteSeriennummer > 0 && !zustand[i].serienStart) zustand[i].serienStart = formatNr(b.letzteSeriennummer + 1, b.serienStellen);
    });
  } catch { /* ohne Stammdaten geht der Dialog trotzdem, die Nummer wird dann von Hand eingegeben */ }
});
const serieVon = (p) => (p.bauteilId && bauteile.value[p.bauteilId] ? !!bauteile.value[p.bauteilId].seriennummern : !!(p.seriennummern || p.teil.seriennummern));
const letzte = (p) => bauteile.value[p.bauteilId]?.letzteSeriennummer ?? 0;
const stellenVon = (p) => bauteile.value[p.bauteilId]?.serienStellen ?? 4;

const sicht = computed(() => props.angebot.positionen.map((p, i) => {
  const z = zustand[i];
  const opts = optionen(p.teil, p.ergebnis);
  const opt = opts.find((o) => o.id === z.optId) ?? opts[0];
  const pos = auftragsPosition(p.teil, p.ergebnis, opt, z.menge);
  const kosten = pos.kosten.map((k) => ({ ...k, an: !z.kostenAus[k.label] }));
  const summe = pos.einzelpreis * pos.menge + kosten.filter((k) => k.an).reduce((s, k) => s + k.betrag, 0);
  const stellen = stellenVon(p);
  const br = bereich(z.serienStart, pos.menge);
  const serie = serieVon(p) ? { letzte: letzte(p), stellen, bereich: br, passt: !br || br.bis <= hoechste(stellen) } : null;
  return { p, z, opts, opt, pos, kosten, summe, serie };
}));

const gesamt = computed(() => sicht.value.filter((s) => s.z.aktiv).reduce((x, s) => x + s.summe, 0));
const anzahl = computed(() => sicht.value.filter((s) => s.z.aktiv).length);
const serieFehlt = computed(() => sicht.value.some((s) => s.z.aktiv && s.serie && (!s.serie.bereich || !s.serie.passt)));

function waehle(s, o) { s.z.optId = o.id; s.z.menge = o.menge; }

const speichert = ref(false);
async function anlegen() {
  if (speichert.value) return;
  const aktive = sicht.value.filter((s) => s.z.aktiv);
  // Der Server rechnet Preise und Summen selbst; hier geht nur die Auswahl hin.
  const positionen = aktive.map((s) => ({
    angebotKey: s.p.key,
    optionId: s.z.optId,
    menge: s.z.menge,
    termin: s.z.termin,
    kostenAus: Object.keys(s.z.kostenAus).filter((label) => s.z.kostenAus[label]),
    arbeitsgaenge: planAus(s.z.plan, uid),
    planSpeichern: s.z.planSpeichern,
    serienStart: s.serie ? String(s.z.serienStart ?? '') : '',
  }));
  speichert.value = true;
  const neu = await b.auftragAnlegen({ angebotId: props.angebot.id, kundenbestellnr: bestellnr.wert, positionen });
  speichert.value = false;
  if (!neu) return;
  for (const s of aktive) {
    if (s.z.planSpeichern && s.z.plan.length) stamm.planEintragen(kundeId, s.p.teil.teilenummer, planAus(s.z.plan, uid));
  }
  emit('angelegt', neu);
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[92vh] w-[min(920px,96vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h2 class="text-base font-semibold">In Auftrag übernehmen</h2>
              <p class="text-xs text-mute">{{ angebot.id }} · {{ angebot.kopf.kundeName }}</p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="min-h-0 flex-1 space-y-3 overflow-auto px-6 py-5">
            <label class="block max-w-sm"><span class="label mb-1 block">Bestellnummer des Kunden</span><input v-model="bestellnr.wert" class="field" placeholder="z. B. PO-48211" /></label>

            <div v-for="s in sicht" :key="s.p.key" class="rounded-2xl border p-4 transition" :class="s.z.aktiv ? 'border-line bg-surface' : 'border-line/60 bg-surface2 opacity-70'">
              <div class="flex items-start gap-4">
                <PartImage :teil="s.p.teil" :groesse="60" />
                <div class="min-w-0 flex-1">
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="font-medium">{{ s.p.teil.name }}</div>
                      <div class="text-xs text-mute">{{ s.p.teil.teilenummer || 'ohne Teilenummer' }}<template v-if="bestellt[s.p.key]"> · bereits bestellt: {{ bestellt[s.p.key] }} Stk</template></div>
                    </div>
                    <Toggle v-model="s.z.aktiv" label="Bestellen" />
                  </div>

                  <div v-if="s.z.aktiv" class="mt-3 space-y-3">
                    <div class="flex flex-wrap items-end gap-3">
                      <div v-if="s.opts.length > 1">
                        <div class="label mb-1">Angebotene Staffel</div>
                        <div class="flex flex-wrap gap-1.5">
                          <button v-for="o in s.opts" :key="o.id" class="rounded-xl border px-3 py-1.5 text-left text-sm transition" :class="s.z.optId === o.id ? 'border-accent bg-accent-soft text-accent' : 'border-line hover:border-mute'" @click="waehle(s, o)">
                            <div class="font-semibold tnum">{{ o.label }}</div><div class="text-[11px] opacity-80 tnum">{{ eur(o.einzel) }} / Stk</div>
                          </button>
                        </div>
                      </div>
                      <NumField v-model="s.z.menge" label="Bestellte Menge" unit="Stk" :decimals="0" :min="1" class="w-36" />
                      <label class="block"><span class="label mb-1 block">Liefertermin</span><input v-model="s.z.termin" type="date" class="field" /></label>
                    </div>

                    <div v-if="s.serie" class="rounded-xl border border-line p-3">
                      <div class="flex flex-wrap items-end gap-3">
                        <SerienFeld v-model="s.z.serienStart" :stellen="s.serie.stellen" label="Seriennummern ab" class="w-44" />
                        <div class="pb-2 text-sm"><Hash :size="14" class="mr-1 inline text-accent" /><template v-if="s.serie.bereich && s.serie.passt">Nummern <span class="font-semibold tnum">{{ bereichText(s.serie.bereich.von, s.serie.bereich.bis, s.serie.stellen) }}</span> ({{ s.pos.menge }} Stk)</template><span v-else-if="s.serie.bereich" class="text-warn">Die Nummern bis {{ s.serie.bereich.bis }} passen nicht in {{ s.serie.stellen }} Stellen.</span><span v-else class="text-warn">Bitte die erste Nummer eingeben, die der Kunde genannt hat.</span></div>
                      </div>
                      <p class="mt-1.5 text-xs text-mute"><template v-if="s.serie.letzte">Letzte vergebene Nummer dieses Bauteils: <span class="tnum">{{ formatNr(s.serie.letzte, s.serie.stellen) }}</span>. </template><template v-else>Für dieses Bauteil ist noch keine Nummer gespeichert, die Startnummer bitte aus der Bestellung eintragen. </template>Seriennummern bestehen nur aus Ziffern ({{ s.serie.stellen }} Stellen, z. B. {{ formatNr(1, s.serie.stellen) }}), laufen fortlaufend und die letzte wird am Bauteil gemerkt.</p>
                      <p v-if="s.serie.bereich && s.serie.letzte && s.serie.bereich.von !== s.serie.letzte + 1" class="mt-1 flex items-center gap-1.5 text-xs text-warn"><AlertTriangle :size="13" /> Das ist nicht die nächste Nummer nach {{ formatNr(s.serie.letzte, s.serie.stellen) }}. Bitte prüfen.</p>
                    </div>

                    <p v-if="s.pos.unterStaffel" class="flex items-center gap-2 text-xs text-warn"><AlertTriangle :size="14" /> Der Staffelpreis gilt ab {{ s.pos.staffelMenge }} Stk, die Menge liegt darunter.</p>

                    <div class="rounded-xl bg-surface2 px-4 py-3 text-sm">
                      <div class="flex justify-between"><span>{{ s.pos.menge }} Stk × {{ eur(s.pos.einzelpreis) }}</span><span class="tnum">{{ eur(s.pos.einzelpreis * s.pos.menge) }}</span></div>
                      <div v-for="k in s.kosten" :key="k.label" class="mt-1.5 flex items-center justify-between gap-3 text-mute">
                        <span class="flex items-center gap-2">↳ {{ k.label }}</span>
                        <span class="flex items-center gap-3"><label class="flex cursor-pointer items-center gap-1.5 text-xs"><input type="checkbox" :checked="k.an" class="accent-[var(--accent)]" @change="s.z.kostenAus[k.label] = !$event.target.checked" /> berechnen</label><span class="tnum" :class="k.an ? '' : 'line-through opacity-50'">{{ eur(k.betrag) }}</span></span>
                      </div>
                      <div class="mt-2 flex justify-between border-t border-line pt-2 font-semibold"><span>Summe Position</span><span class="tnum">{{ eur(s.summe) }}</span></div>
                    </div>

                    <div class="rounded-xl border border-line">
                      <button class="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm" @click="s.z.planOffen = !s.z.planOffen">
                        <Workflow :size="15" class="text-accent" />
                        <span class="font-medium">Arbeitsgänge</span>
                        <span class="text-xs text-mute">{{ s.z.plan.length ? s.z.plan.map((a) => a.name || '?').join(' → ') : 'noch keine, kann auch später in der Fertigung ergänzt werden' }}</span>
                        <ChevronDown :size="15" class="ml-auto text-mute transition" :class="s.z.planOffen ? 'rotate-180' : ''" />
                      </button>
                      <div v-if="s.z.planOffen" class="border-t border-line p-4">
                        <ArbeitsplanEditor :arbeitsgaenge="s.z.plan" :kunde-id="kundeId" :teilenummer="s.p.teil.teilenummer" :teil-info="s.p.teil" />
                        <div class="mt-3"><Toggle v-model="s.z.planSpeichern" klein label="Beim Anlegen des Auftrags am Bauteil speichern" /></div>
                        <p v-if="s.z.plan.some((a) => a.typ === 'fremd')" class="mt-2 flex items-center gap-1.5 text-xs text-mute"><Truck :size="13" /> Fremdvergaben werden nach dem Auftrag beim Lieferanten bestellt (folgt als eigener Schritt).</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <footer class="flex items-center justify-between gap-4 border-t border-line bg-surface2 px-6 py-4">
            <div><div class="text-xs text-mute">{{ anzahl }} Position{{ anzahl === 1 ? '' : 'en' }}</div><div class="text-xl font-semibold tnum">{{ eur(gesamt) }} <span class="text-xs font-normal text-mute">netto</span></div></div>
            <div class="flex gap-2">
              <button class="btn" @click="emit('schliessen')">Abbrechen</button>
              <button class="btn btn-primary" :disabled="!anzahl || speichert || serieFehlt" :class="!anzahl || speichert || serieFehlt ? 'pointer-events-none opacity-40' : ''" @click="anlegen"><ShoppingCart :size="16" /> Auftrag anlegen</button>
            </div>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
