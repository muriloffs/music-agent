<template>
  <div class="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-stone-200 -mx-4 px-4 py-2.5 mb-4">
    <div class="flex items-center gap-2 max-w-3xl mx-auto">
      <span class="text-stone-400 select-none" aria-hidden="true">🔍</span>
      <input
        type="search"
        :value="inputValue"
        @input="onInput"
        @focus="onFocus"
        :placeholder="placeholder"
        aria-label="Buscar em todo o histórico de relatórios"
        class="flex-1 bg-transparent border-0 focus:outline-none focus:ring-0
               font-serif text-[15px] text-stone-900 placeholder-stone-400 py-1"
      />
      <span v-if="loading" class="text-xs text-stone-500 italic whitespace-nowrap">
        carregando edições…
      </span>
      <span v-else-if="loadError" class="text-xs text-red-700 whitespace-nowrap">
        erro: {{ loadError }}
      </span>
      <span v-else-if="isActive" class="text-xs text-stone-500 whitespace-nowrap">
        {{ results.length }} {{ results.length === 1 ? 'resultado' : 'resultados' }}
      </span>
      <button v-if="inputValue"
              type="button"
              @click="onClear"
              aria-label="Limpar busca"
              class="text-stone-400 hover:text-stone-700 text-lg leading-none px-1
                     min-w-[28px] min-h-[28px]">
        ×
      </button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { useSearch } from '../composables/useSearch.js'

const { query, loading, loaded, loadError, isActive, results, daysIndexed,
        loadAllReports, clear } = useSearch()

// Local input value mirrors what the user types instantly; the shared `query`
// only updates after 200ms debounce so filtering doesn't re-run on every key.
const inputValue = ref(query.value)

let debounceTimer = null
function onInput(e) {
  const v = e.target.value
  inputValue.value = v
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { query.value = v }, 200)
}

function onFocus() {
  // Lazy load: kick off the index fetch on the first focus only.
  if (!loaded.value && !loading.value) loadAllReports()
}

function onClear() {
  inputValue.value = ''
  clearTimeout(debounceTimer)
  clear()
}

// Esc key clears the search (works once the input is focused).
function onKey(e) {
  if (e.key === 'Escape' && inputValue.value) onClear()
}
document.addEventListener('keydown', onKey)
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  clearTimeout(debounceTimer)
})

// Placeholder shows the catalog size once loaded, so the user knows the
// scope without having to read docs.
import { computed } from 'vue'
const placeholder = computed(() => {
  if (loaded.value && daysIndexed.value > 0) {
    return `Buscar em ${daysIndexed.value} ${daysIndexed.value === 1 ? 'edição' : 'edições'}`
  }
  return 'Buscar em todo o histórico'
})
</script>
