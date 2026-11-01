<script setup>
// Angebot per Mail schicken: bei einer Mail-Anfrage als Antwort im selben Verlauf, sonst an den Kontakt des Kunden.
// Empfänger, Betreff und Text sind vorbelegt und änderbar; das Angebot hängt als PDF an.
import { ref, onMounted } from 'vue';
import { X, Send, FileText, Reply, AlertTriangle, Loader } from '@lucide/vue';
import { call } from '../data/api.js';
import PdfVorschauDialog from './PdfVorschauDialog.vue';
import { benutzer } from '../data/repo.js';
import { useBelege } from '../stores/belege.js';
import { useMail } from '../stores/mail.js';
import { useUi } from '../stores/ui.js';

const props = defineProps({ angebot: { type: Object, required: true } });
const emit = defineEmits(['schliessen', 'gesendet']);
const ui = useUi();
const belege = useBelege();
const mail = useMail();

const v = ref(null);
const sendet = ref(false);
const pdf = ref(null);
const istAdmin = (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'System Manager'].includes(x));

onMounted(async () => {
  try { v.value = await call('cnc_one.api.mail.antwort_vorschlag', { angebot: props.angebot.id }); } catch (e) { ui.toast(e.message, 'warn'); emit('schliessen'); }
});

async function pdfAnsehen() {
  try { pdf.value = await call('cnc_one.api.angebot.pdf', { id: props.angebot.id }); } catch (e) { ui.toast(e.message, 'warn'); }
}

async function senden() {
  sendet.value = true;
  try {
    const r = await call('cnc_one.api.mail.angebot_senden', { angebot: props.angebot.id, an: v.value.an, cc: v.value.cc, betreff: v.value.betreff, text: v.value.text });
    belege.einsetzen(r.angebot);
    if (r.mailAnfrage) mail.zaehlen();
    ui.toast(`Angebot an ${v.value.an} geschickt`, 'ok');
    if (r.hinweis) ui.toast(r.hinweis, 'warn');
    emit('gesendet', r);
  } catch (e) {
    ui.toast(`Nicht gesendet: ${e.message}`, 'warn');
  } finally {
    sendet.value = false;
  }
}
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
      <Transition name="pop" appear>
        <div class="card flex max-h-[92vh] w-[min(760px,96vw)] flex-col overflow-hidden shadow-2xl">
          <header class="flex items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h2 class="text-base font-semibold">Angebot per Mail senden</h2>
              <p class="text-xs text-mute">{{ angebot.id }} · {{ angebot.kopf.kundeName }}<template v-if="v?.absender"> · von {{ v.absender }}</template></p>
            </div>
            <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="emit('schliessen')"><X :size="18" /></button>
          </header>

          <div v-if="!v" class="flex items-center gap-2 p-6 text-sm text-mute"><Loader :size="15" class="animate-spin" /> Wird vorbereitet …</div>
          <div v-else class="space-y-3 overflow-auto px-6 py-5">
            <p v-if="v.antwortAuf" class="flex items-center gap-2 rounded-xl bg-accent-soft/60 px-3 py-2 text-sm"><Reply :size="15" class="shrink-0 text-accent" /> Antwort auf die Anfrage von <strong>{{ v.antwortAuf.vonName }}</strong> vom {{ zeit(v.antwortAuf.datum) }}, im selben Verlauf</p>
            <p v-if="!v.bereit" class="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-sm text-warn">
              <AlertTriangle :size="15" class="mt-0.5 shrink-0" />
              <span>Die Mail-Anbindung ist noch nicht eingerichtet (SMTP-Server, Benutzer, Passwort).<RouterLink v-if="istAdmin" to="/stammdaten/mail" class="ml-1 underline" @click="emit('schliessen')">Jetzt einrichten</RouterLink></span>
            </p>
            <label class="block"><span class="label mb-1 block">An</span><input v-model="v.an" class="field" placeholder="kunde@firma.de" /></label>
            <label class="block"><span class="label mb-1 block">CC</span><input v-model="v.cc" class="field" placeholder="mehrere mit Komma trennen" /></label>
            <label class="block"><span class="label mb-1 block">Betreff</span><input v-model="v.betreff" class="field" /></label>
            <label class="block"><span class="label mb-1 block">Text</span><textarea v-model="v.text" rows="12" class="field font-[inherit] leading-relaxed" /></label>
            <button class="inline-flex items-center gap-1.5 rounded-lg bg-surface2 px-3 py-1.5 text-sm hover:bg-accent-soft hover:text-accent" title="PDF ansehen" @click="pdfAnsehen"><FileText :size="15" /> {{ v.anhang }}</button>
          </div>

          <footer class="flex items-center justify-end gap-2 border-t border-line px-6 py-4">
            <span v-if="angebot.status === 'Entwurf'" class="mr-auto text-xs text-mute">Nach dem Senden steht das Angebot auf „Gesendet“.</span>
            <button class="btn" @click="emit('schliessen')">Abbrechen</button>
            <button class="btn btn-primary" :disabled="!v || !v.bereit || sendet || !v.an.trim()" :class="!v || !v.bereit || !v.an.trim() ? 'pointer-events-none opacity-40' : ''" @click="senden">
              <Send :size="15" /> {{ sendet ? 'Wird gesendet …' : 'Senden' }}
            </button>
          </footer>
        </div>
      </Transition>
    </div>
    <PdfVorschauDialog v-if="pdf" :url="pdf.url" :name="pdf.name" @schliessen="pdf = null" />
  </Teleport>
</template>
