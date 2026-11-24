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
    aufmass: 0,
    pauschalMaterial: 0,
    pauschalAlsZeile: false,
    messkosten: 0,
    sonderkosten: 0,
    expresskosten: 0,
    inStueckpreis: { ruest: false, mess: false, sonder: false, express: false },
    preisart: 'kalkuliert', // oder 'fest': Stückpreis ohne Kalkulation (festpreis, bei Staffeln je Stufe `preis`)
    festpreis: 0,
    staffel: { aktiv: false, stufen: [{ menge: 5, extra: 0 }, { menge: 25, extra: 0 }, { menge: 100, extra: 0 }] },
    seriennummern: false,
    arbeitsgaenge: [],
    dateien: [],
    vorschaubild: '',
    liefertermin: '', // intern: geht in Auftrag und Fertigung, steht nicht im Angebot
    werkstoffDrucken: false, // Werkstoff im Angebots-PDF nennen
    infoKunde: '', // Beschreibung für den Kunden, steht im Angebot
    notizIntern: '', // nur intern, wird am Bauteil gespeichert
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

// bestellung: { nr, datum, datei } bei einem Entwurf aus einer Bestellung des Kunden (wird nicht gesendet, daraus entsteht direkt der Auftrag)
const leererKopf = () => ({ kundeId: '', anfrageNr: '', gueltigWochen: 4, lieferzeit: 'Nach Absprache', projekt: '', kontaktName: '', kontaktEmail: '', materialDrucken: false, bestellung: null });

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
  // Mail-Anfrage, aus der das Angebot entstanden ist: { id, betreff, vonName, vonEmail } oder null
  const mailAnfrage = ref(null);
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
  // Nur ansehen: gesendetes Angebot zum Nachsehen der Kalkulation (aus Angebot oder Auftrag geöffnet). Nichts wird gespeichert.
  // { status, auftragId, zurueckZu } oder null; zurueckZu = Entwurf, der vorher offen war
  const nurAnsicht = ref(null);

  let unterdrueckt = true;
  let timer = 0;
  let laeuft = false;
  let nochmal = false;
  let laufend = Promise.resolve();
  // Alle Uploads der Workbench nacheinander (Dateien, Vorschaubilder im Hintergrund, Bestell-PDF): gleichzeitig
  // kollidieren die Einträge im Archiv-Protokoll (Nummernkreis, Deadlock)
  let uploadKette = Promise.resolve();
  const hochladenNacheinander = (...args) => {
    const p = uploadKette.then(() => hochladen(...args));
    uploadKette = p.catch(() => {});
    return p;
  };

  const ergebnisse = computed(() => Object.fromEntries(teile.value.map((t) => [t.id, berechne(t)])));
  const netto = computed(() => summe(Object.values(ergebnisse.value)));
  // Frühester Liefertermin der Bauteile: nur als Hinweis; die Lieferzeit im Kopf bleibt frei änderbar
  const fruehesterTermin = computed(() => teile.value.map((t) => t.liefertermin).filter(Boolean).sort()[0] ?? '');
  const auswahl = computed(() => teile.value.find((t) => t.id === auswahlId.value) ?? null);

  async function ruhig(fn) {
    unterdrueckt = true;
    fn();
    await nextTick();
    unterdrueckt = false;
  }

  function zuordnungAus(positionen) {
    const m = {};
    for (const p of positionen) {
      if (p.bauteilId) m[p.key] = { bauteilId: p.bauteilId, herkunft: p.herkunft, seriennummern: !!p.seriennummern, revision: p.bauteilRevision ?? '', revisionen: p.bauteilRevisionen ?? [], frueher: p.bauteilFrueher ?? null };
      // interne Notiz steht am Bauteil: ist sie im Angebot leer, die vom Bauteil zeigen
      const t = teile.value.find((x) => x.id === p.key);
      if (t && !t.notizIntern && p.bauteilNotiz) t.notizIntern = p.bauteilNotiz;
    }
    zuordnung.value = m;
  }

  // Ist nur ansehen aktiv, ändert sich nichts: Hinweis zeigen und true liefern
  function gesperrt() {
    if (!nurAnsicht.value) return false;
    ui.toast('Gesendetes Angebot: nur ansehen, Änderungen sind nicht möglich', 'warn');
    return true;
  }

  // Gespeichertes Angebot laden: ein Entwurf zum Weiterbearbeiten, ein gesendetes nur zum Ansehen.
  // auswahl: Position (Workbench-Bauteil), die gleich gewählt sein soll; auftragId: von dort geöffnet
  async function ausAngebot(record, { auswahl = '', auftragId = '' } = {}) {
    const ansehen = record.status !== 'Entwurf';
    if (speicherStand.value === 'offen' && !nurAnsicht.value) await speichern();
    const zurueckZu = ansehen ? (nurAnsicht.value ? nurAnsicht.value.zurueckZu : angebotId.value && angebotId.value !== record.id ? angebotId.value : '') : '';
    clearTimeout(timer);
    unterdrueckt = true;
    nurAnsicht.value = ansehen ? { status: record.status, auftragId, zurueckZu } : null;
    const k = JSON.parse(JSON.stringify(record.kopf));
    kopf.value = {
      kundeId: k.kundeId, anfrageNr: k.anfrageNr, gueltigWochen: k.gueltigWochen, lieferzeit: k.lieferzeit,
      projekt: k.projekt ?? '', kontaktName: k.kontaktName ?? '', kontaktEmail: k.kontaktEmail ?? '', materialDrucken: !!k.materialDrucken,
      bestellung: k.bestellung?.nr || k.bestellung?.datei ? k.bestellung : null,
    };
    // ältere Angebote hatten „Werkstoff nennen“ nur für das ganze Angebot: an die Positionen übertragen
    teile.value = record.positionen.map((p) => {
      const t = JSON.parse(JSON.stringify(p.teil));
      if (t.werkstoffDrucken === undefined) t.werkstoffDrucken = !!k.materialDrucken;
      return t;
    });
    auswahlId.value = teile.value.find((t) => t.id === (auswahl || sitzung.auswahlId))?.id ?? teile.value[0]?.id ?? null;
    angebotId.value = record.id;
    mailAnfrage.value = record.mailAnfrage ?? null;
    zuordnungAus(record.positionen);
    speicherStand.value = 'gespeichert';
    nextTick().then(() => { unterdrueckt = false; });
  }

  // Speichert den Entwurf. Läuft schon ein Speichern, wird danach noch einmal gespeichert; der Aufrufer wartet auf das
  // laufende (wichtig beim Hochladen: die Dateien brauchen die Angebotsnummer).
  function speichern() {
    clearTimeout(timer);
    if (nurAnsicht.value) return Promise.resolve();
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
      mailAnfrage.value = rec.mailAnfrage ?? null;
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
    if (unterdrueckt || nurAnsicht.value) return;
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
    if (nurAnsicht.value) return; // die Ansicht merkt sich nicht als zuletzt offenes Angebot
    einstellungSpeichern('workbenchAngebot', angebotId.value ?? '');
    einstellungSpeichern('workbenchAuswahl', auswahlId.value ?? '');
  });

  // Beim Start das zuletzt offene Entwurf-Angebot wieder aufnehmen
  const letztes = sitzung.angebotId ? belege.angebot(sitzung.angebotId) : null;
  if (letztes && letztes.status === 'Entwurf') ausAngebot(letztes);
  else nextTick().then(() => { unterdrueckt = false; });

  async function neu() {
    if (speicherStand.value === 'offen') await speichern();
    nurAnsicht.value = null;
    await ruhig(() => {
      teile.value = [];
      zuordnung.value = {};
      auswahlId.value = null;
      angebotId.value = null;
      kopf.value = leererKopf();
      mailAnfrage.value = null;
      speicherStand.value = 'gespeichert';
    });
  }

  function hinzufuegen(name) {
    if (gesperrt()) return null;
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

  // Aktuelle und bekannte Revisionen eines Bauteils aus den Stammdaten (für den Hinweis im Bauteil)
  const revisionenVon = (b) => ({ revision: b.revision ?? '', revisionen: [...new Set((b.revisionen ?? []).map((r) => r.revision).filter(Boolean))] });

  // Bestandsbauteil aus den Stammdaten ins Angebot übernehmen (Angaben und Arbeitsplan, ohne Kalkulationswerte)
  function ausBauteilHinzufuegen(b, materialien = []) {
    if (gesperrt()) return null;
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
      notizIntern: b.notizIntern ?? '',
    });
    zuordnung.value = { ...zuordnung.value, [t.id]: { bauteilId: b.id, herkunft: 'bestand', seriennummern: !!b.seriennummern, ...revisionenVon(b) } };
    teile.value.push(t);
    auswahlId.value = t.id;
    ui.toast(`Bestandsbauteil ${b.teilenummer} übernommen`, 'ok');
    return t;
  }

  function duplizieren(id) {
    if (gesperrt()) return null;
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
    if (gesperrt()) return null;
    const i = teile.value.findIndex((t) => t.id === id);
    if (i < 0) return;
    const [weg] = teile.value.splice(i, 1);
    if (auswahlId.value === id) auswahlId.value = (teile.value[i] ?? teile.value[i - 1])?.id ?? null;
    ui.toast(`„${weg.name}“ entfernt`);
  }

  // Zwei Bauteile gehören zusammen (z. B. Zeichnung und Modell wurden nicht zusammen erkannt): die Dateien von „quelle“
  // kommen zu „ziel“, leere Angaben wie Teilenummer werden ergänzt, „quelle“ entfällt. Kalkulation, Menge und Arbeitsgänge
  // bleiben die von „ziel“.
  function zusammenfuehren(zielId, quelleId) {
    if (gesperrt()) return null;
    const ziel = teile.value.find((t) => t.id === zielId);
    const quelle = teile.value.find((t) => t.id === quelleId);
    if (!ziel || !quelle || ziel === quelle) return;
    const ohneZeichnung = !ziel.dateien.some((d) => d.art === 'Zeichnung');
    for (const d of quelle.dateien) if (!ziel.dateien.some((x) => x.url && x.url === d.url)) ziel.dateien.push(d);
    for (const k of ['teilenummer', 'zeichnungsnr', 'revision']) if (!ziel[k] && quelle[k]) ziel[k] = quelle[k];
    if (!ziel.vorschaubild && quelle.vorschaubild) ziel.vorschaubild = quelle.vorschaubild;
    teile.value.splice(teile.value.indexOf(quelle), 1);
    auswahlId.value = ziel.id;
    const z = ohneZeichnung && ziel.dateien.find((d) => d.art === 'Zeichnung' && d.url);
    if (z) erkennenFuer(ziel, z);
    ui.toast(`„${quelle.name}“ mit „${ziel.name}“ zusammengeführt`, 'ok');
  }

  function verschieben(id, richtung) {
    if (gesperrt()) return null;
    const i = teile.value.findIndex((t) => t.id === id);
    const j = i + richtung;
    if (i < 0 || j < 0 || j >= teile.value.length) return;
    const [t] = teile.value.splice(i, 1);
    teile.value.splice(j, 0, t);
  }

  // Dateien hinzufügen und sofort hochladen (am Angebotsentwurf; beim Anlegen des Bauteils wandern sie dorthin).
  // Ohne Ziel ordnet lib/zuordnung.js zu: Zeichnung und Modell eines Bauteils (auch bei verschiedenen Namen) ergeben ein
  // Bauteil, das fehlende Gegenstück eines schon vorhandenen Bauteils kommt dorthin.
  async function dateienHinzufuegen(files, zielTeil = null) {
    if (gesperrt()) return null;
    const auftraege = [];
    if (zielTeil) {
      for (const f of files) auftraege.push({ teil: zielTeil, datei: f });
    } else {
      const { gruppieren } = await import('../lib/zuordnung.js');
      const vorhandene = teile.value.map((t) => ({ id: t.id, name: t.name, dateien: t.dateien }));
      const gruppen = gruppieren(files.map((f) => ({ name: f.name, art: dateiArt(f.name), paket: 'ablage', datei: f })), { vorhandene });
      let neu = 0;
      for (const g of gruppen) {
        // über das reaktive Array holen, sonst bemerkt das Speichern die hochgeladenen Dateien nicht
        let ziel = g.teilId ? teile.value.find((t) => t.id === g.teilId) : null;
        if (!ziel) {
          const id = hinzufuegen(g.basis).id;
          ziel = teile.value.find((t) => t.id === id);
          neu++;
        }
        for (const d of g.dateien) auftraege.push({ teil: ziel, datei: d.datei });
      }
      ui.toast(`${files.length} Datei${files.length === 1 ? '' : 'en'} → ${neu} neue${neu === 1 ? 's' : ''} Bauteil${neu === 1 ? '' : 'e'}`, 'ok');
    }
    // Dateien hängen am Angebot: der Entwurf muss gespeichert sein
    if (!angebotId.value) await speichern();
    if (!angebotId.value) { ui.toast('Das Angebot ließ sich nicht speichern, die Dateien wurden nicht hochgeladen.', 'warn'); return; }
    // nacheinander hochladen: gleichzeitig kollidieren die Einträge im Archiv-Protokoll (Nummernkreis, Deadlock)
    for (const { teil, datei } of auftraege) uploads.value[teil.id] = [...(uploads.value[teil.id] ?? []), datei.name];
    for (const { teil, datei } of auftraege) await (async () => {
      try {
        const f = await hochladenNacheinander(datei, { doctype: 'Angebot', docname: angebotId.value });
        const eintrag = { id: f.name, name: datei.name, art: dateiArt(datei.name), groesse: datei.size, url: f.file_url };
        teil.dateien.push(eintrag);
        if (eintrag.art === 'Zeichnung') erkennenFuer(teil, eintrag);
        // neues Modell, neues Bild: das bisherige (z. B. vom Bestandsbauteil) entsteht beim Laden neu
        if (eintrag.art === 'STEP') teil.vorschaubild = '';
      } catch (e) {
        ui.toast(`${datei.name}: ${e.message}`, 'warn');
      } finally {
        uploads.value[teil.id] = (uploads.value[teil.id] ?? []).filter((n) => n !== datei.name);
      }
    })();
  }

  // Angebot aus einer Mail-Anfrage (cnc_one.api.mail.angebot_anlegen): Entwurf laden, je Zeichnung/Modell-Paar ein Bauteil
  // mit den schon hochgeladenen Dateien, Mengen aus dem Mailtext (mehrere = Staffel), danach die Zeichnungen erkennen.
  async function ausMailAnfrage({ angebot, dateien = [], text = '', zeilen = [] }) {
    if (speicherStand.value === 'offen') await speichern();
    belege.einsetzen(angebot);
    await ausAngebot(angebot);
    if (!dateien.length) return;
    const [{ gruppieren, mengenAusText, dateiPfad }, { passtZu }] = await Promise.all([import('../lib/mailanfrage.js'), import('../lib/mailtabelle.js')]);
    // dieselbe Datei nur einmal (ältere Anfragen mit zwei gleichen ZIPs liefern sie doppelt)
    const gruppen = gruppieren(dateien.filter((d, i) => !d.url || dateien.findIndex((x) => x.url === d.url) === i));
    for (const g of gruppen) {
      const id = hinzufuegen(g.basis).id;
      const t = teile.value.find((x) => x.id === id);
      t.dateien = g.dateien.map((d) => ({ id: d.id, name: d.name, art: d.art, groesse: d.groesse, url: d.url }));
      // bestätigte Zeile der Tabelle (Menge, Liefertermin), sonst Mengen aus dem Text
      const zeile = zeilen.find((z) => g.dateien.some((d) => (z.datei ? dateiPfad(d) === z.datei : passtZu(z.teilenummer, dateiPfad(d)))));
      if (zeile?.liefertermin) t.liefertermin = zeile.liefertermin;
      const mengen = zeile?.menge?.length ? zeile.menge : mengenAusText(text, g.basis, { einziges: gruppen.length === 1 });
      if (mengen.length) t.menge = mengen[0];
      if (mengen.length > 1) t.staffel = { aktiv: true, stufen: mengen.map((menge) => ({ menge, extra: 0 })) };
    }
    auswahlId.value = teile.value[0]?.id ?? null;
    await speichern();
    for (const t of teile.value) {
      const z = t.dateien.find((d) => d.art === 'Zeichnung');
      if (z) erkennenFuer(t, z);
    }
    ui.toast(`${gruppen.length} Bauteil${gruppen.length === 1 ? '' : 'e'} aus der Anfrage übernommen`, 'ok');
  }

  // Workbench aus einer Bestellung des Kunden (BestellungImportDialog): neuer Entwurf, Projekt = Bestellnummer, je
  // Bestellposition ein Bauteil. Wiederholteile bringen Kalkulation, Rohmaterial und Arbeitsgänge aus ihrem letzten
  // Angebot mit (`quelle`), sonst Zeichnung und Modell des Bauteils. Preis = Stückpreis der Bestellung (fester Preis),
  // Menge und Termin wie bestellt. Das Bestell-PDF hängt am Entwurf, Zeichnungen und Modelle an ihrer Position.
  // positionen: [{ bestellposition, teilenummer, bezeichnung, menge, preis, termin, zeichnungsnr, index, bauteil, quelle, frueher, dateien: [File] }]
  async function ausBestellung({ kundeId, bestellung, positionen, bestellPdf = null }) {
    await neu();
    const { kalkulationUebernehmen } = await import('../lib/historie.js');
    const neueTeile = [];
    for (const p of positionen) {
      const t = neuesTeil(p.bezeichnung || p.teilenummer || 'Bauteil');
      if (p.quelle?.angebot) {
        try {
          kalkulationUebernehmen(t, await call('cnc_one.api.historie.kalkulation', { angebot: p.quelle.angebot, position_key: p.quelle.angebotKey }), uid);
        } catch { ui.toast(`${p.teilenummer}: Kalkulation aus ${p.quelle.angebot} ließ sich nicht laden`, 'warn'); }
      } else if (p.bauteil?.material) t.material = p.bauteil.material;
      const b = p.bauteil;
      Object.assign(t, {
        teilenummer: b?.teilenummer || p.teilenummer || '',
        zeichnungsnr: p.zeichnungsnr || b?.zeichnungsnr || '',
        revision: p.index || '',
        menge: Math.max(1, Math.round(Number(p.menge) || 1)),
        liefertermin: p.termin || '',
        preisart: 'fest',
        festpreis: Number(p.preis) || 0,
        staffel: { ...(t.staffel ?? {}), aktiv: false, stufen: t.staffel?.stufen ?? [] },
        bestellung: { position: p.bestellposition || '', preis: Number(p.preis) || 0, menge: Math.max(1, Math.round(Number(p.menge) || 1)), termin: p.termin || '' },
        dateien: !p.dateien?.length && b ? [
          ...(b.zeichnung ? [{ name: dateiname(b.zeichnung), art: 'Zeichnung', url: b.zeichnung }] : []),
          ...(b.stepDatei ? [{ name: dateiname(b.stepDatei), art: 'STEP', url: b.stepDatei }] : []),
        ] : [],
        vorschaubild: !p.dateien?.some((f) => dateiArt(f.name) === 'STEP') ? (b?.vorschaubild ?? '') : '',
        seriennummern: b ? !!b.seriennummern : t.seriennummern,
      });
      if (p.frueher) t.frueher = { gefertigt: !!p.frueher.gefertigt, notiz: p.frueher.notiz ?? '' };
      neueTeile.push({ t, p });
    }
    await ruhig(() => {
      kopf.value = {
        ...leererKopf(), kundeId,
        projekt: bestellung?.nr ? `Bestellung ${bestellung.nr}` : 'Bestellung',
        lieferzeit: 'laut Bestellung',
        bestellung: { nr: bestellung?.nr ?? '', datum: bestellung?.datum ?? '', datei: '' },
      };
      teile.value = neueTeile.map((x) => x.t);
      auswahlId.value = teile.value[0]?.id ?? null;
    });
    await speichern();
    if (!angebotId.value) { ui.toast('Der Entwurf ließ sich nicht speichern.', 'warn'); return; }
    // Bestell-PDF und die Dateien der Positionen hochladen
    if (bestellPdf) {
      try {
        const f = await hochladenNacheinander(bestellPdf, { doctype: 'Angebot', docname: angebotId.value });
        kopf.value.bestellung = { ...kopf.value.bestellung, datei: f.file_url };
      } catch (e) { ui.toast(`${bestellPdf.name}: ${e.message}`, 'warn'); }
    }
    for (const { p } of neueTeile.filter((x) => x.p.dateien?.length)) {
      const teil = teile.value.find((x) => x.id === neueTeile.find((y) => y.p === p).t.id);
      await dateienHinzufuegen(p.dateien, teil);
    }
    await speichern();
    ui.toast(`${neueTeile.length} Position${neueTeile.length === 1 ? '' : 'en'} aus Bestellung ${bestellung?.nr ?? ''} übernommen`, 'ok');
  }

  // Schriftfeld-Angaben aus der Zeichnung lesen und vorhandene Bauteile dazu suchen. Übernommen wird erst nach Bestätigung.
  async function vorlageHolen(kunde) {
    try {
      const v = await call('cnc_one.api.zeichnung.vorlage', { kunde });
      return Object.keys(v?.felder ?? {}).length ? v : null;
    } catch { return null; }
  }

  async function erkennenFuer(teil, datei) {
    if (gesperrt()) return null;
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
    zuordnung.value = { ...zuordnung.value, [teil.id]: { bauteilId: b.id, herkunft: 'bestand', seriennummern: !!b.seriennummern, ...revisionenVon(b) } };
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
    if (gesperrt()) return null;
    const i = teil.dateien.indexOf(datei);
    if (i >= 0) teil.dateien.splice(i, 1);
  }

  // Vorschaubild des Bauteils aus dem 3D-Modell (PNG) hochladen und setzen
  async function vorschaubildSetzen(teil, blob, melden = false) {
    if (gesperrt()) return null;
    if (!blob) return;
    if (!angebotId.value) await speichern();
    if (!angebotId.value) return;
    try {
      const name = `vorschau-${(teil.teilenummer || teil.id).replace(/[^\w.-]+/g, '_')}.png`;
      const f = await hochladenNacheinander(blob, { doctype: 'Angebot', docname: angebotId.value, name });
      teil.vorschaubild = f.file_url;
      if (melden) ui.toast('Vorschaubild übernommen', 'ok');
    } catch (e) {
      ui.toast(`Vorschaubild: ${e.message}`, 'warn');
    }
  }

  // ---- Vorschaubilder im Hintergrund: alle STEP-Modelle der Workbench werden vorgeladen (mehrere gleichzeitig, das
  // gewählte Bauteil zuerst), fehlende Vorschaubilder entstehen daraus ohne Anklicken. Die Bilder werden nacheinander
  // gerendert (jedes braucht kurz einen eigenen WebGL-Kontext).
  const vorschauInArbeit = new Set();
  let bildKette = Promise.resolve();
  const modellUrl = (t) => t.dateien.find((d) => d.art === 'STEP' && d.url)?.url ?? '';
  function vorschauAutomatisch(teil, netze) {
    if (teil.vorschaubild || nurAnsicht.value || vorschauInArbeit.has(teil.id)) return Promise.resolve();
    vorschauInArbeit.add(teil.id);
    const url = modellUrl(teil);
    const p = bildKette.then(async () => {
      if (teil.vorschaubild || modellUrl(teil) !== url || !teile.value.includes(teil)) return;
      const { vorschauPng } = await import('../lib/modell3d.js');
      const blob = await vorschauPng(netze);
      if (!teil.vorschaubild && modellUrl(teil) === url) await vorschaubildSetzen(teil, blob);
    }).finally(() => vorschauInArbeit.delete(teil.id));
    bildKette = p.catch(() => {});
    return p;
  }
  // Geometrie-Fingerabdruck je Modell (für „ähnliche Bauteile“); wird mit dem Angebot gespeichert und kommt ans Bauteil
  async function geoSetzen(teil, url, netze) {
    if (nurAnsicht.value || teil.geo?.url === url) return;
    const { fingerabdruck } = await import('../lib/geometrie.js');
    const f = fingerabdruck(netze);
    if (f && modellUrl(teil) === url) teil.geo = { url, ...f };
  }
  async function modelleVorladen() {
    const liste = teile.value.map((t) => [t, modellUrl(t)]).filter(([, url]) => url);
    if (!liste.length) return;
    const { stepNetze, stepVorladen } = await import('../lib/step.js');
    // das gewählte Bauteil zuerst, dann die ohne Vorschaubild, dann der Rest
    const rang = (t) => (t.id === auswahlId.value ? 0 : t.vorschaubild ? 2 : 1);
    liste.sort((a, b) => rang(a[0]) - rang(b[0]));
    for (const [t, url] of liste) {
      (rang(t) === 0 ? stepNetze(url) : stepVorladen(url))
        .then((netze) => { geoSetzen(t, url, netze).catch(() => {}); return t.vorschaubild ? null : vorschauAutomatisch(t, netze); })
        .catch(() => {}); // Fehler zeigt die 3D-Ansicht beim Anklicken
    }
  }
  watch(() => teile.value.map((t) => `${t.id}|${modellUrl(t)}|${t.vorschaubild ? 1 : 0}`).join(';'), () => { modelleVorladen(); });

  function beispieleEinfuegen() {
    if (gesperrt()) return null;
    const neue = demoTeile();
    teile.value.push(...neue);
    auswahlId.value = neue[0].id;
    ui.toast('Beispiel-Bauteile eingefügt');
  }

  return { nurAnsicht, kopf, teile, zuordnung, fruehesterTermin, mailAnfrage, ausMailAnfrage, ausBestellung, auswahlId, angebotId, speicherStand, uploads, erkennungen, anlernen, markierung, fokus, ausBauteilHinzufuegen, auswahl, ergebnisse, netto, neu, ausAngebot, speichern, hinzufuegen, duplizieren, loeschen, zusammenfuehren, verschieben, dateienHinzufuegen, dateiEntfernen, vorschaubildSetzen, vorschauAutomatisch, erkennenFuer, anlernPunkt, erkennungUebernehmen, vorlageVergessen, bestandUebernehmen, erkennungVerwerfen, rohmaterialAnlegen, schreibweiseMerken, beispieleEinfuegen };
});
