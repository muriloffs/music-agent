<template>
  <section>
    <header class="mb-5">
      <p class="text-[11px] uppercase tracking-[0.13em] text-stone-500">Resumo da edição</p>
      <p class="font-serif text-[15px] text-stone-700 mt-1">
        <span class="font-bold">{{ cards.length }}</span>
        {{ cards.length === 1 ? 'card' : 'cards' }}
        <span class="text-stone-400">·</span>
        <span class="font-bold">{{ withAM }}</span> com Apple Music
      </p>
    </header>

    <ul class="divide-y divide-stone-200">
      <li v-for="card in sortedCards" :key="card.id"
          class="py-2.5 flex items-center gap-3">
        <!-- Bucket dot (color-coded, tiny visual marker) -->
        <span :class="['w-2 h-2 rounded-full flex-shrink-0', bucketDot(card.bucket)]"
              :title="bucketLabel(card.bucket)"></span>

        <!-- Name + title + tipo, takes remaining space -->
        <button @click="$emit('navigate', card.id)"
                class="flex-1 min-w-0 text-left hover:opacity-80 transition-opacity"
                :aria-label="`Ir pra ${card.artista} — ${card.titulo}`">
          <p class="text-sm leading-tight truncate">
            <span class="font-bold text-stone-900">{{ card.artista || 'Artista desconhecido' }}</span>
            <span class="text-stone-400">—</span>
            <span class="italic text-stone-700">{{ card.titulo }}</span>
            <span v-if="card.tipo && card.tipo !== 'album'"
                  class="text-stone-400 text-xs ml-1">· {{ card.tipo }}</span>
          </p>
        </button>

        <!-- Apple Music link (only when present) -->
        <a v-if="card.links?.apple_music"
           :href="card.links.apple_music"
           target="_blank" rel="noopener"
           @click.stop="handleExternalLinkClick($event, card.links.apple_music)"
           class="text-xs font-semibold px-2 py-1 rounded
                  bg-emerald-50 text-emerald-800 border border-emerald-200
                  hover:bg-emerald-100 whitespace-nowrap min-h-[28px] flex items-center"
           aria-label="Abrir no Apple Music">
          ▶ AM
        </a>

        <!-- Jump-to-card arrow (always present) -->
        <button @click="$emit('navigate', card.id)"
                class="text-xs px-2 py-1 rounded border border-stone-300 text-stone-600
                       hover:text-stone-900 hover:border-stone-500 whitespace-nowrap
                       min-w-[32px] min-h-[28px]"
                aria-label="Ir pro card">
          →
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { bucketLabel } from '../utils/formatters.js'
import { handleExternalLinkClick } from '../utils/openLink.js'

const props = defineProps({
  cards: { type: Array, default: () => [] },
})
defineEmits(['navigate'])

// Color dot per bucket — same hues as the card left-edge accent in
// ReleaseCard, scaled down to a tiny dot for the scannable list.
function bucketDot(bucket) {
  const map = {
    alinhado:        'bg-emerald-600',
    media_afinidade: 'bg-amber-500',
    consensus:       'bg-violet-600',
  }
  return map[bucket] || 'bg-stone-400'
}

// Alphabetical by artist — ICU-aware so "Á" sorts with "A", "Ø" near "O".
// Empty artist (fallback "Artista desconhecido") sinks to the bottom.
const sortedCards = computed(() => {
  return [...props.cards].sort((a, b) => {
    const ar = (a.artista || '').trim()
    const br = (b.artista || '').trim()
    if (!ar && !br) return 0
    if (!ar) return 1
    if (!br) return -1
    return ar.localeCompare(br, 'pt-BR', { sensitivity: 'base' })
  })
})

const withAM = computed(
  () => props.cards.filter(c => c.links?.apple_music).length
)
</script>
