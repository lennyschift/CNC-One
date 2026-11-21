// Arbeitsplan eines Bauteils: Logik für den Arbeitsplan-Editor und die Kalkulationstabelle der Workbench
// (Vorlagen, am Bauteil speichern, Arbeitsgänge hinzufügen/verschieben, Maschinen und Sätze, Lieferantenanfragen,
// Rüsten und je Stück als Zeit × Satz oder direkt in Euro).
// props: { arbeitsgaenge, kundeId, teilenummer, teil?, teilInfo? }
import { ref, computed, onMounted, watch } from 'vue';
import { repo } from '../data/repo.js';
import { leererArbeitsgang, maschinenFuer } from './fertigung.js';
import { preisFuerMenge } from './anfrage.js';
import { uid } from './format.js';
import { agRuest, agStueck } from './calc.js';
import { useStamm } from '../stores/stamm.js';
import { useAnfragen } from '../stores/anfragen.js';
import { useUi } from '../stores/ui.js';

export function useArbeitsplan(props) {
  const stamm = useStamm();
  const anfragen = useAnfragen();
  const ui = useUi();

  const maschinen = ref([]);
  const lieferanten = ref([]);
  onMounted(async () => { [maschinen.value, lieferanten.value] = await Promise.all([repo.maschinen.liste(), repo.lieferanten.liste()]); });

  const vorlagen = computed(() => stamm.vorlagenFuer(props.kundeId));
  const gespeichert = computed(() => stamm.hatPlan(props.kundeId, props.teilenummer));
  const schluesselOk = computed(() => !!stamm.teilKey(props.kundeId, props.teilenummer));

  // Hat das Bauteil schon einen gespeicherten Plan und der aktuelle ist leer, wird er übernommen.
  function ausBauteilLaden(still = false) {
    const p = stamm.planFuer(props.kundeId, props.teilenummer);
    if (!p) return;
    props.arbeitsgaenge.splice(0, props.arbeitsgaenge.length, ...p);
    if (!still) ui.toast(`Arbeitsplan vom Bauteil geladen (${p.length} Arbeitsgänge)`, 'ok');
  }
  watch(() => [props.kundeId, props.teilenummer], () => {
    if (!props.arbeitsgaenge.length && gespeichert.value) {
      ausBauteilLaden(true);
      ui.toast('Arbeitsplan vom Bauteil übernommen', 'ok');
    }
  }, { immediate: true });

  async function bauteilSpeichern() {
    const info = props.teil ?? props.teilInfo ?? {};
    if (await stamm.planSpeichern(props.kundeId, props.teilenummer, props.arbeitsgaenge, info)) ui.toast('Arbeitsplan am Bauteil gespeichert', 'ok');
  }

  function serienArbeitsgang() { props.arbeitsgaenge.push({ ...leererArbeitsgang('intern', uid), name: stamm.serienart }); }
  // Neuer Arbeitsgang einer Arbeitsgangart; intern/extern nach dem Standard der Art
  function hinzu(name, el) {
    if (el) el.value = '';
    const art = stamm.arten.find((a) => a.name === name);
    if (!art) return;
    props.arbeitsgaenge.push(leererArbeitsgang(art.typ, uid, art.name));
  }
  function typSetzen(ag, typ) { ag.typ = typ; }
  function weg(i) { props.arbeitsgaenge.splice(i, 1); }
  function schieben(i, d) {
    const j = i + d;
    if (j < 0 || j >= props.arbeitsgaenge.length) return;
    const [a] = props.arbeitsgaenge.splice(i, 1);
    props.arbeitsgaenge.splice(j, 0, a);
  }
  function vorlageAnwenden(id, el) {
    if (!id) return;
    const kopie = stamm.vorlageKopie(id);
    props.arbeitsgaenge.push(...kopie);
    if (el) el.value = '';
    ui.toast(`${kopie.length} Arbeitsgänge aus der Vorlage hinzugefügt`, 'ok');
  }
  function maschineWechsel(ag, name) {
    ag.maschine = name;
    const m = maschinen.value.find((x) => x.name === name);
    if (m) ag.satz = m.satz;
  }
  const arten = (typ) => stamm.arten.filter((a) => a.typ === typ);
  // Maschinen, die den Arbeitsgang können; eine schon gewählte bleibt sichtbar
  const maschinenFuerAg = (ag) => {
    const l = maschinenFuer(maschinen.value, ag.name);
    return ag.maschine && !l.some((m) => m.name === ag.maschine) ? [...l, { name: ag.maschine, satz: ag.satz }] : l;
  };
  const unbekannteArt = (ag) => !!ag.name && !stamm.arten.some((a) => a.name === ag.name);

  function anfragenZu(ag) { return anfragen.fuerArbeitsgang(ag.id); }
  function preisUebernehmen(ag, a) {
    const pos = a.positionen.find((x) => x.agId === ag.id);
    const menge = props.teil ? (props.teil.staffel?.aktiv && props.teil.staffel.stufen.length ? Math.min(...props.teil.staffel.stufen.map((s) => Number(s.menge) || Infinity)) : props.teil.menge) : pos?.mengen[0];
    const p = preisFuerMenge(a.antwort, menge, pos?.key);
    if (!p) return;
    ag.fremdProStk = p.proStk;
    ag.fremdEinmal = p.einmalig;
    ag.lieferant = a.lieferantName;
    ag.anfrageId = a.id;
    ui.toast(`Preis aus ${a.id} übernommen (${p.menge} Stk)`, 'ok');
  }
  const farbe = { Gesendet: 'text-warn', 'Angebot erhalten': 'text-ok', Abgesagt: 'text-mute' };

  // Rüsten und je Stück: wahlweise Zeit × Satz oder direkt in Euro. Beim Umschalten wird der Betrag übernommen,
  // damit sich die Kalkulation nicht ändert (Zeit aus Euro nur, wenn ein Satz da ist).
  const SPALTEN = [
    { art: 'ruest', label: 'Rüsten', zeit: 'ruestMin', euro: 'ruestEuro', direkt: 'ruestDirekt', schritt: 5, kosten: agRuest, einheit: '' },
    { art: 'stueck', label: 'Je Stück', zeit: 'stueckMin', euro: 'stueckEuro', direkt: 'stueckDirekt', schritt: 0.5, kosten: agStueck, einheit: ' / Stk' },
  ];
  function umschalten(ag, sp, direkt) {
    if (!!ag[sp.direkt] === direkt) return;
    const betrag = sp.kosten(ag);
    if (direkt) ag[sp.euro] = Math.round(betrag * 100) / 100;
    else if (Number(ag.satz) > 0) ag[sp.zeit] = Math.round((betrag / Number(ag.satz)) * 60 * 100) / 100;
    ag[sp.direkt] = direkt;
  }
  const zeitNoetig = (ag) => !ag.ruestDirekt || !ag.stueckDirekt;
  const summe = computed(() => props.arbeitsgaenge.filter((a) => a.typ === 'intern').reduce((s, a) => ({ ruest: s.ruest + agRuest(a), stueck: s.stueck + agStueck(a) }), { ruest: 0, stueck: 0 }));
  const fremdSumme = computed(() => props.arbeitsgaenge.filter((a) => a.typ === 'fremd').reduce((s, a) => ({ ruest: s.ruest + (Number(a.fremdEinmal) || 0), stueck: s.stueck + (Number(a.fremdProStk) || 0) }), { ruest: 0, stueck: 0 }));
  return { stamm, anfragen, ui, maschinen, lieferanten, vorlagen, gespeichert, schluesselOk, ausBauteilLaden, bauteilSpeichern, serienArbeitsgang, hinzu, typSetzen, maschinenFuerAg, unbekannteArt, weg, schieben, vorlageAnwenden, maschineWechsel, arten, anfragenZu, preisUebernehmen, farbe, SPALTEN, umschalten, zeitNoetig, summe, fremdSumme };
}
