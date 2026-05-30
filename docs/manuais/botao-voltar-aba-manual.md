# Manual: Botão "← Voltar para [aba]" — visível em PWA standalone

> Compartilhe este arquivo com outros agentes (music, cardiology, etc.)
> que tenham uma aba de "índice" (lista todas as bandas / todos os
> filmes / todos os papers da edição) com links pra os cards individuais,
> e que sejam abertos pelo usuário via **atalho de tela inicial no
> iPhone** (PWA standalone). Reproduz a feature implementada no
> culture-agent em commit `b58c298` (2026-05-30).

## Quando aplicar

Você tem essa necessidade se **todos** se aplicam:

1. O app é Vue 3 + Vite com **navegação por abas** (no music-agent: aba
   "Resumo", "Críticas", "Notícias", etc.).
2. Existe uma **aba-índice** que lista N itens com link pra o card
   correspondente em outra aba (no music-agent: "Resumo" com todas as
   bandas da edição).
3. O usuário abre o app **via atalho na tela inicial do iPhone** (PWA
   standalone). Nesse modo, o Safari **não tem barra de navegação** —
   logo, **não há botão "←" nativo**. Swipe-back é interceptado.
4. Resultado sem este manual: o usuário clica num item da aba-índice,
   chega no card em outra aba, e **fica preso** — não tem como voltar
   pra aba-índice no scroll exato onde estava.

## A solução em uma frase

Composable `useTabHistory` rastreia a aba anterior via `history.pushState`
e expõe um botão sticky `← Voltar para [aba]` no topo do conteúdo,
visível **apenas** quando o usuário chegou na aba atual vindo da
aba-índice; tap dispara `history.back()` que restaura aba + scroll exato.

## Decisões de design (e o porquê de cada uma)

### 1. **Sticky no topo** — não FAB (Floating Action Button)

FAB no canto inferior é elegante mas **sutil demais** — usuários novos
não associam o ícone "←" canto-direito-baixo com "voltar". Sticky no
topo com texto explícito ("Voltar para 🎵 Resumo") é redundante mas
ZERO ambíguo. O custo são ~40px de altura quando aparece; o benefício é
zero confusão.

### 2. **`history.back()` em vez de `navigate(previousTab)`** — disparar popstate

Tap no botão dispara `window.history.back()`. Isso aciona o evento
`popstate` que já cuidamos — restaura aba + scroll **com a mesma lógica**
do botão Voltar nativo. Se usássemos `navigate(previousTab)`, criaríamos
nova entrada no histórico (o "Voltar" do botão visível não seria
realmente "Voltar", mas "uma navegação a mais"). Mantemos coerência:
qualquer "voltar" do site é exatamente o que o navegador entenderia.

### 3. **Visibilidade restrita a `previousTab === 'resumo'`** — não toda aba

Mostrar "← Voltar para X" em TODA navegação confunde — usuário muda de
aba pra explorar e o botão aparece como se fosse erro de UX. Restringir
à aba-índice específica deixa **claro o intent**: o botão só existe pra
*esse* fluxo (clicou num item da lista, quer voltar pra lista). Composable
é genérico — abrir pra outras abas no futuro = trocar 1 linha.

### 4. **Recuperar `previousTab` de `window.history.state`** — sobreviver a refresh

Refresh da página perde o estado em memória, mas `history.state`
**sobrevive** ao F5. Se o usuário refresha estando no card destino,
ainda dá pra voltar. Não funciona se ele **fechar** o app (history é por
aba do navegador) — mas isso é aceitável: nova sessão = sem origem.

### 5. **Fallback pra entrada única** (`history.length === 1`)

Se alguém abre um deep link compartilhado tipo `/?tab=criticas#item-X`,
o histórico tem só 1 entrada. `history.back()` nesse caso vira no-op em
PWA standalone (em modo navegador, sai do site). O fallback detecta
isso e faz `replaceState` pra `previousTab` salvo no state — sem criar
nova entrada, sem deixar o user preso.

### 6. **Desabilitar quando volta à origem** — não fica órfão

Assim que o user volta pra aba-índice, o botão **deve sumir**. Senão
fica "Voltar para Resumo" exibido em cima da própria aba Resumo — sem
sentido. A condição `activeTab !== 'resumo'` cobre isso.

## Pré-requisito: history-driven navigation

Se o seu app **muta `activeTab` diretamente** (`activeTab.value = "X"`)
sem `pushState`, **não funciona** — botão Voltar do navegador não tem
nada pra voltar, e este manual depende dessa infraestrutura.

A correção é trocar todas as mutações diretas por chamadas do composable
`navigate()` — explicado abaixo.

## Implementação

### Passo 1 — Criar `src/composables/useTabHistory.js`

```js
// src/composables/useTabHistory.js
//
// Singleton composable: gerencia activeTab via URL + history.pushState.
// Expõe activeTab, previousTab e navigate() / goBack() / init().

import { ref, computed, nextTick } from "vue"

const activeTab = ref("resumo")              // ← TROCAR aba default do seu app
const previousTab = ref(null)
const scrollByTab = new Map()
let _initialized = false

// Labels editoriais das suas abas (espelhar do componente de tabs).
// Usado pra montar "Voltar para [label]" do botão. ADAPTAR.
const TAB_LABELS = {
  resumo:     "🎵 Resumo da edição",     // ← aba-índice do music-agent
  criticas:   "📝 Críticas",
  noticias:   "📰 Notícias",
  // ...adicione suas abas aqui
}

const previousTabLabel = computed(
  () => previousTab.value && TAB_LABELS[previousTab.value],
)

function readUrl() {
  const params = new URLSearchParams(window.location.search)
  const hash = window.location.hash || ""
  const m = hash.match(/^#item-(.+)$/)
  return {
    date:   params.get("date") || null,
    tab:    params.get("tab")  || "resumo",   // ← TROCAR aba default
    itemId: m ? m[1] : null,
  }
}

function buildUrl(tab, itemId, date) {
  const params = new URLSearchParams()
  if (date) params.set("date", date)
  if (tab && tab !== "resumo") params.set("tab", tab)   // ← TROCAR aba default
  const qs = params.toString()
  let url = qs ? `/?${qs}` : "/"
  if (itemId) url += `#item-${itemId}`
  return url
}

async function _scrollToItemOrTop(itemId, fallbackY = 0) {
  await nextTick()
  if (itemId) {
    let el = document.getElementById(`item-${itemId}`)
    if (!el) {
      // Aba destino pode ainda não ter renderizado seus cards. Espera 120ms
      // e tenta de novo. Resolve race condition silenciosa no mobile.
      await new Promise(r => setTimeout(r, 120))
      el = document.getElementById(`item-${itemId}`)
    }
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" })
      return
    }
  }
  window.scrollTo({ top: fallbackY, behavior: "instant" })
}

async function navigate(targetTab, { itemId = null, date } = {}) {
  if (typeof window !== "undefined") {
    scrollByTab.set(activeTab.value, window.scrollY)
  }
  const origin = activeTab.value
  const sameTab = origin === targetTab

  if (!sameTab) previousTab.value = origin
  activeTab.value = targetTab

  const currentDate = date !== undefined
    ? date
    : new URLSearchParams(window.location.search).get("date")

  const url = buildUrl(targetTab, itemId, currentDate)
  const state = {
    tab: targetTab,
    itemId,
    date: currentDate,
    previousTab: sameTab ? (window.history.state?.previousTab || null) : origin,
  }

  if (sameTab && !itemId) {
    history.replaceState(state, "", url)
  } else {
    history.pushState(state, "", url)
  }
  await _scrollToItemOrTop(itemId, scrollByTab.get(targetTab) || 0)
}

async function _handlePopstate(event) {
  const state = event.state || readUrl()
  scrollByTab.set(activeTab.value, window.scrollY)
  activeTab.value = state.tab || "resumo"          // ← TROCAR aba default
  previousTab.value = state.previousTab || null
  await _scrollToItemOrTop(state.itemId, scrollByTab.get(activeTab.value) || 0)
}

function goBack() {
  const target = previousTab.value
  if (window.history.length > 1) {
    window.history.back()
  } else if (target) {
    const url = buildUrl(target, null,
      new URLSearchParams(window.location.search).get("date"))
    const state = { tab: target, itemId: null, date: null, previousTab: null }
    history.replaceState(state, "", url)
    scrollByTab.set(activeTab.value, window.scrollY)
    activeTab.value = target
    previousTab.value = null
    _scrollToItemOrTop(null, scrollByTab.get(target) || 0)
  }
}

function init() {
  if (_initialized) return
  _initialized = true
  window.addEventListener("popstate", _handlePopstate)
  const initial = readUrl()
  activeTab.value = initial.tab
  previousTab.value = window.history.state?.previousTab || null
  const url = buildUrl(initial.tab, initial.itemId, initial.date)
  history.replaceState(
    {
      tab: initial.tab,
      itemId: initial.itemId,
      date: initial.date,
      previousTab: previousTab.value,
    },
    "", url,
  )
}

export function useTabHistory() {
  return {
    activeTab, previousTab, previousTabLabel,
    navigate, goBack, init, readUrl,
  }
}
```

### Passo 2 — Criar `src/components/navigation/TabBackButton.vue`

```vue
<template>
  <Transition name="back-bar">
    <button v-if="show"
            @click="goBack"
            class="back-bar"
            :aria-label="`Voltar para ${previousTabLabel}`">
      <span class="back-arrow">←</span>
      <span class="back-text">
        Voltar para
        <strong class="back-strong">{{ previousTabLabel }}</strong>
      </span>
    </button>
  </Transition>
</template>

<script setup>
import { computed } from "vue"
import { useTabHistory } from "@/composables/useTabHistory"

const { previousTab, previousTabLabel, activeTab, goBack } = useTabHistory()

// AJUSTE: trocar 'resumo' pelo nome da SUA aba-índice (no music-agent).
// Composable rastreia previousTab pra TODAS as abas; este v-if restringe
// onde o botão aparece.
const show = computed(() =>
  previousTab.value === "resumo" && activeTab.value !== "resumo",
)
</script>

<style scoped>
.back-bar {
  position: sticky;
  top: 56px;     /* AJUSTE: altura da sua SearchBar/header sticky de cima */
  z-index: 30;   /* sob a SearchBar (z-40), acima dos cards */
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.55rem 1rem;
  background: rgb(249 250 251 / 0.95);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid rgb(231 229 228);
  font-size: 0.875rem;
  color: rgb(55 65 81);
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.back-bar:hover  { background: rgb(243 244 246 / 0.95); }
.back-bar:active { background: rgb(229 231 235 / 0.95); }

.back-arrow {
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1;
  color: rgb(29 78 216);
  flex-shrink: 0;
}
.back-text {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.back-strong {
  font-weight: 600;
  color: rgb(17 24 39);
}

:global(.dark) .back-bar        { background: rgb(17 24 39 / 0.92);
                                  border-bottom-color: rgb(55 65 81);
                                  color: rgb(209 213 219); }
:global(.dark) .back-bar:hover  { background: rgb(31 41 55 / 0.92); }
:global(.dark) .back-arrow      { color: rgb(147 197 253); }
:global(.dark) .back-strong     { color: rgb(243 244 246); }

.back-bar-enter-active,
.back-bar-leave-active {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.back-bar-enter-from,
.back-bar-leave-to { transform: translateY(-100%); opacity: 0; }
</style>
```

### Passo 3 — Wire no `App.vue`

Você precisa de **4 mudanças** no `App.vue`:

#### 3.1. Importar composable + componente

```js
import { useTabHistory } from "@/composables/useTabHistory"
import TabBackButton from "@/components/navigation/TabBackButton.vue"

const { activeTab, navigate, init: initTabHistory } = useTabHistory()
```

#### 3.2. Remover o `ref` local de `activeTab` (vem do composable agora)

```js
// REMOVA:
// const activeTab = ref("resumo")

// (activeTab agora vem de useTabHistory acima)
```

#### 3.3. Inicializar `useTabHistory` no `onMounted`

```js
onMounted(() => {
  initTabHistory()
  // ...resto do seu onMounted
})
```

#### 3.4. Interceptar clique nas abas + adicionar botão no template

No `<template>`:

```vue
<!-- ANTES: -->
<!-- <TopicTabs v-model="activeTab" :items="report.items" /> -->

<!-- DEPOIS: -->
<TopicTabs :modelValue="activeTab"
           @update:modelValue="(t) => navigate(t)"
           :items="report.items" />

<!-- Adicionar logo abaixo das tabs: -->
<TabBackButton />
```

#### 3.5. Onde houver `activeTab.value = "X"`, trocar por `navigate("X")`

Se você tem funções como `jumpToItem(id)` que muta `activeTab` direto:

```js
// ANTES:
function jumpToItem(itemId) {
  const item = items.find(it => it.id === itemId)
  const targetTab = decideTab(item)
  activeTab.value = targetTab  // ← MUTAÇÃO DIRETA
  setTimeout(() => {
    document.getElementById(`item-${itemId}`)?.scrollIntoView(...)
  }, 50)
}

// DEPOIS:
function jumpToItem(itemId) {
  const item = items.find(it => it.id === itemId)
  const targetTab = decideTab(item)
  navigate(targetTab, { itemId })   // ← navigate cuida do pushState E do scroll
}
```

#### 3.6. Preservar `history.state` no watch de selectedDate (se existir)

Se você tem um watcher que atualiza a URL ao mudar de relatório:

```js
// ANTES:
watch(selectedDate, (newDate) => {
  const url = new URL(window.location)
  if (newDate) url.searchParams.set("date", newDate)
  window.history.replaceState({}, "", url)   // ← APAGA o state do useTabHistory!
})

// DEPOIS:
watch(selectedDate, (newDate) => {
  const url = new URL(window.location)
  if (newDate) url.searchParams.set("date", newDate)
  // Preserva o state existente — replaceState({}, ...) zeraria previousTab
  window.history.replaceState(window.history.state || {}, "", url)
})
```

## Adaptações específicas pro music-agent

Em todos os pontos marcados com `// ← TROCAR` no código acima, substitua
`"resumo"` (aba default) e ajuste os labels:

1. **`useTabHistory.js` linha 1 (default activeTab):**
   ```js
   const activeTab = ref("resumo")   // primeira aba do music-agent
   ```

2. **`TAB_LABELS`:** liste TODAS as abas do music-agent com seus rótulos
   editoriais exatos (espelhar do seu `TopicTabs.vue`).

3. **`readUrl()` e `buildUrl()`:** o fallback `"resumo"` é a aba que
   o app abre por padrão (sem `?tab=` na URL).

4. **`TabBackButton.vue` linha do `show` computed:**
   ```js
   const show = computed(() =>
     previousTab.value === "resumo" && activeTab.value !== "resumo",
   )
   ```
   Se a aba-índice no music-agent tem outro nome (ex: `'bandas'`,
   `'indice'`), troque os 2 `'resumo'` por esse nome.

5. **`top: 56px` em `.back-bar`:** medir a altura real do header sticky
   acima dele no music-agent. Se não há header acima, use `top: 0`.

## Edge cases

### iOS PWA standalone (caso principal)

Modo: usuário adicionou o site à tela inicial e abre por lá. Sintomas:
- Não há barra de URL/navegação do Safari
- Botão "←" nativo invisível
- Swipe-back da borda esquerda **não funciona** (interceptado pelo modo
  standalone)

Com este manual: botão sticky no topo da página resolve. É a **única**
forma de voltar nesse modo.

### Refresh da página

`window.history.state` sobrevive ao F5/refresh. O `init()` recupera
`previousTab` dele — se você refresha no card destino, ainda dá pra
voltar pra aba-índice. Se você refresha já na aba-índice, sem origem,
o botão não aparece (correto).

### Fechar e reabrir o app

PWA fechado completamente perde o history (é por aba do navegador). Nova
sessão = sem previousTab. O botão não aparece. Aceitável: usuário não
"estava voltando de algum lugar", está começando agora.

### Deep link / URL compartilhada

Alguém compartilhou `/?tab=criticas#item-XXX`. Você abre, history tem só
1 entrada, `previousTab` = null. **Botão não aparece** (correto — não há
"de onde voltar"). Se você navegar pra outra aba e voltar pra criticas,
o botão pode aparecer dependendo do fluxo.

### Race condition no scroll (mobile)

Quando `navigate` muda de aba e o componente da aba destino ainda não
renderizou todos os cards (componentes Vue lazy), `scrollIntoView` numa
DOM-tree incompleta scrolla pro nada. Mitigação no
`_scrollToItemOrTop`: `nextTick` + se ainda não achou, espera 120ms e
tenta de novo. Resolve sem usar `IntersectionObserver`.

## Testes manuais (smoke test após implementar)

**No PC (Chrome/Firefox/Edge):**

1. Abrir app → URL deve ser `/?date=...` (sem `tab=resumo` — aba default
   é implícita)
2. Clicar na aba-índice (Resumo) → URL não muda (ainda é default)
3. Clicar num item da lista → vai pra outra aba, URL vira
   `/?date=...&tab=X#item-Y`
4. **Botão sticky aparece no topo:** `← Voltar para 🎵 Resumo da edição`
5. Clicar no botão → volta pra aba Resumo no scroll do item original
6. Botão **desaparece** (você está na origem agora)

**No iPhone via atalho (caso crítico):**

Mesmos passos. O botão é a ÚNICA forma de voltar — não há
botão/swipe nativos. Se o botão funciona aqui, o manual está aplicado
corretamente.

**Bonus — URL compartilhada:**

1. No PC, copie a URL `/?date=...&tab=criticas#item-X`
2. Abra em janela anônima
3. Deve abrir direto na aba certa, scrollada até o item
4. Botão **não aparece** (correto — sem origem)

## Variações futuras (não fazer agora)

- **Ampliar pra múltiplas abas-índice:** trocar `previousTab.value === "resumo"`
  por `["resumo", "outra"].includes(previousTab.value)`.

- **Persistir entre fechamentos do app:** salvar `previousTab` em
  `sessionStorage` no `navigate()` e recuperar no `init()`. Risco:
  usuário fecha e reabre 2 dias depois, vê botão pra navegação antiga.

- **Múltiplos níveis de "voltar":** stack de previousTabs em vez de
  apenas a última. Pra navegação em árvore (resumo → banda → álbum).
  Não usar a menos que você TENHA navegação em árvore.

- **Animação de scroll-to-item mais sofisticada:** `IntersectionObserver`
  pra detectar quando o card destino realmente está visível. Substitui o
  retry de 120ms. Mais robusto mas ~30 linhas a mais.

## Custo de implementação no music-agent

- 1 arquivo novo (composable): ~120 linhas
- 1 arquivo novo (componente): ~80 linhas
- ~5 mudanças no `App.vue` (refactor `activeTab` mutações)
- Tempo estimado: 30-45min se o agente está familiarizado com Vue 3
- Zero dependências novas
- Build size: +1-2KB gzip

## Comparação com alternativas

| Abordagem | Funciona em PWA standalone? | Esforço |
|---|---|---|
| `history.back()` nativo só | ❌ (sem barra Safari) | 0 |
| Swipe-back gesture | ❌ (interceptado em standalone) | 0 |
| Stack de previousTab interno (não usa history API) | ✅ mas perde sync com URL | médio |
| **Este manual (history API + botão visível)** | **✅** | **médio** |

A combinação resolve TODAS as plataformas de uma vez:
- PC: botão visível + `Alt+←` nativo + botão "←" do navegador
- iPhone modo navegador: botão + swipe-back + botão "←" da barra
- **iPhone PWA standalone: botão visível** (sem ele, fica preso)
- Android: idem PC, mais swipe da borda

## Referência: commit no culture-agent

A implementação original está em:
- `frontend/src/composables/useTabHistory.js`
- `frontend/src/components/navigation/TabBackButton.vue`
- `frontend/src/App.vue` (refactor de `activeTab`)

Commits relevantes:
- `b614011` — history API + scroll restoration (infra base)
- `b58c298` — botão visível "← Voltar" pra Trailers
