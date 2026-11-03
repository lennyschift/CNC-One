// Belege (Angebot, Rechnung, Lieferschein, Mahnung) als PDF vom Server: dieselbe Datei zum Ansehen, Drucken und Verschicken.
import { textAus } from '../data/api.js';

// `stand` ändert die Adresse, wenn sich der Beleg ändert (Status, Nummer), damit nichts Altes aus dem Zwischenspeicher kommt
export const belegPdfUrl = (doctype, id, stand = '') =>
  `/api/method/cnc_one.api.belegdruck.ansehen?doctype=${encodeURIComponent(doctype)}&id=${encodeURIComponent(id)}&v=${encodeURIComponent(stand)}`;

let rahmen = null;
let adresse = null;

// Lädt das PDF (ArrayBuffer). Bei einem Fehler steht die Meldung des Servers im Fehler (z. B. „Bitte zuerst einen Kunden wählen.“).
export async function pdfLaden(url) {
  let r;
  try {
    r = await fetch(url, { credentials: 'same-origin' });
  } catch {
    throw new Error('Der Server ist nicht erreichbar.');
  }
  if (r.ok && (r.headers.get('content-type') ?? '').includes('pdf')) return r.arrayBuffer();
  if (r.status === 401) throw new Error('Die Sitzung ist abgelaufen. Bitte neu anmelden.');
  let text = '';
  try { text = textAus(await r.json()); } catch { /* keine JSON-Antwort */ }
  throw new Error(text || `Der Server hat das PDF nicht erzeugt (Fehler ${r.status}).`);
}

// Druckt das PDF über einen unsichtbaren Rahmen: der Druckdialog des Browsers zeigt genau das PDF, nicht die App
export async function pdfDrucken(url) {
  const blob = new Blob([await pdfLaden(url)], { type: 'application/pdf' });
  if (adresse) URL.revokeObjectURL(adresse);
  adresse = URL.createObjectURL(blob);
  if (!rahmen) {
    rahmen = document.createElement('iframe');
    rahmen.setAttribute('aria-hidden', 'true');
    rahmen.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none';
    document.body.appendChild(rahmen);
  }
  await new Promise((fertig) => {
    rahmen.onload = () => fertig();
    rahmen.src = adresse;
  });
  // der PDF-Betrachter im Rahmen braucht einen Moment, bis er drucken kann
  await new Promise((weiter) => setTimeout(weiter, 300));
  rahmen.contentWindow.focus();
  rahmen.contentWindow.print();
}
