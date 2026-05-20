<template>
  <nav class="flex flex-wrap gap-2 mb-8 sticky top-0 bg-stone-50/95 backdrop-blur py-3 z-10 -mx-4 px-4">
    <button v-for="b in buckets" :key="b.key"
            @click="$emit('change', b.key)"
            :class="[
              'px-3.5 py-1.5 rounded-full text-sm border transition-colors',
              current === b.key
                ? 'bg-stone-900 text-stone-50 border-stone-900'
                : 'bg-white text-stone-600 border-stone-300 hover:border-stone-500 hover:text-stone-900'
            ]">
      {{ b.label }}
      <span :class="current === b.key ? 'text-stone-400' : 'text-stone-400'">
        {{ counts[b.key] || 0 }}
      </span>
    </button>
  </nav>
</template>

<script setup>
import { bucketLabel } from '../utils/formatters.js'

defineProps({
  current: { type: String, required: true },
  counts:  { type: Object, default: () => ({}) },
})
defineEmits(['change'])

// 5 fixed tabs. Pulso = editorial; 3 buckets; Estreias = cross-bucket filter
// on is_estreia. No genre tabs, no "Laureados" (overlapped Aclamados — awards
// show as card badges), no "BR" (no dedicated bucket — Brazilian releases that
// fit the taste land in Preferidos/Vale explorar like anything else).
const buckets = [
  { key: 'pulso',           label: '📌 Pulso da Semana' },
  { key: 'alinhado',        label: bucketLabel('alinhado') },
  { key: 'media_afinidade', label: bucketLabel('media_afinidade') },
  { key: 'estreias',        label: '🎬 Estreias' },
  { key: 'consensus',       label: bucketLabel('consensus') },
]
</script>
