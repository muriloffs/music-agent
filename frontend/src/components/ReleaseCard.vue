<template>
  <article :id="card.id"
           :class="['border rounded-lg p-4 mb-3 transition', bucketColor(card.bucket)]">
    <header class="flex flex-wrap items-baseline justify-between gap-2">
      <div>
        <h4 class="text-lg font-semibold">{{ card.artista || 'Artista desconhecido' }}</h4>
        <p class="text-stone-700">
          <span class="italic">{{ card.titulo }}</span>
          <span class="text-stone-500 ml-1">({{ card.tipo }})</span>
        </p>
      </div>
      <div class="text-right text-xs text-stone-600">
        <div v-if="card.label">{{ card.label }}</div>
        <div v-if="card.afinidade_score">afinidade {{ card.afinidade_score }}/10</div>
        <div v-if="card._cache_fallback" class="mt-1 px-1 bg-amber-100 text-amber-900 rounded">cache</div>
      </div>
    </header>

    <div class="mt-3 space-y-2 text-sm">
      <p v-if="card.resumo_critica"><span class="font-medium">Crítica:</span> {{ card.resumo_critica }}</p>
      <p v-if="card.parecido_com && card.parecido_com.length">
        <span class="font-medium">Parecido com:</span> {{ card.parecido_com.join(' · ') }}
      </p>
      <p v-if="card.prestar_atencao"><span class="font-medium">Prestar atenção:</span> {{ card.prestar_atencao }}</p>
      <p v-if="card.dados_curiosos"><span class="font-medium">Dados:</span> {{ card.dados_curiosos }}</p>
      <p v-if="card.vale_pra_voce" class="font-medium text-stone-900">{{ card.vale_pra_voce }}</p>
    </div>

    <LinksRow :links="card.links" />
    <FontesFooter :fontes="card.fontes_cobertura" />
  </article>
</template>

<script setup>
import LinksRow from './LinksRow.vue'
import FontesFooter from './FontesFooter.vue'
import { bucketColor } from '../utils/formatters.js'

defineProps({ card: { type: Object, required: true } })
</script>
