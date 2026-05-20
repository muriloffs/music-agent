<template>
  <article :id="card.id"
           :class="['border rounded-lg p-4 mb-3 transition', bucketColor(card.bucket)]">
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div class="flex items-start gap-3 flex-1 min-w-0">
        <img v-if="card.cover_image_url"
             :src="card.cover_image_url"
             :alt="`Capa de ${card.titulo}`"
             class="w-18 h-18 rounded shadow-sm flex-shrink-0 object-cover"
             style="width: 72px; height: 72px;"
             loading="lazy" />
        <div class="min-w-0">
          <h4 class="text-lg font-semibold">{{ card.artista || 'Artista desconhecido' }}</h4>
          <p class="text-stone-700">
            <span class="italic">{{ card.titulo }}</span>
            <span class="text-stone-500 ml-1">({{ card.tipo }})</span>
          </p>
        </div>
      </div>
      <div class="text-right text-xs text-stone-600">
        <div v-if="card.label">{{ card.label }}</div>
        <div v-if="card.afinidade_score">afinidade {{ card.afinidade_score }}/10</div>
        <div v-if="card._cache_fallback" class="mt-1 px-1 bg-amber-100 text-amber-900 rounded">cache</div>
      </div>
    </header>

    <!-- Tags row -->
    <div v-if="card.tags_estilo && card.tags_estilo.length" class="mt-2 flex flex-wrap gap-1">
      <span v-for="t in card.tags_estilo" :key="t"
            class="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200">
        {{ t }}
      </span>
    </div>

    <div class="mt-3 space-y-2 text-sm">
      <p v-if="card.resumo_critica"><span class="font-medium">Crítica:</span> {{ card.resumo_critica }}</p>
      <p v-if="card.na_discografia"><span class="font-medium">Discografia:</span> {{ card.na_discografia }}</p>
      <p v-if="card.letra_fala_sobre"><span class="font-medium">Letra:</span> {{ card.letra_fala_sobre }}</p>
      <p v-if="card.mudanca_musical"><span class="font-medium">Mudança musical:</span> {{ card.mudanca_musical }}</p>
      <p v-if="card.parecido_com && card.parecido_com.length">
        <span class="font-medium">Parecido com:</span> {{ card.parecido_com.join(' · ') }}
      </p>
      <p v-if="card.para_quem_gosta_de"><span class="font-medium">Pra quem curte:</span> {{ card.para_quem_gosta_de }}</p>
      <p v-if="card.prestar_atencao"><span class="font-medium">Prestar atenção:</span> {{ card.prestar_atencao }}</p>
      <p v-if="card.dados_curiosos"><span class="font-medium">Dados:</span> {{ card.dados_curiosos }}</p>
      <p v-if="card.faixas_principais && card.faixas_principais.length">
        <span class="font-medium">Faixas principais:</span> {{ card.faixas_principais.join(' · ') }}
      </p>
      <blockquote v-if="card.citacao_destacada"
                  class="border-l-2 border-stone-400 pl-3 py-1 italic text-stone-700">
        "{{ card.citacao_destacada.texto }}"
        <footer class="not-italic text-xs text-stone-500 mt-1">
          — {{ card.citacao_destacada.fonte }}<span v-if="card.citacao_destacada.nota"> ({{ card.citacao_destacada.nota }})</span>
        </footer>
      </blockquote>
      <blockquote v-if="card.verso_destacado"
                  class="border-l-2 border-stone-300 pl-3 py-1 italic text-stone-600">
        "{{ card.verso_destacado.texto }}"
        <footer v-if="card.verso_destacado.faixa" class="not-italic text-xs text-stone-500 mt-1">
          — faixa "{{ card.verso_destacado.faixa }}"
        </footer>
      </blockquote>
      <p v-if="card.o_que_nao_esperar" class="text-amber-900 bg-amber-50 px-2 py-1 rounded text-xs">
        <span class="font-medium">O que não esperar:</span> {{ card.o_que_nao_esperar }}
      </p>
      <p v-if="card.vale_pra_voce" class="font-medium text-stone-900 pt-2 border-t border-stone-100">{{ card.vale_pra_voce }}</p>
      <p v-if="card.historico_cobertura" class="text-xs text-stone-500">
        <span class="font-medium">No radar:</span> {{ card.historico_cobertura }}
      </p>
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
