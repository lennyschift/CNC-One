<script setup>
// Meine Einstellungen: was in Mails von mir steht (Signatur mit Durchwahl, Absendername). Jeder Benutzer pflegt nur
// seine eigenen; ohne Angaben gilt der gemeinsame Absender aus der Mail-Anbindung.
import { ref, computed, onMounted } from 'vue';
import { UserCog, Check, Mail, PenLine } from '@lucide/vue';
import Toggle from '../components/Toggle.vue';
import { call } from '../data/api.js';
import { useUi } from '../stores/ui.js';

const ui = useUi();
const p = ref(null);
const stand = ref('');
const speichert = ref(false);
const FELDER = ['anzeigename', 'funktion', 'telefon', 'mobil', 'email', 'nameAlsAbsender', 'signatur'];
const formular = () => Object.fromEntries(FELDER.map((k) => [k, p.value[k]]));
function setzen(x) { p.value = x; stand.value = JSON.stringify(formular()); }
onMounted(async () => { try { setzen(await call('cnc_one.api.einstellung.profil')); } catch (e) { ui.toast(e.message, 'warn'); } });
const geaendert = computed(() => p.value && JSON.stringify(formular()) !== stand.value);
const eigene = ref(false);

// Vorschau wie der Server sie baut (Name, Funktion, Firma, Telefon · Mobil, E-Mail)
const vorschau = computed(() => {
  if (!p.value) return '';
  if (p.value.signatur.trim()) return p.value.signatur.trim();
  const name = p.value.anzeigename.trim() || p.value.vorschlagName;
  const tel = [p.value.telefon && `Telefon ${p.value.telefon}`, p.value.mobil && `Mobil ${p.value.mobil}`].filter(Boolean).join(' · ');
  return [name, p.value.funktion, p.value.firma, tel, p.value.email.trim() || p.value.vorschlagEmail].filter(Boolean).join('\n');
});
const absender = computed(() => {
  if (!p.value) return '';
  const basis = p.value.vorschauAbsender.includes(' | ') ? p.value.vorschauAbsender.split(' | ').slice(1).join(' | ') : p.value.vorschauAbsender;
  const name = p.value.anzeigename.trim() || p.value.vorschlagName;
  return p.value.nameAlsAbsender && name ? `${name} | ${basis}` : basis;
});

async function speichern() {
  speichert.value = true;
  try {
    setzen(await call('cnc_one.api.einstellung.profil_speichern', { daten: formular() }));
    ui.toast('Gespeichert – gilt ab der nächsten Mail', 'ok');
  } catch (e) {
    ui.toast(e.message, 'warn');
  } finally {
    speichert.value = false;
  }
}
</script>

<template>
  <div class="mx-auto max-w-[900px]">
    <p class="mb-4 text-sm text-mute">Diese Angaben stehen in den Mails, die du aus CNC One sendest (Angebot, Auftragsbestätigung, Lieferantenanfragen): als Signatur an der Stelle von <code>{absender}</code> im Mailtext und auf Wunsch als Absendername. Jeder Benutzer hat seine eigenen.</p>
    <div v-if="!p" class="card p-5 text-sm text-mute">Wird geladen …</div>
    <form v-else class="grid items-start gap-4 lg:grid-cols-[1fr_340px]" @submit.prevent="speichern">
      <section class="card p-5">
        <h2 class="mb-3 flex items-center gap-2 text-sm font-semibold"><UserCog :size="16" class="text-accent" /> Meine Angaben <span class="font-normal text-mute">· {{ p.benutzer }}</span></h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block"><span class="label mb-1 block">Name in Mails</span><input v-model="p.anzeigename" class="field" :placeholder="p.vorschlagName" /></label>
          <label class="block"><span class="label mb-1 block">Funktion</span><input v-model="p.funktion" class="field" placeholder="z. B. Vertrieb" /></label>
          <label class="block"><span class="label mb-1 block">Telefon (Durchwahl)</span><input v-model="p.telefon" class="field tnum" placeholder="z. B. 07903 3678-12" /></label>
          <label class="block"><span class="label mb-1 block">Mobil</span><input v-model="p.mobil" class="field tnum" /></label>
          <label class="block sm:col-span-2"><span class="label mb-1 block">E-Mail in der Signatur</span><input v-model="p.email" class="field" :placeholder="p.vorschlagEmail" /></label>
          <div class="sm:col-span-2"><Toggle v-model="p.nameAlsAbsender" klein label="Meinen Namen als Absender zeigen" /></div>
        </div>
        <div class="mt-4 border-t border-line pt-4">
          <button v-if="!eigene && !p.signatur" type="button" class="inline-flex items-center gap-1.5 text-sm text-accent hover:underline" @click="eigene = true"><PenLine :size="14" /> Eigene Signatur schreiben statt der erzeugten</button>
          <label v-else class="block"><span class="label mb-1 block">Eigene Signatur</span>
            <textarea v-model="p.signatur" rows="6" class="field resize-y text-sm leading-relaxed" placeholder="leer = aus den Angaben oben erzeugen" />
            <span class="mt-1 block text-xs text-mute">Ersetzt die erzeugte Signatur vollständig. Leer lassen, um sie wieder aus den Angaben zu bilden.</span></label>
        </div>
        <div class="mt-4 flex items-center gap-3">
          <span v-if="geaendert" class="flex items-center gap-1.5 text-xs text-warn"><span class="size-1.5 rounded-full bg-warn" /> Nicht gespeichert</span>
          <button type="submit" class="btn btn-primary ml-auto" :disabled="speichert"><Check :size="15" /> Speichern</button>
        </div>
      </section>

      <aside class="card p-5">
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><Mail :size="15" class="text-accent" /> So sieht es beim Kunden aus</h3>
        <div class="label mb-1">Absender</div>
        <div class="mb-4 rounded-lg bg-surface2 px-3 py-2 text-sm">{{ absender }}</div>
        <div class="label mb-1">Ende der Mail</div>
        <div class="whitespace-pre-line rounded-lg bg-surface2 px-3 py-2 text-sm leading-relaxed">{{ `Mit freundlichen Grüßen
${vorschau}` }}</div>
        <p v-if="!p.angelegt" class="mt-3 text-xs text-mute">Noch nicht gespeichert: bis dahin steht in deinen Mails der gemeinsame Absender „{{ p.vorschauAbsender }}“.</p>
      </aside>
    </form>
  </div>
</template>
