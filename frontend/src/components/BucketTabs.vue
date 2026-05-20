<template>
  <div class="flex flex-wrap gap-2 mb-6 sticky top-0 bg-stone-50 py-3 z-10">
    <button v-for="b in buckets" :key="b.key"
            @click="$emit('change', b.key)"
            :class="[
              'px-3 py-1.5 rounded-full text-sm border transition',
              current === b.key
                ? 'bg-stone-900 text-stone-50 border-stone-900'
                : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-100'
            ]">
      {{ b.label }} <span class="opacity-60">({{ counts[b.key] || 0 }})</span>
    </button>

    <!-- separator + dynamic genre tabs -->
    <template v-if="genreTabs.length > 0">
      <span class="self-center text-stone-300 select-none">|</span>
      <button v-for="g in genreTabs" :key="g.key"
              @click="$emit('change', g.key)"
              :class="[
                'px-3 py-1.5 rounded-full text-sm border transition',
                current === g.key
                  ? 'bg-stone-900 text-stone-50 border-stone-900'
                  : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-100'
              ]">
        {{ g.label }} <span class="opacity-60">({{ g.count }})</span>
      </button>
    </template>
  </div>
</template>

<script setup>
import { bucketLabel } from '../utils/formatters.js'

defineProps({
  current:   { type: String,  required: true },
  counts:    { type: Object,  default: () => ({}) },
  genreTabs: { type: Array,   default: () => [] },
})
defineEmits(['change'])

const buckets = [
  { key: 'pulso',          label: '📌 Pulso da Semana' },
  { key: 'alinhado',       label: bucketLabel('alinhado') },
  { key: 'media_afinidade',label: bucketLabel('media_afinidade') },
  { key: 'consensus',      label: bucketLabel('consensus') },
  { key: 'br',             label: bucketLabel('br') },
  { key: 'estreias',       label: '🎬 Estreias' },
  { key: 'laureados',      label: '🏆 Laureados' },
]
</script>
