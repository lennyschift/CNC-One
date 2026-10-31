// Web-Worker: liest STEP-Dateien mit occt-import-js (OpenCascade als WebAssembly) und liefert Dreiecksnetze für die 3D-Ansicht.
// Läuft im Hintergrund, damit die Oberfläche beim Lesen großer Modelle nicht stockt. Das WASM-Modul wird einmal geladen.
import occtimportjs from 'occt-import-js';
import wasmUrl from 'occt-import-js/dist/occt-import-js.wasm?url';

let occt = null;

self.onmessage = async (e) => {
  const { id, buffer } = e.data;
  try {
    occt ??= await occtimportjs({ locateFile: () => wasmUrl });
    const r = occt.ReadStepFile(new Uint8Array(buffer), { linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.0008, angularDeflection: 0.4 });
    if (!r?.success || !r.meshes?.length) throw new Error('Die STEP-Datei ließ sich nicht lesen oder enthält keine Geometrie.');
    const netze = r.meshes.map((m) => ({
      name: m.name || '',
      farbe: m.color ?? null,
      position: Float32Array.from(m.attributes.position.array),
      normal: m.attributes.normal ? Float32Array.from(m.attributes.normal.array) : null,
      index: Uint32Array.from(m.index.array),
    }));
    const transfer = netze.flatMap((n) => [n.position.buffer, n.index.buffer, ...(n.normal ? [n.normal.buffer] : [])]);
    self.postMessage({ id, netze }, transfer);
  } catch (err) {
    self.postMessage({ id, fehler: String(err?.message || err) });
  }
};
