// Text einer PDF-Seite (pdf.js) mit seiner Lage. Positionen sind auf die Seite bezogen (0 bis 1, Ursprung oben links),
// damit Erkennungsregeln unabhängig von Blattgröße und Maßstab gelten. Wird im Browser und in den Tests (Node) benutzt.
export async function textAusSeite(seite) {
  const vp = seite.getViewport({ scale: 1 });
  const inhalt = await seite.getTextContent();
  const elemente = [];
  for (const it of inhalt.items) {
    const text = (it.str ?? '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const [, , c, d, e, f] = it.transform;
    const h = Math.hypot(c, d) || it.height || 1;
    const [x, grund] = vp.convertToViewportPoint(e, f);
    elemente.push({
      text,
      x: runden(x / vp.width),
      y: runden((grund - h) / vp.height),
      b: runden((it.width || h * text.length * 0.5) / vp.width),
      h: runden(h / vp.height),
    });
  }
  return { breite: Math.round(vp.width), hoehe: Math.round(vp.height), elemente };
}

const runden = (v) => Math.round(v * 10000) / 10000;
