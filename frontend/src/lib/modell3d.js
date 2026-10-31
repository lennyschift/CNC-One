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

// Baut aus den Netzen eine Gruppe mit Flächen und Kanten. Liefert { gruppe, kanten, entsorgen }.
export function modellGruppe(netze, { farbe = STANDARDFARBE, kantenWinkel = 25 } = {}) {
  const gruppe = new THREE.Group();
  const kanten = new THREE.Group();
  const reste = [];
  for (const n of netze) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(n.position, 3));
    if (n.normal) geo.setAttribute('normal', new THREE.BufferAttribute(n.normal, 3));
    geo.setIndex(new THREE.BufferAttribute(n.index, 1));
    if (!n.normal) geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ color: farbeAus(n, farbe), metalness: 0.25, roughness: 0.55, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    gruppe.add(new THREE.Mesh(geo, mat));
    const kg = new THREE.EdgesGeometry(geo, kantenWinkel);
    const km = new THREE.LineBasicMaterial({ color: 0x1f2933, transparent: true, opacity: 0.55 });
    kanten.add(new THREE.LineSegments(kg, km));
    reste.push(geo, mat, kg, km);
  }
  gruppe.add(kanten);
  gruppe.rotation.x = -Math.PI / 2; // CAD Z-oben -> Three.js Y-oben
  gruppe.updateMatrixWorld(true);
  return { gruppe, kanten, entsorgen: () => reste.forEach((r) => r.dispose()) };
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
