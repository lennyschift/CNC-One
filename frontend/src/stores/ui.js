import { defineStore } from 'pinia';
import { ref } from 'vue';
import { uid } from '../lib/format.js';
import { einstellungSpeichern } from '../data/einstellungen.js';

export const useUi = defineStore('ui', () => {
  const dark = ref(document.documentElement.classList.contains('dark'));
  const paletteOffen = ref(false);
  const bauteilWahlOffen = ref(false);
  const toasts = ref([]);

  function setDark(v) {
    dark.value = v;
    document.documentElement.classList.toggle('dark', v);
    einstellungSpeichern('theme', v ? 'dark' : 'light');
  }
  const toggleDark = () => setDark(!dark.value);

  function toast(text, art = 'info') {
    const id = uid();
    toasts.value.push({ id, text, art });
    setTimeout(() => { toasts.value = toasts.value.filter((t) => t.id !== id); }, 3200);
  }

  // Per Drag and Drop abgelegte Dateien für eine Seite, die sie selbst verarbeitet (z. B. Eingangsrechnungen)
  const abgelegt = ref(null);
  return { dark, paletteOffen, bauteilWahlOffen, toasts, abgelegt, setDark, toggleDark, toast };
});
