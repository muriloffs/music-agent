# Manual: Modo Pesquisa — busca textual em todo o histórico

> Compartilhe este arquivo com outros agentes (culture, music, etc.) que
> tenham um dashboard frontend com múltiplos relatórios diários/semanais
> commitados em git. Reproduz a feature implementada no cardiology-agent
> em commit `491da4c` (2026-05-29).

## Quando aplicar

Você tem essa necessidade se **todos** se aplicam:

1. O agente gera relatórios periódicos (diários, semanais) salvos como
   JSONs commitados em `data/relatorio-YYYY-MM-DD.json` (ou equivalente).
2. Já existem **≥10 relatórios** no histórico (com menos, ⌘+F do navegador
   resolve).
3. Usuário quer achar **"em qual dia falamos sobre X?"** ou **"todos os
   posts/cards que mencionam X"** sem ter que abrir cada relatório.
4. O frontend é Vue 3 + Vite (o padrão se adapta a React/Svelte, mas os
   snippets aqui são Vue).
5. Não há ainda backend de busca semântica (Pinecone, Algolia, etc.) — e
   você quer evitar essa complexidade enquanto possível.

## A solução em uma frase

Sticky search bar no topo do app que, ao primeiro focus, **carrega lazy todos
os JSONs do histórico** via `index.json` + `Promise.allSettled`, mantém em
cache durante a sessão, e filtra por substring case-/accent-insensitive,
substituindo a view normal por resultados agrupados por data quando há query.

## Decisões de design (e o porquê de cada uma)

### 1. **Carregamento lazy no primeiro focus** — não no load do site

Site abre em <1s normalmente. Carregar 30 JSONs (~6MB) no boot adicionaria
2-5s ao TTI (time-to-interactive) — desproporcional pra uma feature que a
maioria dos acessos NÃO usa. Lazy load: zero custo até o usuário focar o
input. Trade-off: a 1ª busca da sessão demora 2-5s. Aceitável porque o
usuário acabou de declarar intenção (focou o input).

### 2. **Cache em memória durante a sessão** — não localStorage

Os JSONs do histórico podem somar 5-20MB. localStorage tem limite de 5-10MB
(varia por browser) e bate fácil. Cache em memória (`ref(new Map())`) cobre
todas as buscas da mesma sessão sem rebaixar, e some no F5 — usuário não
nota.

### 3. **`Promise.allSettled`** — não `Promise.all`

`Promise.all` quebra tudo se uma URL falhar (relatório corrompido,
404 transiente). `Promise.allSettled` deixa as outras carregarem. Resultado:
mesmo com 2 falhas em 30, você tem 28 dias indexados em vez de zero.

### 4. **NFD-normalize para case + accent insensitive**

Português gasta muito acento. Sem normalizar, `"isquemico"` não acharia
`"isquêmico"`. `text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()`
resolve com 1 linha — `é` vira `e`, `Ç` vira `c`. Resolver isso na ponta
do **input** (normalizar a query) e na ponta do **conteúdo** (normalizar o
texto pesquisável) é simétrico.

### 5. **Substring match, não fuzzy, não regex**

Fuzzy (Fuse.js, MiniSearch) acerta mais mas surpreende: você digita "ECG"
e acha "EICOSANOIDES" porque tem letras parecidas. Substring é
**previsível**: `"TAVR"` acha exatamente o que tem `TAVR`. Para um produto
pessoal, previsibilidade > recall. Se um dia precisar fuzzy, é trivial
trocar — o adapter está num único arquivo.

### 6. **≥2 caracteres pra ativar busca**

Buscar com 1 char dá resultados demais ("A" matcheia tudo). Threshold de 2
filtra ruído sem prejudicar uso real ("IC", "FA", "MI" — todas siglas
cardio comuns têm 2 chars, e o filtro é >=2).

### 7. **Debounce 200ms no input** — não filtrar a cada tecla

Cada filter rodando contra 30 JSONs × dezenas de items × 10+ campos texto
gasta ~50-100ms. Sem debounce, digitar "ticagrelor" dispararia 10 filtros
em sequência. 200ms é o sweet spot: rápido o suficiente pra parecer
instantâneo, lento o suficiente pra evitar trabalho repetido.

### 8. **Lista explícita de campos por tipo** — não `Object.values`

`Object.values(item)` pega TUDO: URLs, IDs (`art_001`), timestamps,
classes (A/B/C), scores. Resultado: buscar `"002"` matcheia em qualquer
item cujo id comece com 002. Lista explícita por tipo de card no
`extractSearchableText` é mais verbosa MAS revisável: você sabe exatamente
o que entra na busca.

### 9. **Substitui a view atual, não renderiza paralelo**

Quando query ativa, esconder TUDO (abas, cards, sumários) e mostrar só
resultados. Renderizar em paralelo (dropdown sobre os cards) força o
usuário a decidir entre dois UIs simultâneos. Substituir é menos elegante
mas mais claro: você está em modo busca, vê só busca.

### 10. **Snippet centrado no primeiro match com `<mark>` highlight**

Devolver só `titulo` esconde por que aquele item matcheou (palavras-chave
acertam em `principais_resultados`, não no título). Snippet de ~160 chars
ao redor do primeiro match + `<mark class="bg-yellow-200">` no termo
mostra o porquê do match. Usuário entende em 0.5s se vale clicar.

## Arquitetura

```
┌────────────────────────────────────────────┐
│ App.vue                                    │
│   <SearchBar /> (sticky top)               │
│   v-if searchActive: <SearchResults />     │
│   v-else: HeaderStats + abas + cards       │
└────────┬───────────────────────────────────┘
         │ both read/write
         ▼
┌────────────────────────────────────────────┐
│ useSearch() composable (singleton)         │
│   query (ref<string>)                      │
│   allReports (ref<Map<date, report>>)      │
│   loading, loaded, loadError               │
│   isActive computed (>=2 chars)            │
│   results computed                         │
│   resultsByDate, resultsByType computed    │
│   daysIndexed computed                     │
│   loadAllReports() — lazy, Promise.all-    │
│     Settled, fetchReportByDate paralelo    │
│   clear()                                  │
└────────────────────────────────────────────┘
```

## Implementação — 3 arquivos novos + 1 edit

### `composables/useSearch.js` (singleton + cache + filtro)

```js
import { computed, ref } from 'vue'
import { fetchIndex, fetchReportByDate } from '../utils/api'

const query = ref('')
const allReports = ref(new Map())
const loading = ref(false)
const loaded = ref(false)
const loadError = ref(null)

// NFD = decompose chars (ê → e + combining mark); regex strips marks
function normalize(text) {
  if (!text) return ''
  return String(text).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

// Lista EXPLÍCITA de campos por tipo — adapte ao schema do seu agente!
function extractSearchableText(item, type) {
  if (!item) return ''
  const parts = []
  const push = (v) => {
    if (!v) return
    if (Array.isArray(v)) v.forEach(push)
    else if (typeof v === 'string') parts.push(v)
    else if (typeof v === 'object') {
      Object.values(v).forEach((vv) => typeof vv === 'string' && parts.push(vv))
    }
  }
  push(item.titulo)
  push(item.publicacao)
  push(item.autor)
  push(item.autores)
  switch (type) {
    case 'artigo':
      push(item.contexto_clinico); push(item.principais_resultados)
      push(item.conclusao_uma_frase); push(item.pontos_chave)
      // ... outros campos editoriais
      break
    case 'noticia':
      push(item.contexto); push(item.insights); push(item.por_que_importa)
      break
    // ... outros tipos do seu domínio
  }
  return parts.join(' ')
}

function* iterReportItems(report) {
  if (!report) return
  for (const a of report.artigos || []) yield { type: 'artigo', item: a }
  for (const n of report.noticias || []) yield { type: 'noticia', item: n }
  // ... outros tipos
}

function buildSnippet(haystack, needleNorm, contextChars = 80) {
  if (!haystack) return ''
  const norm = normalize(haystack)
  const idx = norm.indexOf(needleNorm)
  if (idx === -1) return haystack.slice(0, 140)
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
    const dates = await fetchIndex() // lê index.json (newest-first)
    const results = await Promise.allSettled(
      dates.map((d) => fetchReportByDate(d).then((r) => [d, r]))
    )
    const map = new Map()
    for (const r of results) {
      if (r.status === 'fulfilled') map.set(r.value[0], r.value[1])
    }
    allReports.value = map
    loaded.value = true
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
```

### `components/SearchBar.vue` (sticky, debounce, lazy)

Pontos críticos:

```vue
<template>
  <div class="sticky top-0 z-40 bg-white/95 backdrop-blur border-b ...">
    <input
      type="search"
      :value="query"
      @input="onInput"
      @focus="onFocus"
      placeholder="Buscar em todo o histórico"
    />
    <span v-if="loading">carregando…</span>
    <span v-else-if="isActive">{{ results.length }} resultados</span>
    <button v-if="query" @click="clear">×</button>
  </div>
</template>

<script setup>
import { useSearch } from '../composables/useSearch'
const { query, loading, loaded, isActive, results, loadAllReports, clear } = useSearch()

let debounceTimer = null
function onInput(e) {
  const v = e.target.value
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { query.value = v }, 200)
}
function onFocus() {
  if (!loaded.value && !loading.value) loadAllReports()
}
</script>
```

### `components/SearchResults.vue` (substitui view normal)

Estrutura: `v-for` em `resultsByDate` (Map preserva ordem de inserção =
mais recente primeiro). Cada resultado mostra chip do tipo + título +
snippet com `<mark>` no termo + link "Abrir fonte". Highlight:

```js
function highlightSnippet(snippet, q) {
  const term = (q || '').trim()
  if (!term) return escapeHtml(snippet)
  const norm = term.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const lowNorm = snippet.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  // Reconstrói preservando os caracteres originais (com acentos) e envolvendo
  // os matches em <mark>; escapa HTML pra não permitir injeção
  // (snippet completo no commit 491da4c do cardiology-agent)
}
```

### `App.vue` — wire da search bar + render condicional

```vue
<template>
  <div>
    <SearchBar />
    <SearchResults v-if="searchActive" />
    <template v-else>
      <HeaderStats /> <!-- abas, cards normais... -->
    </template>
    <BackToTopButton /> <!-- sempre visível -->
  </div>
</template>

<script setup>
import { useSearch } from './composables/useSearch'
import SearchBar from './components/SearchBar.vue'
import SearchResults from './components/SearchResults.vue'
const { isActive: searchActive } = useSearch()
</script>
```

## Detalhes que importam

1. **`index.json` precisa estar atualizado** pelo workflow do CI a cada
   relatório novo. No cardiology-agent é gerado no step "Update index and
   commit" do workflow. Sem ele, `fetchIndex()` retorna `[]` e a busca não
   acha nada. Verifique que seu workflow gera/atualiza esse arquivo.

2. **`Map` preserva ordem de inserção.** Se `index.json` vier newest-first
   (recomendado), o Map também itera newest-first → resultados saem do
   mais recente pro mais antigo sem sort extra.

3. **`@input` em `<input type="search">`** captura também o `×` nativo de
   limpar do browser. Funciona junto com o nosso botão `×` customizado.

4. **`backdrop-blur` no sticky bar** mantém legibilidade quando o conteúdo
   atrás rola. Sem isso, o input fica em cima de texto e fica difícil ler.

5. **Threshold ≥2 chars** evita disparar lazy load com 1 toque acidental
   no input. Você pode subir pra 3 se digitar a maioria dos termos com 3+
   chars; eu fiquei em 2 porque siglas (IC, FA) são úteis.

6. **Escape HTML no snippet** é CRÍTICO. Conteúdo do JSON pode ter `<`,
   `>`, aspas — sem escape, viraria injeção no DOM (XSS). Use a função
   `escapeHtml` antes de inserir `<mark>`.

## Anti-padrões a evitar

| ❌ Anti-padrão | ✅ Por quê não |
|---|---|
| `Object.values(item).join(' ')` pra construir o texto pesquisável | Inclui URLs, IDs, scores — match em lixo |
| `Promise.all` pra carregar relatórios | 1 falha de rede quebra a busca inteira |
| Carregar tudo no mount do App.vue | Adiciona 2-5s ao TTI de quem não vai usar |
| Fuse.js / fuzzy search "porque é melhor" | Surpresas: "ECG" acha "EICOSANOIDES" |
| `localStorage` pra cachear histórico | Estoura limite 5-10MB; nem precisa cache cross-session |
| `input.addEventListener('input', filter)` sem debounce | Re-filtra a cada tecla, lag em 30+ JSONs |
| Renderizar dropdown sobre os cards normais | Dois UIs simultâneos, usuário se perde |
| Highlight com `innerHTML = snippet.replace(term, '<mark>...</mark>')` | XSS se conteúdo tem `<`, `>`, aspas. Escape primeiro |
| Buscar com 1 char | "a" matcheia tudo, ruído > sinal |
| Cmd+K / Ctrl+K como única forma de abrir | Atalho discoverable pra power-user, mobile não tem teclado físico |

## YAGNI deliberados

Considerados durante o desenho e cortados:

- **Filtrar por tipo dentro dos resultados** (botões "só artigos", "só
  notícias") — chips de sumário no topo já mostram contagem; filtrar
  aprofundaria a UI sem benefício real.
- **Histórico de buscas recentes** ("você buscou TAVR ontem") —
  localStorage extra, valor marginal pra 1 usuário.
- **Sugestões de termos** enquanto digita — requer índice extra ou heurística
  de palavras-chave. Volta se ficar fácil com bons sinais.
- **Filtro por intervalo de datas** ("entre 01/05 e 15/05") — dá pra
  scrollar; só vale se histórico passar de 100 dias.
- **Busca booleana** ("TAVR AND idade>70") — domínio errado pra isso;
  usuário expressa intenções em linguagem natural.
- **Atalho `/` pra focar input** estilo GitHub/Notion — pode entrar depois
  se for cobrado, é uma linha.
- **Esc pra limpar busca** — útil no desktop; vale adicionar (3 linhas)
  mas não estava na primeira iteração.

## Custo de implementação

- ~2-3h de desenho + código pra schema cheio
- 3 arquivos novos (~520 linhas Vue/JS): 1 composable, 2 componentes
- 1 edit no `App.vue` (5 linhas)
- **Custo de tokens LLM: zero** — feature 100% frontend client-side
- Overhead bundle: ~10 KB JS + ~2 KB CSS

## Como testar

1. Force-refresh do navegador (ou aba anônima) — cache do JS antigo
2. Abre o site. Search bar deve aparecer sticky no topo, **acima** das
   abas/header.
3. Vazio: deve mostrar `🔍 Buscar em todo o histórico` + `N dias indexados`
4. **Tap no input** → primeiro load (`carregando…` ~2-5s)
5. Digita "TAVR" (ou termo típico do seu domínio):
   - Deve aparecer a contagem `N resultados`
   - Conteúdo normal some, lista agrupada por data aparece
   - Cada resultado tem chip do tipo + título + snippet com termo em
     amarelo
6. Click no `×` ou apagar input → volta pro modo normal

## Commit de referência

`491da4c` (cardiology-agent) — `feat(search): busca textual em todo o
historico (sticky bar)`

## Manuais irmãos

- `docs/manuais/modo-leitura-mobile-manual.md` — modal full-screen de leitura
  para cards densos (do culture-agent)
- `docs/manuais/links-ios-chrome-manual.md` — escape do SFSafariViewController
  em iOS + exceções para apps fortes (do cardiology-agent)
