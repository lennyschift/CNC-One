import { defineStore } from 'pinia';
import { ref } from 'vue';
import { call } from '../data/api.js';
import { stammdatenRoh } from '../data/repo.js';
import { useUi } from './ui.js';

const kopie = (o) => JSON.parse(JSON.stringify(o));

// Die eigenen Firmendaten für Belege (Anschrift, Steuer, Bankverbindungen, Texte). Gibt es genau einmal.
export const useFirma = defineStore('firma', () => {
  const ui = useUi();
  const firma = ref(kopie(stammdatenRoh().firma ?? { firmenname: '', adresse: [], banken: [] }));

  async function speichern(daten) {
    try {
      firma.value = await call('cnc_one.api.firma.speichern', { daten: kopie(daten) });
      ui.toast('Firmendaten gespeichert', 'ok');
      return firma.value;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  return { firma, speichern };
});
