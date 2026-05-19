<template>
  <article class="bg-white border border-stone-200 rounded-lg p-5 mb-4 shadow-sm">
    <header class="flex items-baseline gap-2 mb-2">
      <span v-if="destaque.is_destaque_principal"
            class="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-900 rounded">
        Destaque principal
      </span>
      <h3 class="text-xl font-serif font-semibold text-stone-900">{{ destaque.titulo_tema }}</h3>
    </header>
    <p class="text-stone-700 leading-relaxed">{{ destaque.prosa }}</p>
    <div v-if="referencedCards.length" class="mt-3 text-xs text-stone-500">
      Ver:
      <a v-for="c in referencedCards" :key="c.id"
         :href="`#${c.id}`"
         class="ml-2 underline hover:text-stone-900">
        {{ c.artista }} — {{ c.titulo }}
      </a>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  destaque: { type: Object, required: true },
  allCards: { type: Array, required: true },
})

const referencedCards = computed(() =>
  props.allCards.filter(c => (props.destaque.cards_referenciados || []).includes(c.id))
)
</script>
