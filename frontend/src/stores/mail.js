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
      ui.toast(r.neu ? `${r.neu} neue Mail${r.neu === 1 ? '' : 's'} abgeholt` : 'Keine neuen Mails', r.neu ? 'ok' : 'info');
    } catch (e) {
      ui.toast(`Abrufen fehlgeschlagen: ${e.message}`, 'warn');
    } finally {
      ruft.value = false;
    }
  }

  function eintragen(d) {
    details.value = { ...details.value, [d.id]: d };
    const i = liste.value.findIndex((x) => x.id === d.id);
    const { kundeVorschlag, kontaktVorschlag, tabellen, tabellenVorlage, nachrichten, ...kurz0 } = d;
    const kurz = { ...liste.value[i], ...kurz0 };
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

  // Angebotsentwurf aus der Anfrage (oder das vorhandene Angebot); die Bauteile bildet danach die Workbench
  async function angebotAnlegen(id) {
    try {
      const r = await call('cnc_one.api.mail.angebot_anlegen', { id });
      detail(id);
      return r;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  // Spalten der Anfrage-Tabelle für Kontakt und Kunde merken
  async function tabellenvorlageLernen(id, spalten) {
    try { await call('cnc_one.api.mail.tabellenvorlage_lernen', { id, spalten }); } catch (e) { ui.toast(`Spalten nicht gemerkt: ${e.message}`, 'warn'); }
  }

  // Umsortieren (Anfrage, Bestellung, Rechnung, Lieferant, Sonstiges), erledigt, Lieferant zuordnen
  async function aktion(methode, args, meldung) {
    try {
      const d = eintragen(await call(`cnc_one.api.mail.${methode}`, args));
      if (meldung) ui.toast(typeof meldung === 'function' ? meldung(d) : meldung, 'ok');
      return d;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }
  const kategorieSetzen = (id, kategorie) => aktion('kategorie_setzen', { id, kategorie }, `Verschoben nach „${kategorie}“`);
  const erledigt = (id, wert = 1, auftrag = '') => aktion('erledigt', { id, erledigt: wert ? 1 : 0, auftrag }, wert ? 'Als erledigt markiert' : 'Wieder offen');
  const lieferantZuordnen = (id, lieferant) => aktion('lieferant_zuordnen', { id, lieferant }, (d) => `Lieferant ${d.lieferantId} zugeordnet; seine Mails kommen künftig von selbst`);

  // Eingangsrechnung aus einem Anhang (E-Rechnung wird gelesen, PDF zum Ausfüllen)
  async function eingangsrechnung(id, url) {
    try {
      const r = await call('cnc_one.api.eingangsrechnung.aus_datei', { file_url: url, mail: id });
      await detail(id);
      ui.toast(`Eingangsrechnung ${r.rechnung.id} angelegt`, 'ok');
      return r.rechnung;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  return { liste, anzahl, geladen, ruft, details, laden, zaehlen, abrufen, detail, kundeZuordnen, keineAnfrage, angebotAnlegen, tabellenvorlageLernen, kategorieSetzen, erledigt, lieferantZuordnen, eingangsrechnung };
});
