<script setup>
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowLeft, Printer, PackageCheck, XCircle } from '@lucide/vue';
import LieferscheinDokument from '../components/LieferscheinDokument.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { useLieferung } from '../stores/lieferung.js';

const route = useRoute();
const l = useLieferung();
const ls = computed(() => l.lieferschein(route.params.id));
const auftraege = computed(() => [...new Set((ls.value?.positionen ?? []).map((p) => p.auftragId).filter(Boolean))]);
const stornoFrage = ref(false);
function stornieren() {
  if (!stornoFrage.value) { stornoFrage.value = true; setTimeout(() => { stornoFrage.value = false; }, 4000); return; }
  l.stornieren(ls.value.id);
  stornoFrage.value = false;
}
const drucken = () => window.print();
</script>

<template>
  <div v-if="ls" class="mx-auto grid max-w-[1300px] items-start gap-6 xl:grid-cols-[1fr_340px]">
    <LieferscheinDokument :lieferschein="ls" />

    <aside class="no-print space-y-4 xl:sticky xl:top-0">
      <RouterLink to="/lieferscheine" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Alle Lieferscheine</RouterLink>
      <section class="card p-5">
        <div class="flex items-center justify-between"><h2 class="font-semibold tnum">{{ ls.id }}</h2><StatusBadge :status="ls.status" /></div>
        <p class="mt-1 text-sm text-mute">{{ ls.kundeName }}</p>
        <div class="mt-5 space-y-2">
          <button v-if="ls.status === 'Bereit'" class="btn btn-primary w-full justify-center" @click="l.geliefertSetzen(ls.id)"><PackageCheck :size="16" /> Als geliefert markieren</button>
          <button class="btn w-full justify-center" @click="drucken"><Printer :size="16" /> Drucken / als PDF speichern</button>
          <button v-if="ls.status !== 'Storniert'" class="btn w-full justify-center" :class="stornoFrage ? '!border-accent !bg-accent-soft !text-accent' : '!text-mute'" @click="stornieren"><XCircle :size="16" /> {{ stornoFrage ? 'Wirklich stornieren?' : 'Stornieren' }}</button>
        </div>
        <p v-if="ls.status === 'Bereit'" class="mt-3 text-xs text-mute">Die Menge ist im Fertigbauteil Lager schon abgebucht. Ist noch nicht alles gefertigt, steht dort ein Minus, das mit der Fertigung ausgeglichen wird.</p>
        <p v-if="ls.status === 'Storniert'" class="mt-3 text-xs text-mute">Storniert: die Menge ist ins Lager zurückgebucht und im Auftrag wieder frei.</p>
      </section>
      <section v-if="auftraege.length" class="card p-5">
        <h3 class="mb-2 text-sm font-semibold">Zugehörige Aufträge</h3>
        <ul class="space-y-1 text-sm"><li v-for="a in auftraege" :key="a"><RouterLink :to="`/auftraege/${a}`" class="text-accent hover:underline tnum">{{ a }}</RouterLink></li></ul>
      </section>
    </aside>
  </div>
  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Lieferschein nicht gefunden</p>
    <RouterLink to="/lieferscheine" class="btn mt-4">Zur Liste</RouterLink>
  </div>
</template>
