<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, Printer, Send, Undo2 } from '@lucide/vue';
import MahnungDokument from '../components/MahnungDokument.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useRechnung } from '../stores/rechnung.js';
import { benutzer } from '../data/repo.js';
import { eur } from '../lib/format.js';

const route = useRoute();
const store = useRechnung();
const m = computed(() => store.mahnung(route.params.id));
const darf = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'CNC Buchhaltung', 'System Manager'].includes(x)));
const de = (iso) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '');
const drucken = () => window.print();
</script>

<template>
  <div v-if="m" class="mx-auto grid max-w-[1300px] items-start gap-6 xl:grid-cols-[1fr_340px]">
    <MahnungDokument :mahnung="m" />
    <aside class="no-print space-y-4 xl:sticky xl:top-0">
      <RouterLink to="/mahnwesen" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Mahnwesen</RouterLink>
      <section class="card p-5">
        <div class="flex items-center justify-between"><h2 class="font-semibold tnum">{{ m.id }}</h2><StatusBadge :status="m.status" /></div>
        <p class="mt-1 text-sm text-mute">{{ m.stufe }} · {{ m.kundeName }}</p>
        <p class="mt-1 text-sm">Rechnung <RouterLink :to="`/rechnungen/${m.rechnungId}`" class="text-accent hover:underline tnum">{{ m.rechnungNummer }}</RouterLink> · offen {{ eur(m.offenerBetrag) }}<template v-if="m.gebuehr"> + {{ eur(m.gebuehr) }} Gebühr</template></p>
        <p class="mt-1 text-xs text-mute">Zahlen bis {{ de(m.fristBis) }}<template v-if="m.versandtAm"> · versendet am {{ de(m.versandtAm) }}</template></p>
        <div class="mt-4 space-y-2">
          <button v-if="m.status === 'Angelegt' && darf" class="btn btn-primary w-full justify-center" @click="store.mahnungVersendet(m.id)"><Send :size="16" /> Als versendet markieren</button>
          <button class="btn w-full justify-center" @click="drucken"><Printer :size="16" /> Drucken / als PDF speichern</button>
          <button v-if="['Angelegt', 'Versendet'].includes(m.status) && darf" class="btn w-full justify-center !text-mute" @click="store.mahnungZurueckziehen(m.id)"><Undo2 :size="16" /> Zurückziehen</button>
        </div>
        <p v-if="m.status === 'Erledigt'" class="mt-3 text-xs text-mute">Die Rechnung ist inzwischen bezahlt.</p>
      </section>
    </aside>
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Mahnung nicht gefunden</p>
    <RouterLink to="/mahnwesen" class="btn mt-4">Zum Mahnwesen</RouterLink>
  </div>
</template>
