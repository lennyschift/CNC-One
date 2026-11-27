<script setup>
// Beim Start eines Fertigungsbauteils (Status „In Fertigung“, Board oder erste Buchung): sind Pflichtpunkte der
// Checkliste offen, erscheinen sie hier und lassen sich gleich abhaken. „Starten“ geht erst, wenn alles da ist;
// „Trotzdem starten“ wird am Bauteil vermerkt.
import { computed } from 'vue';
import { X, Play, AlertTriangle } from '@lucide/vue';
import FertigungCheckliste from './FertigungCheckliste.vue';
import { useFertigung } from '../stores/fertigung.js';
import { checkOffen } from '../lib/fertigung.js';

const f = useFertigung();
const fb = computed(() => (f.startAnfrage ? f.bauteil(f.startAnfrage.fbId) : null));
const offen = computed(() => checkOffen(fb.value));
const titel = computed(() => (f.startAnfrage?.status === 'Fertig' ? 'Fertig melden' : 'Fertigung starten'));
</script>

<template>
  <Teleport to="body">
    <div v-if="fb" class="fixed inset-0 z-[70] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="f.startAntwort(null)">
      <div class="card flex max-h-[90vh] w-[min(560px,96vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div>
            <h2 class="text-base font-semibold">{{ titel }}: ist alles da?</h2>
            <p class="text-xs text-mute">{{ fb.id }} · {{ fb.teil.name }} · {{ fb.menge }} Stk</p>
          </div>
          <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="f.startAntwort(null)"><X :size="18" /></button>
        </header>
        <div class="min-h-0 overflow-auto px-5 py-4">
          <FertigungCheckliste :fb="fb" kompakt />
        </div>
        <footer class="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3.5">
          <span v-if="offen.length" class="mr-auto flex items-center gap-1.5 text-xs text-warn"><AlertTriangle :size="13" /> Noch offen: {{ offen.map((p) => p.text).join(', ') }}</span>
          <span v-else class="mr-auto text-xs text-ok">Alle Pflichtpunkte erledigt</span>
          <button v-if="offen.length" class="btn text-sm" title="Wird am Bauteil vermerkt (wer, wann, was offen war)" @click="f.startAntwort({ trotzdem: 1 })">Trotzdem starten</button>
          <button class="btn btn-primary" :disabled="offen.length > 0" :class="offen.length ? 'pointer-events-none opacity-40' : ''" @click="f.startAntwort({ trotzdem: 0 })"><Play :size="15" /> {{ titel === 'Fertig melden' ? 'Weiter' : 'Starten' }}</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
