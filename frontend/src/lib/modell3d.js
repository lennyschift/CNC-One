// Three.js-Hilfen für Bauteilmodelle: Netze aus dem STEP-Leser in eine Szene bringen, Ansichten, Maße und Vorschaubild.
// STEP-Modelle sind Z-oben (CAD); die Gruppe wird so gedreht, dass Z nach oben zeigt, in Three.js ist das Y.
import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

export const STANDARDFARBE = '#b9c3cd';

// Blickrichtungen (vom Modell zur Kamera) in Three.js-Koordinaten nach der Drehung: vorne = -Y des Modells usw.
export const ANSICHTEN = {
  iso: { label: 'Iso', richtung: [1, 0.75, 1] },
  vorne: { label: 'Vorne', richtung: [0, 0, 1] },
  oben: { label: 'Oben', richtung: [0, 1, 0.0001] },
  rechts: { label: 'Rechts', richtung: [1, 0, 0] },
};

function farbeAus(netz, standard) {
  const c = netz.farbe;
  return Array.isArray(c) && c.length >= 3 ? new THREE.Color(c[0], c[1], c[2]) : new THREE.Color(standard);
}

// Baut aus den Netzen eine Gruppe mit Flächen und Kanten. Jedes Netz bekommt dazu eine Rückseite in Akzentfarbe, die nur bei
// einem Schnitt sichtbar wird (so sieht man die Schnittfläche). Liefert { gruppe, kanten, netze, rueckseiten, entsorgen }.
export function modellGruppe(netze, { farbe = STANDARDFARBE, kantenWinkel = 25 } = {}) {
  const gruppe = new THREE.Group();
  const kanten = new THREE.Group();
  const flaechen = [];
  const rueckseiten = [];
  const reste = [];
  netze.forEach((n, i) => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(n.position, 3));
    if (n.normal) geo.setAttribute('normal', new THREE.BufferAttribute(n.normal, 3));
    geo.setIndex(new THREE.BufferAttribute(n.index, 1));
    if (!n.normal) geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ color: farbeAus(n, farbe), metalness: 0.25, roughness: 0.55, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.netz = i;
    gruppe.add(mesh);
    flaechen.push(mesh);
    const rmat = new THREE.MeshBasicMaterial({ color: 0xd4242a, side: THREE.BackSide });
    const rueck = new THREE.Mesh(geo, rmat);
    rueck.visible = false;
    gruppe.add(rueck);
    rueckseiten.push(rueck);
    const kg = new THREE.EdgesGeometry(geo, kantenWinkel);
    const km = new THREE.LineBasicMaterial({ color: 0x1f2933, transparent: true, opacity: 0.55 });
    kanten.add(new THREE.LineSegments(kg, km));
    reste.push(geo, mat, rmat, kg, km);
  });
  gruppe.add(kanten);
  gruppe.rotation.x = -Math.PI / 2; // CAD Z-oben -> Three.js Y-oben
  gruppe.updateMatrixWorld(true);
  return { gruppe, kanten, netze: flaechen, rueckseiten, entsorgen: () => reste.forEach((r) => r.dispose()) };
}

// Hebt eine CAD-Fläche hervor (ihre Dreiecke als eigenes Netz über dem Modell)
export function flaecheHervorheben(netz, dreiecke, farbe = 0xd4242a) {
  const idx = [];
  for (const t of dreiecke) idx.push(netz.index[3 * t], netz.index[3 * t + 1], netz.index[3 * t + 2]);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(netz.position, 3));
  geo.setIndex(idx);
  const mat = new THREE.MeshBasicMaterial({ color: farbe, transparent: true, opacity: 0.45, side: THREE.DoubleSide, depthTest: true, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData.entsorgen = () => { geo.dispose(); mat.dispose(); };
  return mesh;
}

// Punkt eines Quaders (Koordinaten in seiner Ausrichtung, siehe messen.quader) in CAD-Koordinaten
const qp = (r, l) => {
  const B = r.achsen ?? [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  return [0, 1, 2].map((k) => l[0] * B[0][k] + l[1] * B[1][k] + l[2] * B[2][k]);
};

// Linien eines Rohteils in CAD-Koordinaten: Quader { min, max, achsen? } oder Rundmaterial { achse, mitte, durchmesser, laenge }
export function rohteilLinien(r, farbe = 0x2563eb) {
  const pkt = [];
  if (r.art === 'Quader') {
    const [x0, y0, z0] = r.min;
    const [x1, y1, z1] = r.max;
    const e = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]].map((l) => qp(r, l));
    for (const [i, j] of [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]) pkt.push(...e[i], ...e[j]);
  } else {
    const a = new THREE.Vector3(...r.achse).normalize();
    const hilf = Math.abs(a.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
    const u = new THREE.Vector3().crossVectors(a, hilf).normalize();
    const v = new THREE.Vector3().crossVectors(a, u);
    const m = new THREE.Vector3(...r.mitte);
    const rad = r.durchmesser / 2;
    const n = 64;
    const kreis = (s) => Array.from({ length: n + 1 }, (_x, k) => {
      const w = (k / n) * Math.PI * 2;
      return m.clone().addScaledVector(a, s).addScaledVector(u, Math.cos(w) * rad).addScaledVector(v, Math.sin(w) * rad);
    });
    for (const s of [-r.laenge / 2, r.laenge / 2]) {
      const k = kreis(s);
      for (let i = 0; i < n; i++) pkt.push(k[i].x, k[i].y, k[i].z, k[i + 1].x, k[i + 1].y, k[i + 1].z);
    }
    for (let q = 0; q < 4; q++) {
      const w = (q / 4) * Math.PI * 2;
      const p0 = m.clone().addScaledVector(a, -r.laenge / 2).addScaledVector(u, Math.cos(w) * rad).addScaledVector(v, Math.sin(w) * rad);
      const p1 = p0.clone().addScaledVector(a, r.laenge);
      pkt.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pkt, 3));
  const mat = new THREE.LineDashedMaterial({ color: farbe, dashSize: 3, gapSize: 2 });
  const linien = new THREE.LineSegments(geo, mat);
  linien.computeLineDistances();
  linien.userData.entsorgen = () => { geo.dispose(); mat.dispose(); };
  return linien;
}

// Abmessungen des Modells in mm (Ausdehnung in CAD-Achsen X, Y, Z).
export function abmessungen(netze) {
  const box = new THREE.Box3();
  const p = new THREE.Vector3();
  for (const n of netze) {
    for (let i = 0; i < n.position.length; i += 3) box.expandByPoint(p.set(n.position[i], n.position[i + 1], n.position[i + 2]));
  }
  const s = box.getSize(new THREE.Vector3());
  return { x: s.x, y: s.y, z: s.z };
}

// Stellt die Kamera so, dass das ganze Modell aus der gewählten Richtung zu sehen ist.
export function kameraAusrichten(kamera, ziel, objekt, richtung, abstandFaktor = 1.15) {
  const kugel = new THREE.Box3().setFromObject(objekt).getBoundingSphere(new THREE.Sphere());
  const r = Math.max(kugel.radius, 1e-3);
  const abstand = (r / Math.sin((kamera.fov * Math.PI) / 360)) * abstandFaktor;
  kamera.position.copy(kugel.center).add(new THREE.Vector3(...richtung).normalize().multiplyScalar(abstand));
  kamera.near = abstand / 100;
  kamera.far = abstand * 100;
  kamera.updateProjectionMatrix();
  ziel.copy(kugel.center);
  kamera.lookAt(kugel.center);
}

export function lichter(szene) {
  szene.add(new THREE.HemisphereLight(0xffffff, 0x8a96a3, 1.6));
  const a = new THREE.DirectionalLight(0xffffff, 1.8);
  a.position.set(1, 2, 1.5);
  szene.add(a);
  const b = new THREE.DirectionalLight(0xffffff, 0.6);
  b.position.set(-1.5, -0.5, -1);
  szene.add(b);
}

// Rendert ein Vorschaubild (PNG mit durchsichtigem Hintergrund) aus der Iso-Ansicht.
export function vorschauPng(netze, groesse = 480) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setSize(groesse, groesse, false);
  renderer.setClearColor(0x000000, 0);
  const szene = new THREE.Scene();
  lichter(szene);
  const m = modellGruppe(netze);
  szene.add(m.gruppe);
  const kamera = new THREE.PerspectiveCamera(30, 1, 0.1, 1000);
  kameraAusrichten(kamera, new THREE.Vector3(), m.gruppe, ANSICHTEN.iso.richtung, 1.02);
  renderer.render(szene, kamera);
  return new Promise((resolve) => {
    renderer.domElement.toBlob((blob) => {
      m.entsorgen();
      renderer.dispose();
      renderer.forceContextLoss();
      resolve(blob);
    }, 'image/png');
  });
}

// Richtungspfeile am Rohteil, damit klar ist, wohin ein Aufmaß wirkt. Quader: je Fläche ein Pfeil nach außen (X rot, Y grün,
// Z blau wie im CAD) mit „X+“, „X−“ …; Rund: Stirn A/B an den Enden der Achse und ein Pfeil für den Durchmesser.
// Jeder Pfeil hat einen unsichtbaren, dicken Griff zum Ziehen (userData.griff = { richtung, von, dir }); text(richtung, name)
// liefert die Beschriftung (z. B. mit dem Wert), bearbeiten(richtung, div) wird beim Klick auf die Beschriftung gerufen.
// Richtungen: xm, xp, ym, yp, zm, zp (Quader), a, b, r (Rund).
export const ACHS_FARBEN = { X: '#dc2626', Y: '#16a34a', Z: '#2563eb', A: '#d97706', R: '#7c3aed' };
export function richtungsPfeile(r, { text = null, bearbeiten = null } = {}) {
  const gruppe = new THREE.Group();
  const teile = [];
  const reste = [];
  const griffe = [];
  const pfeile = {};
  const pfeil = (richtung, von, richtungVektor, laenge, farbe, name) => {
    const dir = new THREE.Vector3(...richtungVektor).normalize();
    const start = new THREE.Vector3(...von);
    const p = new THREE.ArrowHelper(dir, start, laenge, new THREE.Color(farbe).getHex(), laenge * 0.28, laenge * 0.16);
    for (const m of [p.line.material, p.cone.material]) { m.depthTest = false; m.transparent = true; }
    p.renderOrder = 10;
    gruppe.add(p);
    teile.push(p);
    // Griff: Zylinder um Schaft und Spitze, etwas dicker, damit er sich gut greifen lässt
    const geo = new THREE.CylinderGeometry(laenge * 0.13, laenge * 0.13, laenge * 1.15, 10);
    const mat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, depthTest: false });
    const griff = new THREE.Mesh(geo, mat);
    griff.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    griff.position.copy(start).addScaledVector(dir, laenge * 0.57);
    griff.userData.griff = { richtung, von: start.toArray(), dir: dir.toArray() };
    gruppe.add(griff);
    griffe.push(griff);
    reste.push(geo, mat);
    const div = document.createElement('div');
    div.className = 'achs-beschriftung';
    div.style.background = farbe;
    div.textContent = text ? text(richtung, name) : name;
    if (bearbeiten) {
      div.classList.add('bearbeitbar');
      div.title = 'Klicken und Wert eingeben (oder am Pfeil ziehen)';
      div.addEventListener('pointerdown', (e) => e.stopPropagation());
      div.addEventListener('click', (e) => { e.stopPropagation(); bearbeiten(richtung, div); });
    }
    const l = new CSS2DObject(div);
    l.position.copy(start).addScaledVector(dir, laenge * 1.22);
    gruppe.add(l);
    pfeile[richtung] = { pfeil: p, div };
  };
  if (r.art === 'Quader') {
    const mitte = [0, 1, 2].map((i) => (r.min[i] + r.max[i]) / 2);
    const laenge = Math.max(4, Math.max(r.x, r.y, r.z) * 0.22);
    ['X', 'Y', 'Z'].forEach((achse, i) => {
      for (const s of [-1, 1]) {
        const lokal = [...mitte];
        lokal[i] = s > 0 ? r.max[i] : r.min[i];
        const von = qp(r, lokal);
        const dir = (r.achsen ?? [[1, 0, 0], [0, 1, 0], [0, 0, 1]])[i].map((w) => w * s);
        pfeil(`${achse.toLowerCase()}${s > 0 ? 'p' : 'm'}`, von, dir, laenge, ACHS_FARBEN[achse], `${achse}${s > 0 ? '+' : '−'}`);
      }
    });
  } else {
    const a = new THREE.Vector3(...r.achse).normalize();
    const m = new THREE.Vector3(...r.mitte);
    const laenge = Math.max(4, Math.max(r.durchmesser, r.laenge) * 0.22);
    pfeil('a', m.clone().addScaledVector(a, -r.laenge / 2).toArray(), a.clone().negate().toArray(), laenge, ACHS_FARBEN.A, 'Stirn A');
    pfeil('b', m.clone().addScaledVector(a, r.laenge / 2).toArray(), a.toArray(), laenge, ACHS_FARBEN.A, 'Stirn B');
    const quer = rundQuer(a);
    pfeil('r', m.clone().addScaledVector(quer, r.durchmesser / 2).toArray(), quer.toArray(), laenge * 0.8, ACHS_FARBEN.R, '⌀ je Seite');
  }
  gruppe.userData.griffe = griffe;
  gruppe.userData.pfeile = pfeile;
  gruppe.userData.entsorgen = () => { teile.forEach((p) => p.dispose()); reste.forEach((x) => x.dispose()); };
  return gruppe;
}

// Richtung quer zur Achse, möglichst „nach oben“ (CAD Z)
function rundQuer(a) {
  const hilf = Math.abs(a.z) < 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0);
  const u = new THREE.Vector3().crossVectors(a, hilf).normalize();
  return new THREE.Vector3().crossVectors(u, a).normalize();
}

// Maße des Rohteils direkt am Rahmen: Quader an drei Kanten (X, Y, Z, aus der Iso-Ansicht vorne sichtbar), Rund der
// Durchmesser an der Stirnseite B und die Länge an der Mantellinie. format(mm) liefert den Text.
export function rohteilMasse(r, format) {
  const gruppe = new THREE.Group();
  const marke = (ort, text, farbe) => {
    const div = document.createElement('div');
    div.className = 'roh-mass';
    div.style.borderColor = farbe;
    div.textContent = text;
    const l = new CSS2DObject(div);
    l.position.set(...ort);
    gruppe.add(l);
  };
  if (r.art === 'Quader') {
    const [x0, y0, z0] = r.min;
    const [x1, y1] = r.max;
    const z1 = r.max[2];
    marke(qp(r, [(x0 + x1) / 2, y0, z0]), format(r.x), ACHS_FARBEN.X);
    marke(qp(r, [x1, (y0 + y1) / 2, z0]), format(r.y), ACHS_FARBEN.Y);
    marke(qp(r, [x1, y0, (z0 + z1) / 2]), format(r.z), ACHS_FARBEN.Z);
  } else {
    const a = new THREE.Vector3(...r.achse).normalize();
    const m = new THREE.Vector3(...r.mitte);
    const quer = rundQuer(a);
    const seite = new THREE.Vector3().crossVectors(a, quer).normalize();
    const rad = r.durchmesser / 2;
    marke(m.clone().addScaledVector(a, r.laenge / 2).addScaledVector(seite, -rad).toArray(), `⌀ ${format(r.durchmesser)}`, ACHS_FARBEN.R);
    marke(m.clone().addScaledVector(quer, -rad).toArray(), format(r.laenge), ACHS_FARBEN.A);
  }
  return gruppe;
}
