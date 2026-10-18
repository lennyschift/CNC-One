import { defineStore } from 'pinia';
import { ref, computed, watch, nextTick } from 'vue';
import { berechne, summe } from '../lib/calc.js';
import { uid } from '../lib/format.js';
import { eur } from '../lib/format.js';
import { useUi } from './ui.js';
import { useBelege } from './belege.js';
import { einstellung, einstellungSpeichern } from '../data/einstellungen.js';

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
    seriennummern: false,
    arbeitsgaenge: [],
    dateien: [],
  };
}

// Beispiel-Bauteile zum Ausprobieren (Befehl "Beispiel-Bauteile einfügen")
function demoTeile() {
  const a = neuesTeil('Flansch DN50');
  Object.assign(a, {
    teilenummer: 'F31.683.122', zeichnungsnr: 'Z-4711-B', menge: 50, maschine: 'Hermle C42',
    satzRuest: 105, satzStueck: 105, ruestMin: 90, stueckMin: 14,
    material: '1.4404 Edelstahl', materialPreisKg: 8.1, gewichtKg: 1.35, messkosten: 45,
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

const leererKopf = () => ({ kundeId: '', anfrageNr: '', gueltigWochen: 4, lieferzeit: 'Nach Absprache' });

// Das Angebot, an dem gerade gearbeitet wird. Es liegt als Entwurf in Frappe und wird nach jeder Änderung
// kurz verzögert gespeichert. In Frappe merkt sich die Workbench je Benutzer, welches Angebot offen war.
export const useAngebot = defineStore('angebot', () => {
  const ui = useUi();
  const belege = useBelege();
  const sitzung = { angebotId: einstellung('workbenchAngebot'), auswahlId: einstellung('workbenchAuswahl') };

  const kopf = ref(leererKopf());
  const teile = ref([]);
  const auswahlId = ref(null);
  const angebotId = ref(null);
  // Zuordnung zu den Stammdaten je Workbench-Bauteil: { [teilId]: { bauteilId, herkunft: 'neu' | 'bestand', seriennummern } }
  const zuordnung = ref({});
  // 'gespeichert' | 'offen' | 'speichert' | 'fehler'
  const speicherStand = ref('gespeichert');

  let unterdrueckt = true;
  let timer = 0;
  let laeuft = false;
  let nochmal = false;

  const ergebnisse = computed(() => Object.fromEntries(teile.value.map((t) => [t.id, berechne(t)])));
  const netto = computed(() => summe(Object.values(ergebnisse.value)));
  const auswahl = computed(() => teile.value.find((t) => t.id === auswahlId.value) ?? null);

  async function ruhig(fn) {
    unterdrueckt = true;
    fn();
    await nextTick();
    unterdrueckt = false;
  }

  function zuordnungAus(positionen) {
    const m = {};
    for (const p of positionen) if (p.bauteilId) m[p.key] = { bauteilId: p.bauteilId, herkunft: p.herkunft, seriennummern: !!p.seriennummern };
    zuordnung.value = m;
  }

  // Gespeichertes Angebot (Entwurf) zum Weiterbearbeiten laden.
  function ausAngebot(record) {
    unterdrueckt = true;
    const k = JSON.parse(JSON.stringify(record.kopf));
    kopf.value = { kundeId: k.kundeId, anfrageNr: k.anfrageNr, gueltigWochen: k.gueltigWochen, lieferzeit: k.lieferzeit };
    teile.value = record.positionen.map((p) => JSON.parse(JSON.stringify(p.teil)));
    auswahlId.value = teile.value.find((t) => t.id === sitzung.auswahlId)?.id ?? teile.value[0]?.id ?? null;
    angebotId.value = record.id;
    zuordnungAus(record.positionen);
    speicherStand.value = 'gespeichert';
    nextTick().then(() => { unterdrueckt = false; });
  }

  async function speichern() {
    clearTimeout(timer);
    if (laeuft) { nochmal = true; return; }
    if (!angebotId.value && !teile.value.length && !kopf.value.kundeId) { speicherStand.value = 'gespeichert'; return; }
    laeuft = true;
    speicherStand.value = 'speichert';
    const nettoClient = netto.value;
    try {
      const rec = await belege.angebotSpeichern({ angebotId: angebotId.value, kopf: kopf.value, teile: teile.value });
      angebotId.value = rec.id;
      zuordnungAus(rec.positionen);
      // Ein Bestandsbauteil bringt sein Seriennummern-Kennzeichen aus den Stammdaten mit
      for (const p of rec.positionen) {
        const t = teile.value.find((x) => x.id === p.key);
        if (t && p.herkunft === 'bestand' && !!t.seriennummern !== !!p.seriennummern) t.seriennummern = !!p.seriennummern;
      }
      if (!nochmal && Math.abs(rec.netto - nettoClient) > 0.01) {
        ui.toast(`Server rechnet anders: ${eur(rec.netto)} statt ${eur(nettoClient)}`, 'warn');
      }
      speicherStand.value = 'gespeichert';
    } catch (e) {
      speicherStand.value = 'fehler';
      ui.toast(e.message, 'warn');
    } finally {
      laeuft = false;
      if (nochmal) { nochmal = false; speichern(); }
    }
  }

  function planeSpeichern() {
    if (unterdrueckt) return;
    if (!angebotId.value && !teile.value.length && !kopf.value.kundeId) return;
    speicherStand.value = 'offen';
    clearTimeout(timer);
    timer = setTimeout(speichern, 900);
  }

  watch([kopf, teile], planeSpeichern, { deep: true });
  watch([angebotId, auswahlId], () => {
    einstellungSpeichern('workbenchAngebot', angebotId.value ?? '');
    einstellungSpeichern('workbenchAuswahl', auswahlId.value ?? '');
  });

  // Beim Start das zuletzt offene Entwurf-Angebot wieder aufnehmen
  const letztes = sitzung.angebotId ? belege.angebot(sitzung.angebotId) : null;
  if (letztes && letztes.status === 'Entwurf') ausAngebot(letztes);
  else nextTick().then(() => { unterdrueckt = false; });

  async function neu() {
    if (speicherStand.value === 'offen') await speichern();
    await ruhig(() => {
      teile.value = [];
      zuordnung.value = {};
      auswahlId.value = null;
      angebotId.value = null;
      kopf.value = leererKopf();
      speicherStand.value = 'gespeichert';
    });
  }

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

  // Bestandsbauteil aus den Stammdaten ins Angebot übernehmen (Angaben und Arbeitsplan, ohne Kalkulationswerte)
  function ausBauteilHinzufuegen(b, materialien = []) {
    const t = neuesTeil(b.name || b.teilenummer);
    const m = materialien.find((x) => x.name === b.material);
    Object.assign(t, {
      teilenummer: b.teilenummer, zeichnungsnr: b.zeichnungsnr, material: b.material,
      materialPreisKg: m?.preisKg ?? 0, seriennummern: !!b.seriennummern,
      arbeitsgaenge: (b.arbeitsgaenge ?? []).map((ag) => ({ ...JSON.parse(JSON.stringify(ag)), id: uid(), anfrageId: '' })),
    });
    zuordnung.value = { ...zuordnung.value, [t.id]: { bauteilId: b.id, herkunft: 'bestand', seriennummern: !!b.seriennummern } };
    teile.value.push(t);
    auswahlId.value = t.id;
    ui.toast(`Bestandsbauteil ${b.teilenummer} übernommen`, 'ok');
    return t;
  }

  function duplizieren(id) {
    const q = teile.value.find((t) => t.id === id);
    if (!q) return;
    const kopie = JSON.parse(JSON.stringify(q));
    kopie.id = uid();
    kopie.name = `${q.name} (Kopie)`;
    kopie.dateien = [];
    // Arbeitsgänge der Kopie bekommen eigene Kennungen, sonst hängen Anfragen an beiden
    kopie.arbeitsgaenge = (kopie.arbeitsgaenge ?? []).map((a) => ({ ...a, id: uid(), anfrageId: '' }));
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

  function beispieleEinfuegen() {
    const neue = demoTeile();
    teile.value.push(...neue);
    auswahlId.value = neue[0].id;
    ui.toast('Beispiel-Bauteile eingefügt');
  }

  return { kopf, teile, zuordnung, auswahlId, angebotId, speicherStand, ausBauteilHinzufuegen, auswahl, ergebnisse, netto, neu, ausAngebot, speichern, hinzufuegen, duplizieren, loeschen, verschieben, dateienHinzufuegen, beispieleEinfuegen };
});
