// Was sich die Oberfläche je Benutzer merkt (Farbschema, zuletzt offenes Angebot). Liegt in Frappe, nicht im Browser.
import { call } from './api.js';
import { benutzer } from './repo.js';

const PAUSE = 800;
const timer = {};

export const einstellung = (key) => benutzer()?.einstellungen?.[key] ?? '';

// Merkt den Wert sofort und schickt ihn kurz verzögert an den Server. Fehler stören die Arbeit nicht.
export function einstellungSpeichern(key, wert) {
  const b = benutzer();
  if (b) b.einstellungen = { ...b.einstellungen, [key]: wert ?? '' };
  clearTimeout(timer[key]);
  timer[key] = setTimeout(() => { call('cnc_one.api.stamm.einstellung_setzen', { key, wert: wert ?? '' }).catch(() => {}); }, PAUSE);
}
