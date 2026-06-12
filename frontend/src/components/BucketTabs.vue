<template>
  <nav class="flex flex-wrap gap-2 mb-8 sticky top-0 bg-stone-50/95 backdrop-blur py-3 z-10 -mx-4 px-4">
    <button v-for="b in visibleBuckets" :key="b.key"
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
import { computed } from 'vue'

const props = defineProps({
  current: { type: String, required: true },
  counts:  { type: Object, default: () => ({}) },
})
defineEmits(['change'])

// Abas (nova arquitetura desde 2026-06-08). O eixo editorial mudou: o
// classify não bucketiza mais por afinidade-com-gosto (que falsava
// positivos em ambient/jazz/electronic indiscriminados); agora bucketiza
// por FORÇA do destaque editorial nas fontes. Há uma whitelist de
// artistas — quando bate, vai pra aba "Dos seus artistas".
//   - Pulso             editorial (curadoria semanal do LLM)
//   - Dos seus artistas whitelist explícita; CONDICIONAL (só aparece se >=1)
//   - Destaques         selo nomeado / nota / cobertura múltipla
//   - Estreias          is_estreia=true + sinal editorial
//   - Resumo            scan alfabético utilitário
const BUCKETS = [
  { key: 'pulso',              label: '📌 Pulso da Semana' },
  { key: 'meus_artistas',      label: '⭐ Dos seus artistas', conditional: true },
  { key: 'destaque_editorial', label: '🏆 Destaques editoriais' },
  { key: 'estreias',           label: '🎬 Estreias' },
  { key: 'listas',             label: '📜 Listas', conditional: true },
  { key: 'lista',              label: '📋 Resumo' },
]

// "Dos seus artistas" some quando não tem ninguém — semana sem disco da
// sua lista de artistas favoritos não polui o menu com aba vazia.
const visibleBuckets = computed(() =>
  BUCKETS.filter(b => !b.conditional || (props.counts[b.key] || 0) > 0)
)
</script>
