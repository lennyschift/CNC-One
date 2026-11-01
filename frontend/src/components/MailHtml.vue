<script setup>
// Mail als HTML anzeigen, so wie sie im Mailprogramm aussieht (Tabellen, Bilder). Abgeschottet in einem Rahmen ohne
// Skripte; das HTML ist beim Abholen schon bereinigt. Die Höhe passt sich dem Inhalt an.
import { ref, computed } from 'vue';

const props = defineProps({ html: { type: String, required: true }, maxHoehe: { type: Number, default: 2400 } });
const rahmen = ref(null);
const hoehe = ref(80);

const srcdoc = computed(() => `<!DOCTYPE html><html><head><meta charset="utf-8"><base target="_blank"><style>
body{margin:0;padding:2px 0;font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;font-size:14px;line-height:1.5;color:#1c1c1c;background:#fff;overflow-wrap:anywhere}
img{max-width:100%;height:auto}table{border-collapse:collapse;max-width:100%}td,th{padding:2px 6px;vertical-align:top}
p{margin:0 0 8px}blockquote{margin:6px 0;padding-left:12px;border-left:2px solid #ccc;color:#444}a{color:#d4242a}
</style></head><body>${props.html}</body></html>`);

function messen() {
  const d = rahmen.value?.contentDocument;
  if (!d?.documentElement) return;
  hoehe.value = Math.min(Math.max(d.documentElement.scrollHeight + 4, 40), props.maxHoehe);
}
function geladen() {
  messen();
  // Bilder laden nach: danach noch einmal messen
  for (const img of rahmen.value?.contentDocument?.images ?? []) if (!img.complete) img.addEventListener('load', messen, { once: true });
}
</script>

<template>
  <iframe
    ref="rahmen" :srcdoc="srcdoc" title="Inhalt der Mail" class="w-full rounded-lg border-0 bg-white"
    :style="{ height: `${hoehe}px` }" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" @load="geladen"
  />
</template>
