<script setup>
// Mail-Anbindung: gemeinsames Postfach, aus dem Anfragen geholt werden (nur Mails mit Stichwort im Betreff).
// Das Passwort wird nur gespeichert, nie angezeigt.
import { ref, computed, onMounted } from 'vue';
import { Mail, PlugZap, RefreshCw, Check, AlertTriangle, KeyRound, X, Plus } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import Toggle from '../components/Toggle.vue';
import { call } from '../data/api.js';
import { benutzer } from '../data/repo.js';
import { useUi } from '../stores/ui.js';
import { useMail } from '../stores/mail.js';

const ui = useUi();
const mail = useMail();
const darf = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'System Manager'].includes(x)));
const e = ref(null);
const passwort = ref('');
const speichert = ref(false);
const testet = ref(false);
const test = ref(null);
const stand = ref('');
const neuesWort = ref('');

// Ungespeicherte Änderungen erkennen: „Jetzt abrufen“ speichert sie vorher, statt sie zu verwerfen.
function uebernehmen(daten) {
  e.value = daten;
  stand.value = JSON.stringify(daten);
}
const geaendert = computed(() => !!e.value && (JSON.stringify(e.value) !== stand.value || !!passwort.value));

onMounted(async () => {
  if (!darf.value) return;
  try { uebernehmen(await call('cnc_one.api.mail.einstellungen')); } catch (err) { ui.toast(err.message, 'warn'); }
});

// Stichwörter als Chips; gespeichert wird weiter eines je Zeile
const woerter = computed(() => (e.value?.stichwoerter ?? '').split('\n').map((w) => w.trim()).filter(Boolean));
function wortHinzu() {
  const neu = neuesWort.value.split(/[,;\n]/).map((w) => w.trim()).filter(Boolean);
  const alle = [...woerter.value];
  for (const w of neu) if (!alle.some((x) => x.toLowerCase() === w.toLowerCase())) alle.push(w);
  e.value.stichwoerter = alle.join('\n');
  neuesWort.value = '';
}
function wortWeg(w) {
  e.value.stichwoerter = woerter.value.filter((x) => x !== w).join('\n');
}
function wortTaste(ev) {
  if (ev.key === 'Enter' || ev.key === ',' || ev.key === ';') { ev.preventDefault(); wortHinzu(); }
  else if (ev.key === 'Backspace' && !neuesWort.value && woerter.value.length) wortWeg(woerter.value.at(-1));
}

// Übliche Ports je Verschlüsselung (IONOS: 993/465 mit SSL/TLS)
function verschluesselungWechseln() {
  const ports = { 'SSL/TLS': [993, 465], STARTTLS: [143, 587], 'Ohne (nur Test)': [143, 25] }[e.value.verschluesselung];
  if (ports) [e.value.imapPort, e.value.smtpPort] = ports;
}

async function speichern() {
  if (neuesWort.value.trim()) wortHinzu();
  speichert.value = true;
  try {
    uebernehmen(await call('cnc_one.api.mail.einstellungen_speichern', { daten: { ...e.value, passwort: passwort.value } }));
    passwort.value = '';
    ui.toast('Mail-Anbindung gespeichert', 'ok');
    return true;
  } catch (err) {
    ui.toast(err.message, 'warn');
    return false;
  } finally {
    speichert.value = false;
  }
}

async function testen() {
  if (!(await speichern())) return;
  testet.value = true;
  test.value = null;
  try {
    const r = await call('cnc_one.api.mail.verbindung_testen');
    test.value = { ok: true, text: `Verbindung steht. Im Postfach passen ${r.passend} Mail${r.passend === 1 ? '' : 's'} zu den Stichwörtern.` };
  } catch (err) {
    test.value = { ok: false, text: err.message };
  } finally {
    testet.value = false;
  }
}

async function abrufen() {
  if ((geaendert.value || neuesWort.value.trim()) && !(await speichern())) return;
  await mail.abrufen();
  try {
    // nur den Abrufstand auffrischen, Eingaben bleiben
    const neu = await call('cnc_one.api.mail.einstellungen');
    e.value.letzterAbruf = neu.letzterAbruf;
    e.value.letzterFehler = neu.letzterFehler;
    stand.value = JSON.stringify({ ...JSON.parse(stand.value), letzterAbruf: neu.letzterAbruf, letzterFehler: neu.letzterFehler });
  } catch { /* Anzeige des Stands ist nicht wichtig */ }
}
const zeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'noch nie');
</script>

<template>
  <div class="mx-auto max-w-[1000px]">
    <StammNav />
    <p class="mb-4 text-sm text-mute">CNC One holt aus dem gemeinsamen Postfach Mails bekannter Absender (Kontakte der Kunden, Lieferanten und deren Domains) und Mails mit einem der Stichwörter im Betreff. Von allen anderen werden nur Absender und Kennung gelesen, der Inhalt bleibt im Postfach. Im Postfach ändert sich nichts, die Mails bleiben ungelesen.</p>

    <div v-if="!darf" class="card p-5 text-sm text-mute">Die Mail-Anbindung können nur Administratoren einrichten.</div>
    <div v-else-if="!e" class="card p-5 text-sm text-mute">Wird geladen …</div>
    <form v-else class="space-y-4" @submit.prevent="speichern">
      <section class="card p-5">
        <div class="mb-3 flex flex-wrap items-center gap-3">
          <h2 class="flex items-center gap-2 text-sm font-semibold"><Mail :size="16" class="text-accent" /> Postfach</h2>
          <Toggle v-model="e.aktiv" klein label="Alle 5 Minuten automatisch abholen" class="ml-auto" />
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block"><span class="label mb-1 block">Benutzer (E-Mail-Adresse)</span><input v-model="e.benutzer" class="field" placeholder="info@cnc-hohenstein.de" autocomplete="off" /></label>
          <label class="block">
            <span class="label mb-1 block">Passwort</span>
            <input v-model="passwort" type="password" class="field" :placeholder="e.passwortGesetzt ? '•••••••• gespeichert, zum Ändern neu eingeben' : 'Passwort des Postfachs'" autocomplete="new-password" />
          </label>
          <label class="block"><span class="label mb-1 block">Absendername für Antworten</span><input v-model="e.absenderName" class="field" placeholder="CNC Hohenstein GmbH" /></label>
          <label class="block"><span class="label mb-1 block">Verschlüsselung</span>
            <select v-model="e.verschluesselung" class="field" @change="verschluesselungWechseln"><option>SSL/TLS</option><option>STARTTLS</option><option>Ohne (nur Test)</option></select>
          </label>
          <div class="grid grid-cols-[1fr_90px] gap-3"><label class="block"><span class="label mb-1 block">IMAP-Server (Abholen)</span><input v-model="e.imapServer" class="field" /></label><label class="block"><span class="label mb-1 block">Port</span><input v-model.number="e.imapPort" class="field tnum" /></label></div>
          <div class="grid grid-cols-[1fr_90px] gap-3"><label class="block"><span class="label mb-1 block">SMTP-Server (Senden)</span><input v-model="e.smtpServer" class="field" /></label><label class="block"><span class="label mb-1 block">Port</span><input v-model.number="e.smtpPort" class="field tnum" /></label></div>
        </div>
        <p class="mt-2 flex items-center gap-1.5 text-xs text-mute"><KeyRound :size="13" /> Das Passwort wird verschlüsselt gespeichert und nie wieder angezeigt.</p>
      </section>

      <section class="card p-5">
        <h2 class="mb-3 text-sm font-semibold">Welche Mails geholt werden</h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="sm:row-span-2">
            <span class="label mb-1 block">Stichwörter im Betreff</span>
            <div class="field flex min-h-[96px] flex-wrap content-start items-center gap-1.5 !py-2" @click="$refs.wortFeld?.focus()">
              <span v-for="w in woerter" :key="w" class="inline-flex items-center gap-1 rounded-lg bg-accent-soft py-0.5 pl-2.5 pr-1 text-sm text-accent">
                {{ w }}
                <button type="button" class="rounded p-0.5 hover:bg-accent/15" :title="`${w} entfernen`" @click.stop="wortWeg(w)"><X :size="13" /></button>
              </span>
              <input ref="wortFeld" v-model="neuesWort" class="min-w-[120px] flex-1 bg-transparent text-sm outline-none placeholder:text-mute" :placeholder="woerter.length ? 'weiteres Stichwort …' : 'z. B. Anfrage'" @keydown="wortTaste" @blur="neuesWort.trim() && wortHinzu()" />
              <button v-if="neuesWort.trim()" type="button" class="btn !px-2 !py-0.5 text-xs" @click.stop="wortHinzu"><Plus :size="13" /> Hinzufügen</button>
            </div>
            <p class="mt-1 text-xs text-mute">Mit Enter oder Komma hinzufügen, mit × entfernen.</p>
          </div>
          <label class="block"><span class="label mb-1 block">Nur Mails ab</span><input v-model="e.abholenAb" type="date" class="field" /></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block"><span class="label mb-1 block">Ordner</span><input v-model="e.postfachOrdner" class="field" /></label>
            <label class="block"><span class="label mb-1 block">Ordner für Gesendetes</span><input v-model="e.gesendetOrdner" class="field" /></label>
          </div>
        </div>
        <p class="mt-2 text-xs text-mute">Groß- und Kleinschreibung ist egal, „Anfrage“ findet auch „Preisanfrage“. Antworten des Kunden im selben Verlauf kommen zur bestehenden Anfrage.</p>
        <div class="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2">
          <div class="sm:col-span-2"><Toggle v-model="e.bekannteAbsender" klein label="Auch Mails bekannter Absender holen (ohne Stichwort)" /></div>
          <label class="block"><span class="label mb-1 block">Freemail-Anbieter</span>
            <textarea v-model="e.freemailDomains" rows="4" class="field resize-y text-sm" :placeholder="e.standardFreemail" />
            <span class="mt-1 block text-xs text-mute">Eine Domain je Zeile. Dort zählt nur die genaue Adresse eines Kontakts, nicht die ganze Domain. Leer = Standardliste.</span></label>
          <label class="block"><span class="label mb-1 block">Gesperrte Dateiendungen</span>
            <textarea v-model="e.gesperrteEndungen" rows="4" class="field resize-y text-sm" :placeholder="e.standardGesperrt" />
            <span class="mt-1 block text-xs text-mute">Anhänge mit diesen Endungen (Programme, Office-Dateien mit Makros) und getarnte Programme werden nie übernommen. Leer = Standardliste.</span></label>
        </div>
      </section>

      <section class="card p-5">
        <h2 class="mb-1 text-sm font-semibold">Einordnen im Posteingang</h2>
        <p class="mb-3 text-xs text-mute">Jede neue Mail kommt in ein Register: Anfrage, Bestellung, Rechnung, Lieferant oder Sonstiges. E-Rechnungen (ZUGFeRD, XRechnung) werden immer erkannt und als Eingangsrechnung angelegt. Ein bekannter Kunde mit Zeichnung oder 3D-Modell ohne Stichwort gilt als Anfrage. Im Posteingang lässt sich jede Mail mit einem Klick umsortieren.</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block"><span class="label mb-1 block">Stichwörter für Bestellungen</span><textarea v-model="e.woerterBestellung" rows="3" class="field resize-y text-sm" placeholder="Bestellung" />
            <span class="mt-1 block text-xs text-mute">im Betreff oder Dateinamen eines Anhangs, eines je Zeile</span></label>
          <label class="block"><span class="label mb-1 block">Stichwörter für Rechnungen</span><textarea v-model="e.woerterRechnung" rows="3" class="field resize-y text-sm" placeholder="Rechnung" />
            <span class="mt-1 block text-xs text-mute">gilt für Lieferanten und Unbekannte (fragt ein Kunde zu unserer Rechnung, bleibt es „Sonstiges“)</span></label>
        </div>
      </section>

      <section class="card p-5">
        <h2 class="mb-3 text-sm font-semibold">Antwort mit Angebot</h2>
        <label class="block"><span class="label mb-1 block">Text der Mail</span><textarea v-model="e.antwortVorlage" rows="8" class="field leading-relaxed" /></label>
        <p class="mt-2 text-xs text-mute">Platzhalter: <code>{anrede}</code> (z. B. „Sehr geehrter Herr Muster“ aus dem Kontakt), <code>{angebot}</code>, <code>{anfrage}</code> (Anfrage-Nr. des Kunden), <code>{absender}</code>, <code>{firma}</code>. Unter dem Text steht die zitierte Anfrage; vor dem Senden lässt sich alles ändern.</p>
      </section>

      <section class="card flex flex-wrap items-center gap-3 p-5">
        <div class="text-sm">
          <div>Letzter Abruf: <span class="tnum">{{ zeit(e.letzterAbruf) }}</span></div>
          <div v-if="e.letzterFehler" class="mt-0.5 flex items-start gap-1.5 text-xs text-warn"><AlertTriangle :size="13" class="mt-0.5 shrink-0" /> {{ e.letzterFehler }}</div>
        </div>
        <div class="ml-auto flex flex-wrap items-center gap-2">
          <span v-if="geaendert" class="flex items-center gap-1.5 text-xs text-warn"><span class="size-1.5 rounded-full bg-warn" /> Nicht gespeichert</span>
          <button type="button" class="btn" :disabled="testet || speichert" @click="testen"><PlugZap :size="15" /> {{ testet ? 'Teste …' : 'Speichern und testen' }}</button>
          <button type="button" class="btn" :disabled="mail.ruft" @click="abrufen"><RefreshCw :size="15" :class="mail.ruft ? 'animate-spin' : ''" /> {{ geaendert ? 'Speichern und abrufen' : 'Jetzt abrufen' }}</button>
          <button type="submit" class="btn btn-primary" :disabled="speichert"><Check :size="15" /> Speichern</button>
        </div>
        <p v-if="test" class="w-full rounded-xl px-3 py-2 text-sm" :class="test.ok ? 'bg-ok/10 text-ok' : 'bg-warn/10 text-warn'">{{ test.text }}</p>
      </section>
    </form>
  </div>
</template>
