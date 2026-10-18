<script setup>
import { computed, ref } from 'vue';
import { onClickOutside } from '@vueuse/core';
import { useRoute, useRouter } from 'vue-router';
import { useEventListener } from '@vueuse/core';
import { Search, Moon, Sun, Database, Truck, Warehouse, Plus, Copy, Trash2, RotateCcw, Layers, Calculator, FileText, ClipboardList, Factory, Send, Settings, LogOut } from '@lucide/vue';
import AppRail from './components/AppRail.vue';
import CommandPalette from './components/CommandPalette.vue';
import DropOverlay from './components/DropOverlay.vue';
import Toasts from './components/Toasts.vue';
import { useUi } from './stores/ui.js';
import { useAngebot } from './stores/angebot.js';
import { benutzer } from './data/repo.js';
import { abmelden } from './data/api.js';
import { STAMM_PUNKTE } from './data/stammNav.js';

const nutzer = benutzer();
const initialen = computed(() => (nutzer?.name || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase());
const cncRollen = computed(() => (nutzer?.rollen ?? []).filter((r) => r.startsWith('CNC') || r === 'System Manager'));
const menue = ref(false);
const menueRef = ref(null);
onClickOutside(menueRef, () => { menue.value = false; });
const route = useRoute();
const router = useRouter();
const ui = useUi();
const a = useAngebot();

function onDateien(files) {
  if (route.meta.bereich !== 'workbench') router.push('/workbench');
  a.dateienHinzufuegen(files);
}

const untertitel = computed(() => (route.meta.bereich === 'workbench' ? (a.angebotId ? `${a.angebotId} · Entwurf` : 'Neues Angebot') : ''));

const befehle = computed(() => [
  { id: 'go-wb', label: 'Zur Workbench', gruppe: 'Gehe zu', icon: Calculator, run: () => router.push('/workbench') },
  { id: 'go-ang', label: 'Zu den Angeboten', gruppe: 'Gehe zu', icon: FileText, run: () => router.push('/angebote') },
  { id: 'go-auf', label: 'Zu den Aufträgen', gruppe: 'Gehe zu', icon: ClipboardList, run: () => router.push('/auftraege') },
  { id: 'go-fer', label: 'Zur Fertigung', gruppe: 'Gehe zu', icon: Factory, run: () => router.push('/fertigung') },
  { id: 'go-ls', label: 'Zu den Lieferscheinen', gruppe: 'Gehe zu', icon: Truck, run: () => router.push('/lieferscheine') },
  { id: 'go-lager', label: 'Zum Lager', stichworte: 'bestand fertigbauteil rohmaterial', gruppe: 'Gehe zu', icon: Warehouse, run: () => router.push('/lager') },
  { id: 'go-anf', label: 'Zu den Lieferantenanfragen', gruppe: 'Gehe zu', icon: Send, run: () => router.push('/anfragen') },
  { id: 'go-stamm', label: 'Zu den Stammdaten', stichworte: 'einstellungen übersicht', gruppe: 'Gehe zu', icon: Settings, run: () => router.push('/stammdaten') },
  ...STAMM_PUNKTE.map((p) => ({ id: 'stamm-' + p.id, label: `Stammdaten: ${p.label}`, stichworte: `${p.text} stammdaten`, gruppe: 'Gehe zu', icon: p.icon, run: () => router.push(p.to) })),
  { id: 'bestand', label: 'Bestandsbauteil aus den Stammdaten wählen', stichworte: 'bauteil stammdaten vorhanden', gruppe: 'Aktion', icon: Database, run: () => { router.push('/workbench'); ui.bauteilWahlOffen = true; } },
  { id: 'neu', label: 'Neues Bauteil anlegen', gruppe: 'Aktion', icon: Plus, run: () => { router.push('/workbench'); a.hinzufuegen('Neues Bauteil'); } },
  { id: 'dup', label: 'Aktuelles Bauteil duplizieren', gruppe: 'Aktion', icon: Copy, run: () => a.auswahlId && a.duplizieren(a.auswahlId) },
  { id: 'del', label: 'Aktuelles Bauteil löschen', gruppe: 'Aktion', icon: Trash2, run: () => a.auswahlId && a.loeschen(a.auswahlId) },
  { id: 'theme', label: ui.dark ? 'Zu hellem Design wechseln' : 'Zu dunklem Design wechseln', stichworte: 'dunkel hell theme modus', gruppe: 'Ansicht', icon: ui.dark ? Sun : Moon, run: ui.toggleDark },
  { id: 'beispiel', label: 'Beispiel-Bauteile einfügen', stichworte: 'demo testdaten', gruppe: 'Daten', icon: RotateCcw, run: () => { router.push('/workbench'); a.beispieleEinfuegen(); } },
  ...a.teile.map((t, i) => ({ id: 'teil-' + t.id, label: `Gehe zu: ${i + 1}. ${t.name || 'Ohne Namen'}`, gruppe: 'Bauteil', icon: Layers, run: () => { a.auswahlId = t.id; } })),
]);

useEventListener(window, 'keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    ui.paletteOffen = !ui.paletteOffen;
    return;
  }
  const tag = e.target?.tagName;
  const tippt = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || e.target?.isContentEditable;
  if (tippt || e.ctrlKey || e.metaKey || e.altKey || ui.paletteOffen || route.meta.bereich !== 'workbench') return;
  if (e.key.toLowerCase() === 'n') { e.preventDefault(); a.hinzufuegen('Neues Bauteil'); }
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    const i = a.teile.findIndex((t) => t.id === a.auswahlId);
    const j = Math.min(a.teile.length - 1, Math.max(0, i + (e.key === 'ArrowDown' ? 1 : -1)));
    if (a.teile[j]) { e.preventDefault(); a.auswahlId = a.teile[j].id; }
  }
});
</script>

<template>
  <div class="flex h-full">
    <AppRail />
    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface/80 px-6 backdrop-blur">
        <div>
          <h1 class="text-[15px] font-semibold leading-tight">{{ route.meta.titel }}</h1>
          <p v-if="untertitel" class="text-xs leading-tight text-mute">{{ untertitel }}</p>
        </div>
        <button class="btn ml-auto !gap-3 !py-1.5 !text-mute" @click="ui.paletteOffen = true">
          <Search :size="15" /> Befehl suchen <span class="flex gap-1"><span class="kbd">Strg</span><span class="kbd">K</span></span>
        </button>
        <button class="btn !px-2.5 !py-2" :title="ui.dark ? 'Helles Design' : 'Dunkles Design'" @click="ui.toggleDark">
          <Transition name="fade" mode="out-in"><Sun v-if="ui.dark" :size="17" /><Moon v-else :size="17" /></Transition>
        </button>
        <div ref="menueRef" class="relative">
          <button class="grid h-9 w-9 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent transition hover:ring-2 hover:ring-accent/40" :title="nutzer?.name" @click="menue = !menue">{{ initialen }}</button>
          <Transition name="pop">
            <div v-if="menue" class="card absolute right-0 z-30 mt-2 w-64 p-3 shadow-xl">
              <div class="px-2 pb-2"><div class="text-sm font-semibold">{{ nutzer?.name }}</div><div class="text-xs text-mute">{{ nutzer?.id }}</div></div>
              <div class="flex flex-wrap gap-1 border-y border-line px-2 py-2"><span v-for="r in cncRollen" :key="r" class="rounded-md bg-surface2 px-1.5 py-0.5 text-[11px] text-mute">{{ r }}</span></div>
              <button class="mt-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-mute transition hover:bg-surface2 hover:text-ink" @click="abmelden"><LogOut :size="15" /> Abmelden</button>
            </div>
          </Transition>
        </div>
      </header>
      <main class="min-h-0 flex-1 overflow-auto p-6">
        <RouterView />
      </main>
    </div>
    <CommandPalette :offen="ui.paletteOffen" :befehle="befehle" @schliessen="ui.paletteOffen = false" />
    <DropOverlay @dateien="onDateien" />
    <Toasts />
  </div>
</template>
