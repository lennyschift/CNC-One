<script setup>
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { Plus, Copy, Trash2, ArrowUp, ArrowDown, FileBox, Send } from '@lucide/vue';
import AnimatedNumber from './AnimatedNumber.vue';
import PartImage from './PartImage.vue';
import { eur } from '../lib/format.js';
import { useAngebot } from '../stores/angebot.js';
import { useAnfragen } from '../stores/anfragen.js';

const a = useAngebot();
const anfragen = useAnfragen();
// Anfragen, in denen dieses Bauteil vorkommt, und ob schon überall ein Angebot da ist
const anfrageStand = (t) => {
  const l = anfragen.liste.filter((x) => x.positionen.some((p) => p.teilId === t.id));
  return l.length ? { n: l.length, fertig: l.every((x) => x.status !== 'Gesendet') } : null;
};
const anteil = (id) => (a.netto > 0 ? Math.max(0.03, (a.ergebnisse[id]?.gesamt ?? 0) / a.netto) : 0);
</script>

<template>
  <section class="card flex min-h-0 flex-col">
    <header class="flex items-center justify-between px-4 pb-2 pt-4">
      <h2 class="text-sm font-semibold">Bauteile <span class="ml-1 rounded-full bg-surface2 px-2 py-0.5 text-xs font-medium text-mute tnum">{{ a.teile.length }}</span></h2>
      <button class="btn btn-primary !py-1.5" @click="a.hinzufuegen('Neues Bauteil')"><Plus :size="15" /> Neu <span class="kbd !border-white/30 !bg-white/15 !text-white">N</span></button>
    </header>

    <div v-auto-animate class="min-h-0 flex-1 space-y-1.5 overflow-auto p-2">
      <div
        v-for="(t, i) in a.teile"
        :key="t.id"
        role="button"
        tabindex="0"
        class="group relative cursor-pointer overflow-hidden rounded-xl border p-3 transition duration-150"
        :class="a.auswahlId === t.id ? 'border-accent/60 bg-accent-soft shadow-sm' : 'border-transparent hover:border-line hover:bg-surface2'"
        @click="a.auswahlId = t.id"
        @keydown.enter="a.auswahlId = t.id"
      >
        <div class="flex items-start gap-3">
          <PartImage :teil="t" :groesse="44" />
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium"><span class="mr-1.5 text-xs text-mute tnum">{{ i + 1 }}</span>{{ t.name || 'Ohne Namen' }}</div>
            <div class="mt-0.5 truncate text-xs text-mute">
              {{ t.teilenummer || 'ohne Teilenummer' }} · {{ t.menge }} Stk<template v-if="t.material"> · {{ t.material }}</template>
            </div>
          </div>
          <div class="text-right">
            <div class="text-sm font-semibold"><AnimatedNumber :value="a.ergebnisse[t.id]?.gesamt ?? 0" :format="eur" /></div>
            <div class="mt-0.5 flex items-center justify-end gap-2 text-[11px] text-mute">
              <span v-if="anfrageStand(t)" class="inline-flex items-center gap-1" :class="anfrageStand(t).fertig ? 'text-ok' : 'text-warn'" :title="anfrageStand(t).fertig ? 'Lieferantenangebot liegt vor' : 'Lieferantenanfrage gesendet, Angebot fehlt noch'"><Send :size="11" />{{ anfrageStand(t).n }}</span>
              <span v-if="t.dateien.length" class="inline-flex items-center gap-1"><FileBox :size="12" />{{ t.dateien.length }}</span>
            </div>
          </div>
        </div>
        <div class="mt-2.5 h-1 overflow-hidden rounded-full bg-line/70">
          <div class="h-full rounded-full bg-accent transition-all duration-500" :style="{ width: anteil(t.id) * 100 + '%' }" />
        </div>
        <div class="absolute right-2 top-2 flex gap-0.5 rounded-lg border border-line bg-surface p-0.5 opacity-0 shadow-sm transition group-hover:opacity-100">
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" title="Nach oben" @click.stop="a.verschieben(t.id, -1)"><ArrowUp :size="13" /></button>
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" title="Nach unten" @click.stop="a.verschieben(t.id, 1)"><ArrowDown :size="13" /></button>
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" title="Duplizieren" @click.stop="a.duplizieren(t.id)"><Copy :size="13" /></button>
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-accent-soft hover:text-accent" title="Löschen" @click.stop="a.loeschen(t.id)"><Trash2 :size="13" /></button>
        </div>
      </div>

      <div v-if="!a.teile.length" class="grid place-items-center px-6 py-14 text-center">
        <FileBox :size="34" class="text-mute" :stroke-width="1.4" />
        <p class="mt-3 text-sm font-medium">Noch keine Bauteile</p>
        <p class="mt-1 text-xs text-mute">STEP- und PDF-Dateien einfach ins Fenster ziehen oder mit <span class="kbd">N</span> ein Bauteil anlegen.</p>
      </div>
    </div>
  </section>
</template>
