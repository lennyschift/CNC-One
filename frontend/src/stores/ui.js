import { defineStore } from 'pinia';
import { ref } from 'vue';
import { uid } from '../lib/format.js';

export const useUi = defineStore('ui', () => {
  const dark = ref(document.documentElement.classList.contains('dark'));
  const paletteOffen = ref(false);
  const toasts = ref([]);

  function setDark(v) {
    dark.value = v;
    document.documentElement.classList.toggle('dark', v);
    try { localStorage.setItem('cnc-one:theme', v ? 'dark' : 'light'); } catch { /* egal */ }
  }
  const toggleDark = () => setDark(!dark.value);

  function toast(text, art = 'info') {
    const id = uid();
    toasts.value.push({ id, text, art });
    setTimeout(() => { toasts.value = toasts.value.filter((t) => t.id !== id); }, 3200);
  }

  return { dark, paletteOffen, toasts, setDark, toggleDark, toast };
});
