<script setup>
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { ref } from 'vue';
import { Plus, Copy, Trash2, ArrowUp, ArrowDown, FileBox, Send, Database, Hash, Merge, FileText, Box } from '@lucide/vue';
import AnimatedNumber from './AnimatedNumber.vue';
import PartImage from './PartImage.vue';
import { eur } from '../lib/format.js';
import { useAngebot } from '../stores/angebot.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

const a = useAngebot();
const anfragen = useAnfragen();
const ui = useUi();
// Anfragen, in denen dieses Bauteil vorkommt, und ob schon überall ein Angebot da ist
const anfrageStand = (t) => {
  const l = anfragen.liste.filter((x) => x.positionen.some((p) => p.teilId === t.id));
  return l.length ? { n: l.length, fertig: l.every((x) => x.status !== 'Gesendet') } : null;
};
// Preise wie im Angebots-PDF: je Staffel Menge, Stückpreis und Gesamt, sonst Menge × Stückpreis und die eigenen Zeilen
const preise = (t) => {
  const e = a.ergebnisse[t.id];
  if (!e) return null;
  if (t.staffel?.aktiv) return { staffel: true, stufen: e.stufen, zusatz: e.zeilen.filter((z) => z.typ === 'kosten') };
  const teil = e.zeilen.find((z) => z.typ === 'teil');
  return { staffel: false, teil, zusatz: e.zeilen.filter((z) => z.typ === 'kosten') };
};
// Zusammenführen: in welches Bauteil (Ziel) ein anderes aufgehen soll; die Auswahl zeigt die übrigen Bauteile
const zusammenZiel = ref(null);
const hat = (t, art) => t.dateien.some((d) => d.art === art);
function zusammenfuehren(quelle) {
  a.zusammenfuehren(zusammenZiel.value, quelle.id);
  zusammenZiel.value = null;
}
const anteil = (id) => (a.netto > 0 ? Math.max(0.03, (a.ergebnisse[id]?.gesamt ?? 0) / a.netto) : 0);
</script>

<template>
  <section class="card flex min-h-0 flex-col">
    <header class="flex items-center justify-between px-4 pb-2 pt-4">
      <h2 class="text-sm font-semibold">Bauteile <span class="ml-1 rounded-full bg-surface2 px-2 py-0.5 text-xs font-medium text-mute tnum">{{ a.teile.length }}</span></h2>
      <div v-if="!a.nurAnsicht" class="flex gap-1.5">
        <button class="btn !py-1.5" title="Bauteil des Kunden aus den Stammdaten übernehmen" @click="ui.bauteilWahlOffen = true"><Database :size="14" /> Aus Stammdaten</button>
        <button class="btn btn-primary !py-1.5" title="Neues Bauteil anlegen, es steht danach in den Stammdaten" @click="a.hinzufuegen('Neues Bauteil')"><Plus :size="15" /> Neu <span class="kbd !border-white/30 !bg-white/15 !text-white">N</span></button>
      </div>
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
          <PartImage iso :teil="t" :groesse="44" />
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium"><span class="mr-1.5 text-xs text-mute tnum">{{ i + 1 }}</span>{{ t.name || 'Ohne Namen' }}
              <span v-if="a.zuordnung[t.id]" class="ml-1.5 rounded-full px-1.5 py-0.5 align-middle text-[10px] font-semibold" :class="a.zuordnung[t.id].herkunft === 'neu' ? 'bg-accent-soft text-accent' : 'bg-surface2 text-mute'" :title="a.zuordnung[t.id].herkunft === 'neu' ? 'Mit diesem Angebot neu angelegt, steht in den Stammdaten' : 'Bestandsbauteil aus den Stammdaten'">{{ a.zuordnung[t.id].herkunft === 'neu' ? 'Neu' : 'Bestand' }}</span>
              <Hash v-if="t.seriennummern" :size="11" class="ml-1 inline text-mute" title="Seriennummern" />
            </div>
            <div class="mt-0.5 truncate text-xs text-mute">
              {{ t.teilenummer || 'ohne Teilenummer' }}<template v-if="!t.staffel?.aktiv"> · {{ t.menge }} Stk</template><template v-if="t.material"> · {{ t.material }}</template>
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
        <!-- Preise wie im Angebot -->
        <div v-if="preise(t)" class="preise mt-2 rounded-lg px-2.5 py-1.5 text-[11px] tnum" :class="a.auswahlId === t.id ? 'bg-surface/70' : 'bg-surface2'">
          <template v-if="preise(t).staffel">
            <div v-for="(s, k) in preise(t).stufen" :key="s.menge" class="grid grid-cols-[1fr_auto_auto] gap-x-3" :class="k === 0 ? 'font-medium text-ink' : 'text-mute'">
              <span>{{ s.menge }} Stk</span><span class="text-right">{{ eur(s.stueckpreis) }}</span><span class="w-[4.6rem] text-right">{{ eur(s.gesamt) }}</span>
            </div>
          </template>
          <div v-else-if="preise(t).teil" class="flex justify-between gap-3 font-medium text-ink"><span>{{ preise(t).teil.menge }} × {{ eur(preise(t).teil.einzel) }}</span><span>{{ eur(preise(t).teil.betrag) }}</span></div>
          <div v-for="z in preise(t).zusatz" :key="z.label" class="flex justify-between gap-3 text-mute"><span class="truncate">+ {{ z.label }}</span><span>{{ eur(z.betrag) }}</span></div>
        </div>
        <!-- Zusammenführen: anderes Bauteil wählen -->
        <div v-if="zusammenZiel === t.id" class="relative z-20 mt-2 rounded-xl border border-line bg-surface p-2 shadow-lg" @click.stop @keydown.enter.stop>
          <div class="px-1.5 pb-1.5 text-xs"><span class="font-semibold">Zusammenführen mit …</span>
            <span class="block text-mute">Die Dateien des gewählten Bauteils kommen zu „{{ t.name || 'Ohne Namen' }}“, das gewählte entfällt. Menge und Kalkulation bleiben von „{{ t.name || 'Ohne Namen' }}“.</span></div>
          <button v-for="(x, k) in a.teile" v-show="x.id !== t.id" :key="x.id" class="flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-left text-sm hover:bg-surface2" @click="zusammenfuehren(x)">
            <PartImage :teil="x" :groesse="28" />
            <span class="min-w-0 flex-1 truncate"><span class="mr-1 text-xs text-mute tnum">{{ k + 1 }}</span>{{ x.name || 'Ohne Namen' }}</span>
            <FileText v-if="hat(x, 'Zeichnung')" :size="13" class="shrink-0 text-mute" title="Zeichnung" />
            <Box v-if="hat(x, 'STEP')" :size="13" class="shrink-0 text-mute" title="3D-Modell" />
          </button>
          <button class="mt-1 w-full rounded-lg px-1.5 py-1 text-xs text-mute hover:bg-surface2" @click="zusammenZiel = null">Abbrechen</button>
        </div>
        <div class="mt-2.5 h-1 overflow-hidden rounded-full bg-line/70">
          <div class="h-full rounded-full bg-accent transition-all duration-500" :style="{ width: anteil(t.id) * 100 + '%' }" />
        </div>
        <div v-if="!a.nurAnsicht" class="absolute right-2 top-2 flex gap-0.5 rounded-lg border border-line bg-surface p-0.5 shadow-sm transition group-hover:opacity-100" :class="zusammenZiel === t.id ? 'opacity-100' : 'opacity-0'">
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" title="Nach oben" @click.stop="a.verschieben(t.id, -1)"><ArrowUp :size="13" /></button>
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" title="Nach unten" @click.stop="a.verschieben(t.id, 1)"><ArrowDown :size="13" /></button>
          <button class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" title="Duplizieren" @click.stop="a.duplizieren(t.id)"><Copy :size="13" /></button>
          <button v-if="a.teile.length > 1" class="grid h-6 w-6 place-items-center rounded-md text-mute hover:bg-surface2 hover:text-ink" :class="zusammenZiel === t.id ? '!bg-accent-soft !text-accent' : ''" title="Mit einem anderen Bauteil zusammenführen" @click.stop="zusammenZiel = zusammenZiel === t.id ? null : t.id"><Merge :size="13" /></button>
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
