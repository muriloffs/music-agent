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
      <BucketTabs :current="currentBucket" :counts="bucketCounts"
                  :genre-tabs="dynamicGenreTabs"
                  @change="(b) => currentBucket = b" />

      <!-- Pulso tab -->
      <section v-if="currentBucket === 'pulso'">
        <PulsoCard v-for="d in report.pulso_da_semana" :key="d.id || d.titulo_tema"
                   :destaque="d" :all-cards="report.cards" />
        <div v-if="report.sequencia_sabado"
             class="mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
          <h3 class="text-sm font-medium text-emerald-900 mb-1">🎵 Pra esse sábado</h3>
          <p class="text-sm text-stone-700">{{ report.sequencia_sabado.fluxo }}</p>
          <ol class="mt-2 text-sm text-emerald-900 list-decimal list-inside">
            <li v-for="cid in report.sequencia_sabado.ordem" :key="cid">
              <a :href="`#${cid}`" class="underline">{{ cardLabelById(cid) }}</a>
              <a v-if="cardMusicUrl(cid)" :href="cardMusicUrl(cid)"
                 target="_blank" rel="noopener"
                 class="ml-2 text-xs px-1.5 py-0.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 no-underline">
                ▶ ouvir
              </a>
            </li>
          </ol>
        </div>
      </section>

      <!-- Bucket tabs (other than pulso) -->
      <section v-else>
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
    <BackToTopButton />
  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PulsoCard from './components/PulsoCard.vue'
import ReleaseCard from './components/ReleaseCard.vue'
import BucketTabs from './components/BucketTabs.vue'
import BackToTopButton from './components/BackToTopButton.vue'
import { formatDate, cardGenres, genreLabel, GENRE_KEYS } from './utils/formatters.js'

const GENRE_TAB_THRESHOLD = 5

const report = ref(null)
const loading = ref(true)
const error = ref(null)
const currentBucket = ref('pulso')

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
  // After data loads + Vue renders, scroll to anchor if URL has one
  if (typeof window !== 'undefined' && window.location.hash) {
    const targetId = window.location.hash.slice(1)
    // Wait next tick + a bit more for v-for to render
    setTimeout(() => {
      const el = document.getElementById(targetId)
      if (el) {
        // If anchor card is in a bucket that's not current, switch tab
        const cards = report.value?.cards || []
        const targetCard = cards.find(c => c.id === targetId)
        if (targetCard && targetCard.bucket !== currentBucket.value) {
          currentBucket.value = targetCard.bucket
          // re-wait for render
          setTimeout(() => document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
        } else {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }
    }, 200)
  }
})

const bucketCounts = computed(() => {
  if (!report.value) return {}
  const cards = report.value.cards || []
  const counts = { pulso: (report.value.pulso_da_semana || []).length }
  for (const c of cards) {
    counts[c.bucket] = (counts[c.bucket] || 0) + 1
  }
  // virtual buckets — cross-cutting filters
  counts.estreias = cards.filter(c => c.is_estreia).length
  counts.laureados = cards.filter(c => (c.selos_editoriais || []).length > 0).length
  // genre counts
  for (const c of cards) {
    for (const gKey of cardGenres(c)) {
      counts[gKey] = (counts[gKey] || 0) + 1
    }
  }
  return counts
})

const dynamicGenreTabs = computed(() => {
  if (!report.value) return []
  const cards = report.value.cards || []
  const genreCounts = {}
  for (const c of cards) {
    for (const gKey of cardGenres(c)) {
      genreCounts[gKey] = (genreCounts[gKey] || 0) + 1
    }
  }
  return GENRE_KEYS
    .filter(key => (genreCounts[key] || 0) >= GENRE_TAB_THRESHOLD)
    .map(key => ({ key, label: genreLabel(key), count: genreCounts[key] }))
})

const filteredCards = computed(() => {
  if (!report.value) return []
  const cards = report.value.cards || []
  if (currentBucket.value === 'estreias') {
    return cards.filter(c => c.is_estreia)
      .sort((a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0))
  }
  if (currentBucket.value === 'laureados') {
    return cards.filter(c => (c.selos_editoriais || []).length > 0)
      .sort((a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0))
  }
  if (GENRE_KEYS.includes(currentBucket.value)) {
    return cards.filter(c => cardGenres(c).has(currentBucket.value))
      .sort((a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0))
  }
  return cards
    .filter(c => c.bucket === currentBucket.value)
    .sort((a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0))
})

function cardLabelById(id) {
  const c = (report.value?.cards || []).find(x => x.id === id)
  return c ? `${c.artista} — ${c.titulo}` : id
}

function cardMusicUrl(id) {
  const c = (report.value?.cards || []).find(x => x.id === id)
  if (!c) return null
  return (c.links && (c.links.apple_music || c.links.spotify)) || null
}
</script>
