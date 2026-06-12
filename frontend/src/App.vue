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
                  @change="(b) => navigate(b)" />

      <!-- Sticky no topo logo abaixo da SearchBar; só aparece quando o
           usuário veio da aba "Resumo" (composable rastreia previousTab). -->
      <TabBackButton />

      <!-- Pulso tab -->
      <section v-if="currentBucket === 'pulso'">
        <PulsoCard v-for="d in report.pulso_da_semana" :key="d.id || d.titulo_tema"
                   :destaque="d" :all-cards="report.cards"
                   @navigate="goToCard" />
        <div v-if="report.sequencia_sabado"
             class="mt-6 p-5 bg-emerald-50 border border-emerald-200 rounded-lg">
          <h3 class="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-800 mb-2">
            🎵 Pra esse sábado
          </h3>
          <p class="font-serif text-[15px] leading-relaxed text-stone-700">{{ report.sequencia_sabado.fluxo }}</p>
          <ol class="mt-3 space-y-1.5 text-sm text-stone-800 list-decimal list-inside">
            <li v-for="cid in report.sequencia_sabado.ordem" :key="cid">
              <!-- Era `<a href="#card_NNN">` simples, mas com o useTabHistory
                   o card alvo pode estar em outra aba e nem estar no DOM
                   atual; anchor scroll silenciosamente vira no-op. Botão
                   roteado por goToCard() faz navigate() com tab + scroll. -->
              <button type="button" @click="goToCard(cid)"
                      class="underline decoration-stone-300 hover:decoration-stone-600
                             text-left bg-transparent border-0 p-0 cursor-pointer">
                {{ cardLabelById(cid) }}
              </button>
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

      <!-- Listas editoriais da semana (roundups/playlists das fontes) -->
      <ListasView v-else-if="currentBucket === 'listas'"
                  :listas="report.listas_da_semana || []"
                  :current-date="report.relatorio_data"
                  @navigate="goToCard" />

      <!-- Resumo (lista alfabética com link AM + ir pro card) -->
      <IndexList v-else-if="currentBucket === 'lista'"
                 :cards="report.cards || []"
                 @navigate="goToCard" />

      <!-- Bucket / Estreias tabs -->
      <section v-else>
        <!-- Toggle global Compacto/Completo — preferência gruda em
             localStorage; cada card ainda abre/fecha individualmente. -->
        <div v-if="filteredCards.length" class="flex items-center justify-between mb-3">
          <p class="text-xs text-stone-400">{{ filteredCards.length }} {{ filteredCards.length === 1 ? 'card' : 'cards' }}</p>
          <button type="button" @click="toggleExpandedAll"
                  class="text-xs px-3 py-1.5 rounded-full border border-stone-300 bg-white
                         text-stone-600 hover:border-stone-500 hover:text-stone-900">
            {{ expandedAll ? '📖 Completo' : '📑 Compacto' }}
          </button>
        </div>
        <div v-if="filteredCards.length === 0" class="text-stone-500 italic font-serif">
          Nada nesta categoria esta semana.
        </div>
        <ReleaseCard v-for="c in filteredCards" :key="c.id" :card="c"
                     :relatorio-data="report.relatorio_data"
                     :expanded-default="expandedAll" />
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
import ListasView from './components/ListasView.vue'
import BackToTopButton from './components/BackToTopButton.vue'
import ArchiveDropdown from './components/ArchiveDropdown.vue'
import ReaderModal from './components/ReaderModal.vue'
import SearchBar from './components/SearchBar.vue'
import SearchResults from './components/SearchResults.vue'
import TabBackButton from './components/TabBackButton.vue'
import { useSearch } from './composables/useSearch.js'
import { useTabHistory } from './composables/useTabHistory.js'
import { formatDate, normalizeBucket } from './utils/formatters.js'
import { handleExternalLinkClick } from './utils/openLink.js'

const { isActive: searchActive } = useSearch()
// currentBucket vem do composable agora (singleton com history.pushState
// integrado). Mutar direto era OK até a feature do botão Voltar — a partir
// daqui qualquer mudança DEVE ir por navigate() ou setTab() pra manter
// previousTab consistente.
const { activeTab: currentBucket, navigate, setTab, init: initTabHistory,
        readUrl: readTabUrl } = useTabHistory()

const report = ref(null)
const loading = ref(true)
const error = ref(null)

// Modo compacto (manual modo-compacto-cards): default = compacto, a
// preferência do leitor persiste entre sessões via localStorage.
const expandedAll = ref(
  typeof localStorage !== 'undefined' && localStorage.getItem('cardsExpanded') === '1'
)
function toggleExpandedAll() {
  expandedAll.value = !expandedAll.value
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('cardsExpanded', expandedAll.value ? '1' : '0')
  }
}

// True when the URL carries ?r=YYYY-MM-DD — i.e., we're viewing an archived
// edition rather than the latest one. Drives the "voltar pra atual" link.
const viewingPast = computed(() => {
  if (typeof window === 'undefined') return false
  return /^\d{4}-\d{2}-\d{2}$/.test(new URLSearchParams(window.location.search).get('r') || '')
})

onMounted(async () => {
  // Inicializa o composable ANTES de qualquer fetch — assim activeTab e
  // history.state ficam corretos mesmo se o report demorar a carregar.
  initTabHistory()

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
  // Deep link recovery: a URL como /?r=DATA#card_NNN não carrega `&tab=`,
  // então o composable iniciou em 'pulso' (default). Se o card mora em
  // outra aba, faz uma troca SILENCIOSA (setTab — sem previousTab) pra não
  // fazer o botão Voltar aparecer dizendo "Voltar pra Pulso da Semana"
  // num link que o usuário simplesmente abriu de fora.
  setTimeout(() => {
    const initial = readTabUrl()
    if (!initial.itemId) return
    const cards = report.value?.cards || []
    const targetCard = cards.find(c => c.id === initial.itemId)
    if (targetCard && targetCard.bucket !== currentBucket.value) {
      setTab(targetCard.bucket, { itemId: initial.itemId })
    } else if (targetCard) {
      // Mesma aba: só scrolla.
      document.getElementById(initial.itemId)?.scrollIntoView(
        { behavior: 'smooth', block: 'start' },
      )
    }
  }, 200)
})

const bucketCounts = computed(() => {
  if (!report.value) return {}
  const cards = report.value.cards || []
  const counts = { pulso: (report.value.pulso_da_semana || []).length }
  // Conta pelo bucket NORMALIZADO — relatórios antigos (alinhado/media/
  // consensus) viram destaque_editorial pra contagem ficar consistente
  // entre edições novas e antigas.
  for (const c of cards) {
    const b = normalizeBucket(c.bucket)
    counts[b] = (counts[b] || 0) + 1
  }
  counts.lista = cards.length
  counts.estreias = cards.filter(c => c.is_estreia).length
  // Aba condicional 📜 Listas — some quando a semana não trouxe roundups.
  counts.listas = (report.value.listas_da_semana || []).length
  return counts
})

const filteredCards = computed(() => {
  if (!report.value) return []
  const cards = report.value.cards || []
  const bySore = (a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0)
  if (currentBucket.value === 'estreias') {
    return cards.filter(c => c.is_estreia).sort(bySore)
  }
  // Match pelo bucket normalizado pra relatórios antigos (alinhado/media/
  // consensus) também caírem em destaque_editorial.
  return cards.filter(c => normalizeBucket(c.bucket) === currentBucket.value)
              .sort(bySore)
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

// Disparado quando o usuário tapa numa linha da aba Resumo. navigate()
// cuida de: setar previousTab='lista' (porque vem daqui), trocar a aba,
// fazer pushState, e scrollar até o card depois do re-render.
function goToCard(cardId) {
  const c = (report.value?.cards || []).find(x => x.id === cardId)
  if (!c) return
  navigate(c.bucket, { itemId: cardId })
}
</script>
