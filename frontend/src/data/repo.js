// Stammdaten der Oberfläche. Kommen beim Start aus Frappe (cnc_one.api.stamm.bootstrap) und liegen dann im Speicher.
// Änderungen laufen über die Stores, die die API aufrufen.
import { call } from './api.js';

let daten = { benutzer: null, kunden: [], lieferanten: [], maschinen: [], materialien: [], arten: [], vorlagen: [], bauteile: [], angebote: [], auftraege: [], fertigung: [], anfragen: [] };

export async function ladeStammdaten() {
  daten = await call('cnc_one.api.stamm.bootstrap');
  return daten;
}

export const stammdatenRoh = () => daten;
export const benutzer = () => daten.benutzer;

// Gleiche Form wie bisher, damit die Bildschirme nichts davon merken.
export const repo = {
  kunden: { async liste() { return daten.kunden; } },
  maschinen: { async liste() { return daten.maschinen; } },
  materialien: { async liste() { return daten.materialien; } },
  lieferanten: { async liste() { return daten.lieferanten; } },
};
