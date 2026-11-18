<script setup>
// Lieferantenanfrage per Mail: eine Mail für den ganzen Vorgang, die Lieferanten stehen in BCC und sehen sich nicht.
// An, CC, BCC, Betreff und Text sind frei änderbar; {tabelle} im Text wird zur Tabelle der Positionen.
import { ref, onMounted } from 'vue';
import { X, Send, AlertTriangle, Loader, EyeOff, Table2 } from '@lucide/vue';
import { call } from '../data/api.js';
import Toggle from './Toggle.vue';
import { benutzer } from '../data/repo.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ vorgang: { type: String, required: true } });
const emit = defineEmits(['schliessen', 'gesendet']);
const ui = useUi();
const anfragen = useAnfragen();

const v = ref(null);
const sendet = ref(false);
const zeichnungen = ref(true);
const modelle = ref(false);
const textfeld = ref(null);
const istAdmin = (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'System Manager'].includes(x));

onMounted(async () => {
  try { v.value = await call('cnc_one.api.anfrage.mail_vorschlag', { vorgang: props.vorgang }); } catch (e) { ui.toast(e.message, 'warn'); emit('schliessen'); }
});

// Platzhalter für die Tabelle an der Cursorstelle einsetzen (falls er gelöscht wurde)
function tabelleEinfuegen() {
  const el = textfeld.value;
  const pos = el?.selectionStart ?? v.value.text.length;
  v.value.text = `${v.value.text.slice(0, pos)}{tabelle}${v.value.text.slice(pos)}`;
}

async function senden() {
  sendet.value = true;
  try {
    const r = await call('cnc_one.api.anfrage.mail_senden', {
      vorgang: props.vorgang, an: v.value.an, cc: v.value.cc, bcc: v.value.bcc, betreff: v.value.betreff, text: v.value.text,
      zeichnungen: zeichnungen.value ? 1 : 0, modelle: modelle.value ? 1 : 0,
    });
    anfragen.alleEinsetzen(r.anfragen);
    ui.toast(`Anfrage ${props.vorgang} verschickt`, 'ok');
    if (r.hinweis) ui.toast(r.hinweis, 'warn');
    emit('gesendet', r);
  } catch (e) {
    ui.toast(`Nicht gesendet: ${e.message}`, 'warn');
  } finally {
    sendet.value = false;
  }
}
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
const bereit = () => v.value && v.value.bereit && (v.value.an.trim() || v.value.cc.trim() || v.value.bcc.trim()) && v.value.betreff.trim();
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[55] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[94vh] w-[min(860px,96vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h2 class="text-base font-semibold">Anfrage per Mail senden</h2>
              <p class="text-xs text-mute">Vorgang {{ vorgang }}<template v-if="v?.absender"> · von {{ v.absender }}</template></p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div v-if="!v" class="flex items-center gap-2 p-6 text-sm text-mute"><Loader :size="15" class="animate-spin" /> Wird vorbereitet …</div>
          <div v-else class="space-y-3 overflow-auto px-6 py-5">
            <p v-if="v.versendetAm" class="rounded-xl bg-surface2 px-3 py-2 text-sm">Schon verschickt am {{ zeit(v.versendetAm) }}. Erneut senden schickt die Mail noch einmal.</p>
            <p v-if="!v.bereit" class="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-sm text-warn">
              <AlertTriangle :size="15" class="mt-0.5 shrink-0" />
              <span>Die Mail-Anbindung ist noch nicht eingerichtet (SMTP-Server, Benutzer, Passwort).<RouterLink v-if="istAdmin" to="/stammdaten/mail" class="ml-1 underline" @click="emit('schliessen')">Jetzt einrichten</RouterLink></span>
            </p>
            <p v-if="v.ohneAdresse.length" class="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-sm text-warn">
              <AlertTriangle :size="15" class="mt-0.5 shrink-0" />
              <span>Ohne Mail-Adresse: {{ v.ohneAdresse.join(', ') }}. Bitte unten in BCC ergänzen oder beim Lieferanten in den Stammdaten eintragen.</span>
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="block"><span class="label mb-1 block">An</span><input v-model="v.an" class="field" placeholder="z. B. unsere eigene Adresse" /></label>
              <label class="block"><span class="label mb-1 block">CC</span><input v-model="v.cc" class="field" placeholder="mehrere mit Komma trennen" /></label>
            </div>
            <label class="block">
              <span class="label mb-1 flex items-center gap-1.5"><EyeOff :size="12" /> BCC – die Lieferanten (sehen sich nicht gegenseitig)</span>
              <input v-model="v.bcc" class="field" />
            </label>
            <label class="block"><span class="label mb-1 block">Betreff</span><input v-model="v.betreff" class="field" /></label>
            <label class="block">
              <span class="label mb-1 flex items-center justify-between">
                <span>Text</span>
                <button v-if="!v.text.includes('{tabelle}')" type="button" class="inline-flex items-center gap-1 text-xs normal-case tracking-normal text-accent hover:underline" @click="tabelleEinfuegen"><Table2 :size="12" /> Tabelle hier einsetzen</button>
              </span>
              <textarea ref="textfeld" v-model="v.text" rows="12" class="field font-[inherit] leading-relaxed" />
              <span class="mt-1 block text-[11px] text-mute">An der Stelle <code class="rounded bg-surface2 px-1">{tabelle}</code> steht in der Mail die Tabelle der Positionen.</span>
            </label>
            <div class="overflow-auto rounded-xl border border-line">
              <table class="w-full text-left text-xs">
                <thead class="bg-surface2 text-mute"><tr><th v-for="k in v.tabelle.kopf" :key="k" class="px-3 py-2 font-medium">{{ k }}</th></tr></thead>
                <tbody><tr v-for="(z, i) in v.tabelle.zeilen" :key="i" class="border-t border-line"><td v-for="(w, j) in z" :key="j" class="px-3 py-2 align-top">{{ w }}</td></tr></tbody>
              </table>
            </div>
            <div v-if="v.zeichnungen" class="flex flex-wrap gap-5">
              <Toggle v-model="zeichnungen" klein label="Zeichnungen anhängen" />
              <Toggle v-model="modelle" klein label="3D-Modelle anhängen" />
            </div>
          </div>

          <footer class="flex items-center justify-end gap-2 border-t border-line px-6 py-4">
            <span class="mr-auto text-xs text-mute">Antworten mit der Nummer {{ vorgang }} landen automatisch bei der Anfrage des Lieferanten.</span>
            <button class="btn" @click="emit('schliessen')">Später</button>
            <button class="btn btn-primary" :disabled="!bereit() || sendet" :class="!bereit() ? 'pointer-events-none opacity-40' : ''" @click="senden">
              <Send :size="15" /> {{ sendet ? 'Wird gesendet …' : 'Senden' }}
            </button>
          </footer>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>
