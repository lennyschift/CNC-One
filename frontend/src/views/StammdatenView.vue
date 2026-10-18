<script setup>
import { ref, onMounted } from 'vue';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Trash2, Truck, Cog, ListTree } from '@lucide/vue';
import VorlageKarte from '../components/VorlageKarte.vue';
import { repo } from '../data/repo.js';
import { useStamm } from '../stores/stamm.js';
import { useUi } from '../stores/ui.js';

const stamm = useStamm();
const ui = useUi();
const kunden = ref([]);
onMounted(async () => { kunden.value = await repo.kunden.liste(); });

const neuerName = ref('');
const neuerTyp = ref('intern');
async function artAnlegen() {
  if (!(await stamm.artHinzu(neuerName.value, neuerTyp.value))) { ui.toast('Name fehlt oder ist schon vorhanden', 'warn'); return; }
  neuerName.value = '';
}
async function vorlageKopieren(v) {
  await stamm.vorlageNeu({ name: `${v.name} (Kopie)`, kundeId: v.kundeId, arbeitsgaenge: stamm.vorlageKopie(v.id) });
}
</script>

<template>
  <div class="mx-auto grid max-w-[1300px] items-start gap-6 xl:grid-cols-[360px_1fr]">
    <!-- Arbeitsgangarten -->
    <section class="card p-5">
      <h2 class="mb-1 flex items-center gap-2 text-sm font-semibold"><ListTree :size="16" class="text-accent" /> Arbeitsgangarten</h2>
      <p class="mb-4 text-xs text-mute">Die Namen, aus denen Arbeitsgänge und Fremdvergaben gewählt werden, zum Beispiel „Oberflächenbehandlung“.</p>
      <div v-auto-animate class="space-y-1.5">
        <div v-for="a in stamm.arten" :key="a.id" class="group flex items-center gap-2.5 rounded-xl bg-surface2 px-3 py-2 text-sm">
          <component :is="a.typ === 'fremd' ? Truck : Cog" :size="14" class="text-mute" />
          <input v-model="a.name" class="min-w-0 flex-1 bg-transparent outline-none" @change="stamm.artSpeichern(a)" />
          <select v-model="a.typ" class="rounded-md bg-surface px-1.5 py-0.5 text-xs text-mute outline-none" @change="stamm.artSpeichern(a)"><option value="intern">Intern</option><option value="fremd">Fremd</option></select>
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute opacity-0 transition hover:text-accent group-hover:opacity-100" title="Entfernen" @click="stamm.artLoeschen(a.id)"><Trash2 :size="13" /></button>
        </div>
      </div>
      <form class="mt-4 flex gap-2" @submit.prevent="artAnlegen">
        <input v-model="neuerName" class="field" placeholder="Neue Art, z. B. Strahlen" />
        <select v-model="neuerTyp" class="field !w-28"><option value="intern">Intern</option><option value="fremd">Fremd</option></select>
        <button class="btn btn-primary" type="submit"><Plus :size="15" /></button>
      </form>
    </section>

    <!-- Vorlagen -->
    <section class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-sm font-semibold">Vorlagen für Arbeitsgänge</h2>
          <p class="text-xs text-mute">Ein Kunde kann eigene Vorlagen haben. Sie lassen sich bei Bauteilen, Aufträgen und in der Fertigung anwenden.</p>
        </div>
        <button class="btn btn-primary" @click="stamm.vorlageNeu()"><Plus :size="16" /> Neue Vorlage</button>
      </div>

      <div v-auto-animate class="space-y-4">
        <VorlageKarte v-for="v in stamm.vorlagen" :key="v.id" :vorlage="v" :kunden="kunden" @kopieren="vorlageKopieren" @loeschen="stamm.vorlageLoeschen($event.id)" />
      </div>
      <p v-if="!stamm.vorlagen.length" class="card px-6 py-12 text-center text-sm text-mute">Noch keine Vorlagen.</p>
    </section>
  </div>
</template>
