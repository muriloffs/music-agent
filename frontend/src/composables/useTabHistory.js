// useTabHistory.js — singleton composable que gerencia a aba ativa
// (activeTab) via URL + history.pushState. Expõe previousTab pra que o
// botão "← Voltar" possa saber de onde o usuário veio.
//
// Adaptado do manual culture-agent (docs/manuais/botao-voltar-aba-manual.md).
// Convenções deste app:
//   - Aba default: 'pulso' (no manual era 'resumo').
//   - Aba-índice: 'lista' (no manual era 'resumo').
//   - URL: ?r=YYYY-MM-DD&tab=X#card_NNN (manual usava ?date=…#item-X).
//
// Por que o composable é singleton (refs module-level): a tab ativa é um
// fato global do app — qualquer componente que renderiza/escuta precisa da
// mesma instância. Sem o singleton, `useTabHistory()` em dois lugares
// criaria estados separados que silenciosamente divergem.

import { computed, nextTick, ref } from 'vue'

const DEFAULT_TAB = 'pulso'

// Labels editoriais das abas — usado pra montar "Voltar para [label]".
// Espelhar do BucketTabs.vue (qualquer mudança lá precisa refletir aqui).
// Os labels legados ficam aqui também pra que relatórios antigos
// (?r=2026-05-30 etc.) continuem rotulando corretamente quando navegados.
const TAB_LABELS = {
  pulso:              '📌 Pulso da Semana',
  meus_artistas:      '⭐ Dos seus artistas',
  destaque_editorial: '🏆 Destaques editoriais',
  estreias:           '🎬 Estreias',
  listas:             '📜 Listas',
  playlist:           '▶️ Playlist',
  lista:              '📋 Resumo',
  // legacy — caem em "Destaques" mas mantêm rótulo descritivo se acessados
  alinhado:           '🏆 Destaques editoriais',
  media_afinidade:    '🏆 Destaques editoriais',
  consensus:          '🏆 Destaques editoriais',
}

const activeTab = ref(DEFAULT_TAB)
const previousTab = ref(null)
const scrollByTab = new Map()
let _initialized = false

const previousTabLabel = computed(
  () => previousTab.value && TAB_LABELS[previousTab.value],
)

// Lê a URL atual em forma estruturada. Default `tab` é o pulso pra cobrir
// links externos que vêm sem `?tab=`. Hash esperado: `#card_NNN`.
function readUrl() {
  const params = new URLSearchParams(window.location.search)
  const hash = window.location.hash || ''
  const m = hash.match(/^#(card_\w+)$/)
  return {
    r:      params.get('r') || null,
    tab:    params.get('tab') || DEFAULT_TAB,
    itemId: m ? m[1] : null,
  }
}

// Monta uma URL canônica. Omitimos `tab=` quando é o default pra deixar a
// URL limpa quando não precisa ("/?r=2026-05-30" em vez de "/?r=…&tab=pulso").
function buildUrl(tab, itemId, r) {
  const params = new URLSearchParams()
  if (r) params.set('r', r)
  if (tab && tab !== DEFAULT_TAB) params.set('tab', tab)
  const qs = params.toString()
  let url = qs ? `/?${qs}` : '/'
  if (itemId) url += `#${itemId}`
  return url
}

// Scrolla até o card alvo ou (se ausente) até a posição salva na aba.
// `id` do DOM dos cards no music-agent é o id literal (`card_NNN`); o
// itemId que carregamos da URL JÁ é esse id, sem prefixo extra.
async function _scrollToItemOrTop(itemId, fallbackY = 0) {
  await nextTick()
  if (itemId) {
    let el = document.getElementById(itemId)
    if (!el) {
      // Aba destino pode ainda não ter renderizado todos os cards (Vue
      // lazy). Espera 120ms e tenta de novo — resolve race condition
      // silenciosa que aparece principalmente em mobile lento.
      await new Promise((r) => setTimeout(r, 120))
      el = document.getElementById(itemId)
    }
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
  }
  window.scrollTo({ top: fallbackY, behavior: 'instant' })
}

// API principal de navegação. SEMPRE prefira chamar isto a mutar
// activeTab diretamente — o composable cuida de pushState + previousTab.
async function navigate(targetTab, { itemId = null, r } = {}) {
  if (typeof window !== 'undefined') {
    scrollByTab.set(activeTab.value, window.scrollY)
  }
  const origin = activeTab.value
  const sameTab = origin === targetTab

  if (!sameTab) previousTab.value = origin
  activeTab.value = targetTab

  const currentR = r !== undefined
    ? r
    : new URLSearchParams(window.location.search).get('r')

  const url = buildUrl(targetTab, itemId, currentR)
  const state = {
    tab: targetTab,
    itemId,
    r: currentR,
    // Se ficamos na mesma aba (só mudou itemId), preserva previousTab.
    // Senão, registra a origem.
    previousTab: sameTab ? (window.history.state?.previousTab || null) : origin,
  }

  if (sameTab && !itemId) {
    history.replaceState(state, '', url)
  } else {
    history.pushState(state, '', url)
  }
  await _scrollToItemOrTop(itemId, scrollByTab.get(targetTab) || 0)
}

// Versão silenciosa: troca de aba SEM empilhar histórico e SEM marcar
// previousTab. Usado quando o usuário chega via deep link tipo
// `?r=…#card_NNN` (sem `&tab=`) e o card mora numa aba diferente do
// default — App.vue detecta após carregar os dados e ajusta a URL no lugar.
function setTab(tab, { itemId = null } = {}) {
  if (typeof window !== 'undefined') {
    scrollByTab.set(activeTab.value, window.scrollY)
  }
  activeTab.value = tab
  const currentR = new URLSearchParams(window.location.search).get('r')
  const url = buildUrl(tab, itemId, currentR)
  history.replaceState({
    tab,
    itemId,
    r: currentR,
    previousTab: window.history.state?.previousTab || null,
  }, '', url)
  _scrollToItemOrTop(itemId, scrollByTab.get(tab) || 0)
}

async function _handlePopstate(event) {
  const state = event.state || readUrl()
  scrollByTab.set(activeTab.value, window.scrollY)
  activeTab.value = state.tab || DEFAULT_TAB
  previousTab.value = state.previousTab || null
  await _scrollToItemOrTop(state.itemId, scrollByTab.get(activeTab.value) || 0)
}

// Botão sticky chama isto. Sempre que possível, dispara history.back() —
// assim o popstate cuida da restauração com a MESMA lógica do Voltar
// nativo do navegador. Fallback: deep link compartilhado (histórico de 1
// entrada) não consegue back, então fazemos um replaceState pro previousTab.
function goBack() {
  const target = previousTab.value
  if (window.history.length > 1) {
    window.history.back()
  } else if (target) {
    const url = buildUrl(target, null,
      new URLSearchParams(window.location.search).get('r'))
    const state = { tab: target, itemId: null, r: null, previousTab: null }
    history.replaceState(state, '', url)
    scrollByTab.set(activeTab.value, window.scrollY)
    activeTab.value = target
    previousTab.value = null
    _scrollToItemOrTop(null, scrollByTab.get(target) || 0)
  }
}

function init() {
  if (_initialized) return
  _initialized = true
  window.addEventListener('popstate', _handlePopstate)
  const initial = readUrl()
  activeTab.value = initial.tab
  previousTab.value = window.history.state?.previousTab || null
  const url = buildUrl(initial.tab, initial.itemId, initial.r)
  history.replaceState({
    tab: initial.tab,
    itemId: initial.itemId,
    r: initial.r,
    previousTab: previousTab.value,
  }, '', url)
}

export function useTabHistory() {
  return {
    activeTab, previousTab, previousTabLabel,
    navigate, setTab, goBack, init, readUrl,
  }
}
