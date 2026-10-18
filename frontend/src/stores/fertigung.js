import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import {
  ausPlan, leererArbeitsgang, normalisiere, nachzuholen, nochNichtGesendet, fremdGebucht,
  autoStatus, arbeitsgangStatus, produziert,
} from '../lib/fertigung.js';
import { uid } from '../lib/format.js';
import { useBelege } from './belege.js';
import { useStamm } from './stamm.js';
import { useUi } from './ui.js';

const KEY = 'cnc-one:fertigung:v1';
const heute = () => new Date().toISOString().slice(0, 10);
const jetzt = () => new Date().toISOString();

function laden() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* egal */ }
  return null;
}

// Fertigungsbauteile. Aktuell im Browser, später über die Frappe-API (siehe data/repo.js).
export const useFertigung = defineStore('fertigung', () => {
  const ui = useUi();
  const belege = useBelege();
  const stamm = useStamm();
  const g = laden();
  const liste = ref((g?.liste ?? []).map((fb) => {
    normalisiere(fb);
    fb.kundeId ??= belege.auftrag(fb.auftragId)?.kunde?.id ?? '';
    return fb;
  }));
  const zaehler = ref(g?.zaehler ?? 0);

  watch([liste, zaehler], () => {
    try { localStorage.setItem(KEY, JSON.stringify({ liste: liste.value, zaehler: zaehler.value })); } catch { /* egal */ }
  }, { deep: true });

  const bauteil = (id) => liste.value.find((x) => x.id === id) ?? null;
  const fuerAuftrag = (auftragId) => liste.value.filter((x) => x.auftragId === auftragId);
  const offen = computed(() => liste.value.filter((x) => x.status !== 'Fertig'));

  function auftragStatusAktualisieren(auftragId) {
    const a = belege.auftrag(auftragId);
    const fbs = fuerAuftrag(auftragId);
    if (!a || !fbs.length) return;
    a.status = fbs.every((x) => x.status === 'Fertig') ? 'Fertig' : 'In Fertigung';
  }

  // Arbeitsplan eines Auftragspostens: im Auftrag gepflegt, sonst am Bauteil gespeichert, sonst aus dem Angebot, sonst leer.
  function planFuerPosition(a, pos, kalk) {
    if (pos.arbeitsgaenge?.length) return pos.arbeitsgaenge;
    const kundeId = a.kunde?.id ?? '';
    return stamm.planFuer(kundeId, pos.teil.teilenummer) ?? kalk?.arbeitsgaenge ?? [];
  }

  function ausAuftrag(auftragId) {
    const a = belege.auftrag(auftragId);
    if (!a || fuerAuftrag(auftragId).length) return;
    const angebot = belege.angebot(a.angebotId);
    let ohnePlan = 0;
    for (const pos of a.positionen) {
      const kalk = angebot?.positionen.find((p) => p.key === pos.angebotKey)?.teil;
      const plan = planFuerPosition(a, pos, kalk);
      if (!plan.length) ohnePlan += 1;
      zaehler.value += 1;
      liste.value.push({
        id: `FB-${new Date().getFullYear()}-${String(zaehler.value).padStart(4, '0')}`,
        auftragId,
        auftragPosKey: pos.key,
        kundeId: a.kunde?.id ?? '',
        kundeName: a.kundeName,
        teil: { name: pos.teil.name, teilenummer: pos.teil.teilenummer, zeichnungsnr: pos.teil.zeichnungsnr, material: pos.teil.material, vorschaubild: pos.teil.vorschaubild ?? '' },
        menge: pos.menge,
        termin: pos.termin || '',
        prioritaet: 'Normal',
        status: 'Offen',
        arbeitsgaenge: ausPlan(plan, uid),
        buchungen: [],
        rohmaterial: { werkstoff: pos.teil.material || '', charge: '', lagerplatz: '', info: '', verbrauchtMm: 0 },
        notizen: { pruefmasse: '', bemerkungen: '' },
      });
    }
    auftragStatusAktualisieren(auftragId);
    ui.toast(ohnePlan
      ? `${a.positionen.length} Fertigungsbauteile angelegt, ${ohnePlan} ohne Arbeitsgänge`
      : `${a.positionen.length} Fertigungsbauteil${a.positionen.length === 1 ? '' : 'e'} angelegt`, ohnePlan ? 'warn' : 'ok');
  }

  function neuBewerten(fb, ag) {
    if (ag) ag.status = arbeitsgangStatus(ag, fb.menge);
    fb.status = autoStatus(fb);
    auftragStatusAktualisieren(fb.auftragId);
  }

  const logEintrag = (fb, ag, menge, auto) => fb.buchungen.unshift({ id: uid(), zeit: jetzt(), agId: ag.id, agName: ag.name, menge, benutzer: 'LH', auto: !!auto });

  // Frühere Arbeitsgänge gelten als abgehakt: intern wird nachgebucht, Fremdvergabe bekommt eine abgehakte Sendung.
  function abhaken(fb, agId, delta) {
    const ag = fb.arbeitsgaenge.find((x) => x.id === agId);
    if (!ag || !(delta > 0)) return;
    if (ag.typ === 'fremd') ag.sendungen.push({ id: uid(), menge: delta, datumWeg: heute(), datumZurueck: heute(), abgehakt: true });
    ag.gebucht += delta;
    logEintrag(fb, ag, delta, true);
    ag.status = arbeitsgangStatus(ag, fb.menge);
  }

  function buchen(fbId, agId, menge) {
    const fb = bauteil(fbId);
    const ag = fb?.arbeitsgaenge.find((x) => x.id === agId);
    const m = Math.floor(Number(menge));
    if (!ag || !(m > 0)) return;
    const neueGesamt = ag.gebucht + m;
    const nach = nachzuholen(fb, agId, neueGesamt);
    for (const k of nach) abhaken(fb, k.agId, k.delta);
    ag.gebucht = neueGesamt;
    logEintrag(fb, ag, m);
    neuBewerten(fb, ag);
    if (nach.length) ui.toast(`${nach.length} vorherige${nach.length === 1 ? 'r' : ''} Arbeitsgang${nach.length === 1 ? '' : 'e'} mit abgehakt`);
    if (ag.gebucht > fb.menge) ui.toast(`Überproduktion: ${ag.gebucht - fb.menge} Stk über Soll, später ins Lager`);
  }

  function buchungLoeschen(fbId, buchungId) {
    const fb = bauteil(fbId);
    const b = fb?.buchungen.find((x) => x.id === buchungId);
    const ag = fb?.arbeitsgaenge.find((x) => x.id === b?.agId);
    if (!b) return;
    if (ag) ag.gebucht = Math.max(0, ag.gebucht - b.menge);
    fb.buchungen = fb.buchungen.filter((x) => x.id !== buchungId);
    neuBewerten(fb, ag);
  }

  function arbeitsgangHinzu(fbId, typ) {
    const fb = bauteil(fbId);
    if (!fb) return;
    fb.arbeitsgaenge.push(...ausPlan([leererArbeitsgang(typ, uid)], uid));
    neuBewerten(fb);
  }

  function vorlageAnwenden(fbId, vorlageId) {
    const fb = bauteil(fbId);
    if (!fb) return;
    const neu = ausPlan(stamm.vorlageKopie(vorlageId), uid);
    fb.arbeitsgaenge.push(...neu);
    neuBewerten(fb);
    ui.toast(`${neu.length} Arbeitsgänge aus der Vorlage hinzugefügt`, 'ok');
  }

  async function planAmBauteilSpeichern(fbId) {
    const fb = bauteil(fbId);
    if (!fb) return;
    if (await stamm.planSpeichern(fb.kundeId, fb.teil.teilenummer, fb.arbeitsgaenge, fb.teil)) ui.toast('Arbeitsplan am Bauteil gespeichert', 'ok');
    else if (!stamm.teilKey(fb.kundeId, fb.teil.teilenummer)) ui.toast('Dafür braucht das Bauteil einen Kunden und eine Teilenummer', 'warn');
  }

  function arbeitsgangWeg(fbId, agId) {
    const fb = bauteil(fbId);
    if (!fb) return;
    fb.arbeitsgaenge = fb.arbeitsgaenge.filter((x) => x.id !== agId);
    neuBewerten(fb);
  }

  function arbeitsgangVerschieben(fbId, agId, richtung) {
    const fb = bauteil(fbId);
    const i = fb?.arbeitsgaenge.findIndex((x) => x.id === agId);
    const j = i + richtung;
    if (!fb || i < 0 || j < 0 || j >= fb.arbeitsgaenge.length) return;
    const [a] = fb.arbeitsgaenge.splice(i, 1);
    fb.arbeitsgaenge.splice(j, 0, a);
  }

  // Fremdvergabe in Sendungen: jede Sendung kann eine Teilmenge sein.
  function sendungAnlegen(fbId, agId, menge) {
    const fb = bauteil(fbId);
    const ag = fb?.arbeitsgaenge.find((x) => x.id === agId);
    if (!ag) return;
    const m = Math.floor(Number(menge ?? nochNichtGesendet(fb, ag)));
    if (!(m > 0)) { ui.toast('Es ist schon die ganze Menge versendet', 'warn'); return; }
    ag.sendungen.push({ id: uid(), menge: m, datumWeg: '', datumZurueck: '' });
  }

  function sendungWeg(fbId, agId, sendungId) {
    const fb = bauteil(fbId);
    const ag = fb?.arbeitsgaenge.find((x) => x.id === agId);
    const s = ag?.sendungen.find((x) => x.id === sendungId);
    if (!s) return;
    if (!ag.lieferant) { ui.toast('Bitte zuerst einen Lieferanten wählen', 'warn'); return; }
    s.datumWeg = heute();
    neuBewerten(fb, ag);
  }

  function sendungZurueck(fbId, agId, sendungId) {
    const fb = bauteil(fbId);
    const ag = fb?.arbeitsgaenge.find((x) => x.id === agId);
    const s = ag?.sendungen.find((x) => x.id === sendungId);
    if (!s) return;
    if (!s.datumWeg) s.datumWeg = heute();
    s.datumZurueck = heute();
    const neueGesamt = fremdGebucht(ag);
    const nach = nachzuholen(fb, agId, neueGesamt);
    for (const k of nach) abhaken(fb, k.agId, k.delta);
    const delta = neueGesamt - ag.gebucht;
    ag.gebucht = neueGesamt;
    if (delta > 0) logEintrag(fb, ag, delta);
    neuBewerten(fb, ag);
    ui.toast('Ware vom Lieferanten zurück gebucht', 'ok');
  }

  function sendungLoeschen(fbId, agId, sendungId) {
    const fb = bauteil(fbId);
    const ag = fb?.arbeitsgaenge.find((x) => x.id === agId);
    if (!ag) return;
    ag.sendungen = ag.sendungen.filter((x) => x.id !== sendungId);
    ag.gebucht = fremdGebucht(ag);
    neuBewerten(fb, ag);
  }

  // Manuelle Statusänderung (Board). Fertig bucht den Rest, Offen ist nur ohne Buchungen möglich.
  function statusSetzen(fbId, status) {
    const fb = bauteil(fbId);
    if (!fb || fb.status === status) return;
    if (status === 'Offen' && produziert(fb) + fb.buchungen.length > 0) {
      ui.toast('Mit vorhandenen Buchungen kann das Bauteil nicht auf „Offen“ zurück', 'warn');
      return;
    }
    if (status === 'Fertig') {
      if (!fb.arbeitsgaenge.length) { ui.toast('Ohne Arbeitsgänge lässt sich nichts fertig buchen. Bitte zuerst Arbeitsgänge anlegen.', 'warn'); return; }
      for (const ag of fb.arbeitsgaenge) abhaken(fb, ag.id, fb.menge - ag.gebucht);
      for (const ag of fb.arbeitsgaenge) ag.status = arbeitsgangStatus(ag, fb.menge);
      ui.toast('Restmenge in allen Arbeitsgängen gebucht');
    } else if (status === 'In Fertigung') {
      const erster = fb.arbeitsgaenge.find((a) => a.status === 'Offen');
      if (erster) erster.status = 'Läuft';
    }
    fb.status = status === 'Fertig' ? 'Fertig' : status === 'In Fertigung' ? 'In Fertigung' : 'Offen';
    auftragStatusAktualisieren(fb.auftragId);
  }

  return {
    liste, offen, bauteil, fuerAuftrag, ausAuftrag, buchen, buchungLoeschen,
    arbeitsgangHinzu, arbeitsgangWeg, arbeitsgangVerschieben, vorlageAnwenden, planAmBauteilSpeichern,
    sendungAnlegen, sendungWeg, sendungZurueck, sendungLoeschen, statusSetzen,
  };
});
