<template>
  <main class="max-w-3xl mx-auto px-4 py-8">
    <header class="mb-8">
      <h1 class="text-3xl font-serif font-bold text-stone-900">Music Agent</h1>
      <p v-if="report" class="mt-1 text-sm text-stone-600">
        Relatório de {{ formatDate(report.periodo_inicio) }} a {{ formatDate(report.periodo_fim) }}
      </p>
    </header>

    <p v-if="loading" class="text-stone-600">Carregando relatório...</p>
    <p v-if="error" class="text-red-700">Erro: {{ error }}</p>

    <template v-if="report">
      <!-- Pulso da Semana -->
      <section class="mb-10">
        <h2 class="text-xl font-serif font-semibold text-stone-900 mb-4">Pulso da Semana</h2>
        <PulsoCard v-for="d in report.pulso_da_semana" :key="d.id || d.titulo_tema"
                   :destaque="d" :all-cards="report.cards" />
        <div v-if="report.sequencia_sabado"
             class="mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
          <h3 class="text-sm font-medium text-emerald-900 mb-1">Pra esse sábado</h3>
          <p class="text-sm text-stone-700">{{ report.sequencia_sabado.fluxo }}</p>
          <ol class="mt-2 text-sm text-emerald-900 list-decimal list-inside">
            <li v-for="cid in report.sequencia_sabado.ordem" :key="cid">
              <a :href="`#${cid}`" class="underline">{{ cardLabelById(cid) }}</a>
            </li>
          </ol>
        </div>
      </section>

      <!-- Arquivo navegável -->
      <section>
        <h2 class="text-xl font-serif font-semibold text-stone-900 mb-4">Arquivo da Semana</h2>
        <BucketTabs :current="currentBucket" :counts="bucketCounts"
                    @change="(b) => currentBucket = b" />
        <div v-if="filteredCards.length === 0" class="text-stone-500 italic">
          Nada nesta categoria esta semana.
        </div>
        <ReleaseCard v-for="c in filteredCards" :key="c.id" :card="c" />
      </section>

      <!-- Footer stats -->
      <footer class="mt-12 pt-6 border-t border-stone-200 text-xs text-stone-500">
        <p>{{ report.stats.items_brutos_total }} items brutos · {{ report.stats.items_pos_dedup }} pós-dedup · {{ report.stats.items_no_relatorio }} no relatório · {{ report.stats.duracao_segundos }}s</p>
        <p class="mt-1">Fontes:
          <span v-for="(f, idx) in report.fontes_usadas" :key="f.id" class="ml-1">
            {{ f.id }} ({{ f.status }}{{ f.items_brutos ? ', ' + f.items_brutos : '' }}){{ idx < report.fontes_usadas.length - 1 ? ' · ' : '' }}
          </span>
        </p>
      </footer>
    </template>
  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PulsoCard from './components/PulsoCard.vue'
import ReleaseCard from './components/ReleaseCard.vue'
import BucketTabs from './components/BucketTabs.vue'
import { formatDate } from './utils/formatters.js'

const report = ref(null)
const loading = ref(true)
const error = ref(null)
const currentBucket = ref('alinhado')

onMounted(async () => {
  try {
    const resp = await fetch('/api/report')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    report.value = await resp.json()
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
})

const bucketCounts = computed(() => {
  if (!report.value) return {}
  const counts = {}
  for (const c of report.value.cards) {
    counts[c.bucket] = (counts[c.bucket] || 0) + 1
  }
  return counts
})

const filteredCards = computed(() => {
  if (!report.value) return []
  return report.value.cards
    .filter(c => c.bucket === currentBucket.value)
    .sort((a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0))
})

function cardLabelById(id) {
  const c = (report.value?.cards || []).find(x => x.id === id)
  return c ? `${c.artista} — ${c.titulo}` : id
}
</script>
