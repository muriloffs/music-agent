// useSearch.js — module-level singleton state for full-history search.
// Adapted from docs/manuais/modo-pesquisa-historico-manual.md.
//
// Two types of searchable item in music-agent:
//   - 'release' = a card from report.cards (artist editorial card)
//   - 'pulso'   = a destaque from report.pulso_da_semana (weekly highlight)
//
// Lazy-loads every committed report on first focus, caches in memory, filters
// by substring (NFD-normalized so "acai" matches "açaí", etc).

import { computed, ref } from 'vue'
import { fetchIndex, fetchReportByDate } from '../utils/api.js'

const query = ref('')
const allReports = ref(new Map())   // date -> report JSON
const loading = ref(false)
const loaded = ref(false)
const loadError = ref(null)

// NFD decomposes accented chars (é → e + combining acute); the regex strips
// the combining marks. Result: case- and accent-insensitive matching.
function normalize(text) {
  if (!text) return ''
  return String(text).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

// Explicit per-type field list — NEVER Object.values(item). Including URLs,
// IDs, scores, etc. would make searches match on irrelevant noise like
// "card_042" or apple.com.
function extractSearchableText(item, type) {
  if (!item) return ''
  const parts = []
  const push = (v) => {
    if (!v) return
    if (Array.isArray(v)) v.forEach(push)
    else if (typeof v === 'string') parts.push(v)
    else if (typeof v === 'number') parts.push(String(v))
    else if (typeof v === 'object') {
      // Shallow walk — items have nested dicts like citacao_destacada{texto,fonte}
      Object.values(v).forEach((vv) => typeof vv === 'string' && parts.push(vv))
    }
  }

  push(item.artista)
  push(item.titulo)
  push(item.tipo)
  push(item.label)

  if (type === 'release') {
    push(item.tags_estilo)
    push(item.resumo_critica)
    push(item.razao_curta_classify)
    push(item.na_discografia)
    push(item.letra_fala_sobre)
    push(item.mudanca_musical)
    push(item.parecido_com)
    push(item.para_quem_gosta_de)
    push(item.faixas_principais)
    push(item.prestar_atencao)
    push(item.dados_curiosos)
    push(item.o_que_nao_esperar)
    push(item.vale_pra_voce)
    push(item.historico_cobertura)
    // Quote dicts ({texto, fonte} / {texto, faixa})
    if (item.citacao_destacada) push(item.citacao_destacada.texto)
    if (item.verso_destacado) push(item.verso_destacado.texto)
    // Seal dicts (fonte + tipo are searchable; nota is numeric, skip)
    if (Array.isArray(item.selos_editoriais)) {
      for (const s of item.selos_editoriais) {
        push(s.fonte)
        push(s.tipo)
      }
    }
  } else if (type === 'pulso') {
    push(item.titulo_tema)
    push(item.texto)
    push(item.por_que_destacar)
    push(item.tema)
  } else if (type === 'lista') {
    push(item.resumo)
    // Itens podem ser strings ("Artista — Obra") ou objetos estruturados;
    // só os campos textuais entram — URLs de apple_music NÃO são indexadas
    // (buscar "music" não pode casar com toda lista por causa dos links).
    for (const it of item.itens || []) {
      if (typeof it === 'string') push(it)
      else if (it) { push(it.texto); push(it.artista); push(it.obra) }
    }
    push(item.fonte_id)
  }

  return parts.join(' ')
}

function* iterReportItems(report) {
  if (!report) return
  for (const c of report.cards || []) yield { type: 'release', item: c }
  for (const p of report.pulso_da_semana || []) yield { type: 'pulso', item: p }
  for (const l of report.listas_da_semana || []) yield { type: 'lista', item: l }
}

function buildSnippet(haystack, needleNorm, contextChars = 80) {
  if (!haystack) return ''
  const norm = normalize(haystack)
  const idx = norm.indexOf(needleNorm)
  if (idx === -1) return haystack.slice(0, 160)
  const start = Math.max(0, idx - contextChars)
  const end = Math.min(haystack.length, idx + needleNorm.length + contextChars)
  let snip = haystack.slice(start, end)
  if (start > 0) snip = '… ' + snip
  if (end < haystack.length) snip = snip + ' …'
  return snip
}

async function loadAllReports() {
  if (loaded.value || loading.value) return
  loading.value = true
  loadError.value = null
  try {
    const dates = await fetchIndex()
    // Promise.allSettled — a single 404 or transient fetch failure must NOT
    // wipe out the whole search. Indexes whatever loads; logs the rest.
    const settled = await Promise.allSettled(
      dates.map((d) => fetchReportByDate(d).then((r) => [d, r]))
    )
    const map = new Map()
    let failed = 0
    for (const r of settled) {
      if (r.status === 'fulfilled') {
        const [date, report] = r.value
        map.set(date, report)
      } else {
        failed++
      }
    }
    allReports.value = map
    loaded.value = true
    if (failed) {
      // Soft warning — search still works on what loaded
      // eslint-disable-next-line no-console
      console.warn(`useSearch: ${failed}/${dates.length} reports failed to load`)
    }
  } catch (e) {
    loadError.value = e?.message || 'Falha ao carregar histórico'
  } finally {
    loading.value = false
  }
}

const isActive = computed(() => query.value.trim().length >= 2)

const results = computed(() => {
  if (!isActive.value) return []
  const needle = normalize(query.value.trim())
  if (!needle) return []
  const out = []
  for (const [date, report] of allReports.value.entries()) {
    for (const { type, item } of iterReportItems(report)) {
      const text = extractSearchableText(item, type)
      if (!text) continue
      if (normalize(text).includes(needle)) {
        out.push({ date, type, item, snippet: buildSnippet(text, needle) })
      }
    }
  }
  return out
})

const resultsByDate = computed(() => {
  // Map preserves insertion order — since allReports is built from /api/reports
  // which returns newest-first, this groups newest-first too.
  const g = new Map()
  for (const r of results.value) {
    if (!g.has(r.date)) g.set(r.date, [])
    g.get(r.date).push(r)
  }
  return g
})

const resultsByType = computed(() => {
  const c = {}
  for (const r of results.value) c[r.type] = (c[r.type] || 0) + 1
  return c
})

const daysIndexed = computed(() => allReports.value.size)

export function useSearch() {
  return {
    query, loading, loaded, loadError, isActive,
    results, resultsByDate, resultsByType, daysIndexed,
    loadAllReports,
    clear() { query.value = '' },
  }
}

// Exported for testing / SearchResults <mark> rendering.
export { normalize, extractSearchableText, buildSnippet }
