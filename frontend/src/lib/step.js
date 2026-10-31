// STEP-Modelle laden: Datei holen, im Web-Worker lesen, Ergebnis je URL merken (Wechsel zwischen Bauteilen ist dann sofort da).
let worker = null;
let naechsteId = 0;
const wartend = new Map();
const cache = new Map();

function holeWorker() {
  if (worker) return worker;
  worker = new Worker(new URL('./stepWorker.js', import.meta.url), { type: 'module' });
  worker.onmessage = (e) => {
    const w = wartend.get(e.data.id);
    if (!w) return;
    wartend.delete(e.data.id);
    if (e.data.fehler) w.reject(new Error(e.data.fehler));
    else w.resolve(e.data.netze);
  };
  worker.onerror = (e) => {
    // Der Worker ist abgestürzt (z. B. zu wenig Speicher): alle offenen Aufträge abbrechen, beim nächsten Mal neu starten
    for (const w of wartend.values()) w.reject(new Error(e.message || 'Das 3D-Modell ließ sich nicht lesen.'));
    wartend.clear();
    worker.terminate();
    worker = null;
  };
  return worker;
}

async function lesen(url) {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(`Die Datei ließ sich nicht laden (${r.status}).`);
  const buffer = await r.arrayBuffer();
  return new Promise((resolve, reject) => {
    const id = ++naechsteId;
    wartend.set(id, { resolve, reject });
    holeWorker().postMessage({ id, buffer }, [buffer]);
  });
}

// Liefert die Dreiecksnetze [{ name, farbe, position, normal, index }] eines STEP-Modells.
export function stepNetze(url) {
  if (!cache.has(url)) cache.set(url, lesen(url).catch((e) => { cache.delete(url); throw e; }));
  return cache.get(url);
}
