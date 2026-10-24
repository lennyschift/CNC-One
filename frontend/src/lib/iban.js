// IBAN prüfen (Länge für Deutschland und Prüfziffer nach Modulo 97). Spiegel von cnc_one/logic/rechnung.py iban_gueltig, getestet in iban.test.js.

export const ibanBereinigt = (iban) => String(iban ?? '').replace(/\s+/g, '').toUpperCase();

export function ibanGueltig(iban) {
  const s = ibanBereinigt(iban);
  if (s.length < 15 || s.length > 34 || !/^[A-Z0-9]+$/.test(s)) return false;
  if (s.startsWith('DE') && s.length !== 22) return false;
  const umgestellt = s.slice(4) + s.slice(0, 4);
  let rest = 0;
  for (const ch of umgestellt) {
    const wert = /\d/.test(ch) ? ch : String(ch.charCodeAt(0) - 55);
    for (const z of wert) rest = (rest * 10 + Number(z)) % 97;
  }
  return rest === 1;
}

// DE64 6225 0030 0005 4437 72
export const ibanFormatiert = (iban) => ibanBereinigt(iban).replace(/(.{4})/g, '$1 ').trim();
