import { defineStore } from 'pinia';
import { ref } from 'vue';
import { call } from '../data/api.js';
import { stammdatenAktualisieren } from '../data/repo.js';
import { useUi } from './ui.js';

// Anfragen aus dem gemeinsamen Postfach (nur Mails mit Stichwort im Betreff) und die Zahl der offenen für die Navigation.
export const useMail = defineStore('mail', () => {
  const ui = useUi();
  const liste = ref([]);
  const anzahl = ref(0);
  const geladen = ref(false);
  const ruft = ref(false);
  const details = ref({});

  async function laden() {
    try {
      liste.value = await call('cnc_one.api.mail.liste');
      geladen.value = true;
      zaehlen();
    } catch (e) {
      ui.toast(e.message, 'warn');
    }
  }

  async function zaehlen() {
    try { anzahl.value = await call('cnc_one.api.mail.anzahl'); } catch { /* Abzeichen ist nicht wichtig */ }
  }

  async function abrufen() {
    ruft.value = true;
    try {
      const r = await call('cnc_one.api.mail.abrufen');
      liste.value = r.liste;
      zaehlen();
      ui.toast(r.neu ? `${r.neu} neue Anfrage${r.neu === 1 ? '' : 'n'} abgeholt` : 'Keine neuen Anfragen', r.neu ? 'ok' : 'info');
    } catch (e) {
      ui.toast(`Abrufen fehlgeschlagen: ${e.message}`, 'warn');
    } finally {
      ruft.value = false;
    }
  }

  function eintragen(d) {
    details.value = { ...details.value, [d.id]: d };
    const i = liste.value.findIndex((x) => x.id === d.id);
    const kurz = { id: d.id, status: d.status, betreff: d.betreff, vonEmail: d.vonEmail, vonName: d.vonName, datum: d.datum, letzteNachricht: d.letzteNachricht, neueAntwort: d.neueAntwort, kundeId: d.kundeId, kundeName: d.kundeName, angebotId: d.angebotId };
    if (i >= 0) liste.value.splice(i, 1, kurz);
    zaehlen();
    return d;
  }

  async function detail(id) {
    try {
      let d = await call('cnc_one.api.mail.detail', { id });
      if (d.neueAntwort) d = await call('cnc_one.api.mail.gelesen', { id });
      return eintragen(d);
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  // Kunde wählen oder neu anlegen; die Absenderadresse wird dort als Kontakt angelegt, falls sie fehlt
  async function kundeZuordnen(id, { kunde = '', neuerKunde = '', kontakt = {} }) {
    try {
      const d = eintragen(await call('cnc_one.api.mail.kunde_zuordnen', { id, kunde, neuer_kunde: neuerKunde, kontakt }));
      await stammdatenAktualisieren();
      ui.toast(`Zugeordnet: ${d.kundeName}`, 'ok');
      return d;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  async function keineAnfrage(id) {
    try {
      await call('cnc_one.api.mail.keine_anfrage', { id });
      liste.value = liste.value.filter((x) => x.id !== id);
      zaehlen();
      ui.toast('Aus CNC One entfernt, im Postfach bleibt die Mail', 'ok');
      return true;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return false;
    }
  }

  return { liste, anzahl, geladen, ruft, details, laden, zaehlen, abrufen, detail, kundeZuordnen, keineAnfrage };
});
