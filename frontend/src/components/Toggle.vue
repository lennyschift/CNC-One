<script setup>
defineProps({ modelValue: Boolean, label: { type: String, default: '' }, klein: Boolean });
defineEmits(['update:modelValue']);
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    class="group inline-flex items-center gap-2 text-left"
    @click="$emit('update:modelValue', !modelValue)"
  >
    <span
      class="relative inline-block shrink-0 rounded-full transition-colors duration-200"
      :class="[klein ? 'h-4 w-7' : 'h-5 w-9', modelValue ? 'bg-accent' : 'bg-line']"
    >
      <span
        class="absolute top-0.5 left-0.5 rounded-full bg-white shadow transition-transform duration-200"
        :class="[klein ? 'h-3 w-3' : 'h-4 w-4', modelValue ? (klein ? 'translate-x-3' : 'translate-x-4') : '']"
      />
    </span>
    <span v-if="label" class="text-xs text-mute transition-colors group-hover:text-ink">{{ label }}</span>
  </button>
</template>
