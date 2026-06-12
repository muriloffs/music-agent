<template>
  <section>
    <article v-for="l in listas" :key="l.id"
             class="bg-white border border-stone-200 border-l-4 border-l-teal-600
                    rounded-r-lg rounded-l-sm shadow-[0_1px_3px_rgba(0,0,0,0.04)]
                    mb-5 overflow-hidden p-5">
      <header class="mb-2">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-[10px] font-semibold uppercase tracking-[0.13em] text-teal-800">
            {{ sourceLabel(l.fonte_id) }}
          </span>
          <span class="text-[10px] uppercase tracking-[0.13em] text-stone-400">
            · 📜 lista {{ l.tipo_lista }}
          </span>
        </div>
        <h2 class="font-serif text-[1.25rem] leading-tight font-bold text-stone-900">
          {{ l.titulo }}
        </h2>
      </header>

      <p v-if="l.resumo" class="font-serif text-[15px] leading-relaxed text-stone-700 mb-3">
        {{ l.resumo }}
      </p>

      <!-- Itens extraídos do artigo, na ordem da fonte -->
      <ol v-if="l.itens && l.itens.length"
          class="space-y-1 mb-3 list-decimal list-inside marker:text-stone-400 marker:text-xs">
        <li v-for="(item, i) in l.itens" :key="i"
            class="font-serif text-[14.5px] leading-relaxed text-stone-800">
          {{ item }}
        </li>
      </ol>
      <p v-else class="text-stone-400 italic text-sm mb-3">
        Itens não extraídos — abra a fonte pra ver a lista completa.
      </p>

      <a :href="l.url" target="_blank" rel="noopener"
         @click.stop="handleExternalLinkClick($event, l.url)"
         class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100 inline-block">
        🔗 Ler na {{ sourceLabel(l.fonte_id) }}
      </a>
    </article>

    <p v-if="!listas.length" class="text-stone-500 italic font-serif">
      Nenhuma lista editorial esta semana.
    </p>
  </section>
</template>

<script setup>
import { sourceLabel } from '../utils/formatters.js'
import { handleExternalLinkClick } from '../utils/openLink.js'

defineProps({
  listas: { type: Array, default: () => [] },
})
</script>
