<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { Search, CornerDownLeft } from '@lucide/vue';

const props = defineProps({ offen: Boolean, befehle: { type: Array, default: () => [] } });
const emit = defineEmits(['schliessen']);

const suche = ref('');
const index = ref(0);
const eingabe = ref(null);

const treffer = computed(() => {
  const q = suche.value.trim().toLowerCase();
  if (!q) return props.befehle;
  return props.befehle.filter((b) => `${b.label} ${b.gruppe ?? ''} ${b.stichworte ?? ''}`.toLowerCase().includes(q));
});

watch(() => props.offen, async (v) => {
  if (v) {
    suche.value = '';
    index.value = 0;
    await nextTick();
    eingabe.value?.focus();
  }
});
watch(suche, () => { index.value = 0; });

function ausfuehren(b) {
  if (!b) return;
  emit('schliessen');
  b.run();
}

function taste(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); index.value = (index.value + 1) % Math.max(1, treffer.value.length); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); index.value = (index.value - 1 + treffer.value.length) % Math.max(1, treffer.value.length); }
  else if (e.key === 'Enter') { e.preventDefault(); ausfuehren(treffer.value[index.value]); }
  else if (e.key === 'Escape') emit('schliessen');
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="offen" class="fixed inset-0 z-50 grid place-items-start justify-center bg-black/40 pt-[14vh] backdrop-blur-[2px]" @mousedown.self="emit('schliessen')">
        <Transition name="pop" appear>
          <div v-if="offen" class="card w-[min(560px,92vw)] overflow-hidden shadow-2xl">
            <div class="flex items-center gap-3 border-b border-line px-4 py-3">
              <Search :size="18" class="text-mute" />
              <input ref="eingabe" v-model="suche" class="w-full bg-transparent text-[15px] outline-none placeholder:text-mute" placeholder="Befehl suchen …" @keydown="taste" />
              <span class="kbd">Esc</span>
            </div>
            <ul class="max-h-[50vh] overflow-auto p-2">
              <li v-for="(b, i) in treffer" :key="b.id">
                <button
                  class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition"
                  :class="i === index ? 'bg-accent-soft text-ink' : 'text-ink hover:bg-surface2'"
                  @mousemove="index = i"
                  @click="ausfuehren(b)"
                >
                  <component :is="b.icon" :size="17" class="shrink-0" :class="i === index ? 'text-accent' : 'text-mute'" />
                  <span class="flex-1">{{ b.label }}</span>
                  <span v-if="b.gruppe" class="text-xs text-mute">{{ b.gruppe }}</span>
                  <CornerDownLeft v-if="i === index" :size="14" class="text-accent" />
                </button>
              </li>
              <li v-if="!treffer.length" class="px-3 py-6 text-center text-sm text-mute">Nichts gefunden</li>
            </ul>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
