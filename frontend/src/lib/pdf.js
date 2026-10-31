// pdf.js einmal laden und für Ansicht und Erkennung teilen. Der Worker wird als .js gebündelt (nginx liefert .mjs nicht als JavaScript aus).
import * as pdfjs from 'pdfjs-dist';
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker';
import { textAusSeite } from './zeichnungText.js';

pdfjs.GlobalWorkerOptions.workerPort ??= new PdfWorker();

export { pdfjs };

// Text der ersten Seite einer Zeichnung mit Lage (für die Erkennung der Schriftfeld-Angaben)
export async function zeichnungLesen(url) {
  const aufgabe = pdfjs.getDocument({ url, withCredentials: true });
  try {
    const doc = await aufgabe.promise;
    return await textAusSeite(await doc.getPage(1));
  } finally {
    aufgabe.destroy();
  }
}
