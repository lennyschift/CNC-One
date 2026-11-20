<script setup>
// 3D-Ansicht eines STEP-Modells: drehen (linke Maustaste), verschieben (rechte), zoomen (Rad), feste Ansichten, Kanten,
// Vollbild und „aktuelle Ansicht als Vorschaubild“. Werkzeuge: Kante oder Fläche anklicken (Länge, Radius, Durchmesser,
// Bohrung oder Welle), Abstand messen mit Fangpunkten (Endpunkt, Kantenmitte, Kreismitte, Achse, Ebene), Rohteil als Quader
// oder Rundmaterial mit Aufmaß und Gewicht, Schnitt entlang einer Achse und Röntgenansicht. Three.js wird nur bei Bedarf geladen.
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { useEventListener, useResizeObserver } from '@vueuse/core';
import { Maximize2, Minimize2, Scan, ImagePlus, Loader, AlertTriangle, Spline, Download, Ruler, Box, Scissors, ScanEye, MousePointerClick, X, Check, MonitorUp, RotateCw, Crosshair, ArrowDownToLine } from '@lucide/vue';
import { stepNetze } from '../lib/step.js';
import { ANSICHTEN, modellGruppe, abmessungen, kameraAusrichten, lichter, flaecheHervorheben, rohteilLinien } from '../lib/modell3d.js';
import { cadKanten, kanteAmStrahl, fangpunkt, flaechenpunkt, messen } from '../lib/kanten.js';
import { volumenUndFlaeche, rohteile, rundmaterial, quader, flaecheAnalysieren, flaecheZuDreieck, gewichtKg, ACHSEN, drehteilErkennen, drehrohteil, achseZuFlaeche } from '../lib/messen.js';
import { zahl } from '../lib/format.js';

const props = defineProps({
  url: { type: String, required: true },
  name: { type: String, default: '' },
  dichte: { type: Number, default: 0 }, // kg/dm³ des gewählten Rohmaterials (0 = unbekannt)
  dichteGeschaetzt: { type: Boolean, default: false }, // Richtwert, am Rohmaterial ist keine Dichte gepflegt
  aufmass: { type: Number, default: 0 }, // mm je Seite für das Rohteil
  nurAnsehen: { type: Boolean, default: false }, // z. B. in der Fertigung: nichts ans Bauteil übernehmen
  fensterKnopf: { type: Boolean, default: false }, // Knopf für das eigene Fenster (zweiter Bildschirm), meldet 'fenster'
});
const emit = defineEmits(['geladen', 'vorschau', 'gewicht', 'rohteil', 'vorschlag', 'update:aufmass', 'fenster']);

const huelle = ref(null);
const stand = ref('laedt'); // 'laedt' | 'bereit' | 'fehler'
const fehler = ref('');
const masse = ref(null);
const kantenAn = ref(true);
const ansicht = ref('iso');
const vollbild = ref(false);

// Werkzeuge
const werkzeug = ref('flaeche'); // 'flaeche' (anklicken zeigt Maß) | 'messen' (zwei Fangpunkte)
const flaechenInfo = ref(null); // Analyse der angeklickten Fläche
const kantenInfo = ref(null); // angeklickte CAD-Kante (Gerade, Kreis, Bogen, Kurve)
const messung = ref([]); // bis zu zwei Fangpunkte { punkt, art, kante?, analyse?, normale?, achse? }
const rohteilAn = ref(!props.nurAnsehen); // in der Workbench gleich an, ausblenden per Knopf
const rohteilWahl = ref(''); // '' = Vorschlag | 'Quader' | 'X' | 'Y' | 'Z' | 'Drehen'
// Drehfrästeil: erkannte Hauptdrehachse oder eine per Klick auf einen Durchmesser gewählte Referenzachse
const dreh = ref(null); // { istDrehteil, anteil, haupt, achsen }
const drehAchse = ref(null); // gewählte Achse (Gruppe gleichachsiger Zylinder)
const drehReferenz = ref(false); // true: Achse kommt aus einer angeklickten Fläche
const drehDurchmesser = ref('huelle'); // 'huelle' (alles, was absteht) | 'drehen' (größter Drehdurchmesser)
const achseWaehlen = ref(false); // nächster Klick auf eine runde Fläche legt die Drehachse fest
const hinweis = ref('');
const schnitt = ref({ an: false, achse: 'X', anteil: 0.5, umgekehrt: false });
const roentgen = ref(false);
const kennwerte = ref(null); // { volumen, flaeche }

let renderer = null;
let renderer2d = null;
let szene = null;
let kamera = null;
let steuerung = null;
let modell = null;
let netzeAktuell = [];
let beobachter = null;
let aktiv = true;
let hervorhebung = null;
let rohteilObjekt = null;
let messObjekte = [];
let hoverObjekte = [];
let kantenObjekt = null;
let kantenListe = null; // CAD-Kanten des geladenen Modells (einmal berechnet)
const schnittEbene = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);
const raycaster = new THREE.Raycaster();

const zeichnen = () => {
  if (!renderer) return;
  renderer.render(szene, kamera);
  renderer2d.render(szene, kamera);
};

function groesseAnpassen() {
  const el = huelle.value;
  if (!el || !renderer) return;
  const w = Math.max(el.clientWidth, 1);
  const h = Math.max(el.clientHeight, 1);
  renderer.setSize(w, h, false);
  renderer2d.setSize(w, h);
  kamera.aspect = w / h;
  kamera.updateProjectionMatrix();
  zeichnen();
}

function zeigen(name) {
  if (!modell) return;
  ansicht.value = name;
  kameraAusrichten(kamera, steuerung.target, modell.gruppe, ANSICHTEN[name].richtung);
  steuerung.update();
  zeichnen();
}

function entfernen(obj) {
  if (!obj) return;
  obj.parent?.remove(obj);
  obj.userData.entsorgen?.();
  obj.traverse?.((o) => { if (o.element) o.element.remove(); });
}

function modellEntfernen() {
  if (!modell) return;
  [hervorhebung, rohteilObjekt, kantenObjekt, ...messObjekte, ...hoverObjekte].forEach(entfernen);
  hervorhebung = null;
  rohteilObjekt = null;
  kantenObjekt = null;
  messObjekte = [];
  hoverObjekte = [];
  hoverSchluessel = '';
  kantenListe = null;
  szene.remove(modell.gruppe);
  modell.entsorgen();
  modell = null;
}

async function laden() {
  stand.value = 'laedt';
  fehler.value = '';
  masse.value = null;
  flaechenInfo.value = null;
  kantenInfo.value = null;
  messung.value = [];
  dreh.value = null;
  drehAchse.value = null;
  drehReferenz.value = false;
  achseWaehlen.value = false;
  modellEntfernen();
  zeichnen();
  const url = props.url;
  try {
    const netze = await stepNetze(url);
    if (!aktiv || url !== props.url) return;
    netzeAktuell = netze;
    modell = modellGruppe(netze);
    modell.kanten.visible = kantenAn.value;
    szene.add(modell.gruppe);
    masse.value = abmessungen(netze);
    kennwerte.value = volumenUndFlaeche(netze);
    try { dreh.value = drehteilErkennen(netze); } catch { dreh.value = null; }
    drehAchse.value = dreh.value?.haupt ?? null;
    stand.value = 'bereit';
    await nextTick();
    groesseAnpassen();
    zeigen('iso');
    darstellungAnwenden();
    emit('geladen', netze);
    // Kanten im Leerlauf vorbereiten, damit das erste Fangen nicht stockt
    (window.requestIdleCallback ?? setTimeout)(() => { if (modell && netzeAktuell === netze) kantenHolen(); });
  } catch (e) {
    if (!aktiv) return;
    stand.value = 'fehler';
    fehler.value = e.message;
  }
}

function alsVorschau() {
  if (!modell) return;
  zeichnen();
  renderer.domElement.toBlob((blob) => blob && emit('vorschau', blob), 'image/png');
}

// ---- Kanten, Flächen und Fangpunkte unter dem Mauszeiger
function kantenHolen() {
  if (!kantenListe) { try { kantenListe = cadKanten(netzeAktuell); } catch { kantenListe = []; } }
  return kantenListe;
}
// Was liegt unter dem Mauszeiger? Getroffene Fläche (mit Analyse), nächste CAD-Kante und der Fangpunkt
function suchen(e) {
  const r = renderer.domElement.getBoundingClientRect();
  raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), kamera);
  const treffer = raycaster.intersectObjects(modell.netze, false).find((t) => !schnitt.value.an || schnittEbene.distanceToPoint(t.point) >= 0);
  let analyse = null;
  let klick = null;
  if (treffer) {
    const netz = netzeAktuell[treffer.object.userData.netz];
    const f = flaecheZuDreieck(netz, treffer.faceIndex);
    analyse = f >= 0 ? { ...flaecheAnalysieren(netz, f), netz } : null;
    klick = modell.gruppe.worldToLocal(treffer.point.clone()).toArray();
  }
  // Strahl in CAD-Koordinaten (die Gruppe ist nur gedreht)
  const o = modell.gruppe.worldToLocal(raycaster.ray.origin.clone()).toArray();
  const d = raycaster.ray.direction.clone().applyQuaternion(modell.gruppe.quaternion.clone().invert()).toArray();
  const proPixel = (2 * Math.tan((kamera.fov * Math.PI) / 360)) / Math.max(r.height, 1);
  const kante = schnitt.value.an || roentgen.value ? null : kanteAmStrahl(kantenHolen(), o, d, { proPixel, fangPx: 8, bisT: treffer ? treffer.distance : Infinity });
  let fang = null;
  if (kante) fang = fangpunkt(kante, 10 * proPixel * kante.t);
  else if (analyse) fang = flaechenpunkt(klick, analyse);
  return { analyse, kante, fang };
}

// ---- Klicken: Maß der Kante/Fläche zeigen bzw. Fangpunkt setzen (Ziehen zum Drehen zählt nicht als Klick)
let unten = null;
function runter(e) { unten = { x: e.clientX, y: e.clientY }; }
function hoch(e) {
  if (!unten || Math.hypot(e.clientX - unten.x, e.clientY - unten.y) > 4 || e.button !== 0 || !modell) { unten = null; return; }
  unten = null;
  const { analyse, kante, fang } = suchen(e);
  if (achseWaehlen.value) {
    if (analyse?.art !== 'Zylinder') { hinweis.value = 'Bitte einen Durchmesser anklicken (Welle, Absatz oder Bohrung).'; return; }
    drehAchseAus(analyse);
    flaechenInfo.value = analyse;
    kantenInfo.value = null;
    hervorhebungZeichnen();
    return;
  }
  if (werkzeug.value === 'messen') {
    if (!fang) return;
    messung.value = messung.value.length >= 2 ? [fang] : [...messung.value, fang];
    messungZeichnen();
  } else if (kante) {
    // Kante angeklickt: Länge, Radius oder Durchmesser
    kantenInfo.value = kante.kante;
    flaechenInfo.value = null;
    hervorhebungZeichnen();
  } else {
    flaechenInfo.value = analyse;
    kantenInfo.value = null;
    hervorhebungZeichnen();
  }
  hoverSchluessel = '';
  zeichnen();
}

// Beim Überfahren: Kante hervorheben und beim Messen den Fangpunkt zeigen
let hoverPlan = 0;
function bewegen(e) {
  if (e.buttons || !modell || stand.value !== 'bereit') return;
  cancelAnimationFrame(hoverPlan);
  hoverPlan = requestAnimationFrame(() => {
    if (!modell) return;
    const { kante, fang } = suchen(e);
    hoverZeichnen(kante?.kante ?? null, werkzeug.value === 'messen' ? fang : null);
  });
}
function mausWeg() {
  cancelAnimationFrame(hoverPlan);
  hoverZeichnen(null, null);
}
let hoverSchluessel = '';
function hoverZeichnen(kante, fang) {
  const schluessel = `${kante && kantenListe ? kantenListe.indexOf(kante) : -1}|${fang ? fang.art + fang.punkt.map((v) => v.toFixed(3)).join(',') : ''}`;
  if (schluessel === hoverSchluessel) return;
  hoverSchluessel = schluessel;
  hoverObjekte.forEach(entfernen);
  hoverObjekte = [];
  if (!modell) return;
  if (kante && kante !== kantenInfo.value) hoverObjekte.push(linieZeichnen(kante.punkte, 0xf59e0b));
  if (fang) {
    hoverObjekte.push(kugelZeichnen(fang.punkt, 0xf59e0b, 0.011));
    const l = beschriftung(fangText(fang), fang.punkt);
    l.element.classList.add('fang');
    modell.gruppe.add(l);
    hoverObjekte.push(l);
  }
  zeichnen();
}

function modellRadius() {
  return masse.value ? Math.hypot(masse.value.x, masse.value.y, masse.value.z) / 2 : 50;
}
function linieZeichnen(punkte, farbe) {
  const geo = new THREE.BufferGeometry().setFromPoints(punkte.map((p) => new THREE.Vector3(...p)));
  const mat = new THREE.LineBasicMaterial({ color: farbe, depthTest: false, transparent: true });
  const linie = new THREE.Line(geo, mat);
  linie.renderOrder = 11;
  linie.userData.entsorgen = () => { geo.dispose(); mat.dispose(); };
  modell.gruppe.add(linie);
  return linie;
}
function kugelZeichnen(p, farbe, groesse = 0.012) {
  const kugel = new THREE.Mesh(new THREE.SphereGeometry(modellRadius() * groesse, 16, 12), new THREE.MeshBasicMaterial({ color: farbe, depthTest: false }));
  kugel.position.set(...p);
  kugel.renderOrder = 12;
  kugel.userData.entsorgen = () => { kugel.geometry.dispose(); kugel.material.dispose(); };
  modell.gruppe.add(kugel);
  return kugel;
}

function hervorhebungZeichnen() {
  entfernen(hervorhebung);
  hervorhebung = null;
  entfernen(kantenObjekt);
  kantenObjekt = null;
  if (kantenInfo.value && modell) kantenObjekt = linieZeichnen(kantenInfo.value.punkte, 0xd4242a);
  const a = flaechenInfo.value;
  if (a && modell) {
    hervorhebung = flaecheHervorheben(a.netz, a.dreiecke);
    modell.gruppe.add(hervorhebung);
  }
  zeichnen();
}

function beschriftung(text, ort) {
  const div = document.createElement('div');
  div.className = 'mess-beschriftung';
  div.textContent = text;
  const obj = new CSS2DObject(div);
  obj.position.set(...ort);
  return obj;
}

function messungZeichnen() {
  messObjekte.forEach(entfernen);
  messObjekte = [];
  if (!modell) return;
  for (const m of messung.value) {
    messObjekte.push(kugelZeichnen(m.punkt, 0x2563eb));
    if (m.kante) messObjekte.push(linieZeichnen(m.kante.punkte, 0x2563eb));
  }
  const e = messErgebnis.value;
  if (e) {
    const linie = linieZeichnen([e.von, e.bis], 0x2563eb);
    linie.add(beschriftung(`${mm(e.gesamt)} mm`, e.von.map((v, i) => (v + e.bis[i]) / 2)));
    messObjekte.push(linie);
    // Fußpunkt bei senkrechter Messung
    for (const p of [e.von, e.bis]) if (!messung.value.some((m) => m.punkt.every((v, i) => Math.abs(v - p[i]) < 1e-6))) messObjekte.push(kugelZeichnen(p, 0x2563eb, 0.007));
  }
  zeichnen();
}
const messErgebnis = computed(() => (messung.value.length === 2 ? messen(messung.value[0], messung.value[1]) : null));
// Beschreibung eines Fangpunkts mit dem Maß seines Elements
function fangText(f) {
  const k = f.kante;
  if (f.art === 'Kreismitte') return `Kreismitte ⌀${mm(2 * k.radius)}`;
  if (f.art === 'Bogenmitte') return `Mitte R${mm(k.radius)}`;
  if (k) return k.art === 'Gerade' ? `${f.art} · Kante ${mm(k.laenge)}` : f.art;
  if (f.analyse?.art === 'Zylinder') return f.analyse.rundung ? `Mitte R${mm(f.analyse.radius)}` : `${f.art} ⌀${mm(f.analyse.durchmesser)}`;
  return f.art === 'Fläche' && f.normale ? 'Ebene Fläche' : f.art;
}

// ---- Rohteil
// Aufmaß auch ohne v-model änderbar (nur zum Ansehen)
const aufmassWert = ref(props.aufmass);
watch(() => props.aufmass, (v) => { aufmassWert.value = v; });
const rohteilListe = computed(() => (kennwerte.value ? rohteile(netzeAktuell, aufmassWert.value) : null));
const rohteil = computed(() => {
  if (!rohteilListe.value) return null;
  const w = rohteilWahl.value;
  if (w === 'Quader') return quader(netzeAktuell, aufmassWert.value);
  if (ACHSEN[w]) return { ...rundmaterial(netzeAktuell, ACHSEN[w], aufmassWert.value), achsName: w };
  if (w === 'Drehen' || (w === '' && dreh.value?.istDrehteil)) return drehRohteil.value ?? rohteilListe.value.vorschlag;
  return rohteilListe.value.vorschlag;
});
// Drehfräs-Rohteil mittig auf der Drehachse; Durchmesser als Hülle oder als größter Drehdurchmesser
const drehRohteil = computed(() => {
  const g = drehAchse.value;
  if (!g || !kennwerte.value) return null;
  const d = drehDurchmesser.value === 'drehen' && g.aussenDurchmesser ? g.aussenDurchmesser : null;
  return drehrohteil(netzeAktuell, g.achse, g.punkt, { aufmass: aufmassWert.value, durchmesser: d });
});
const huelleDurchmesser = computed(() => (drehRohteil.value ? drehRohteil.value.huelle - 2 * aufmassWert.value : 0));
const huelleGroesser = computed(() => !!drehAchse.value?.aussenDurchmesser && huelleDurchmesser.value > drehAchse.value.aussenDurchmesser + 0.05);
const istDrehen = computed(() => rohteilWahl.value === 'Drehen' || (rohteilWahl.value === '' && !!dreh.value?.istDrehteil));
function drehAchseAus(analyse) {
  drehAchse.value = achseZuFlaeche(dreh.value?.achsen ?? [], analyse);
  drehReferenz.value = true;
  achseWaehlen.value = false;
  hinweis.value = '';
  rohteilWahl.value = 'Drehen';
  rohteilAn.value = true;
}
function automatischeAchse() {
  drehAchse.value = dreh.value?.haupt ?? null;
  drehReferenz.value = false;
  achseWaehlen.value = false;
  hinweis.value = '';
}
function achseWaehlenUm() {
  achseWaehlen.value = !achseWaehlen.value;
  hinweis.value = '';
}
// Rohteil ans Bauteil: Form, Maße (auf 0,1 mm) und Gewicht
function rohteilDaten() {
  const r = rohteil.value;
  if (!r) return null;
  const rund = (v) => Math.round(v * 100) / 100;
  const gewicht = Math.round(rohGewicht.value * 1000) / 1000;
  return r.art === 'Quader'
    ? { form: 'Flach', x: rund(r.x), y: rund(r.y), z: rund(r.z), gewicht, aufmass: aufmassWert.value }
    : { form: 'Rund', durchmesser: rund(r.durchmesser), laenge: rund(r.laenge), drehteil: !!r.drehteil, gewicht, aufmass: aufmassWert.value };
}
function rohteilUebernehmen() {
  const d = rohteilDaten();
  if (d) emit('rohteil', d);
}
// Das aktuelle Rohteil laufend als Vorschlag melden (die Workbench zeigt ihn beim Rohmaterial an)
watch(rohteil, () => { const d = rohteilDaten(); if (d && !props.nurAnsehen) emit('vorschlag', d); });
const rohteilText = (r) => (r.art === 'Quader' ? `Quader ${mm(r.x)} × ${mm(r.y)} × ${mm(r.z)}` : `Rund ⌀${mm(r.durchmesser)} × ${mm(r.laenge)}`);
const fertigGewicht = computed(() => (kennwerte.value && props.dichte ? gewichtKg(kennwerte.value.volumen, props.dichte) : 0));
// Das Rohteil steht als Leiste unter dem Modell (nicht darüber): das Modell rückt um ihre Höhe nach oben
const leiste = ref(null);
const leisteHoehe = ref(0);
useResizeObserver(leiste, (e) => { leisteHoehe.value = Math.ceil(e[0]?.borderBoxSize?.[0]?.blockSize ?? e[0]?.contentRect.height ?? 0); });
watch(() => rohteilAn.value && !!rohteil.value, (an) => { if (!an) leisteHoehe.value = 0; });
const rohGewicht = computed(() => (rohteil.value && props.dichte ? gewichtKg(rohteil.value.volumen, props.dichte) : 0));

function rohteilZeichnen() {
  entfernen(rohteilObjekt);
  rohteilObjekt = null;
  if (rohteilAn.value && rohteil.value && modell) {
    rohteilObjekt = rohteilLinien(rohteil.value);
    // Drehachse als rote Strichlinie, etwas länger als das Rohteil
    if (rohteil.value.drehteil) {
      const r = rohteil.value;
      const a = new THREE.Vector3(...r.achse);
      const m = new THREE.Vector3(...r.mitte);
      const h = r.laenge * 0.62;
      const geo = new THREE.BufferGeometry().setFromPoints([m.clone().addScaledVector(a, -h), m.clone().addScaledVector(a, h)]);
      const mat = new THREE.LineDashedMaterial({ color: 0xd4242a, dashSize: 6, gapSize: 2, depthTest: false });
      const linie = new THREE.Line(geo, mat);
      linie.computeLineDistances();
      linie.renderOrder = 9;
      const alt = rohteilObjekt.userData.entsorgen;
      rohteilObjekt.userData.entsorgen = () => { alt?.(); geo.dispose(); mat.dispose(); };
      rohteilObjekt.add(linie);
    }
    modell.gruppe.add(rohteilObjekt);
  }
  zeichnen();
}
function achseAusFlaeche() {
  if (flaechenInfo.value?.art !== 'Zylinder') return;
  drehAchseAus(flaechenInfo.value);
}
const aufmassText = computed({
  get: () => String(aufmassWert.value ?? 0).replace('.', ','),
  set: (v) => { aufmassWert.value = Math.max(0, Number(String(v).replace(',', '.')) || 0); emit('update:aufmass', aufmassWert.value); },
});

// ---- Schnitt und Röntgen
function darstellungAnwenden() {
  if (!modell) return;
  const s = schnitt.value;
  if (s.an) {
    const box = new THREE.Box3();
    for (const n of netzeAktuell) for (let i = 0; i < n.position.length; i += 3) box.expandByPoint(new THREE.Vector3(n.position[i], n.position[i + 1], n.position[i + 2]));
    const k = { X: 0, Y: 1, Z: 2 }[s.achse];
    const lo = box.min.getComponent(k);
    const hi = box.max.getComponent(k);
    const normale = new THREE.Vector3().setComponent(k, s.umgekehrt ? 1 : -1);
    const lage = lo + (hi - lo) * s.anteil;
    // Ebene in CAD-Koordinaten, dann in Welt-Koordinaten (das Modell ist gedreht)
    schnittEbene.set(normale, s.umgekehrt ? -lage : lage).applyMatrix4(modell.gruppe.matrixWorld);
  }
  const ebenen = s.an ? [schnittEbene] : [];
  modell.netze.forEach((m, i) => {
    m.material.clippingPlanes = ebenen;
    m.material.side = s.an ? THREE.FrontSide : THREE.DoubleSide;
    m.material.transparent = roentgen.value;
    m.material.opacity = roentgen.value ? 0.16 : 1;
    m.material.depthWrite = !roentgen.value;
    m.material.needsUpdate = true;
    const r = modell.rueckseiten[i];
    r.visible = s.an && !roentgen.value;
    r.material.clippingPlanes = ebenen;
  });
  modell.kanten.children.forEach((k) => { k.material.clippingPlanes = ebenen; k.material.opacity = roentgen.value ? 0.9 : 0.55; });
  if (hervorhebung) hervorhebung.material.clippingPlanes = ebenen;
  zeichnen();
}

onMounted(() => {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.localClippingEnabled = true;
  renderer.domElement.className = 'block h-full w-full';
  huelle.value.appendChild(renderer.domElement);
  renderer2d = new CSS2DRenderer();
  renderer2d.domElement.className = 'pointer-events-none absolute inset-0';
  huelle.value.appendChild(renderer2d.domElement);
  szene = new THREE.Scene();
  lichter(szene);
  kamera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
  steuerung = new OrbitControls(kamera, renderer.domElement);
  steuerung.addEventListener('change', zeichnen);
  renderer.domElement.addEventListener('pointerdown', runter);
  renderer.domElement.addEventListener('pointerup', hoch);
  renderer.domElement.addEventListener('pointermove', bewegen);
  renderer.domElement.addEventListener('pointerleave', mausWeg);
  beobachter = new ResizeObserver(groesseAnpassen);
  beobachter.observe(huelle.value);
  laden();
});

onBeforeUnmount(() => {
  aktiv = false;
  cancelAnimationFrame(hoverPlan);
  beobachter?.disconnect();
  steuerung?.dispose();
  modellEntfernen();
  renderer?.dispose();
  renderer?.forceContextLoss();
  renderer = null;
});

watch(() => props.url, laden);
watch(kantenAn, (an) => { if (modell) { modell.kanten.visible = an; zeichnen(); } });
watch(vollbild, () => nextTick(groesseAnpassen));
watch([rohteilAn, rohteil], rohteilZeichnen);
watch([schnitt, roentgen], darstellungAnwenden, { deep: true });
watch(werkzeug, () => { messung.value = []; flaechenInfo.value = null; kantenInfo.value = null; hoverZeichnen(null, null); messungZeichnen(); hervorhebungZeichnen(); });
useEventListener(window, 'keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (achseWaehlen.value) { achseWaehlen.value = false; hinweis.value = ''; } else if (vollbild.value) vollbild.value = false;
  else if (messung.value.length || flaechenInfo.value || kantenInfo.value) { messung.value = []; flaechenInfo.value = null; kantenInfo.value = null; messungZeichnen(); hervorhebungZeichnen(); }
});

const mm = (v) => zahl(v, v < 10 ? 2 : 1);
const kg = (v) => `${zahl(v, v < 1 ? 3 : 2)} kg`;
const cm3 = (v) => `${zahl(v / 1000, 1)} cm³`;
</script>

<template>
  <div class="h-full">
    <Teleport to="body" :disabled="!vollbild">
      <div class="modell-flaeche overflow-hidden border border-line" :class="vollbild ? 'fixed inset-3 z-50 rounded-3xl shadow-2xl' : 'relative h-full rounded-2xl'" :style="{ '--unten': `${leisteHoehe}px` }">
        <div ref="huelle" class="absolute inset-x-0 top-0" :style="{ bottom: `${leisteHoehe}px` }" :class="werkzeug === 'messen' || achseWaehlen ? 'cursor-crosshair' : ''" />

        <!-- Ansichten und Werkzeuge -->
        <div v-if="stand === 'bereit'" class="werkzeug left-3 top-3 flex-wrap">
          <button v-for="(a, k) in ANSICHTEN" :key="k" class="knopf" :class="ansicht === k ? 'aktiv' : ''" @click="zeigen(k)">{{ a.label }}</button>
          <span class="mx-0.5 w-px self-stretch bg-line" />
          <button class="knopf" :class="kantenAn ? 'aktiv' : ''" title="Kanten ein-/ausblenden" @click="kantenAn = !kantenAn"><Spline :size="15" /></button>
          <button class="knopf" title="Modell einpassen" @click="zeigen(ansicht)"><Scan :size="15" /></button>
          <span class="mx-0.5 w-px self-stretch bg-line" />
          <button class="knopf" :class="werkzeug === 'flaeche' ? 'aktiv' : ''" title="Anklicken zeigt das Maß: Kante (Länge, Radius, Durchmesser) oder Fläche (Bohrung, Welle, Rundung, Ebene)" @click="werkzeug = 'flaeche'"><MousePointerClick :size="15" /></button>
          <button class="knopf" :class="werkzeug === 'messen' ? 'aktiv' : ''" title="Abstand messen: fängt Endpunkte, Kantenmitten, Kreis- und Bohrungsmitten und Flächen" @click="werkzeug = 'messen'"><Ruler :size="15" /></button>
          <button class="knopf" :class="rohteilAn ? 'aktiv' : ''" title="Rohteil: Quader oder Rundmaterial mit Aufmaß und Gewicht" @click="rohteilAn = !rohteilAn"><Box :size="15" /></button>
          <button class="knopf" :class="schnitt.an ? 'aktiv' : ''" title="Schnitt: Modell entlang einer Achse aufschneiden" @click="schnitt.an = !schnitt.an"><Scissors :size="15" /></button>
          <button class="knopf" :class="roentgen ? 'aktiv' : ''" title="Röntgen: Außenhaut durchsichtig, Bohrungen und Innenkonturen sichtbar" @click="roentgen = !roentgen"><ScanEye :size="15" /></button>
        </div>
        <div class="werkzeug right-3 top-3">
          <button v-if="stand === 'bereit' && !nurAnsehen" class="knopf" title="Aktuelle Ansicht als Vorschaubild des Bauteils übernehmen" @click="alsVorschau"><ImagePlus :size="15" /></button>
          <a class="knopf" :href="url" :download="name || true" title="STEP-Datei herunterladen"><Download :size="15" /></a>
          <button v-if="fensterKnopf" class="knopf" title="Im eigenen Fenster zeigen (auf den zweiten Bildschirm ziehen)" @click="emit('fenster')"><MonitorUp :size="15" /></button>
          <button class="knopf" :title="vollbild ? 'Vollbild verlassen (Esc)' : 'Vollbild'" @click="vollbild = !vollbild"><Minimize2 v-if="vollbild" :size="15" /><Maximize2 v-else :size="15" /></button>
        </div>

        <!-- Schnitt -->
        <div v-if="stand === 'bereit' && schnitt.an" class="karte left-3 top-14 w-60">
          <div class="mb-1.5 flex items-center gap-1 text-xs font-medium"><Scissors :size="13" class="text-accent" /> Schnitt
            <span class="ml-auto flex gap-0.5"><button v-for="a in ['X', 'Y', 'Z']" :key="a" class="knopf !h-6 !min-w-6" :class="schnitt.achse === a ? 'aktiv' : ''" @click="schnitt.achse = a">{{ a }}</button></span>
          </div>
          <input v-model.number="schnitt.anteil" type="range" min="0" max="1" step="0.005" class="w-full accent-[var(--accent)]" />
          <button class="mt-1 text-[11px] text-mute hover:text-ink" @click="schnitt.umgekehrt = !schnitt.umgekehrt">Andere Seite zeigen</button>
        </div>

        <!-- Hinweis beim Wählen der Drehachse, sonst „Drehfrästeil erkannt“ -->
        <div v-if="stand === 'bereit' && (achseWaehlen || hinweis)" class="karte left-1/2 top-14 -translate-x-1/2 text-xs">
          <span class="flex items-center gap-1.5"><Crosshair :size="13" class="text-accent" /> {{ hinweis || 'Durchmesser anklicken, dessen Achse die Drehachse ist (Esc bricht ab)' }}</span>
        </div>
        <div v-else-if="stand === 'bereit' && dreh?.istDrehteil && !schnitt.an" class="drehmarke absolute left-3 top-14 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium" :title="`Gedrehte Flächen um die Hauptachse: ${Math.round(dreh.anteil * 100)} % der Oberfläche`">
          <RotateCw :size="12" /> Drehfrästeil erkannt · ⌀{{ mm(dreh.haupt.aussenDurchmesser) }}
        </div>

        <!-- Angeklickte Fläche -->
        <div v-if="flaechenInfo" class="karte unten right-3 max-w-[16rem]">
          <button class="absolute right-1.5 top-1.5 text-mute hover:text-ink" title="Schließen (Esc)" @click="flaechenInfo = null; hervorhebungZeichnen()"><X :size="13" /></button>
          <template v-if="flaechenInfo.art === 'Zylinder' && flaechenInfo.rundung">
            <div class="text-[11px] text-mute">Rundung {{ flaechenInfo.bohrung ? '(innen)' : '(außen)' }}</div>
            <div class="text-lg font-semibold tnum">R {{ zahl(flaechenInfo.radius, 2) }} mm</div>
            <div class="text-xs text-mute tnum">⌀ {{ zahl(flaechenInfo.durchmesser, 2) }} · {{ zahl(flaechenInfo.umlauf, 0) }}° · Länge {{ zahl(flaechenInfo.laenge, 2) }} mm</div>
          </template>
          <template v-else-if="flaechenInfo.art === 'Zylinder'">
            <div class="text-[11px] text-mute">{{ flaechenInfo.bohrung ? 'Bohrung' : 'Welle / Außendurchmesser' }}</div>
            <div class="text-lg font-semibold tnum">⌀ {{ zahl(flaechenInfo.durchmesser, 2) }} mm</div>
            <div class="text-xs text-mute tnum">R {{ zahl(flaechenInfo.radius, 2) }} · Länge {{ zahl(flaechenInfo.laenge, 2) }} mm</div>
            <button class="mt-1.5 inline-flex items-center gap-1 text-[11px] text-accent hover:underline" @click="achseAusFlaeche"><RotateCw :size="11" /> Als Drehachse verwenden</button>
          </template>
          <template v-else-if="flaechenInfo.art === 'Ebene'">
            <div class="text-[11px] text-mute">Ebene Fläche</div>
            <div class="text-sm font-semibold tnum">{{ zahl(flaechenInfo.flaeche / 100, 2) }} cm²</div>
          </template>
          <template v-else>
            <div class="text-[11px] text-mute">Freiform- oder Kegelfläche</div>
            <div class="text-sm font-semibold tnum">{{ zahl(flaechenInfo.flaeche / 100, 2) }} cm²</div>
          </template>
        </div>

        <!-- Angeklickte Kante: Länge, Radius oder Durchmesser -->
        <div v-if="kantenInfo" class="karte unten right-3 max-w-[16rem]">
          <button class="absolute right-1.5 top-1.5 text-mute hover:text-ink" title="Schließen (Esc)" @click="kantenInfo = null; hervorhebungZeichnen()"><X :size="13" /></button>
          <template v-if="kantenInfo.art === 'Kreis'">
            <div class="text-[11px] text-mute">Kreiskante</div>
            <div class="text-lg font-semibold tnum">⌀ {{ zahl(2 * kantenInfo.radius, 2) }} mm</div>
            <div class="text-xs text-mute tnum">R {{ zahl(kantenInfo.radius, 2) }} · Umfang {{ zahl(kantenInfo.laenge, 2) }} mm</div>
          </template>
          <template v-else-if="kantenInfo.art === 'Bogen'">
            <div class="text-[11px] text-mute">Bogen</div>
            <div class="text-lg font-semibold tnum">R {{ zahl(kantenInfo.radius, 2) }} mm</div>
            <div class="text-xs text-mute tnum">⌀ {{ zahl(2 * kantenInfo.radius, 2) }} · {{ zahl((kantenInfo.winkel * 180) / Math.PI, 1) }}° · Bogenlänge {{ zahl(kantenInfo.laenge, 2) }} mm</div>
          </template>
          <template v-else>
            <div class="text-[11px] text-mute">{{ kantenInfo.art === 'Gerade' ? 'Gerade Kante' : 'Kurve' }}</div>
            <div class="text-lg font-semibold tnum">{{ zahl(kantenInfo.laenge, 2) }} mm</div>
            <div v-if="kantenInfo.art === 'Gerade'" class="text-xs text-mute tnum">ΔX {{ mm(Math.abs(kantenInfo.ende[0] - kantenInfo.start[0])) }} · ΔY {{ mm(Math.abs(kantenInfo.ende[1] - kantenInfo.start[1])) }} · ΔZ {{ mm(Math.abs(kantenInfo.ende[2] - kantenInfo.start[2])) }}</div>
          </template>
        </div>

        <!-- Messung -->
        <div v-if="werkzeug === 'messen' && stand === 'bereit'" class="karte unten right-3 max-w-[18rem]">
          <div class="flex items-center gap-1 text-xs font-medium"><Ruler :size="13" class="text-accent" /> Abstand messen</div>
          <p v-if="!messErgebnis" class="mt-0.5 text-[11px] text-mute">{{ messung.length ? `${fangText(messung[0])} – jetzt die zweite Stelle anklicken …` : 'Fängt Endpunkte, Kantenmitten, Kreis- und Bohrungsmitten sowie Flächen. Erste Stelle anklicken.' }}</p>
          <template v-else>
            <div class="text-lg font-semibold tnum">{{ mm(messErgebnis.gesamt) }} mm</div>
            <div class="text-[11px] text-mute tnum">{{ messErgebnis.art }} · ΔX {{ mm(messErgebnis.dx) }} · ΔY {{ mm(messErgebnis.dy) }} · ΔZ {{ mm(messErgebnis.dz) }}</div>
            <div class="text-[11px] text-mute">{{ messung.map(fangText).join(' → ') }}</div>
          </template>
        </div>

        <!-- Rohteil als Leiste unter dem Modell, sonst die Abmessungen -->
        <div v-if="rohteilAn && rohteil" ref="leiste" class="rohleiste absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line px-3 py-2 text-xs">
          <span class="flex items-center gap-1 font-medium"><Box :size="13" class="text-accent" /> Rohteil<span v-if="!rohteilWahl" class="text-[10px] font-normal text-mute">(Vorschlag)</span></span>
          <span class="flex flex-wrap gap-0.5">
            <button class="knopf !h-6" :class="rohteilWahl === '' ? 'aktiv' : ''" title="Kleinstes Rohteil" @click="rohteilWahl = ''">Auto</button>
            <button class="knopf !h-6" :class="rohteilWahl === 'Quader' ? 'aktiv' : ''" @click="rohteilWahl = 'Quader'">Quader</button>
            <button v-for="a in ['X', 'Y', 'Z']" :key="a" class="knopf !h-6" :class="rohteilWahl === a ? 'aktiv' : ''" :title="`Rundmaterial, Achse ${a}`" @click="rohteilWahl = a">⌀ {{ a }}</button>
            <button v-if="drehAchse" class="knopf !h-6" :class="rohteilWahl === 'Drehen' ? 'aktiv' : ''" title="Drehfräs-Rohteil: Rundmaterial mittig auf der Drehachse" @click="rohteilWahl = 'Drehen'"><span class="flex items-center gap-1"><RotateCw :size="12" /> Drehen</span></button>
          </span>
          <!-- Drehachse: automatisch erkannt oder Referenz-Durchmesser anklicken; Durchmesser als Hülle oder Drehdurchmesser -->
          <span v-if="istDrehen && drehAchse" class="flex w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-surface2 px-2 py-1">
            <span class="text-mute">Drehachse</span>
            <span class="font-medium">{{ drehReferenz ? 'aus angeklicktem Durchmesser' : 'automatisch erkannt' }}</span>
            <button class="knopf !h-6 !text-[11px]" :class="achseWaehlen ? 'aktiv' : ''" title="Einen Durchmesser anklicken, dessen Achse als Drehachse gilt (z. B. wenn eine Fräskontur die Erkennung stört)" @click="achseWaehlenUm"><span class="flex items-center gap-1"><Crosshair :size="12" /> {{ achseWaehlen ? 'Jetzt Durchmesser anklicken …' : 'Referenz anklicken' }}</span></button>
            <button v-if="drehReferenz && dreh?.haupt" class="text-[11px] text-mute hover:text-ink hover:underline" @click="automatischeAchse">wieder automatisch</button>
            <span v-if="drehAchse.aussenDurchmesser" class="ml-auto flex gap-0.5" role="radiogroup" aria-label="Durchmesser des Rohteils">
              <button class="knopf !h-6 !text-[11px]" :class="drehDurchmesser === 'huelle' ? 'aktiv' : ''" title="Alles, was absteht (auch Fräskonturen), muss ins Rohteil" @click="drehDurchmesser = 'huelle'">Hülle ⌀{{ mm(huelleDurchmesser) }}</button>
              <button class="knopf !h-6 !text-[11px]" :class="drehDurchmesser === 'drehen' ? 'aktiv' : ''" title="Größter gedrehter Durchmesser auf dieser Achse, abstehende Fräskonturen zählen nicht" @click="drehDurchmesser = 'drehen'">Drehdurchmesser ⌀{{ mm(drehAchse.aussenDurchmesser) }}</button>
            </span>
            <span v-if="huelleGroesser && drehDurchmesser === 'huelle'" class="w-full text-[11px] text-warn">Etwas steht über den Drehdurchmesser hinaus, z. B. eine Fräskontur.</span>
          </span>
          <span class="text-sm font-semibold tnum">{{ rohteilText(rohteil) }} mm</span>
          <label class="flex items-center gap-1 text-mute">Aufmaß <input v-model.lazy="aufmassText" class="field !w-12 !px-1.5 !py-0.5 text-right text-xs" /> mm</label>
          <span class="text-mute tnum" :title="dichte && dichteGeschaetzt ? `Dichte geschätzt (${zahl(dichte, 2)} kg/dm³), bitte am Rohmaterial in den Stammdaten pflegen` : ''">
            Fertig {{ cm3(kennwerte.volumen) }}<template v-if="dichte"> · {{ kg(fertigGewicht) }}</template> · Roh {{ cm3(rohteil.volumen) }}<template v-if="dichte"> · <strong class="text-ink">{{ kg(rohGewicht) }}</strong><template v-if="dichteGeschaetzt">*</template></template>
          </span>
          <span v-if="!dichte" class="text-mute">Für das Gewicht ein Rohmaterial mit Dichte wählen.</span>
          <button v-if="!nurAnsehen" class="btn ml-auto !py-0.5 text-xs" title="Form, Maße und Gewicht ins Rohmaterial des Bauteils übernehmen" @click="rohteilUebernehmen"><ArrowDownToLine :size="13" /> Rohteil übernehmen</button>
        </div>
        <div v-else-if="masse" class="absolute bottom-3 left-3 rounded-lg bg-surface/85 px-2.5 py-1 text-xs shadow-sm backdrop-blur tnum" title="Größe des umschließenden Quaders (X × Y × Z)">
          {{ mm(masse.x) }} × {{ mm(masse.y) }} × {{ mm(masse.z) }} mm
        </div>

        <div v-if="stand === 'laedt'" class="absolute inset-0 grid place-items-center">
          <div class="flex items-center gap-2 rounded-xl bg-surface/85 px-3.5 py-2 text-sm text-mute shadow-sm backdrop-blur"><Loader :size="15" class="animate-spin" /> 3D-Modell wird gelesen …</div>
        </div>
        <div v-else-if="stand === 'fehler'" class="absolute inset-0 grid place-items-center p-6 text-center">
          <div><AlertTriangle :size="22" class="mx-auto text-accent" /><p class="mt-2 text-sm">{{ fehler }}</p></div>
        </div>
      </div>
    </Teleport>
    <div v-if="vollbild" class="grid h-full place-items-center rounded-2xl border border-dashed border-line text-xs text-mute">Im Vollbild geöffnet</div>
  </div>
</template>

<style scoped>
.modell-flaeche { background: radial-gradient(ellipse at 30% 15%, var(--surface), var(--surface-2) 70%); }
.werkzeug { position: absolute; display: flex; gap: 0.15rem; border-radius: 0.8rem; padding: 0.2rem; background: color-mix(in srgb, var(--surface) 85%, transparent); box-shadow: 0 1px 3px rgb(0 0 0 / 0.08); backdrop-filter: blur(6px); }
.left-3.werkzeug { max-width: calc(100% - 9rem); }
.karte.unten { bottom: calc(var(--unten, 0px) + 0.75rem); }
.rohleiste { background: color-mix(in srgb, var(--surface) 96%, transparent); backdrop-filter: blur(6px); }
.karte { position: absolute; border-radius: 0.8rem; padding: 0.55rem 0.7rem; background: color-mix(in srgb, var(--surface) 92%, transparent); box-shadow: 0 2px 8px rgb(0 0 0 / 0.1); backdrop-filter: blur(6px); }
.knopf { display: grid; place-items: center; height: 1.85rem; min-width: 1.85rem; padding: 0 0.5rem; border-radius: 0.6rem; font-size: 0.72rem; color: var(--mute); }
.knopf:hover { background: var(--surface-2); color: var(--ink); }
.knopf.aktiv { background: var(--accent-soft); color: var(--accent); }
.drehmarke { color: var(--ok); background: color-mix(in srgb, var(--ok) 14%, var(--surface)); }
:deep(.mess-beschriftung) { padding: 0.1rem 0.4rem; border-radius: 0.4rem; background: #2563eb; color: #fff; font-size: 0.72rem; font-variant-numeric: tabular-nums; white-space: nowrap; }
:deep(.mess-beschriftung.fang) { background: #f59e0b; color: #1f2933; margin: -1.4rem 0 0 1.6rem; }
</style>
