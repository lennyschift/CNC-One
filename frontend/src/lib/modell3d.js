// Three.js-Hilfen für Bauteilmodelle: Netze aus dem STEP-Leser in eine Szene bringen, Ansichten, Maße und Vorschaubild.
// STEP-Modelle sind Z-oben (CAD); die Gruppe wird so gedreht, dass Z nach oben zeigt, in Three.js ist das Y.
import * as THREE from 'three';

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

// Linien eines Rohteils in CAD-Koordinaten: Quader { min, max } oder Rundmaterial { achse, mitte, durchmesser, laenge }
export function rohteilLinien(r, farbe = 0x2563eb) {
  const pkt = [];
  if (r.art === 'Quader') {
    const [x0, y0, z0] = r.min;
    const [x1, y1, z1] = r.max;
    const e = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
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
