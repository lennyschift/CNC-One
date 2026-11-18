<script setup>
// Angebote der Lieferanten eines Vorgangs nebeneinander: je Position und Menge Preis je Einheit, Einmalkosten und Gesamt,
// der günstigste ist markiert; darunter die Summe je Mengenstufe, Lieferzeit, Gültigkeit und der Zuschlag.
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, Award, Crown, Inbox, Pencil, Scale } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useAnfragen } from '../stores/anfragen.js';
import { vergleich } from '../lib/vergleich.js';
import { eur } from '../lib/format.js';

const route = useRoute();
const store = useAnfragen();
const anfragen = computed(() => store.vorgang(String(route.params.vorgang)));
const v = computed(() => vergleich(anfragen.value));
const erste = computed(() => anfragen.value[0] ?? null);
const mitPreisen = computed(() => v.value.lieferanten.filter((l) => l.hatPreise).length);
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '–');
</script>

<template>
  <div v-if="erste" class="mx-auto max-w-[1400px] space-y-4">
    <RouterLink to="/anfragen" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Anfragen</RouterLink>

    <section class="card flex flex-wrap items-center gap-4 p-5">
      <Scale :size="22" class="text-accent" />
      <div class="min-w-0 flex-1">
        <h2 class="text-lg font-semibold">Angebotsvergleich <span class="tnum">{{ route.params.vorgang }}</span></h2>
        <p class="text-sm text-mute">{{ erste.art }} · {{ erste.positionen.length }} Position{{ erste.positionen.length === 1 ? '' : 'en' }} · {{ v.lieferanten.length }} Lieferanten, {{ mitPreisen }} mit Preisen</p>
      </div>
      <p class="max-w-md text-xs text-mute">Preise erfasst du bei der Anfrage des Lieferanten (Stift). Grün ist je Zeile der günstigste Gesamtpreis.</p>
    </section>

    <section class="card overflow-x-auto">
      <table class="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr class="border-b border-line bg-surface2 align-bottom">
            <th class="sticky left-0 z-10 bg-surface2 px-4 py-3 text-left text-xs font-medium text-mute">Position</th>
            <th class="px-3 py-3 text-right text-xs font-medium text-mute">Menge</th>
            <th v-for="l in v.lieferanten" :key="l.id" class="min-w-[170px] px-3 py-3 text-right">
              <RouterLink :to="`/anfragen/${l.id}`" class="group inline-flex items-center gap-1.5 font-semibold hover:text-accent">
                <Award v-if="l.zuschlag" :size="15" class="text-ok" />{{ l.name }}<Pencil :size="12" class="text-mute opacity-0 transition group-hover:opacity-100" />
              </RouterLink>
              <div class="mt-1 flex items-center justify-end gap-1.5"><Inbox v-if="l.neueAntwort" :size="13" class="text-accent" /><StatusBadge :status="l.status" /></div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="z in v.zeilen" :key="z.key" :class="z.ersteZeile ? 'border-t border-line' : ''">
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
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2.5 text-right align-top tnum" :class="z.bester === l.id && Object.values(z.zellen).filter(Boolean).length > 1 ? 'bg-ok/10' : ''">
              <template v-if="z.zellen[l.id]">
                <div class="font-semibold" :class="z.bester === l.id ? 'text-ok' : ''"><Crown v-if="z.bester === l.id && Object.values(z.zellen).filter(Boolean).length > 1" :size="12" class="mr-1 inline" />{{ eur(z.zellen[l.id].gesamt) }}</div>
                <div class="text-[11px] text-mute">{{ eur(z.zellen[l.id].proStk) }} / {{ z.einheit }}<template v-if="z.zellen[l.id].einmalig"> + {{ eur(z.zellen[l.id].einmalig) }} einmalig</template></div>
              </template>
              <span v-else class="text-mute">–</span>
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr v-for="s in v.summen" :key="s.stufe" class="border-t border-line bg-surface2/60">
            <td class="sticky left-0 z-10 bg-surface2 px-4 py-2.5 text-sm font-semibold">Summe {{ v.summen.length > 1 ? `${s.stufe + 1}. Menge` : '' }}</td>
            <td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2.5 text-right tnum" :class="s.bester === l.id ? 'text-ok' : ''">
              <span v-if="s.je[l.id].vollstaendig" class="font-semibold">{{ eur(s.je[l.id].betrag) }}</span>
              <span v-else-if="s.je[l.id].betrag" class="text-xs text-mute">unvollständig ({{ eur(s.je[l.id].betrag) }})</span>
              <span v-else class="text-mute">–</span>
            </td>
          </tr>
          <tr class="border-t border-line text-xs">
            <td class="sticky left-0 z-10 bg-surface px-4 py-2 text-mute">Lieferzeit</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right">{{ l.lieferzeit || '–' }}</td>
          </tr>
          <tr class="text-xs">
            <td class="sticky left-0 z-10 bg-surface px-4 py-2 text-mute">Angebot · gültig bis</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-2 text-right">{{ l.angebotsnr || '–' }} · {{ de(l.gueltigBis) }}</td>
          </tr>
          <tr class="border-t border-line">
            <td class="sticky left-0 z-10 bg-surface px-4 py-3 text-xs text-mute">Zuschlag</td><td />
            <td v-for="l in v.lieferanten" :key="l.id" class="px-3 py-3 text-right">
              <button v-if="l.hatPreise" class="btn !py-1 !text-xs" :class="l.zuschlag ? '!border-ok !text-ok' : ''" @click="store.zuschlag(l.id, !l.zuschlag)"><Award :size="13" /> {{ l.zuschlag ? 'Zuschlag erteilt' : 'Zuschlag' }}</button>
            </td>
          </tr>
        </tfoot>
      </table>
    </section>
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Zu diesem Vorgang gibt es keine Anfragen</p>
    <RouterLink to="/anfragen" class="btn mt-4">Zur Übersicht</RouterLink>
  </div>
</template>
