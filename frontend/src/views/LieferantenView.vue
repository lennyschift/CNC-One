<script setup>
import { Truck, UserRound, Plus, Trash2, Send } from '@lucide/vue';
import StammListe from '../components/StammListe.vue';

const felder = [
  { key: 'leistung', label: 'Leistung', hinweis: 'z. B. Härten, Eloxieren' },
  { key: 'email', label: 'E-Mail', hinweis: 'allgemeine Adresse, z. B. verkauf@…' },
  { key: 'weitereEmails', label: 'Weitere E-Mail-Adressen', typ: 'text-lang', hinweis: 'eine je Zeile, z. B. rechnung@… – Mails von dort kommen in den Posteingang' },
  { key: 'ustId', label: 'USt-IdNr.', hinweis: 'ordnet E-Rechnungen dem Lieferanten zu' },
  { key: 'telefon', label: 'Telefon' },
  { key: 'adresse', label: 'Adresse', typ: 'text-lang' },
];
const leerKontakt = () => ({ anrede: '', vorname: '', nachname: '', funktion: '', email: '', telefon: '', mobil: '', anfragen: false });
// Ältere Einträge (und „Neu“) kommen ohne Liste: hier anlegen
const kontakte = (x) => (x.kontakte ??= []);
</script>

<template>
  <StammListe art="lieferant" einzahl="Lieferant" :icon="Truck" beschreibung="Lieferanten für Fremdvergabe und Lieferantenanfragen." :felder="felder" :spalten="['leistung', 'email', 'telefon']" dialog-breite="820px">
    <template #mehr="{ x, darf }">
      <section>
        <div class="mb-2 flex items-center justify-between">
          <h3 class="flex items-center gap-2 text-sm font-semibold"><UserRound :size="15" class="text-accent" /> Ansprechpartner</h3>
          <button v-if="darf" type="button" class="btn !py-1 !text-xs" @click="kontakte(x).push(leerKontakt())"><Plus :size="13" /> Ansprechpartner</button>
        </div>
        <div class="space-y-2">
          <div v-for="(c, i) in kontakte(x)" :key="i" class="rounded-xl border border-line p-3">
            <div class="grid gap-2 sm:grid-cols-[90px_1fr_1fr_1fr]">
              <select v-model="c.anrede" class="field" :disabled="!darf"><option value="">–</option><option>Herr</option><option>Frau</option></select>
              <input v-model="c.vorname" class="field" placeholder="Vorname" :disabled="!darf" />
              <input v-model="c.nachname" class="field" placeholder="Nachname" :disabled="!darf" />
              <input v-model="c.funktion" class="field" placeholder="Funktion, z. B. Verkauf" :disabled="!darf" />
            </div>
            <div class="mt-2 grid gap-2 sm:grid-cols-[1.4fr_1fr_1fr]">
              <input v-model="c.email" type="email" class="field" placeholder="E-Mail" :disabled="!darf" />
              <input v-model="c.telefon" class="field" placeholder="Telefon" :disabled="!darf" />
              <input v-model="c.mobil" class="field" placeholder="Mobil" :disabled="!darf" />
            </div>
            <div class="mt-2 flex items-center justify-between">
              <label class="flex cursor-pointer items-center gap-2 text-xs text-mute" title="Lieferantenanfragen gehen an alle Ansprechpartner mit diesem Haken; ohne Haken an die E-Mail des Lieferanten"><input v-model="c.anfragen" type="checkbox" class="accent-[var(--accent)]" :disabled="!darf" /> <Send :size="12" /> Bekommt unsere Anfragen</label>
              <button v-if="darf" type="button" class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:text-accent" title="Ansprechpartner entfernen" @click="kontakte(x).splice(i, 1)"><Trash2 :size="14" /></button>
            </div>
          </div>
          <p v-if="!kontakte(x).length" class="text-xs text-mute">Noch keine Ansprechpartner. Mails von ihren Adressen werden dem Lieferanten zugeordnet; mit „Bekommt unsere Anfragen“ gehen Anfragen direkt an sie.</p>
        </div>
      </section>
    </template>
  </StammListe>
</template>
