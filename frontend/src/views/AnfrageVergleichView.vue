<script setup>
// Angebote der Lieferanten eines Vorgangs nebeneinander: je Position und Menge Preis je Einheit, Einmalkosten und Gesamt,
// der günstigste ist markiert; darunter die Summe je Mengenstufe, Lieferzeit, Gültigkeit und der Zuschlag.
// Was im Angebot sonst noch steht (Optionen, Alternativen, nicht angefragte Positionen), steht darunter und lässt sich
// in die Summe einrechnen. Das PDF des Angebots geht im Belegfenster auf (gern auf dem zweiten Bildschirm).
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, Award, Crown, Inbox, Pencil, Scale, AlertTriangle, FileText, Shuffle, CornerDownRight, Truck, FilePlus2 } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import BelegLink from '../components/BelegLink.vue';
import ZuschlagDialog from '../components/ZuschlagDialog.vue';
import AngebotDazuDialog from '../components/AngebotDazuDialog.vue';
import LieferangebotDialog from '../components/LieferangebotDialog.vue';
import AngebotZelle from '../components/AngebotZelle.vue';
import { abgleich } from '../lib/lieferangebot.js';
import { useAnfragen } from '../stores/anfragen.js';
import { vergleich } from '../lib/vergleich.js';
import { eur, zahl } from '../lib/format.js';

const route = useRoute();
const store = useAnfragen();
const anfragen = computed(() => store.vorgang(String(route.params.vorgang)));
// weitere Angebotspositionen, die in die Summe sollen (statt ihrer Position bzw. zusätzlich)
const alternativen = ref([]);
const v = computed(() => vergleich(anfragen.value, { alternativen: alternativen.value }));
const umschalten = (key) => { alternativen.value = alternativen.value.includes(key) ? alternativen.value.filter((k) => k !== key) : [...alternativen.value, key]; };
// Optionen ohne passende Position stehen unten; Zuschlag mit Positionsauswahl im Dialog
const zusaetzlich = computed(() => v.value.weitere.filter((w) => !w.bezug));
const zuschlagFuer = ref(null);
const zuschlagText = (l) => {
  if (!l.zuschlag) return 'Zuschlag';
  const n = l.zuschlagPositionen.length;
  return n >= (erste.value?.positionen.length ?? 0) && !l.zuschlagAlternativen.length ? 'Zuschlag erteilt' : `Zuschlag: ${n} von ${erste.value?.positionen.length}`;
};
const nrVon = (posKey) => (erste.value?.positionen.findIndex((p) => p.key === posKey) ?? -1) + 1;
const beschreibung = (o) => [[o.werkstoff, o.zustand].filter(Boolean).join(' '), [o.form, o.abmessung].filter(Boolean).join(' ')].filter(Boolean).join(' · ') || String(o.text ?? '').split(/\r?\n/)[0] || `Position ${o.pos}`;
const mengenText = (o) => [o.stueck != null && `${zahl(o.stueck, 0)} Stk`, o.kg != null && `${zahl(o.kg, 2)} kg`, o.meter != null && `${zahl(o.meter, 3)} m`].filter(Boolean).join(' · ');
const preisText = (o) => (o.preis ? `${eur(o.preis)} / ${o.preisJe || 'Stk'}` : '');
const erste = computed(() => anfragen.value[0] ?? null);
const mitPreisen = computed(() => v.value.lieferanten.filter((l) => l.hatPreise).length);
// aus dem Posteingang gekommen: Rückweg anbieten und beim Weitergehen mitnehmen
const von = computed(() => (route.query.von === 'posteingang' ? { von: 'posteingang' } : {}));
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
// Liefertermin einer Position: als Datum, wenn lesbar, sonst der Text aus dem PDF
const termin = (datum, text) => (datum ? de(datum) : (text || '').slice(0, 40));
// Angebote kommen zeitlich versetzt: weiteres PDF einlesen, auch von einem Lieferanten, der noch nicht im Vergleich ist
const dazu = ref(false);
const einlesen = ref(null); // { anfrage, datei }
const ersetzt = computed(() => anfragen.value.some((a) => a.status === 'Ersetzt'));
function dazuWeiter(x) { dazu.value = false; einlesen.value = x; }
// was der Lieferant anders anbietet als angefragt (Werkstoff, Zustand, Form, Maße)
const abwVon = (o, posKey) => {
  const p = erste.value?.positionen.find((x) => x.key === posKey);
  return o && p ? abgleich(o, p).filter((x) => x.ok === false).map((x) => ({ feld: x.feld, angeboten: x.angeboten, erwartet: x.angefragt })) : [];
};
</script>

<template>
  <div v-if="erste" class="mx-auto max-w-[1400px] space-y-4">
    <div class="flex flex-wrap items-center gap-4">
      <RouterLink v-if="von.von" to="/posteingang" class="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"><ArrowLeft :size="15" /> Zurück zum Posteingang</RouterLink>
      <RouterLink to="/anfragen" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft v-if="!von.von" :size="15" /> Alle Anfragen</RouterLink>
    </div>

    <section class="card flex flex-wrap items-center gap-4 p-5">
      <Scale :size="22" class="text-accent" />
      <div class="min-w-0 flex-1">
        <h2 class="text-lg font-semibold">Angebotsvergleich <span class="tnum">{{ route.params.vorgang }}</span></h2>
        <p class="text-sm text-mute">{{ erste.art }} · {{ erste.positionen.length }} Position{{ erste.positionen.length === 1 ? '' : 'en' }} · {{ v.lieferanten.length }} Lieferanten, {{ mitPreisen }} mit Preisen</p>
      </div>
      <button v-if="!ersetzt" class="btn btn-primary" @click="dazu = true"><FilePlus2 :size="15" /> Weiteres Angebot einlesen</button>
      <p class="max-w-md text-xs text-mute">Preise erfasst du bei der Anfrage des Lieferanten (Stift), am schnellsten mit „Angebot aus PDF einlesen“. Grün ist je Zeile der günstigste Gesamtpreis; die Summe enthält die Nebenkosten. Das PDF-Symbol öffnet das Angebot im Belegfenster.</p>
    </section>

    <section class="card overflow-x-auto">
      <table class="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr class="border-b border-line bg-surface2 align-bottom">
            <th class="sticky left-0 z-10 bg-surface2 px-4 py-3 text-left text-xs font-medium text-mute">Position</th>
            <th class="px-3 py-3 text-right text-xs font-medium text-mute">Menge</th>
            <th v-for="l in v.lieferanten" :key="l.id" class="min-w-[170px] px-3 py-3 text-right">
              <RouterLink :to="{ path: `/anfragen/${l.id}`, query: von }" class="group inline-flex items-center gap-1.5 font-semibold hover:text-accent">
                <Award v-if="l.zuschlag" :size="15" class="text-ok" />{{ l.name }}<Pencil :size="12" class="text-mute opacity-0 transition group-hover:opacity-100" />
              </RouterLink>
              <BelegLink v-if="l.pdf" :url="l.pdf" :name="`Angebot ${l.angebotsnr}`" :titel="l.name" class="ml-1.5 inline-flex items-center rounded-md p-0.5 align-middle text-accent hover:bg-accent/10"><FileText :size="14" /></BelegLink>
              <div class="mt-1 flex items-center justify-end gap-1.5"><Inbox v-if="l.neueAntwort" :size="13" class="text-accent" /><StatusBadge :status="l.status" /></div>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="z in v.zeilen" :key="z.key">
            <tr :class="z.ersteZeile ? 'border-t border-line' : ''">
              <td class="sticky left-0 z-10 bg-surface px-4 py-2.5 align-top">
                <div v-if="z.ersteZeile" class="flex items-center gap-3">
                  <PartImage :teil="z.teil" :groesse="40" />
                  <div class="min-w-0">
                    <div class="truncate font-medium"><span class="mr-1.5 text-mute">{{ z.nr }}</span>{{ z.agName ? `${z.agName}: ` : '' }}{{ z.teil.name }}</div>
                    <div class="truncate text-xs text-mute">{{ [z.teil.material, z.abmessung, z.teil.teilenummer].filter(Boolean).join(' · ') }}</div>
                  </div>
                </div>
              </td>
              <td class="whitespace-nowrap px-3 py-2.5 text-right align-top font-medium tnum">{{ z.menge }} {{ z.einheit }}</td>
              <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2.5 text-right align-top tnum" :class="[z.bester === l.id && Object.values(z.zellen).filter(Boolean).length > 1 ? 'bg-ok/10' : '', z.vergeben?.id === l.id && !z.vergeben.perAlternative ? 'ring-2 ring-inset ring-ok/60' : '']">
                <template v-if="z.zellen[l.id]">
                  <div class="font-semibold" :class="z.bester === l.id ? 'text-ok' : ''"><Award v-if="z.vergeben?.id === l.id && !z.vergeben.perAlternative" :size="13" class="mr-1 inline text-ok" /><Crown v-else-if="z.bester === l.id && Object.values(z.zellen).filter(Boolean).length > 1" :size="12" class="mr-1 inline" />{{ eur(z.zellen[l.id].gesamt) }}</div>
                  <div class="text-[11px] text-mute">{{ eur(z.zellen[l.id].proStk) }} / {{ z.einheit }}<template v-if="z.zellen[l.id].einmalig"> + {{ eur(z.zellen[l.id].einmalig) }} einmalig</template></div>
                  <div v-if="z.zellen[l.id].abweichung != null" class="mt-0.5 inline-flex items-center gap-1 rounded-full bg-warn/15 px-1.5 text-[10px] text-warn" :title="`Der Lieferant bietet ${z.zellen[l.id].abweichung} ${z.einheit} an; der Preis je ${z.einheit} gilt hier für die angefragte Menge`"><AlertTriangle :size="10" /> angeboten {{ z.zellen[l.id].abweichung }} {{ z.einheit }}</div>
                  <AngebotZelle v-if="z.zellen[l.id].o && z.ersteZeile" :o="z.zellen[l.id].o" :abw="abwVon(z.zellen[l.id].o, z.posKey)" :termin="false" class="mt-1" />
                  <div v-if="z.zellen[l.id].termin" class="mt-1 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold" :class="z.schnellste.includes(l.id) ? 'bg-ok/15 text-ok' : z.zellen[l.id].datum && z.zellen[l.id].datum === l.spaetester && l.verschieden ? 'bg-warn/15 text-warn' : 'bg-surface2 text-ink'" :title="`Liefertermin laut Angebot: ${z.zellen[l.id].termin}${z.schnellste.includes(l.id) ? ' (schnellster)' : ''}`"><Truck :size="12" /> {{ termin(z.zellen[l.id].datum, z.zellen[l.id].termin) }}</div>
                </template>
                <span v-else class="text-mute">–</span>
              </td>
            </tr>
            <!-- Optionen und Alternativen der Lieferanten direkt unter der Position, die sie ersetzen würden -->
            <template v-if="z.stufe === z.stufen - 1">
              <tr v-for="w in v.weitere.filter((x) => x.bezug === z.posKey)" :key="w.key" class="bg-surface2/30">
                <td class="sticky left-0 z-10 bg-surface2 py-2 pl-10 pr-4 align-top">
                  <div class="flex items-center gap-1.5">
                    <CornerDownRight :size="15" class="shrink-0 text-mute" />
                    <span class="shrink-0 rounded-full bg-warn/15 px-1.5 text-[10px] font-semibold text-warn">{{ w.option ? 'Option' : 'Alternative' }}</span>
                    <span class="min-w-0 truncate text-sm">{{ beschreibung(w.o) }}</span>
                  </div>
                  <div class="truncate pl-5 text-xs text-mute">{{ v.lieferanten.find((l) => l.id === w.lieferantId)?.name }} · Pos. {{ w.o.pos || '–' }} im Angebot · statt Position {{ z.nr }}</div>
                </td>
                <td class="whitespace-nowrap px-3 py-2 text-right align-top text-xs tnum">{{ mengenText(w.o) }}</td>
                <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right align-top tnum" :class="l.id === w.lieferantId && w.zuschlag ? 'ring-2 ring-inset ring-ok/60' : ''">
                  <template v-if="l.id === w.lieferantId">
                    <label class="inline-flex cursor-pointer items-center gap-1.5 font-semibold" :title="`In der Summe statt Position ${z.nr} rechnen`">
                      <input type="checkbox" class="accent-[var(--accent)]" :checked="alternativen.includes(w.key)" @change="umschalten(w.key)" /><Award v-if="w.zuschlag" :size="13" class="text-ok" />{{ eur(w.o.betrag) }}
                    </label>
                    <div class="text-[11px] text-mute">{{ preisText(w.o) }}</div>
                    <div v-if="w.o.liefertermin" class="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-mute" :title="`Liefertermin laut Angebot: ${w.o.liefertermin}`"><Truck :size="10" /> {{ termin(w.o.lieferdatum, w.o.liefertermin) }}</div>
                  </template>
                </td>
              </tr>
            </template>
          </template>
          <template v-if="zusaetzlich.length">
            <tr class="border-t border-line bg-surface2/40">
              <td :colspan="2 + v.lieferanten.length" class="py-2 text-[11px] font-semibold uppercase tracking-wide text-mute">
                <div class="sticky left-0 inline-block px-4"><Shuffle :size="12" class="mr-1 inline" /> Zusätzlich angeboten (nicht angefragt) <span class="font-normal normal-case tracking-normal">· Haken = in die Summe rechnen</span></div>
              </td>
            </tr>
            <tr v-for="w in zusaetzlich" :key="w.key" class="border-t border-line/60">
              <td class="sticky left-0 z-10 bg-surface px-4 py-2 align-top">
                <div class="flex items-center gap-1.5">
                  <span class="shrink-0 rounded-full px-1.5 text-[10px] font-semibold" :class="w.option ? 'bg-warn/15 text-warn' : 'bg-accent/10 text-accent'">{{ w.option ? 'Option' : 'zusätzlich' }}</span>
                  <span class="min-w-0 truncate text-sm">{{ beschreibung(w.o) }}</span>
                </div>
                <div class="truncate text-xs text-mute">{{ v.lieferanten.find((l) => l.id === w.lieferantId)?.name }} · Pos. {{ w.o.pos || '–' }} im Angebot</div>
              </td>
              <td class="whitespace-nowrap px-3 py-2 text-right align-top text-xs tnum">{{ mengenText(w.o) }}</td>
              <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right align-top tnum" :class="l.id === w.lieferantId && w.zuschlag ? 'ring-2 ring-inset ring-ok/60' : ''">
                <template v-if="l.id === w.lieferantId">
                  <label class="inline-flex cursor-pointer items-center gap-1.5 font-semibold" title="Zusätzlich in die Summe rechnen">
                    <input type="checkbox" class="accent-[var(--accent)]" :checked="alternativen.includes(w.key)" @change="umschalten(w.key)" /><Award v-if="w.zuschlag" :size="13" class="text-ok" />{{ eur(w.o.betrag) }}
                  </label>
                  <div class="text-[11px] text-mute">{{ preisText(w.o) }}</div>
                  <div v-if="w.o.liefertermin" class="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-mute" :title="`Liefertermin laut Angebot: ${w.o.liefertermin}`"><Truck :size="10" /> {{ termin(w.o.lieferdatum, w.o.liefertermin) }}</div>
                </template>
              </td>
            </tr>
          </template>
        </tbody>
        <tfoot>
          <tr v-if="v.lieferanten.some((l) => l.nebenkosten)" class="border-t border-line text-xs">
            <td class="sticky left-0 z-10 bg-surface px-4 py-2 text-mute">Nebenkosten (Verpackung, Fracht …)</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right tnum" :title="l.nebenkostenText">{{ l.nebenkosten ? eur(l.nebenkosten) : '–' }}</td>
          </tr>
          <tr v-for="s in v.summen" :key="s.stufe" class="border-t border-line bg-surface2/60">
            <td class="sticky left-0 z-10 bg-surface2 px-4 py-2.5 text-sm font-semibold">Summe {{ v.summen.length > 1 ? `${s.stufe + 1}. Menge` : '' }}<span v-if="v.lieferanten.some((l) => l.nebenkosten)" class="block text-[11px] font-normal text-mute">inkl. Nebenkosten</span></td>
            <td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2.5 text-right tnum" :class="s.bester === l.id ? 'text-ok' : ''">
              <span v-if="s.je[l.id].mitAlternative" class="mr-1 rounded-full bg-accent/10 px-1.5 text-[10px] font-normal text-accent" title="Mit gewählten Optionen/Alternativen gerechnet">mit Alternative</span>
              <span v-if="s.je[l.id].vollstaendig" class="font-semibold">{{ eur(s.je[l.id].betrag) }}</span>
              <span v-else-if="s.je[l.id].betrag" class="text-xs text-mute">unvollständig ({{ eur(s.je[l.id].betrag) }})</span>
              <span v-else class="text-mute">–</span>
            </td>
          </tr>
          <tr v-if="v.lieferanten.some((l) => l.netto)" class="border-t border-line text-xs">
            <td class="sticky left-0 z-10 bg-surface px-4 py-2 text-mute">Ganzes Angebot laut PDF (netto)</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right tnum">{{ l.netto ? eur(l.netto) : '–' }}</td>
          </tr>
          <tr class="border-t border-line text-xs">
            <td class="sticky left-0 z-10 bg-surface px-4 py-2 text-mute">Liefertermin<span class="block text-[11px]">alles da (späteste Position)</span></td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right align-top">
              <template v-if="l.spaetester">
                <div class="font-semibold tnum" :class="l.schnellster ? 'text-ok' : ''"><Truck :size="12" class="mr-1 inline" />{{ de(l.spaetester) }}</div>
                <div v-if="l.verschieden" class="text-[11px] text-mute">Termine je Position verschieden</div>
                <div v-if="l.ohneDatum.length" class="text-[11px] text-warn" :title="l.ohneDatum.join('\n')">+ {{ l.ohneDatum.length }} ohne Datum: {{ l.ohneDatum[0].slice(0, 30) }}</div>
              </template>
              <template v-else>{{ l.lieferzeit || '–' }}</template>
            </td>
          </tr>
          <tr class="text-xs">
            <td class="sticky left-0 z-10 bg-surface px-4 py-2 text-mute">Angebot · gültig bis</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right">
              <BelegLink v-if="l.pdf" :url="l.pdf" :name="`Angebot ${l.angebotsnr}`" :titel="l.name" class="mr-1 inline-flex items-center gap-0.5 text-accent hover:underline"><FileText :size="12" /></BelegLink>{{ l.angebotsnr || '–' }} · {{ de(l.gueltigBis) }}
            </td>
          </tr>
          <tr class="border-t border-line">
            <td class="sticky left-0 z-10 bg-surface px-4 py-3 text-xs text-mute">Zuschlag</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-3 text-right">
              <button v-if="l.hatPreise" class="btn !py-1 !text-xs" :class="l.zuschlag ? '!border-ok !text-ok' : ''" @click="zuschlagFuer = anfragen.find((x) => x.id === l.id)"><Award :size="13" /> {{ zuschlagText(l) }}</button>
            </td>
          </tr>
        </tfoot>
      </table>
    </section>
    <ZuschlagDialog v-if="zuschlagFuer" :anfrage="zuschlagFuer" :andere="anfragen" @schliessen="zuschlagFuer = null" />
    <AngebotDazuDialog v-if="dazu" :vorgang="String(route.params.vorgang)" :anfragen="anfragen" @schliessen="dazu = false" @weiter="dazuWeiter" />
    <LieferangebotDialog v-if="einlesen" :anfrage="einlesen.anfrage" :datei="einlesen.datei" @schliessen="einlesen = null" @erfasst="einlesen = null" />
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Zu diesem Vorgang gibt es keine Anfragen</p>
    <RouterLink to="/anfragen" class="btn mt-4">Zur Übersicht</RouterLink>
  </div>
</template>
