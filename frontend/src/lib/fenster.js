// Zeichnung und 3D-Modell in einem eigenen Browserfenster (z. B. auf dem zweiten Bildschirm).
// Je Art gibt es genau ein Fenster mit festem Namen: window.open mit demselben Namen öffnet keinen neuen Tab, sondern
// verwendet das vorhandene Fenster. Die Workbench schickt über einen BroadcastChannel, was gerade gezeigt werden soll;
// wählt man ein anderes Bauteil, zeigt das Fenster dessen Zeichnung bzw. Modell. Ob ein Fenster offen ist, gilt für die
// Sitzung (sessionStorage); Lage und Größe merkt sich der Browser (localStorage), damit es wieder dort aufgeht.
import { reactive } from 'vue';

export const ARTEN = { zeichnung: 'Zeichnung', modell: '3D-Modell', beleg: 'Beleg' };
const KANAL = 'cnc-one-fenster';

const lesen = (speicher, k) => { try { return speicher.getItem(k); } catch { return null; } };
const schreiben = (speicher, k, v) => { try { if (v == null) speicher.removeItem(k); else speicher.setItem(k, v); } catch { /* privat */ } };

let kanal = null;
function kanalHolen() {
  if (!kanal && typeof BroadcastChannel !== 'undefined') kanal = new BroadcastChannel(KANAL);
  return kanal;
}

// ------------------------------------------------------------------ Hauptfenster (Workbench)
export const fenster = reactive({
  zeichnung: lesen(sessionStorage, 'fenster:zeichnung') === '1',
  modell: lesen(sessionStorage, 'fenster:modell') === '1',
});
const letzter = { zeichnung: null, modell: null };
const empfaenger = new Set();
const fensterRef = {};

function offenSetzen(art, offen) {
  fenster[art] = offen;
  schreiben(sessionStorage, `fenster:${art}`, offen ? '1' : null);
}

let hauptGestartet = false;
function hauptStarten() {
  if (hauptGestartet) return;
  const k = kanalHolen();
  if (!k) return;
  hauptGestartet = true;
  k.addEventListener('message', ({ data }) => {
    if (!data?.art || !(data.art in ARTEN)) return;
    if (data.typ === 'hallo') {
      antwort[data.art] = Date.now();
      offenSetzen(data.art, true);
      k.postMessage({ typ: 'inhalt', art: data.art, inhalt: letzter[data.art] });
    } else if (data.typ === 'zu') {
      offenSetzen(data.art, false);
    } else {
      for (const f of empfaenger) f(data);
    }
  });
  // Nach dem Neuladen der Workbench: lebt das Fenster noch? Sonst gilt es als geschlossen.
  for (const art of Object.keys(ARTEN)) {
    if (!fenster[art]) continue;
    const vorher = Date.now();
    k.postMessage({ typ: 'ping', art });
    setTimeout(() => { if (!antwort[art] || antwort[art] < vorher) offenSetzen(art, false); }, 1500);
  }
}
const antwort = {};

// ------------------------------------------------------------------ zweiter Bildschirm (Chrome/Edge: „Fensterverwaltung“)
// Ist die Berechtigung schon erteilt, wissen wir die Bildschirme im Voraus; dann geht ein neues Fenster ohne gemerkte
// Lage gleich auf den anderen Bildschirm. Die Berechtigung erfragt der Knopf „Auf 2. Bildschirm“ im Fenster selbst.
let bildschirme = null;
async function bildschirmeLaden() {
  if (typeof window === 'undefined' || !('getScreenDetails' in window)) return;
  try {
    const p = await navigator.permissions.query({ name: 'window-management' });
    if (p.state === 'granted') bildschirme = await window.getScreenDetails();
  } catch { /* Browser kann es nicht */ }
}
bildschirmeLaden();

export const andererBildschirm = (details) => {
  const liste = details?.screens ?? [];
  if (liste.length < 2) return null;
  return liste.find((s) => s !== details.currentScreen && !s.isPrimary) ?? liste.find((s) => s !== details.currentScreen) ?? null;
};

// Im Fenster: sich selbst auf den anderen Bildschirm legen (aus einem Klick, fragt beim ersten Mal nach der Berechtigung)
export async function aufAnderenBildschirm() {
  if (!('getScreenDetails' in window)) return 'Dieser Browser kann Fenster nicht auf einen anderen Bildschirm legen. Bitte das Fenster einmal hinüberziehen, es öffnet sich dann wieder dort.';
  let d;
  try { d = await window.getScreenDetails(); } catch { return 'Die Berechtigung „Fenster verwalten“ wurde nicht erteilt (Schloss-Symbol in der Adresszeile).'; }
  const s = andererBildschirm(d);
  if (!s) return 'Es ist nur ein Bildschirm angeschlossen.';
  window.moveTo(s.availLeft, s.availTop);
  window.resizeTo(s.availWidth, s.availHeight);
  return '';
}

// Ein Fenster öffnen bzw. nach vorne holen. Muss aus einem Klick heraus aufgerufen werden (Popup-Sperre).
export function oeffnen(art, inhalt) {
  hauptStarten();
  letzter[art] = inhalt ?? null;
  let lage = null;
  try { lage = JSON.parse(lesen(localStorage, `fensterLage:${art}`) || 'null'); } catch { lage = null; }
  const anderer = lage ? null : andererBildschirm(bildschirme);
  if (anderer) lage = { links: anderer.availLeft, oben: anderer.availTop, breite: anderer.availWidth, hoehe: anderer.availHeight };
  const b = lage?.breite || Math.round(screen.availWidth * 0.6);
  const h = lage?.hoehe || Math.round(screen.availHeight * 0.85);
  const merkmale = [`popup=yes`, `width=${b}`, `height=${h}`, ...(lage ? [`left=${lage.links}`, `top=${lage.oben}`] : [])].join(',');
  const url = `${location.pathname}${location.search}#/fenster/${art}`;
  // Mit leerer Adresse liefert der Browser ein schon offenes Fenster dieses Namens, ohne es neu zu laden;
  // nur ein neues (leeres) Fenster bekommt die Adresse der Ansicht.
  const w = window.open('', `cnc-one-${art}`, merkmale);
  if (!w) return false;
  fensterRef[art] = w;
  let neu = true;
  try { neu = !w.location.href || w.location.href === 'about:blank'; } catch { neu = true; }
  offenSetzen(art, true);
  if (neu) w.location.replace(url);
  else senden(art, inhalt);
  try { w.focus(); } catch { /* egal */ }
  return true;
}

// Neuen Inhalt an ein offenes Fenster schicken ({ titel, url, name, … } oder null für „nichts da“)
export function senden(art, inhalt) {
  hauptStarten();
  letzter[art] = inhalt ?? null;
  if (fenster[art]) kanalHolen()?.postMessage({ typ: 'inhalt', art, inhalt: letzter[art] });
}

// Fenster schließen, die Ansicht kommt zurück in die Workbench
export function schliessen(art) {
  kanalHolen()?.postMessage({ typ: 'schliessen', art });
  try { fensterRef[art]?.close(); } catch { /* egal */ }
  offenSetzen(art, false);
}

// Nachrichten aus den Fenstern (z. B. Rohteilgewicht übernehmen); liefert eine Abmeldefunktion
export function empfangen(f) {
  hauptStarten();
  empfaenger.add(f);
  return () => empfaenger.delete(f);
}

// ------------------------------------------------------------------ das Fenster selbst
// `beiInhalt(inhalt)` wird bei jedem neuen Inhalt aufgerufen. Liefert { melden(typ, daten), beenden() }.
export function fensterStarten(art, beiInhalt) {
  const k = kanalHolen();
  const hallo = () => k?.postMessage({ typ: 'hallo', art });
  const lageMerken = () => schreiben(localStorage, `fensterLage:${art}`, JSON.stringify({ links: window.screenX, oben: window.screenY, breite: window.outerWidth, hoehe: window.outerHeight }));
  const nachricht = ({ data }) => {
    if (data?.art !== art) return;
    if (data.typ === 'inhalt') beiInhalt(data.inhalt);
    else if (data.typ === 'ping') hallo();
    else if (data.typ === 'schliessen') { lageMerken(); window.close(); }
  };
  const zu = () => { lageMerken(); k?.postMessage({ typ: 'zu', art }); };
  k?.addEventListener('message', nachricht);
  window.addEventListener('pagehide', zu);
  const takt = setInterval(lageMerken, 3000);
  hallo();
  return {
    melden: (typ, daten) => k?.postMessage({ typ, art, ...daten }),
    beenden: () => { clearInterval(takt); k?.removeEventListener('message', nachricht); window.removeEventListener('pagehide', zu); },
  };
}
