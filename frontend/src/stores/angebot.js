import { defineStore } from 'pinia';
import { ref, computed, watch, nextTick } from 'vue';
import { berechne, summe } from '../lib/calc.js';
import { uid } from '../lib/format.js';
import { eur } from '../lib/format.js';
import { useUi } from './ui.js';
import { useBelege } from './belege.js';
import { einstellung, einstellungSpeichern } from '../data/einstellungen.js';
import { call, hochladen } from '../data/api.js';
import { repo } from '../data/repo.js';

export function neuesTeil(name = 'Neues Bauteil') {
  return {
    id: uid(),
    name,
    teilenummer: '',
    zeichnungsnr: '',
    revision: '',
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
    vorschaubild: '',
  };
}

// Art einer Datei nach der Endung: STEP-Modell, Zeichnung (PDF) oder sonstige
export function dateiArt(name) {
  const ext = (/\.([^.]+)$/.exec(name)?.[1] ?? '').toLowerCase();
  return ['step', 'stp'].includes(ext) ? 'STEP' : ext === 'pdf' ? 'Zeichnung' : ext.toUpperCase() || 'Datei';
}

const dateiname = (url) => decodeURIComponent(url.split('/').pop() ?? url);

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
  // Laufende Uploads je Workbench-Bauteil: { [teilId]: [Dateiname, …] }
  const uploads = ref({});
  // Aus der Zeichnung erkannte Angaben je Workbench-Bauteil (nur im Browser, bis übernommen oder verworfen):
  // { [teilId]: { stand: 'laeuft' | 'fertig' | 'fehler', datei, seite, felder, werkstoffNr, passende, vorlage, gelernt, fehler } }
  const erkennungen = ref({});
  // Anlernen: welches Feld gerade per Klick in der Zeichnung gesucht wird { teilId, feld, label }; Markierung in der Zeichnung { teilId, lage }
  const anlernen = ref(null);
  const markierung = ref(null);
  // Stelle, an die die Zeichnungsansicht heranzoomt (Fadenkreuz in der Erkennung) { teilId, lage, n }
  const fokus = ref(null);

  let unterdrueckt = true;
  let timer = 0;
  let laeuft = false;
  let nochmal = false;
  let laufend = Promise.resolve();

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

  // Speichert den Entwurf. Läuft schon ein Speichern, wird danach noch einmal gespeichert; der Aufrufer wartet auf das
  // laufende (wichtig beim Hochladen: die Dateien brauchen die Angebotsnummer).
  function speichern() {
    clearTimeout(timer);
    if (laeuft) { nochmal = true; return laufend; }
    laufend = speichernJetzt();
    return laufend;
  }

  async function speichernJetzt() {
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
  // Kunde erst nach dem Ablegen gewählt: offene Erkennungen mit der Vorlage dieses Kunden neu lesen,
  // ohne Vorlage zumindest ein schon vorhandenes Bauteil dieses Kunden verwenden
  watch(() => kopf.value.kundeId, async (kunde, vorher) => {
    if (!kunde || kunde === vorher || unterdrueckt) return;
    const offen = teile.value.filter((t) => erkennungen.value[t.id]?.stand === 'fertig' && erkennungen.value[t.id].vorlage?.kundeId !== kunde);
    if (!offen.length) return;
    const mitVorlage = !!(await vorlageHolen(kunde));
    for (const t of offen) {
      const e = erkennungen.value[t.id];
      const datei = t.dateien.find((d) => d.url === e?.datei);
      if (mitVorlage && datei) erkennenFuer(t, datei);
      else if (e) {
        const automatisch = await bestandAutomatisch(t, e.passende);
        if (automatisch) erkennungen.value[t.id] = { ...erkennungen.value[t.id], automatisch };
      }
    }
  });
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
      teilenummer: b.teilenummer, zeichnungsnr: b.zeichnungsnr, revision: b.revision ?? '', material: b.material,
      materialPreisKg: m?.preisKg ?? 0, seriennummern: !!b.seriennummern,
      arbeitsgaenge: (b.arbeitsgaenge ?? []).map((ag) => ({ ...JSON.parse(JSON.stringify(ag)), id: uid(), anfrageId: '' })),
      // Zeichnung, Modell und Bild des Bauteils gleich mit anzeigen
      dateien: [
        ...(b.zeichnung ? [{ name: dateiname(b.zeichnung), art: 'Zeichnung', url: b.zeichnung }] : []),
        ...(b.stepDatei ? [{ name: dateiname(b.stepDatei), art: 'STEP', url: b.stepDatei }] : []),
      ],
      vorschaubild: b.vorschaubild ?? '',
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
    kopie.vorschaubild = '';
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

  // Dateien hinzufügen und sofort hochladen (am Angebotsentwurf; beim Anlegen des Bauteils wandern sie dorthin).
  // Ohne Ziel werden sie nach Namen gruppiert: Zeichnung.pdf + Zeichnung.step ergeben ein Bauteil.
  async function dateienHinzufuegen(files, zielTeil = null) {
    const auftraege = [];
    if (zielTeil) {
      for (const f of files) auftraege.push({ teil: zielTeil, datei: f });
    } else {
      const gruppen = new Map();
      for (const f of files) {
        const basis = (/^(.*?)(\.[^.]+)?$/.exec(f.name)?.[1] ?? f.name).trim();
        const schluessel = basis.toLowerCase().replace(/[\s_-]+/g, '');
        if (!gruppen.has(schluessel)) gruppen.set(schluessel, { basis, dateien: [] });
        gruppen.get(schluessel).dateien.push(f);
      }
      let neu = 0;
      for (const g of gruppen.values()) {
        let ziel = teile.value.find((t) => t.name.toLowerCase().replace(/[\s_-]+/g, '') === g.basis.toLowerCase().replace(/[\s_-]+/g, ''));
        if (!ziel) {
          // über das reaktive Array holen, sonst bemerkt das Speichern die hochgeladenen Dateien nicht
          const id = hinzufuegen(g.basis.replace(/_/g, ' ')).id;
          ziel = teile.value.find((t) => t.id === id);
          neu++;
        }
        for (const f of g.dateien) auftraege.push({ teil: ziel, datei: f });
      }
      ui.toast(`${files.length} Datei${files.length === 1 ? '' : 'en'} → ${neu} neue${neu === 1 ? 's' : ''} Bauteil${neu === 1 ? '' : 'e'}`, 'ok');
    }
    // Dateien hängen am Angebot: der Entwurf muss gespeichert sein
    if (!angebotId.value) await speichern();
    if (!angebotId.value) { ui.toast('Das Angebot ließ sich nicht speichern, die Dateien wurden nicht hochgeladen.', 'warn'); return; }
    await Promise.all(auftraege.map(async ({ teil, datei }) => {
      uploads.value[teil.id] = [...(uploads.value[teil.id] ?? []), datei.name];
      try {
        const f = await hochladen(datei, { doctype: 'Angebot', docname: angebotId.value });
        const eintrag = { id: f.name, name: datei.name, art: dateiArt(datei.name), groesse: datei.size, url: f.file_url };
        teil.dateien.push(eintrag);
        if (eintrag.art === 'Zeichnung') erkennenFuer(teil, eintrag);
      } catch (e) {
        ui.toast(`${datei.name}: ${e.message}`, 'warn');
      } finally {
        uploads.value[teil.id] = (uploads.value[teil.id] ?? []).filter((n) => n !== datei.name);
      }
    }));
  }

  // Schriftfeld-Angaben aus der Zeichnung lesen und vorhandene Bauteile dazu suchen. Übernommen wird erst nach Bestätigung.
  async function vorlageHolen(kunde) {
    try {
      const v = await call('cnc_one.api.zeichnung.vorlage', { kunde });
      return Object.keys(v?.felder ?? {}).length ? v : null;
    } catch { return null; }
  }

  async function erkennenFuer(teil, datei) {
    erkennungen.value[teil.id] = { stand: 'laeuft', datei: datei.url };
    try {
      const [{ zeichnungLesen }, { erkennen, kundeFinden }] = await Promise.all([import('../lib/pdf.js'), import('../lib/erkennung.js')]);
      const seite = await zeichnungLesen(datei.url);
      // Angelernte Regeln des Kunden gehen vor. Ist noch kein Kunde gewählt, zählt der Kunde aus dem Schriftfeld.
      let kundeId = kopf.value.kundeId;
      let vorlage = kundeId ? await vorlageHolen(kundeId) : null;
      let r = erkennen(seite, datei.name, vorlage);
      if (!kundeId && r.felder.kunde) {
        const k = kundeFinden(r.felder.kunde.wert, await repo.kunden.liste());
        vorlage = k ? await vorlageHolen(k.id) : null;
        if (vorlage) { kundeId = k.id; r = erkennen(seite, datei.name, vorlage); }
      }
      const kunden = vorlage ? await repo.kunden.liste() : [];
      const vorlageInfo = vorlage ? { kundeId, kundeName: kunden.find((k) => k.id === kundeId)?.name ?? kundeId, anzahl: Object.values(vorlage.felder).flat().length } : null;
      let passende = [];
      if (r.felder.teilenummer || r.felder.zeichnungsnr) {
        try {
          passende = await call('cnc_one.api.bauteil.passende', { teilenummer: r.felder.teilenummer?.wert ?? '', zeichnungsnr: r.felder.zeichnungsnr?.wert ?? '', kunde: kopf.value.kundeId });
        } catch { /* ohne Vorschläge weiter */ }
      }
      const automatisch = await bestandAutomatisch(teil, passende);
      erkennungen.value[teil.id] = { stand: 'fertig', datei: datei.url, seite, ...r, passende, vorlage: vorlageInfo, vorlageFelder: vorlage?.felder ?? null, gelernt: {}, automatisch };
    } catch (e) {
      erkennungen.value[teil.id] = { stand: 'fehler', datei: datei.url, fehler: e.message };
    }
  }

  // Klick in die Zeichnung beim Anlernen: Textstück an der Stelle suchen, als Wert setzen und die Lernregel vormerken
  async function anlernPunkt(teil, x, y) {
    const e = erkennungen.value[teil.id];
    const feld = anlernen.value?.teilId === teil.id ? anlernen.value.feld : null;
    if (!feld || !e?.seite) return;
    const { elementBei, lernregel, regelnAus } = await import('../lib/erkennung.js');
    const el = elementBei(e.seite, x, y);
    if (!el) { ui.toast('Dort steht kein lesbarer Text. Bitte genau auf den Wert klicken.', 'warn'); return; }
    const regel = lernregel(e.seite, el);
    erkennungen.value[teil.id] = {
      ...e,
      felder: { ...e.felder, [feld]: { wert: regel.wert, sicherheit: 'hoch', quelle: 'Angelernt', lage: regel.lage } },
      gelernt: { ...e.gelernt, [feld]: regelnAus(regel) },
    };
    anlernen.value = null;
    markierung.value = { teilId: teil.id, lage: regel.lage };
  }

  // Bestätigte Angaben übernehmen: { name, teilenummer, zeichnungsnr, revision, material: { name, preisKg }, kundeId }.
  // `lernen` sind die angelernten oder korrigierten Angaben { feld: { regeln, wert } }. Sie werden mit den bisherigen Regeln
  // des Kunden zusammengeführt (neue vorne, auf dieser Zeichnung widerlegte fallen weg) und beim Kunden gespeichert.
  async function erkennungUebernehmen(teil, werte, lernen = {}) {
    const e = erkennungen.value[teil.id];
    for (const k of ['name', 'teilenummer', 'zeichnungsnr', 'revision']) if (werte[k] !== undefined) teil[k] = werte[k];
    if (werte.material) { teil.material = werte.material.name; teil.materialPreisKg = werte.material.preisKg ?? teil.materialPreisKg; }
    if (werte.kundeId && !kopf.value.kundeId) kopf.value.kundeId = werte.kundeId;
    delete erkennungen.value[teil.id];
    markierung.value = null;
    const anzahl = Object.keys(lernen).length;
    const kunde = kopf.value.kundeId;
    if (!anzahl) { ui.toast('Angaben aus der Zeichnung übernommen', 'ok'); return; }
    if (!kunde) { ui.toast('Übernommen. Ohne Kunde ließ sich die Stelle nicht merken.', 'warn'); return; }
    try {
      const { regelnZusammenfuehren } = await import('../lib/erkennung.js');
      const alte = e?.vorlage?.kundeId === kunde ? (e.vorlageFelder ?? {}) : ((await vorlageHolen(kunde))?.felder ?? {});
      const felder = Object.fromEntries(Object.entries(lernen).map(([feld, { regeln, wert }]) => [feld, regelnZusammenfuehren(alte[feld], regeln, e?.seite, feld, wert)]));
      await call('cnc_one.api.zeichnung.lernen', { kunde, felder });
      ui.toast(`Übernommen und für den Kunden gemerkt: ${anzahl} Angabe${anzahl === 1 ? '' : 'n'}`, 'ok');
    } catch (err) {
      ui.toast(`Übernommen, aber nicht gemerkt: ${err.message}`, 'warn');
    }
  }

  // Angelernte Regeln des Kunden löschen und die Zeichnung neu erkennen
  async function vorlageVergessen(teil) {
    const e = erkennungen.value[teil.id];
    if (!e?.vorlage) return;
    try {
      await call('cnc_one.api.zeichnung.vergessen', { kunde: e.vorlage.kundeId });
      ui.toast('Angelernte Regeln des Kunden gelöscht');
      const datei = teil.dateien.find((d) => d.url === e.datei);
      if (datei) erkennenFuer(teil, datei);
    } catch (err) {
      ui.toast(err.message, 'warn');
    }
  }

  // Ein vorgeschlagenes Bestandsbauteil verwenden: Angaben und Arbeitsplan aus den Stammdaten, Kunde falls noch keiner gewählt
  // Gibt es das Bauteil beim gewählten Kunden schon (gleiche Teilenummer, sonst gleiche Zeichnungsnummer), wird es auf jeden
  // Fall verwendet. Liefert die Bauteil-Nummer oder ''. Die Maske bleibt offen, z. B. für einen Hinweis auf eine neue Revision.
  async function bestandAutomatisch(teil, passende) {
    const kunde = kopf.value.kundeId;
    const eigene = (passende ?? []).filter((x) => x.kundeId === kunde && x.status !== 'Gesperrt');
    const b = eigene.find((x) => x.grund === 'teilenummer') ?? eigene[0];
    if (!kunde || !b) return '';
    if (zuordnung.value[teil.id]?.bauteilId !== b.id) bestandUebernehmen(teil, b, await repo.materialien.liste(), { automatisch: true });
    return b.id;
  }

  function bestandUebernehmen(teil, b, materialien = [], { automatisch = false } = {}) {
    if (kopf.value.kundeId && kopf.value.kundeId !== b.kundeId) { ui.toast('Das Bauteil gehört zu einem anderen Kunden.', 'warn'); return; }
    if (!kopf.value.kundeId) kopf.value.kundeId = b.kundeId;
    const m = materialien.find((x) => x.name === b.material);
    Object.assign(teil, {
      teilenummer: b.teilenummer, name: b.name || teil.name, zeichnungsnr: b.zeichnungsnr, revision: b.revision ?? '',
      seriennummern: !!b.seriennummern,
    });
    if (b.material) { teil.material = b.material; teil.materialPreisKg = m?.preisKg ?? teil.materialPreisKg; }
    if (!teil.arbeitsgaenge?.length && b.arbeitsgaenge?.length) teil.arbeitsgaenge = b.arbeitsgaenge.map((ag) => ({ ...JSON.parse(JSON.stringify(ag)), id: uid(), anfrageId: '' }));
    if (!teil.vorschaubild && b.vorschaubild) teil.vorschaubild = b.vorschaubild;
    zuordnung.value = { ...zuordnung.value, [teil.id]: { bauteilId: b.id, herkunft: 'bestand', seriennummern: !!b.seriennummern } };
    if (automatisch) {
      ui.toast(`${b.teilenummer} gibt es bei diesem Kunden schon (${b.id}), das Bauteil wird verwendet`, 'ok');
      return;
    }
    delete erkennungen.value[teil.id];
    ui.toast(`Bestandsbauteil ${b.teilenummer} verwendet`, 'ok');
  }

  // Rohmaterial zu einem Werkstoff von der Zeichnung anlegen (Preis je kg später in den Stammdaten)
  async function rohmaterialAnlegen(name, schreibweise) {
    try {
      const m = await call('cnc_one.api.zeichnung.rohmaterial_anlegen', { name, schreibweise });
      repo.materialien.merken(m);
      ui.toast(`Rohmaterial „${m.name}“ angelegt. Den Preis je kg bitte in den Stammdaten nachtragen.`, 'ok');
      return m;
    } catch (e) {
      ui.toast(e.message, 'warn');
      return null;
    }
  }

  // Merkt sich am Rohmaterial, wie es auf Zeichnungen geschrieben wird; danach passt die Zuordnung bei allen Kunden von selbst
  async function schreibweiseMerken(material, text) {
    try {
      repo.materialien.merken(await call('cnc_one.api.zeichnung.schreibweise_merken', { material, text }));
    } catch (e) {
      ui.toast(`Schreibweise nicht gemerkt: ${e.message}`, 'warn');
    }
  }

  function erkennungVerwerfen(teil) {
    delete erkennungen.value[teil.id];
    if (anlernen.value?.teilId === teil.id) anlernen.value = null;
    if (markierung.value?.teilId === teil.id) markierung.value = null;
  }

  function dateiEntfernen(teil, datei) {
    const i = teil.dateien.indexOf(datei);
    if (i >= 0) teil.dateien.splice(i, 1);
  }

  // Vorschaubild des Bauteils aus dem 3D-Modell (PNG) hochladen und setzen
  async function vorschaubildSetzen(teil, blob, melden = false) {
    if (!blob) return;
    if (!angebotId.value) await speichern();
    if (!angebotId.value) return;
    try {
      const name = `vorschau-${(teil.teilenummer || teil.id).replace(/[^\w.-]+/g, '_')}.png`;
      const f = await hochladen(blob, { doctype: 'Angebot', docname: angebotId.value, name });
      teil.vorschaubild = f.file_url;
      if (melden) ui.toast('Vorschaubild übernommen', 'ok');
    } catch (e) {
      ui.toast(`Vorschaubild: ${e.message}`, 'warn');
    }
  }

  function beispieleEinfuegen() {
    const neue = demoTeile();
    teile.value.push(...neue);
    auswahlId.value = neue[0].id;
    ui.toast('Beispiel-Bauteile eingefügt');
  }

  return { kopf, teile, zuordnung, auswahlId, angebotId, speicherStand, uploads, erkennungen, anlernen, markierung, fokus, ausBauteilHinzufuegen, auswahl, ergebnisse, netto, neu, ausAngebot, speichern, hinzufuegen, duplizieren, loeschen, verschieben, dateienHinzufuegen, dateiEntfernen, vorschaubildSetzen, erkennenFuer, anlernPunkt, erkennungUebernehmen, vorlageVergessen, bestandUebernehmen, erkennungVerwerfen, rohmaterialAnlegen, schreibweiseMerken, beispieleEinfuegen };
});
