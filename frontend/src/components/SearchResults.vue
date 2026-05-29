<template>
  <section class="max-w-3xl mx-auto">
    <!-- Status bar: count + per-type chips -->
    <header class="mb-5">
      <p class="text-xs uppercase tracking-[0.13em] text-stone-500">
        Busca em {{ daysIndexed }} {{ daysIndexed === 1 ? 'edição' : 'edições' }}
      </p>
      <p class="font-serif text-[20px] text-stone-900 mt-1">
        <span class="font-bold">{{ results.length }}</span>
        {{ results.length === 1 ? 'resultado' : 'resultados' }} para
        <span class="italic">"{{ query }}"</span>
      </p>
      <div v-if="Object.keys(resultsByType).length" class="flex flex-wrap gap-2 mt-3">
        <span v-for="(count, type) in resultsByType" :key="type"
              class="text-[11px] uppercase tracking-[0.1em] px-2 py-0.5 rounded
                     bg-stone-100 text-stone-600">
          {{ typeLabel(type) }}: {{ count }}
        </span>
      </div>
    </header>

    <p v-if="loading" class="text-stone-600 italic">Carregando edições…</p>
    <p v-else-if="loadError" class="text-red-700">Erro: {{ loadError }}</p>
    <p v-else-if="!results.length"
       class="text-stone-500 font-serif italic">
      Nada encontrado em "{{ query }}".
    </p>

    <!-- Results grouped by date (newest first via Map iteration order) -->
    <div v-for="[date, dateResults] in resultsByDate" :key="date" class="mb-8">
      <h3 class="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-800 mb-2">
        {{ formatDate(date) }}
      </h3>
      <article v-for="r in dateResults" :key="`${date}-${r.type}-${itemKey(r)}`"
               class="border-l-2 border-stone-200 pl-4 py-2 mb-3">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-[10px] uppercase tracking-[0.13em] font-semibold
                       px-1.5 py-0.5 rounded bg-stone-100 text-stone-600">
            {{ typeLabel(r.type) }}
          </span>
          <a :href="resultLink(date, r)"
             class="font-serif text-[16px] text-stone-900 hover:underline
                    decoration-amber-400 underline-offset-2">
            <span v-if="r.item.artista" class="font-bold">{{ r.item.artista }}</span>
            <span v-if="r.item.artista && (r.item.titulo || r.item.titulo_tema)"> — </span>
            <span class="italic">{{ r.item.titulo || r.item.titulo_tema }}</span>
          </a>
        </div>
        <p class="font-serif text-[14px] leading-relaxed text-stone-700"
           v-html="highlightSnippet(r.snippet, query)"></p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { useSearch } from '../composables/useSearch.js'
import { formatDate } from '../utils/formatters.js'

const { query, loading, loadError, results, resultsByDate, resultsByType,
        daysIndexed } = useSearch()

const TYPE_LABELS = { release: 'Card', pulso: 'Pulso' }
function typeLabel(t) { return TYPE_LABELS[t] || t }

function itemKey(r) {
  return r.item.id || r.item.titulo_tema || r.item.titulo || Math.random().toString(36)
}

function resultLink(date, r) {
  // Releases deep-link to the specific card; pulso highlights just open
  // the report on the default Pulso tab.
  if (r.type === 'release' && r.item.id) return `/?r=${date}#${r.item.id}`
  return `/?r=${date}`
}

// --- Highlight: NFD-aware position mapping + HTML escape (XSS-safe) ----

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function highlightSnippet(snippet, q) {
  const term = (q || '').trim()
  if (!term || !snippet) return escapeHtml(snippet || '')

  // Decompose accented chars then strip combining marks; lowercase for
  // case-insensitive matching.
  const normTerm = term.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  if (!normTerm) return escapeHtml(snippet)

  // Build the normalized snippet AND a per-normalized-char index back to the
  // original snippet's char position. A single original char like "é" can
  // expand to 1 normalized char ("e"), and the combining mark is dropped —
  // both rows in normToOrig point to the same origIndex.
  let normSnippet = ''
  const normToOrig = []
  for (let i = 0; i < snippet.length; i++) {
    const normCh = snippet[i].normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    for (let k = 0; k < normCh.length; k++) {
      normSnippet += normCh[k]
      normToOrig.push(i)
    }
  }

  // Find every match position in normalized text; translate to ranges in
  // original snippet via normToOrig.
  const ranges = []
  let pos = 0
  while (true) {
    const idx = normSnippet.indexOf(normTerm, pos)
    if (idx === -1) break
    const origStart = normToOrig[idx]
    const origLast = normToOrig[idx + normTerm.length - 1]
    ranges.push([origStart, origLast + 1])
    pos = idx + normTerm.length
  }
  if (!ranges.length) return escapeHtml(snippet)

  // Render the snippet, wrapping each match range in <mark>. escapeHtml
  // is applied to BOTH the surrounding text and the matched text so any
  // `<`, `>`, quotes in the source content can't break out into the DOM.
  let result = ''
  let cur = 0
  for (const [s, e] of ranges) {
    if (s > cur) result += escapeHtml(snippet.slice(cur, s))
    result += `<mark class="bg-amber-200 text-stone-900 px-0.5 rounded-sm">${escapeHtml(snippet.slice(s, e))}</mark>`
    cur = e
  }
  if (cur < snippet.length) result += escapeHtml(snippet.slice(cur))
  return result
}
</script>
