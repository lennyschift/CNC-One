import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { berechne, summe } from '../lib/calc.js';
import { uid } from '../lib/format.js';
import { useUi } from './ui.js';

const KEY = 'cnc-one:workbench:v1';

export function neuesTeil(name = 'Neues Bauteil') {
  return {
    id: uid(),
    name,
    teilenummer: '',
    zeichnungsnr: '',
    menge: 10,
    maschine: '',
    satzRuest: 0,
    satzStueck: 0,
    ruestMin: 0,
    stueckMin: 0,
    material: '',
    materialPreisKg: 0,
    gewichtKg: 0,
    pauschalMaterial: 0,
    pauschalAlsZeile: false,
    messkosten: 0,
    sonderkosten: 0,
    expresskosten: 0,
    inStueckpreis: { ruest: false, mess: false, sonder: false, express: false },
    staffel: { aktiv: false, stufen: [{ menge: 5, extra: 0 }, { menge: 25, extra: 0 }, { menge: 100, extra: 0 }] },
    arbeitsgaenge: [],
    dateien: [],
  };
}

function demoTeile() {
  const a = neuesTeil('Flansch DN50');
  Object.assign(a, {
    teilenummer: 'F31.683.122', zeichnungsnr: 'Z-4711-B', menge: 50, maschine: 'Hermle C42',
    satzRuest: 105, satzStueck: 105, ruestMin: 90, stueckMin: 14,
    material: '1.4404 Edelstahl', materialPreisKg: 8.1, gewichtKg: 1.35, messkosten: 45,
    inStueckpreis: { ruest: false, mess: false, sonder: false, express: false },
  });
  a.staffel.aktiv = true;
  const plan = (name, typ, extra = {}) => ({ id: uid(), name, typ, maschine: '', satz: 0, ruestMin: 0, stueckMin: 0, lieferant: '', fremdProStk: 0, fremdEinmal: 0, anfrageId: '', ...extra });
  a.arbeitsgaenge = [
    plan('Drehen', 'intern', { maschine: 'CTX400', satz: 88, ruestMin: 45, stueckMin: 6 }),
    plan('Fräsen', 'intern', { maschine: 'Hermle C42', satz: 105, ruestMin: 45, stueckMin: 8 }),
    plan('Oberflächenbehandlung', 'fremd', { lieferant: 'Eloxal Beispiel GmbH', fremdProStk: 1.8 }),
  ];
  const b = neuesTeil('Distanzhülse');
  Object.assign(b, {
    teilenummer: 'P27.135.322', menge: 200, maschine: 'CTX400', satzRuest: 88, satzStueck: 88,
    ruestMin: 45, stueckMin: 2.5, material: '1.4305 Automatenstahl', materialPreisKg: 6.9, gewichtKg: 0.12,
  });
  const c = neuesTeil('Gehäusedeckel');
  Object.assign(c, {
    teilenummer: 'G-2210', zeichnungsnr: 'Z-5120-A', menge: 12, maschine: 'Mori NTX2000', satzRuest: 125, satzStueck: 125,
    ruestMin: 120, stueckMin: 38, material: 'EN AW-7075 Aluminium', materialPreisKg: 9.8, gewichtKg: 2.9,
    messkosten: 60, expresskosten: 150,
  });
  return [a, b, c];
}

function laden() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const d = JSON.parse(raw);
      if (Array.isArray(d.teile)) return d;
    }
  } catch { /* egal */ }
  return null;
}

export const useAngebot = defineStore('angebot', () => {
  const ui = useUi();
  const gespeichert = laden();

  const kopf = ref(gespeichert?.kopf ?? { kundeId: '', anfrageNr: '', gueltigWochen: 4, lieferzeit: 'Nach Absprache' });
  const teile = ref(gespeichert?.teile ?? demoTeile());
  const auswahlId = ref(gespeichert?.auswahlId ?? teile.value[0]?.id ?? null);
  const angebotId = ref(gespeichert?.angebotId ?? null);
  // bleibt gleich, bis ein neues Angebot begonnen wird; so lassen sich Lieferantenanfragen schon vor dem Speichern zuordnen
  const entwurfId = ref(gespeichert?.entwurfId ?? uid());

  watch([kopf, teile, auswahlId, angebotId, entwurfId], () => {
    try {
      localStorage.setItem(KEY, JSON.stringify({ kopf: kopf.value, teile: teile.value, auswahlId: auswahlId.value, angebotId: angebotId.value, entwurfId: entwurfId.value }));
    } catch { /* egal */ }
  }, { deep: true });

  function neu() {
    teile.value = [];
    auswahlId.value = null;
    angebotId.value = null;
    entwurfId.value = uid();
    kopf.value = { kundeId: '', anfrageNr: '', gueltigWochen: 4, lieferzeit: 'Nach Absprache' };
  }

  // Gespeichertes Angebot (Entwurf) zum Weiterbearbeiten in die Workbench laden.
  function ausAngebot(record) {
    const k = JSON.parse(JSON.stringify(record.kopf));
    kopf.value = { kundeId: k.kundeId, anfrageNr: k.anfrageNr, gueltigWochen: k.gueltigWochen, lieferzeit: k.lieferzeit };
    teile.value = record.positionen.map((p) => JSON.parse(JSON.stringify(p.teil)));
    auswahlId.value = teile.value[0]?.id ?? null;
    angebotId.value = record.id;
    entwurfId.value = record.entwurfId ?? uid();
  }

  const auswahl = computed(() => teile.value.find((t) => t.id === auswahlId.value) ?? null);
  const ergebnisse = computed(() => Object.fromEntries(teile.value.map((t) => [t.id, berechne(t)])));
  const netto = computed(() => summe(Object.values(ergebnisse.value)));

  function hinzufuegen(name) {
    const t = neuesTeil(name);
    const letzte = auswahl.value;
    if (letzte) {
      Object.assign(t, {
        maschine: letzte.maschine, satzRuest: letzte.satzRuest, satzStueck: letzte.satzStueck,
        material: letzte.material, materialPreisKg: letzte.materialPreisKg,
      });
    }
    teile.value.push(t);
    auswahlId.value = t.id;
    return t;
  }

  function duplizieren(id) {
    const q = teile.value.find((t) => t.id === id);
    if (!q) return;
    const kopie = JSON.parse(JSON.stringify(q));
    kopie.id = uid();
    kopie.name = `${q.name} (Kopie)`;
    kopie.dateien = [];
    const i = teile.value.findIndex((t) => t.id === id);
    teile.value.splice(i + 1, 0, kopie);
    auswahlId.value = kopie.id;
    ui.toast('Bauteil dupliziert');
  }

  function loeschen(id) {
    const i = teile.value.findIndex((t) => t.id === id);
    if (i < 0) return;
    const [weg] = teile.value.splice(i, 1);
    if (auswahlId.value === id) auswahlId.value = (teile.value[i] ?? teile.value[i - 1])?.id ?? null;
    ui.toast(`„${weg.name}“ entfernt`);
  }

  function verschieben(id, richtung) {
    const i = teile.value.findIndex((t) => t.id === id);
    const j = i + richtung;
    if (i < 0 || j < 0 || j >= teile.value.length) return;
    const [t] = teile.value.splice(i, 1);
    teile.value.splice(j, 0, t);
  }

  // Dateien werden nach Namen gruppiert: Zeichnung.pdf + Zeichnung.step ergeben ein Bauteil.
  function dateienHinzufuegen(files) {
    const gruppen = new Map();
    for (const f of files) {
      const m = /^(.*?)(\.[^.]+)?$/.exec(f.name);
      const basis = (m?.[1] ?? f.name).trim();
      const ext = (m?.[2] ?? '').toLowerCase().slice(1);
      const art = ['step', 'stp'].includes(ext) ? 'STEP' : ext === 'pdf' ? 'Zeichnung' : ext.toUpperCase() || 'Datei';
      const schluessel = basis.toLowerCase().replace(/[\s_-]+/g, '');
      if (!gruppen.has(schluessel)) gruppen.set(schluessel, { basis, dateien: [] });
      gruppen.get(schluessel).dateien.push({ name: f.name, art, groesse: f.size });
    }
    let neu = 0;
    for (const g of gruppen.values()) {
      const vorhanden = teile.value.find((t) => t.name.toLowerCase().replace(/[\s_-]+/g, '') === g.basis.toLowerCase().replace(/[\s_-]+/g, ''));
      const ziel = vorhanden ?? hinzufuegen(g.basis.replace(/_/g, ' '));
      if (!vorhanden) neu++;
      ziel.dateien.push(...g.dateien);
    }
    ui.toast(`${files.length} Datei${files.length === 1 ? '' : 'en'} → ${neu} neue${neu === 1 ? 's' : ''} Bauteil${neu === 1 ? '' : 'e'}`, 'ok');
  }

  function zuruecksetzen() {
    teile.value = demoTeile();
    auswahlId.value = teile.value[0].id;
    kopf.value = { kundeId: '', anfrageNr: '', gueltigWochen: 4, lieferzeit: 'Nach Absprache' };
    angebotId.value = null;
    entwurfId.value = uid();
    ui.toast('Beispieldaten geladen');
  }

  return { kopf, teile, auswahlId, angebotId, entwurfId, auswahl, ergebnisse, netto, neu, ausAngebot, hinzufuegen, duplizieren, loeschen, verschieben, dateienHinzufuegen, zuruecksetzen };
});
