<script setup>
// 3D-Ansicht eines STEP-Modells: drehen (linke Maustaste), verschieben (rechte), zoomen (Rad), feste Ansichten, Kanten,
// Vollbild und „aktuelle Ansicht als Vorschaubild“. Werkzeuge: Fläche anklicken (Ebene oder Zylinder mit Durchmesser,
// Bohrung oder Welle), Abstand messen (auf Zylindern zur Achse, z. B. Bohrungsmitte zu Bohrungsmitte), Rohteil als Quader
// oder Rundmaterial mit Aufmaß und Gewicht, Schnitt entlang einer Achse und Röntgenansicht. Three.js wird nur bei Bedarf geladen.
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { useEventListener } from '@vueuse/core';
import { Maximize2, Minimize2, Scan, ImagePlus, Loader, AlertTriangle, Spline, Download, Ruler, Box, Scissors, ScanEye, MousePointerClick, X, Check } from '@lucide/vue';
import { stepNetze } from '../lib/step.js';
import { ANSICHTEN, modellGruppe, abmessungen, kameraAusrichten, lichter, flaecheHervorheben, rohteilLinien } from '../lib/modell3d.js';
import { volumenUndFlaeche, rohteile, rundmaterial, quader, flaecheAnalysieren, flaecheZuDreieck, messpunkt, abstand, gewichtKg, ACHSEN } from '../lib/messen.js';
import { zahl } from '../lib/format.js';

const props = defineProps({
  url: { type: String, required: true },
  name: { type: String, default: '' },
  dichte: { type: Number, default: 0 }, // kg/dm³ des gewählten Rohmaterials (0 = unbekannt)
  dichteGeschaetzt: { type: Boolean, default: false }, // Richtwert, am Rohmaterial ist keine Dichte gepflegt
  aufmass: { type: Number, default: 0 }, // mm je Seite für das Rohteil
  nurAnsehen: { type: Boolean, default: false }, // z. B. in der Fertigung: nichts ans Bauteil übernehmen
});
const emit = defineEmits(['geladen', 'vorschau', 'gewicht', 'update:aufmass']);

const huelle = ref(null);
const stand = ref('laedt'); // 'laedt' | 'bereit' | 'fehler'
const fehler = ref('');
const masse = ref(null);
const kantenAn = ref(true);
const ansicht = ref('iso');
const vollbild = ref(false);

// Werkzeuge
const werkzeug = ref('flaeche'); // 'flaeche' (anklicken zeigt Maß) | 'messen' (zwei Punkte)
const flaechenInfo = ref(null); // Analyse der angeklickten Fläche
const messung = ref([]); // bis zu zwei Messpunkte { punkt, art }
const rohteilAn = ref(false);
const rohteilWahl = ref(''); // '' = Vorschlag | 'Quader' | 'X' | 'Y' | 'Z' | 'Fläche'
const eigeneAchse = ref(null); // Achse aus einer angeklickten Zylinderfläche
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
  [hervorhebung, rohteilObjekt, ...messObjekte].forEach(entfernen);
  hervorhebung = null;
  rohteilObjekt = null;
  messObjekte = [];
  szene.remove(modell.gruppe);
  modell.entsorgen();
  modell = null;
}

async function laden() {
  stand.value = 'laedt';
  fehler.value = '';
  masse.value = null;
  flaechenInfo.value = null;
  messung.value = [];
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
    stand.value = 'bereit';
    await nextTick();
    groesseAnpassen();
    zeigen('iso');
    darstellungAnwenden();
    emit('geladen', netze);
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

// ---- Klicken: Fläche erkennen bzw. Messpunkt setzen (Ziehen zum Drehen zählt nicht als Klick)
let unten = null;
function runter(e) { unten = { x: e.clientX, y: e.clientY }; }
function hoch(e) {
  if (!unten || Math.hypot(e.clientX - unten.x, e.clientY - unten.y) > 4 || e.button !== 0 || !modell) { unten = null; return; }
  unten = null;
  const r = renderer.domElement.getBoundingClientRect();
  raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), kamera);
  const treffer = raycaster.intersectObjects(modell.netze, false).find((t) => !schnitt.value.an || schnittEbene.distanceToPoint(t.point) >= 0);
  if (!treffer) return;
  const netz = netzeAktuell[treffer.object.userData.netz];
  const f = flaecheZuDreieck(netz, treffer.faceIndex);
  const analyse = f >= 0 ? { ...flaecheAnalysieren(netz, f), netz } : null;
  const klick = modell.gruppe.worldToLocal(treffer.point.clone()).toArray();
  if (werkzeug.value === 'messen') {
    const p = messpunkt(klick, analyse);
    messung.value = messung.value.length >= 2 ? [p] : [...messung.value, p];
    messungZeichnen();
  } else {
    flaechenInfo.value = analyse;
    hervorhebungZeichnen();
  }
  zeichnen();
}

function hervorhebungZeichnen() {
  entfernen(hervorhebung);
  hervorhebung = null;
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
  const radius = new THREE.Box3().setFromObject(modell.gruppe).getBoundingSphere(new THREE.Sphere()).radius;
  for (const m of messung.value) {
    const kugel = new THREE.Mesh(new THREE.SphereGeometry(radius * 0.012, 16, 12), new THREE.MeshBasicMaterial({ color: 0x2563eb, depthTest: false }));
    kugel.position.set(...m.punkt);
    kugel.renderOrder = 10;
    kugel.userData.entsorgen = () => { kugel.geometry.dispose(); kugel.material.dispose(); };
    modell.gruppe.add(kugel);
    messObjekte.push(kugel);
  }
  if (messung.value.length === 2) {
    const [a, b] = messung.value.map((m) => m.punkt);
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
    const linie = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0x2563eb, depthTest: false }));
    linie.renderOrder = 10;
    linie.userData.entsorgen = () => { geo.dispose(); linie.material.dispose(); };
    const mitte = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
    linie.add(beschriftung(`${mm(abstand(a, b).gesamt)} mm`, mitte));
    modell.gruppe.add(linie);
    messObjekte.push(linie);
  }
  zeichnen();
}
const messErgebnis = computed(() => (messung.value.length === 2 ? abstand(messung.value[0].punkt, messung.value[1].punkt) : null));

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
  if (w === 'Fläche' && eigeneAchse.value) return { ...rundmaterial(netzeAktuell, eigeneAchse.value, aufmassWert.value), achsName: 'Fläche' };
  return rohteilListe.value.vorschlag;
});
const rohteilText = (r) => (r.art === 'Quader' ? `Quader ${mm(r.x)} × ${mm(r.y)} × ${mm(r.z)}` : `Rund ⌀${mm(r.durchmesser)} × ${mm(r.laenge)}`);
const fertigGewicht = computed(() => (kennwerte.value && props.dichte ? gewichtKg(kennwerte.value.volumen, props.dichte) : 0));
const rohGewicht = computed(() => (rohteil.value && props.dichte ? gewichtKg(rohteil.value.volumen, props.dichte) : 0));

function rohteilZeichnen() {
  entfernen(rohteilObjekt);
  rohteilObjekt = null;
  if (rohteilAn.value && rohteil.value && modell) {
    rohteilObjekt = rohteilLinien(rohteil.value);
    modell.gruppe.add(rohteilObjekt);
  }
  zeichnen();
}
function achseAusFlaeche() {
  if (flaechenInfo.value?.art !== 'Zylinder') return;
  eigeneAchse.value = flaechenInfo.value.achse;
  rohteilWahl.value = 'Fläche';
  rohteilAn.value = true;
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
  beobachter = new ResizeObserver(groesseAnpassen);
  beobachter.observe(huelle.value);
  laden();
});

onBeforeUnmount(() => {
  aktiv = false;
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
watch(werkzeug, () => { messung.value = []; flaechenInfo.value = null; messungZeichnen(); hervorhebungZeichnen(); });
useEventListener(window, 'keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (vollbild.value) vollbild.value = false;
  else if (messung.value.length || flaechenInfo.value) { messung.value = []; flaechenInfo.value = null; messungZeichnen(); hervorhebungZeichnen(); }
});

const mm = (v) => zahl(v, v < 10 ? 2 : 1);
const kg = (v) => `${zahl(v, v < 1 ? 3 : 2)} kg`;
const cm3 = (v) => `${zahl(v / 1000, 1)} cm³`;
</script>

<template>
  <div class="h-full">
    <Teleport to="body" :disabled="!vollbild">
      <div class="modell-flaeche overflow-hidden border border-line" :class="vollbild ? 'fixed inset-3 z-50 rounded-3xl shadow-2xl' : 'relative h-full rounded-2xl'">
        <div ref="huelle" class="absolute inset-0" :class="werkzeug === 'messen' ? 'cursor-crosshair' : ''" />

        <!-- Ansichten und Werkzeuge -->
        <div v-if="stand === 'bereit'" class="werkzeug left-3 top-3 flex-wrap">
          <button v-for="(a, k) in ANSICHTEN" :key="k" class="knopf" :class="ansicht === k ? 'aktiv' : ''" @click="zeigen(k)">{{ a.label }}</button>
          <span class="mx-0.5 w-px self-stretch bg-line" />
          <button class="knopf" :class="kantenAn ? 'aktiv' : ''" title="Kanten ein-/ausblenden" @click="kantenAn = !kantenAn"><Spline :size="15" /></button>
          <button class="knopf" title="Modell einpassen" @click="zeigen(ansicht)"><Scan :size="15" /></button>
          <span class="mx-0.5 w-px self-stretch bg-line" />
          <button class="knopf" :class="werkzeug === 'flaeche' ? 'aktiv' : ''" title="Fläche anklicken: Maß und Art (Bohrung, Welle, Ebene)" @click="werkzeug = 'flaeche'"><MousePointerClick :size="15" /></button>
          <button class="knopf" :class="werkzeug === 'messen' ? 'aktiv' : ''" title="Abstand messen: zwei Stellen anklicken (auf Zylindern zählt die Achse)" @click="werkzeug = 'messen'"><Ruler :size="15" /></button>
          <button class="knopf" :class="rohteilAn ? 'aktiv' : ''" title="Rohteil: Quader oder Rundmaterial mit Aufmaß und Gewicht" @click="rohteilAn = !rohteilAn"><Box :size="15" /></button>
          <button class="knopf" :class="schnitt.an ? 'aktiv' : ''" title="Schnitt: Modell entlang einer Achse aufschneiden" @click="schnitt.an = !schnitt.an"><Scissors :size="15" /></button>
          <button class="knopf" :class="roentgen ? 'aktiv' : ''" title="Röntgen: Außenhaut durchsichtig, Bohrungen und Innenkonturen sichtbar" @click="roentgen = !roentgen"><ScanEye :size="15" /></button>
        </div>
        <div class="werkzeug right-3 top-3">
          <button v-if="stand === 'bereit' && !nurAnsehen" class="knopf" title="Aktuelle Ansicht als Vorschaubild des Bauteils übernehmen" @click="alsVorschau"><ImagePlus :size="15" /></button>
          <a class="knopf" :href="url" :download="name || true" title="STEP-Datei herunterladen"><Download :size="15" /></a>
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

        <!-- Angeklickte Fläche -->
        <div v-if="flaechenInfo" class="karte bottom-3 right-3 max-w-[16rem]">
          <button class="absolute right-1.5 top-1.5 text-mute hover:text-ink" title="Schließen (Esc)" @click="flaechenInfo = null; hervorhebungZeichnen()"><X :size="13" /></button>
          <template v-if="flaechenInfo.art === 'Zylinder'">
            <div class="text-[11px] text-mute">{{ flaechenInfo.bohrung ? 'Bohrung' : 'Welle / Außendurchmesser' }}</div>
            <div class="text-lg font-semibold tnum">⌀ {{ zahl(flaechenInfo.durchmesser, 2) }} mm</div>
            <div class="text-xs text-mute tnum">Länge {{ zahl(flaechenInfo.laenge, 2) }} mm</div>
            <button class="mt-1.5 text-[11px] text-accent hover:underline" @click="achseAusFlaeche">Als Achse für Rundmaterial</button>
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

        <!-- Messung -->
        <div v-if="werkzeug === 'messen' && stand === 'bereit'" class="karte bottom-3 right-3 max-w-[17rem]">
          <div class="flex items-center gap-1 text-xs font-medium"><Ruler :size="13" class="text-accent" /> Abstand messen</div>
          <p v-if="!messErgebnis" class="mt-0.5 text-[11px] text-mute">{{ messung.length ? 'Zweite Stelle anklicken …' : 'Erste Stelle anklicken. Auf einer Bohrung oder Welle zählt die Mittelachse.' }}</p>
          <template v-else>
            <div class="text-lg font-semibold tnum">{{ mm(messErgebnis.gesamt) }} mm</div>
            <div class="text-[11px] text-mute tnum">ΔX {{ mm(messErgebnis.dx) }} · ΔY {{ mm(messErgebnis.dy) }} · ΔZ {{ mm(messErgebnis.dz) }}</div>
            <div class="text-[11px] text-mute">{{ messung.map((m) => m.art).join(' → ') }}</div>
          </template>
        </div>

        <!-- Rohteil oder Abmessungen -->
        <div v-if="rohteilAn && rohteil" class="karte bottom-3 left-3 w-[17.5rem]">
          <div class="flex items-center gap-1 text-xs font-medium"><Box :size="13" class="text-accent" /> Rohteil
            <span class="ml-auto text-[10px] text-mute">{{ rohteilWahl ? '' : 'Vorschlag' }}</span>
          </div>
          <div class="mt-1 flex flex-wrap gap-0.5">
            <button class="knopf !h-6" :class="rohteilWahl === '' ? 'aktiv' : ''" title="Kleinstes Rohteil" @click="rohteilWahl = ''">Auto</button>
            <button class="knopf !h-6" :class="rohteilWahl === 'Quader' ? 'aktiv' : ''" @click="rohteilWahl = 'Quader'">Quader</button>
            <button v-for="a in ['X', 'Y', 'Z']" :key="a" class="knopf !h-6" :class="rohteilWahl === a ? 'aktiv' : ''" :title="`Rundmaterial, Achse ${a}`" @click="rohteilWahl = a">⌀ {{ a }}</button>
            <button v-if="eigeneAchse" class="knopf !h-6" :class="rohteilWahl === 'Fläche' ? 'aktiv' : ''" title="Rundmaterial um die Achse der angeklickten Zylinderfläche" @click="rohteilWahl = 'Fläche'">⌀ Fläche</button>
          </div>
          <div class="mt-1.5 text-sm font-semibold tnum">{{ rohteilText(rohteil) }} mm</div>
          <label class="mt-1 flex items-center gap-1.5 text-[11px] text-mute">Aufmaß je Seite <input v-model.lazy="aufmassText" class="field !w-14 !px-1.5 !py-0.5 text-right text-xs" /> mm</label>
          <dl class="mt-1.5 grid grid-cols-2 gap-x-2 text-[11px] tnum">
            <dt class="text-mute">Fertigteil</dt><dd class="text-right">{{ cm3(kennwerte.volumen) }}<template v-if="dichte"> · {{ kg(fertigGewicht) }}</template></dd>
            <dt class="text-mute">Rohteil</dt><dd class="text-right">{{ cm3(rohteil.volumen) }}<template v-if="dichte"> · {{ kg(rohGewicht) }}</template></dd>
          </dl>
          <button v-if="dichte && !nurAnsehen" class="btn mt-2 w-full justify-center !py-1 text-xs" @click="emit('gewicht', Math.round(rohGewicht * 1000) / 1000)"><Check :size="13" /> Rohteilgewicht übernehmen</button>
          <p v-if="dichte && dichteGeschaetzt" class="mt-1 text-[10px] text-mute">Dichte geschätzt ({{ zahl(dichte, 2) }} kg/dm³), bitte am Rohmaterial in den Stammdaten pflegen.</p>
          <p v-else-if="!dichte" class="mt-1.5 text-[11px] text-mute">Für das Gewicht ein Rohmaterial mit Dichte wählen.</p>
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
.karte { position: absolute; border-radius: 0.8rem; padding: 0.55rem 0.7rem; background: color-mix(in srgb, var(--surface) 92%, transparent); box-shadow: 0 2px 8px rgb(0 0 0 / 0.1); backdrop-filter: blur(6px); }
.knopf { display: grid; place-items: center; height: 1.85rem; min-width: 1.85rem; padding: 0 0.5rem; border-radius: 0.6rem; font-size: 0.72rem; color: var(--mute); }
.knopf:hover { background: var(--surface-2); color: var(--ink); }
.knopf.aktiv { background: var(--accent-soft); color: var(--accent); }
:deep(.mess-beschriftung) { padding: 0.1rem 0.4rem; border-radius: 0.4rem; background: #2563eb; color: #fff; font-size: 0.72rem; font-variant-numeric: tabular-nums; white-space: nowrap; }
</style>
