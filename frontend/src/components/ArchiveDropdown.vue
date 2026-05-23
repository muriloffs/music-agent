<template>
  <div ref="containerRef" class="relative inline-block text-right">
    <button
      type="button"
      @click="open = !open"
      :aria-expanded="open"
      class="text-xs text-stone-500 hover:text-stone-800 underline decoration-dotted decoration-stone-400 underline-offset-2"
    >
      Edições anteriores {{ open ? '▴' : '▾' }}
    </button>
    <div
      v-if="open"
      class="absolute right-0 mt-2 w-48 bg-white border border-stone-200 rounded shadow-lg z-20 max-h-80 overflow-y-auto"
    >
      <p v-if="loading" class="text-xs text-stone-400 italic px-3 py-2">carregando...</p>
      <p v-else-if="!dates.length" class="text-xs text-stone-400 italic px-3 py-2">nenhum arquivo</p>
      <a
        v-for="d in dates"
        :key="d"
        :href="`/?r=${d}`"
        :class="[
          'block px-3 py-1.5 text-sm font-serif border-b border-stone-100 last:border-b-0',
          d === currentDate
            ? 'text-stone-400 italic cursor-default pointer-events-none'
            : 'text-stone-800 hover:bg-stone-50',
        ]"
      >
        {{ formatDate(d) }}<span v-if="d === currentDate" class="not-italic"> · atual</span>
      </a>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { formatDate } from '../utils/formatters.js'

defineProps({
  currentDate: { type: String, default: '' },
})

const open = ref(false)
const dates = ref([])
const loading = ref(true)
const containerRef = ref(null)

function onDocClick(e) {
  if (containerRef.value && !containerRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', onDocClick)
  try {
    const resp = await fetch('/api/reports')
    if (resp.ok) {
      const data = await resp.json()
      dates.value = data.dates || []
    }
  } catch {
    // Dropdown silently stays empty if the endpoint fails — never blocks the page.
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>
