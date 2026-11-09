<script setup>
// Projektname (intern) als kleine Marke in Listen und Kopfzeilen
import { FolderKanban } from '@lucide/vue';

defineProps({ projekt: { type: String, default: '' } });
</script>

<template>
  <span v-if="projekt" class="inline-flex max-w-[260px] items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent" :title="`Projekt: ${projekt}`">
    <FolderKanban :size="11" class="shrink-0" /><span class="truncate">{{ projekt }}</span>
  </span>
</template>
