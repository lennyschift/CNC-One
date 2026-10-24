<script setup>
import { reactive, computed, ref } from 'vue';
import { Plus, Trash2, AlertTriangle, Check } from '@lucide/vue';
import StammNav from '../components/StammNav.vue';
import NumField from '../components/NumField.vue';
import { useFirma } from '../stores/firma.js';
import { benutzer } from '../data/repo.js';
import { ibanGueltig, ibanFormatiert } from '../lib/iban.js';

const store = useFirma();
const f = reactive(JSON.parse(JSON.stringify(store.firma)));
const darf = computed(() => (benutzer()?.rollen ?? []).some((x) => ['CNC Admin', 'CNC Buchhaltung', 'System Manager'].includes(x)));
const speichert = ref(false);

const bankStatus = (b) => (!b.iban.trim() ? 'leer' : ibanGueltig(b.iban) ? 'ok' : 'falsch');
const gueltig = computed(() => !!f.firmenname.trim() && f.banken.every((b) => bankStatus(b) !== 'falsch'));

function ibanFertig(b) { if (ibanGueltig(b.iban)) b.iban = ibanFormatiert(b.iban); }
async function speichern() {
  speichert.value = true;
  const rec = await store.speichern(f);
  speichert.value = false;
  if (rec) Object.assign(f, JSON.parse(JSON.stringify(rec)));
}
</script>

<template>
  <div class="mx-auto max-w-[1000px]">
    <StammNav />
    <p class="mb-4 text-sm text-mute">Diese Angaben stehen auf Angeboten, Lieferscheinen, Rechnungen und Mahnungen. Bei einer Rechnung werden sie beim Festschreiben als Kopie gespeichert.</p>

    <form class="space-y-4" @submit.prevent="speichern">
      <section class="card p-5">
        <h2 class="mb-3 text-sm font-semibold">Firma und Anschrift</h2>
        <div class="grid gap-3 sm:grid-cols-[1fr_180px]">
          <label class="block"><span class="label mb-1 block">Name der Firma</span><input v-model="f.firmenname" class="field" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">Rechtsform</span><input v-model="f.rechtsform" class="field" placeholder="z. B. GmbH" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">Straße und Nummer</span><input v-model="f.strasse" class="field" :disabled="!darf" /></label>
          <span class="hidden sm:block" />
          <div class="grid grid-cols-[110px_1fr] gap-3 sm:col-span-2"><label class="block"><span class="label mb-1 block">PLZ</span><input v-model="f.plz" class="field" :disabled="!darf" /></label><label class="block"><span class="label mb-1 block">Ort</span><input v-model="f.ort" class="field" :disabled="!darf" /></label></div>
          <label class="block"><span class="label mb-1 block">Telefon</span><input v-model="f.telefon" class="field" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">E-Mail</span><input v-model="f.email" class="field" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">Webseite</span><input v-model="f.web" class="field" :disabled="!darf" /></label>
        </div>
        <p class="mt-3 text-xs text-mute">Das Logo lässt sich später hier ergänzen.</p>
      </section>

      <section class="card p-5">
        <h2 class="mb-3 text-sm font-semibold">Steuer und Register</h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block"><span class="label mb-1 block">Steuernummer</span><input v-model="f.steuernummer" class="field" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">USt-IdNr.</span><input v-model="f.ustId" class="field" placeholder="DE123456789" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">Handelsregister</span><input v-model="f.handelsregister" class="field" placeholder="z. B. Amtsgericht Stuttgart HRB 12345" :disabled="!darf" /></label>
          <label class="block"><span class="label mb-1 block">Geschäftsführer</span><input v-model="f.geschaeftsfuehrer" class="field" :disabled="!darf" /></label>
        </div>
      </section>

      <section class="card p-5">
        <div class="mb-3 flex items-center justify-between"><h2 class="text-sm font-semibold">Bankverbindungen</h2><button v-if="darf" type="button" class="btn !py-1 !text-xs" @click="f.banken.push({ bezeichnung: '', iban: '', bic: '' })"><Plus :size="13" /> Bank</button></div>
        <div class="space-y-2">
          <div v-for="(b, i) in f.banken" :key="i" class="grid items-start gap-2 rounded-xl border border-line p-3 sm:grid-cols-[170px_1fr_150px_auto]">
            <input v-model="b.bezeichnung" class="field" placeholder="Bank, z. B. Sparkasse" :disabled="!darf" />
            <div>
              <input v-model="b.iban" class="field tnum" placeholder="IBAN" :disabled="!darf" @blur="ibanFertig(b)" />
              <p v-if="bankStatus(b) === 'falsch'" class="mt-1 flex items-center gap-1 text-[11px] text-accent"><AlertTriangle :size="12" /> Die IBAN stimmt nicht (Länge oder Prüfziffer).</p>
              <p v-else-if="bankStatus(b) === 'ok'" class="mt-1 flex items-center gap-1 text-[11px] text-ok"><Check :size="12" /> Prüfziffer stimmt.</p>
            </div>
            <input v-model="b.bic" class="field" placeholder="BIC" :disabled="!darf" />
            <button v-if="darf" type="button" class="grid h-9 w-9 place-items-center rounded-lg text-mute hover:text-accent" title="Entfernen" @click="f.banken.splice(i, 1)"><Trash2 :size="15" /></button>
          </div>
          <p v-if="!f.banken.length" class="rounded-xl border border-dashed border-line px-4 py-5 text-center text-sm text-mute">Noch keine Bankverbindung.</p>
        </div>
      </section>

      <section class="card p-5">
        <h2 class="mb-3 text-sm font-semibold">Rechnung und Mahnwesen</h2>
        <div class="grid gap-3 sm:grid-cols-3">
          <NumField v-model="f.zahlungszielTage" label="Zahlungsziel (Standard)" unit="Tage" :decimals="0" />
          <NumField v-model="f.mahnfristTage" label="Frist je Mahnung" unit="Tage" :decimals="0" />
          <NumField v-model="f.mahngebuehr" label="Mahngebühr je Mahnung" unit="€" hint="0 = keine, die Zahlungserinnerung ist immer gebührenfrei" />
          <label class="block sm:col-span-3"><span class="label mb-1 block">Einleitungstext der Rechnung</span><textarea v-model="f.rechnungText" rows="2" class="field resize-y" :disabled="!darf" /></label>
          <label class="block sm:col-span-3"><span class="label mb-1 block">Fußtext der Rechnung</span><textarea v-model="f.rechnungFusstext" rows="2" class="field resize-y" :disabled="!darf" /></label>
        </div>
      </section>

      <div v-if="darf" class="flex justify-end"><button type="submit" class="btn btn-primary" :disabled="!gueltig || speichert" :class="!gueltig || speichert ? 'pointer-events-none opacity-40' : ''">Firmendaten speichern</button></div>
      <p v-else class="text-center text-xs text-mute">Die Firmendaten pflegt die Buchhaltung oder der Admin.</p>
    </form>
  </div>
</template>
