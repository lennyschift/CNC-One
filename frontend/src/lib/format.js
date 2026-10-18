const eurFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' });
const numFmt = (d) => new Intl.NumberFormat('de-DE', { minimumFractionDigits: 0, maximumFractionDigits: d });

export const eur = (v) => eurFmt.format(Number(v) || 0);
export const zahl = (v, d = 2) => numFmt(d).format(Number(v) || 0);

// "12,5" und "12.5" werden beide als 12.5 gelesen.
export function parseDe(text) {
  const s = String(text ?? '').trim().replace(/\s/g, '');
  if (!s) return 0;
  const normal = s.includes(',') ? s.replace(/\./g, '').replace(',', '.') : s;
  const n = Number(normal);
  return Number.isFinite(n) ? n : NaN;
}

export function uid() {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}
