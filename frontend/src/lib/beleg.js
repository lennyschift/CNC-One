// Regeln für den Übergang Angebot → Auftrag. Reine Funktionen, getestet in beleg.test.js.
import { berechne, r2, num } from './calc.js';

// Auswahlmöglichkeiten einer Angebotsposition: jede Staffel, oder die eine Angebotsmenge.
export function optionen(teil, ergebnis) {
  if (teil.staffel?.aktiv && ergebnis.stufen.length) {
    return ergebnis.stufen.map((s) => ({ id: String(s.menge), label: `${s.menge} Stk`, menge: s.menge, einzel: s.stueckpreis }));
  }
  const z = ergebnis.zeilen.find((x) => x.typ === 'teil');
  return [{ id: 'einzel', label: `${ergebnis.menge} Stk`, menge: ergebnis.menge, einzel: z ? z.einzel : 0 }];
}

// Auftragsposition aus einer Angebotsposition: gewählte Option + tatsächlich bestellte Menge.
export function auftragsPosition(teil, ergebnis, option, menge) {
  const q = Math.max(1, Math.floor(num(menge)) || 1);
  let einzel;
  let kosten;
  if (teil.staffel?.aktiv) {
    einzel = option.einzel;
    kosten = ergebnis.zeilen.filter((z) => z.typ === 'kosten');
  } else {
    const r = berechne({ ...teil, menge: q });
    einzel = r.zeilen.find((z) => z.typ === 'teil')?.einzel ?? 0;
    kosten = r.zeilen.filter((z) => z.typ === 'kosten');
  }
  const kostenZeilen = kosten.map((k) => ({ label: k.label, betrag: k.betrag }));
  const summe = r2(einzel * q + kostenZeilen.reduce((s, k) => s + k.betrag, 0));
  return {
    menge: q,
    einzelpreis: r2(einzel),
    staffelMenge: teil.staffel?.aktiv ? option.menge : null,
    kosten: kostenZeilen,
    summe,
    unterStaffel: teil.staffel?.aktiv && q < option.menge,
  };
}

// Status eines Angebots aus gespeichertem Status und vorhandenen Aufträgen.
export function angebotStatus(angebot, bestelltJeKey) {
  if (angebot.status !== 'Gesendet') return angebot.status;
  const keys = angebot.positionen.map((p) => p.key);
  const bestellt = keys.filter((k) => (bestelltJeKey[k] ?? 0) > 0).length;
  if (!bestellt) return 'Gesendet';
  return bestellt === keys.length ? 'Bestellt' : 'Teilweise bestellt';
}

// Position für den Auftrag mit allem, was der Dialog auswählt: Staffel (optionId), Menge und abgewählte Kostenzeilen.
// Der Server rechnet dasselbe nach (cnc_one/logic/beleg.py), geprüft mit shared/auftrag_faelle.json.
export function positionFuerAuftrag(teil, ergebnis, optionId, menge, kostenAus = []) {
  const opts = optionen(teil, ergebnis);
  const opt = opts.find((o) => o.id === String(optionId)) ?? opts[0];
  const pos = auftragsPosition(teil, ergebnis, opt, menge);
  const kosten = pos.kosten.filter((k) => !kostenAus.includes(k.label));
  const summe = r2(pos.einzelpreis * pos.menge + kosten.reduce((s, k) => s + k.betrag, 0));
  return { ...pos, kosten, summe };
}
