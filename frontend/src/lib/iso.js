// ISO-Materialgruppen der Zerspanung (ISO 513): P Stahl, M rostfreier Stahl, K Guss, N NE-Metalle, S Superlegierungen und Titan,
// H harte Werkstoffe. Gepflegt am Rohmaterial (Feld „ISO-Gruppe“); ist dort nichts eingetragen, wird sie aus dem Namen bzw. der
// Werkstoffnummer abgeleitet. H lässt sich nicht ableiten (Härte steht nicht im Namen) und wird nur von Hand gesetzt.
// Nur für die Oberfläche (Bild in Workbench, Auftrag, Fertigung), nicht für PDFs.
export const ISO_GRUPPEN = {
  P: { code: 'P', name: 'Stahl', farbe: '#2563eb', schrift: '#fff' },
  M: { code: 'M', name: 'Rostfreier Stahl', farbe: '#eab308', schrift: '#1f2937' },
  K: { code: 'K', name: 'Gusseisen', farbe: '#dc2626', schrift: '#fff' },
  N: { code: 'N', name: 'NE-Metalle', farbe: '#16a34a', schrift: '#fff' },
  S: { code: 'S', name: 'Superlegierungen und Titan', farbe: '#c2410c', schrift: '#fff' },
  H: { code: 'H', name: 'Harte Werkstoffe', farbe: '#6b7280', schrift: '#fff' },
};

// Gruppe aus dem Werkstoffnamen ableiten ('' wenn unklar)
export function isoAusName(name) {
  const s = String(name ?? '').trim().toUpperCase().replace(/\s+/g, ' ');
  if (!s) return '';
  const nr = s.match(/\b([0-3])\.(\d)(\d{2,3})\b/);
  if (nr) {
    const [, g, h] = nr;
    if (g === '1') return h === '4' ? 'M' : 'P';
    if (g === '0') return h === '6' || h === '7' ? 'K' : '';
    if (g === '2') return h === '4' ? 'S' : 'N'; // 2.4xxx Nickel, sonst Kupfer/Messing/Bronze
    if (g === '3') return h === '7' ? 'S' : 'N'; // 3.7xxx Titan, sonst Aluminium/Magnesium
  }
  if (/\bEN[- ]?(GJ[LSMV]|JL|JS)\b|\bGG[GV]?\b|GUSSEISEN|GRAUGUSS|SPHÄROGUSS|TEMPERGUSS/.test(s)) return 'K';
  if (/INCONEL|HASTELLOY|NIMONIC|WASPALOY|MONEL|\bTITAN|\bTI[- ]?\d|\bTIAL|\bNICR|\bNIMO/.test(s)) return 'S';
  if (/\bEN ?A[WC]\b|\bAL[A-Z]|\bALU|ALUMINIUM|\bCW\d|\bCC\d|\bCU[A-Z]|KUPFER|MESSING|BRONZE|\bMS ?\d|\bMG|MAGNESIUM|\bPOM|\bPA ?\d|\bPEEK|\bPE[- ]?HD|\bPTFE|KUNSTSTOFF/.test(s)) return 'N';
  if (/\bX\d+CR(?!MOV)|\bV[24]A\b|EDELSTAHL|NIROSTA|ROSTFREI|\bAISI ?[34]\d\d(?!\d)|\bA[24]\b/.test(s)) return 'M';
  if (/\bS\d{3}|\bC\d{2}E?\b|\b\d{2}(CRMO|CRNIMO|MNCR|MNSI|SMNPB|SMN|NICRMO)|\bST ?\d{2}|\b\d{2}MNV|\b\d{2}CRMOV|\bX\d+CRMOV|\bAISI ?1\d{3}|\bAISI ?4\d{3}|STAHL/.test(s)) return 'P';
  return '';
}

// { code, name, farbe, schrift, abgeleitet } aus der gepflegten Gruppe (Stammdaten) oder dem Namen, sonst null
export function isoGruppe(material, gepflegt = '') {
  if (!material && !gepflegt) return null;
  const code = gepflegt || isoAusName(material);
  return code && ISO_GRUPPEN[code] ? { ...ISO_GRUPPEN[code], abgeleitet: !gepflegt } : null;
}
