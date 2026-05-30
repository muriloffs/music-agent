<template>
  <main class="max-w-3xl mx-auto px-4 py-10">
    <SearchBar />

    <SearchResults v-if="searchActive" />

    <template v-else>
    <header class="mb-9">
      <div class="flex items-start justify-between gap-4">
        <h1 class="text-4xl font-serif font-bold text-stone-900 tracking-tight">Music Agent</h1>
        <ArchiveDropdown :current-date="report?.relatorio_data || ''" />
      </div>
      <p v-if="report" class="mt-1.5 text-sm text-stone-500">
        Relatório de {{ formatDate(report.periodo_inicio) }} a {{ formatDate(report.periodo_fim) }}
        <a v-if="viewingPast" href="/"
           class="ml-2 text-xs text-stone-600 hover:text-stone-900 underline decoration-stone-300">
          ← voltar pra edição atual
        </a>
      </p>
    </header>

    <p v-if="loading" class="text-stone-600">Carregando relatório...</p>
    <p v-if="error" class="text-red-700">Erro: {{ error }}</p>

    <template v-if="report">
      <BucketTabs :current="currentBucket" :counts="bucketCounts"
                  @change="(b) => currentBucket = b" />

      <!-- Pulso tab -->
      <section v-if="currentBucket === 'pulso'">
        <PulsoCard v-for="d in report.pulso_da_semana" :key="d.id || d.titulo_tema"
                   :destaque="d" :all-cards="report.cards" />
        <div v-if="report.sequencia_sabado"
             class="mt-6 p-5 bg-emerald-50 border border-emerald-200 rounded-lg">
          <h3 class="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-800 mb-2">
            🎵 Pra esse sábado
          </h3>
          <p class="font-serif text-[15px] leading-relaxed text-stone-700">{{ report.sequencia_sabado.fluxo }}</p>
          <ol class="mt-3 space-y-1.5 text-sm text-stone-800 list-decimal list-inside">
            <li v-for="cid in report.sequencia_sabado.ordem" :key="cid">
              <a :href="`#${cid}`" class="underline decoration-stone-300 hover:decoration-stone-600">{{ cardLabelById(cid) }}</a>
              <a v-if="cardMusicUrl(cid)" :href="cardMusicUrl(cid)"
                 target="_blank" rel="noopener"
                 @click.stop="handleExternalLinkClick($event, cardMusicUrl(cid))"
                 class="ml-2 text-xs px-1.5 py-0.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 no-underline">
                ▶ ouvir
              </a>
            </li>
          </ol>
        </div>
      </section>

      <!-- Resumo (lista alfabética com link AM + ir pro card) -->
      <IndexList v-else-if="currentBucket === 'lista'"
                 :cards="report.cards || []"
                 @navigate="goToCard" />

      <!-- Bucket / Estreias tabs -->
      <section v-else>
        <div v-if="filteredCards.length === 0" class="text-stone-500 italic font-serif">
          Nada nesta categoria esta semana.
        </div>
        <ReleaseCard v-for="c in filteredCards" :key="c.id" :card="c"
                     :relatorio-data="report.relatorio_data" />
      </section>

      <!-- Footer stats -->
      <footer class="mt-14 pt-6 border-t border-stone-200 text-xs text-stone-400">
        <p>{{ report.stats.items_brutos_total }} items brutos · {{ report.stats.items_pos_dedup }} pós-dedup · {{ report.stats.items_no_relatorio }} no relatório · {{ report.stats.duracao_segundos }}s</p>
        <p class="mt-1">Fontes:
          <span v-for="(f, idx) in report.fontes_usadas" :key="f.id" class="ml-1">
            {{ f.id }} ({{ f.status }}{{ f.items_brutos ? ', ' + f.items_brutos : '' }}){{ idx < report.fontes_usadas.length - 1 ? ' · ' : '' }}
          </span>
        </p>
      </footer>
    </template>
    </template><!-- /v-else (normal view) -->

    <BackToTopButton />
    <ReaderModal />
  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PulsoCard from './components/PulsoCard.vue'
import ReleaseCard from './components/ReleaseCard.vue'
import BucketTabs from './components/BucketTabs.vue'
import IndexList from './components/IndexList.vue'
import BackToTopButton from './components/BackToTopButton.vue'
import ArchiveDropdown from './components/ArchiveDropdown.vue'
import ReaderModal from './components/ReaderModal.vue'
import SearchBar from './components/SearchBar.vue'
import SearchResults from './components/SearchResults.vue'
import { useSearch } from './composables/useSearch.js'
import { formatDate } from './utils/formatters.js'
import { handleExternalLinkClick } from './utils/openLink.js'

const { isActive: searchActive } = useSearch()

const report = ref(null)
const loading = ref(true)
const error = ref(null)
const currentBucket = ref('pulso')

// True when the URL carries ?r=YYYY-MM-DD — i.e., we're viewing an archived
// edition rather than the latest one. Drives the "voltar pra atual" link.
const viewingPast = computed(() => {
  if (typeof window === 'undefined') return false
  return /^\d{4}-\d{2}-\d{2}$/.test(new URLSearchParams(window.location.search).get('r') || '')
})

onMounted(async () => {
  try {
    // ?r=YYYY-MM-DD loads that week's archived report (permalink from a
    // Things task / WhatsApp share); no param = the latest report.
    const params = new URLSearchParams(window.location.search)
    const r = params.get('r')
    const apiUrl = (r && /^\d{4}-\d{2}-\d{2}$/.test(r))
      ? `/api/report?date=${r}`
      : '/api/report'
    const resp = await fetch(apiUrl)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    report.value = await resp.json()
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
  // Deep link: opening /#card_NNN scrolls to that card, switching to its
  // bucket tab first if needed (WhatsApp shares land on the right place).
  if (typeof window !== 'undefined' && window.location.hash) {
    const targetId = window.location.hash.slice(1)
    setTimeout(() => {
      const cards = report.value?.cards || []
      const targetCard = cards.find(c => c.id === targetId)
      if (targetCard && targetCard.bucket !== currentBucket.value) {
        currentBucket.value = targetCard.bucket
        setTimeout(() => document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120)
      } else {
        document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
  // Resumo lists every card (alphabetical scan view).
  counts.lista = cards.length
  // estreias is a cross-bucket filter, not a real bucket
  counts.estreias = cards.filter(c => c.is_estreia).length
  return counts
})

const filteredCards = computed(() => {
  if (!report.value) return []
  const cards = report.value.cards || []
  const bySore = (a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0)
  if (currentBucket.value === 'estreias') {
    return cards.filter(c => c.is_estreia).sort(bySore)
  }
  return cards.filter(c => c.bucket === currentBucket.value).sort(bySore)
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

// Called from the Resumo list when the user taps an artist row or the →
// button. Switches to that card's bucket tab (so the card is actually in
// the DOM), then scrolls to it. nextTick-style wait is implemented as a
// small setTimeout — Vue re-renders after the bucket change, then the
// scroll target appears.
function goToCard(cardId) {
  const c = (report.value?.cards || []).find(x => x.id === cardId)
  if (!c) return
  if (c.bucket !== currentBucket.value) {
    currentBucket.value = c.bucket
    setTimeout(() => {
      document.getElementById(cardId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  } else {
    document.getElementById(cardId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}
</script>
