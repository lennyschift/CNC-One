// STEP-Modelle laden: Datei holen, in Web-Workern lesen, Ergebnis je URL merken (Wechsel zwischen Bauteilen ist dann sofort da).
// Mehrere Worker lesen gleichzeitig (je nach Prozessorkernen bis zu drei). Was gerade angezeigt werden soll (stepNetze),
// kommt vor dem Vorladen im Hintergrund (stepVorladen) dran; ein schon wartendes Modell rückt dann nach vorne.
const ANZAHL = Math.max(1, Math.min(3, ((typeof navigator !== 'undefined' && navigator.hardwareConcurrency) || 2) - 1));
const arbeiter = []; // { worker, auftrag }
const schlange = []; // Aufträge { url, eilig, resolve, reject }
const cache = new Map(); // url -> { promise, auftrag }
let naechsteId = 0;

function neuerArbeiter() {
  const a = { worker: new Worker(new URL('./stepWorker.js', import.meta.url), { type: 'module' }), auftrag: null };
  a.worker.onmessage = (e) => {
    const auf = a.auftrag;
    a.auftrag = null;
    if (auf && e.data.id === auf.id) {
      if (e.data.fehler) auf.reject(new Error(e.data.fehler));
      else auf.resolve(e.data.netze);
    }
    weiter();
  };
  a.worker.onerror = (e) => {
    // Der Worker ist abgestürzt (z. B. zu wenig Speicher): diesen Auftrag abbrechen, den Worker ersetzen
    a.auftrag?.reject(new Error(e.message || 'Das 3D-Modell ließ sich nicht lesen.'));
    a.auftrag = null;
    a.worker.terminate();
    arbeiter.splice(arbeiter.indexOf(a), 1);
    weiter();
  };
  arbeiter.push(a);
  return a;
}

function naechsterAuftrag() {
  const i = schlange.findIndex((x) => x.eilig);
  return schlange.splice(i >= 0 ? i : 0, 1)[0];
}

function weiter() {
  while (schlange.length) {
    const frei = arbeiter.find((a) => !a.auftrag) ?? (arbeiter.length < ANZAHL ? neuerArbeiter() : null);
    if (!frei) return;
    const auf = naechsterAuftrag();
    auf.id = ++naechsteId;
    frei.auftrag = auf;
    starten(frei, auf);
  }
}

async function starten(a, auf) {
  try {
    const r = await fetch(auf.url, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(`Die Datei ließ sich nicht laden (${r.status}).`);
    const buffer = await r.arrayBuffer();
    if (a.auftrag !== auf) return; // Worker inzwischen abgestürzt
    a.worker.postMessage({ id: auf.id, buffer }, [buffer]);
  } catch (e) {
    if (a.auftrag !== auf) return;
    a.auftrag = null;
    auf.reject(e);
    weiter();
  }
}

function anfordern(url, eilig) {
  const da = cache.get(url);
  if (da) {
    if (eilig && da.auftrag) da.auftrag.eilig = true; // wartet noch: nach vorne
    return da.promise;
  }
  const eintrag = {};
  eintrag.promise = new Promise((resolve, reject) => {
    eintrag.auftrag = { url, eilig, resolve, reject };
  }).finally(() => { eintrag.auftrag = null; });
  eintrag.promise.catch(() => cache.delete(url));
  cache.set(url, eintrag);
  schlange.push(eintrag.auftrag);
  weiter();
  return eintrag.promise;
}

// Liefert die Dreiecksnetze [{ name, farbe, position, normal, index }] eines STEP-Modells (wird sofort gebraucht).
export function stepNetze(url) {
  return anfordern(url, true);
}

// Modell im Hintergrund vorladen (z. B. alle Bauteile der Workbench, für Vorschaubilder und schnelles Umschalten).
export function stepVorladen(url) {
  return anfordern(url, false);
}
