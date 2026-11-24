<script setup>
// Zuschlag an einen Lieferanten: alle Positionen mit Preis sind vorgewählt und lassen sich abwählen; Optionen und
// Alternativen aus dem eingelesenen Angebot stehen unter ihrer Position und ersetzen sie, wenn man sie wählt.
// Eine Position geht nur an einen Lieferanten: war sie schon an einen anderen vergeben, fällt sie dort heraus.
import { ref, computed } from 'vue';
import { X, Award, CornerDownRight, AlertTriangle, Undo2 } from '@lucide/vue';
import { weiterePositionen } from '../lib/vergleich.js';
import { eur, zahl } from '../lib/format.js';
import { useAnfragen } from '../stores/anfragen.js';

const props = defineProps({ anfrage: { type: Object, required: true }, andere: { type: Array, default: () => [] } });
const emit = defineEmits(['schliessen']);
const store = useAnfragen();
const a = props.anfrage;

// je Position der Preis der ersten Menge
const positionen = computed(() => a.positionen.map((p, i) => {
  const m = p.mengen[0];
  const q = (a.antwort?.preise ?? []).find((x) => x.posKey === p.key && Number(x.menge) === Number(m));
  const gesamt = q && (Number(q.proStk) > 0 || Number(q.einmalig) > 0) ? Math.round(((Number(q.proStk) || 0) * m + (Number(q.einmalig) || 0)) * 100) / 100 : null;
  return { ...p, nr: i + 1, menge: m, gesamt };
}));
const weitere = computed(() => weiterePositionen([a]));
const unter = (key) => weitere.value.filter((w) => w.bezug === key);
const zusaetzlich = computed(() => weitere.value.filter((w) => !w.bezug));

// Auswahl: bestehender Zuschlag oder alle Positionen mit Preis
const altGewaehlt = ref(new Set(a.zuschlag ? a.zuschlagAlternativen ?? [] : []));
const ersetzt = (key) => unter(key).some((w) => altGewaehlt.value.has(w.index));
const posGewaehlt = ref(new Set(a.zuschlag
  ? (a.zuschlagPositionen ?? []).filter((k) => !ersetzt(k))
  : positionen.value.filter((p) => p.gesamt != null).map((p) => p.key)));

function pos(key) {
  const s = new Set(posGewaehlt.value);
  if (s.has(key)) s.delete(key);
  else {
    s.add(key);
    const alt = new Set(altGewaehlt.value);
    for (const w of unter(key)) alt.delete(w.index); // Position statt Alternative
    altGewaehlt.value = alt;
  }
  posGewaehlt.value = s;
}
function alt(w) {
  const s = new Set(altGewaehlt.value);
  if (s.has(w.index)) s.delete(w.index);
  else {
    s.add(w.index);
    if (w.bezug) { const p = new Set(posGewaehlt.value); p.delete(w.bezug); posGewaehlt.value = p; } // Alternative statt Position
  }
  altGewaehlt.value = s;
}
const alleMitPreis = computed(() => positionen.value.filter((p) => p.gesamt != null).map((p) => p.key));
function alle(an) {
  posGewaehlt.value = new Set(an ? alleMitPreis.value : []);
  altGewaehlt.value = new Set();
}

// was an den Server geht: Positionen inkl. der durch Alternativen ersetzten
const ergebnis = computed(() => {
  const alts = weitere.value.filter((w) => altGewaehlt.value.has(w.index));
  const keys = [...new Set([...posGewaehlt.value, ...alts.map((w) => w.bezug).filter(Boolean)])];
  const summe = positionen.value.filter((p) => posGewaehlt.value.has(p.key)).reduce((s, p) => s + (p.gesamt ?? 0), 0) + alts.reduce((s, w) => s + Number(w.o.betrag), 0);
  return { keys, alts: alts.map((w) => w.index), summe: Math.round((summe + (keys.length || alts.length ? Number(a.antwort?.nebenkosten) || 0 : 0)) * 100) / 100 };
});
// bisher an einen anderen Lieferanten vergeben
const bisher = (key) => props.andere.find((x) => x.id !== a.id && x.zuschlag && (x.zuschlagPositionen ?? []).includes(key))?.lieferantName ?? '';
const konflikte = computed(() => ergebnis.value.keys.filter((k) => bisher(k)));

const speichert = ref(false);
async function erteilen() {
  if (!ergebnis.value.keys.length && !ergebnis.value.alts.length) return;
  speichert.value = true;
  try {
    if (await store.zuschlag(a.id, true, ergebnis.value.keys, ergebnis.value.alts)) emit('schliessen');
  } finally { speichert.value = false; }
}
async function zuruecknehmen() {
  speichert.value = true;
  try {
    if (await store.zuschlag(a.id, false)) emit('schliessen');
  } finally { speichert.value = false; }
}
const beschreibung = (o) => [[o.werkstoff, o.zustand].filter(Boolean).join(' '), [o.form, o.abmessung].filter(Boolean).join(' ')].filter(Boolean).join(' · ') || String(o.text ?? '').split(/\r?\n/)[0] || `Position ${o.pos}`;
const mengenText = (o) => [o.stueck != null && `${zahl(o.stueck, 0)} Stk`, o.kg != null && `${zahl(o.kg, 2)} kg`, o.meter != null && `${zahl(o.meter, 3)} m`].filter(Boolean).join(' · ');
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-3 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[92vh] w-[min(760px,98vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
            <div class="min-w-0">
              <h2 class="flex items-center gap-2 text-base font-semibold"><Award :size="18" class="text-ok" /> Zuschlag an {{ a.lieferantName }}</h2>
              <p class="text-xs text-mute">Was soll bei diesem Lieferanten bestellt werden? Abwählen, was woanders bestellt wird.</p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div class="min-h-0 flex-1 overflow-auto px-6 py-4">
            <div class="mb-2 flex gap-3 text-xs">
              <button class="text-accent hover:underline" @click="alle(true)">Alle mit Preis</button>
              <button class="text-mute hover:text-ink hover:underline" @click="alle(false)">Keine</button>
            </div>
            <div class="divide-y divide-line rounded-xl border border-line">
              <template v-for="p in positionen" :key="p.key">
                <label class="flex items-center gap-3 px-3 py-2.5" :class="p.gesamt == null ? 'opacity-50' : 'cursor-pointer hover:bg-surface2/60'">
                  <input type="checkbox" class="h-4 w-4 accent-[var(--accent)]" :disabled="p.gesamt == null" :checked="posGewaehlt.has(p.key)" @change="pos(p.key)" />
                  <span class="w-6 shrink-0 text-sm text-mute">{{ p.nr }}</span>
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-sm font-medium">{{ p.agName ? `${p.agName}: ` : '' }}{{ p.teil.name }}</span>
                    <span class="block truncate text-xs text-mute">{{ p.menge }} {{ p.einheit }}<template v-if="ersetzt(p.key)"> · ersetzt durch die Alternative darunter</template><template v-if="bisher(p.key)"> · bisher an {{ bisher(p.key) }}</template></span>
                  </span>
                  <span class="text-sm font-semibold tnum">{{ p.gesamt == null ? 'kein Preis' : eur(p.gesamt) }}</span>
                </label>
                <label v-for="w in unter(p.key)" :key="w.key" class="flex cursor-pointer items-center gap-3 bg-surface2/40 py-2 pl-10 pr-3 hover:bg-surface2/70">
                  <CornerDownRight :size="15" class="shrink-0 text-mute" />
                  <input type="checkbox" class="h-4 w-4 accent-[var(--accent)]" :checked="altGewaehlt.has(w.index)" @change="alt(w)" />
                  <span class="min-w-0 flex-1">
                    <span class="flex items-center gap-1.5 text-sm"><span class="rounded-full bg-warn/15 px-1.5 text-[10px] font-semibold text-warn">{{ w.option ? 'Option' : 'Alternative' }}</span><span class="truncate">{{ beschreibung(w.o) }}</span></span>
                    <span class="block text-xs text-mute">Pos. {{ w.o.pos || '–' }} im Angebot · {{ mengenText(w.o) }} · statt Position {{ p.nr }}</span>
                  </span>
                  <span class="text-sm font-semibold tnum">{{ eur(w.o.betrag) }}</span>
                </label>
              </template>
              <label v-for="w in zusaetzlich" :key="w.key" class="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-surface2/60">
                <input type="checkbox" class="h-4 w-4 accent-[var(--accent)]" :checked="altGewaehlt.has(w.index)" @change="alt(w)" />
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-1.5 text-sm"><span class="rounded-full bg-accent/10 px-1.5 text-[10px] font-semibold text-accent">zusätzlich</span><span class="truncate">{{ beschreibung(w.o) }}</span></span>
                  <span class="block text-xs text-mute">Pos. {{ w.o.pos || '–' }} im Angebot · {{ mengenText(w.o) }}</span>
                </span>
                <span class="text-sm font-semibold tnum">{{ eur(w.o.betrag) }}</span>
              </label>
            </div>
            <p v-if="konflikte.length" class="mt-3 flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-xs">
              <AlertTriangle :size="14" class="mt-0.5 shrink-0 text-warn" />
              <span>Position {{ konflikte.map((k) => positionen.find((p) => p.key === k)?.nr).join(', ') }} ging bisher an einen anderen Lieferanten; dort wird sie herausgenommen.</span>
            </p>
          </div>

          <footer class="flex flex-wrap items-center gap-3 border-t border-line px-6 py-4">
            <div class="text-sm">Summe <span class="font-semibold tnum">{{ eur(ergebnis.summe) }}</span><span v-if="a.antwort?.nebenkosten" class="text-xs text-mute"> inkl. {{ eur(a.antwort.nebenkosten) }} Nebenkosten</span></div>
            <button v-if="a.zuschlag" class="btn ml-auto" :disabled="speichert" @click="zuruecknehmen"><Undo2 :size="15" /> Zuschlag zurücknehmen</button>
            <button class="btn btn-primary" :class="a.zuschlag ? '' : 'ml-auto'" :disabled="speichert || (!ergebnis.keys.length && !ergebnis.alts.length)" @click="erteilen"><Award :size="15" /> {{ a.zuschlag ? 'Zuschlag ändern' : 'Zuschlag erteilen' }}</button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
