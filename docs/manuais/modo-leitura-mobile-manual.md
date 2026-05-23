# Manual: Modo Leitura Mobile para cards editoriais

> Compartilhe este arquivo com outros agentes (cardiology, music-agent, etc.)
> que tenham cards com texto editorial denso no frontend. Reproduz a feature
> implementada no culture-agent em commit `ec6f1d9` (2026-05-23).

## Quando aplicar

Você tem essa necessidade se **todos** se aplicam:

1. Frontend tem cards com **texto editorial longo** (síntese, resumo de notícia, análise)
2. A fonte do card está calibrada pra **densidade no feed** (~14-16px) — boa pra scanear, ruim pra ler
3. Os usuários acessam principalmente por **celular ou tablet**
4. Não há um "modo zoom" próprio — depender do zoom do navegador é ruim de descobrir

## A solução em uma frase

Botão **📖 Ler** no header do card → abre um modal full-screen em serif grande
(default 22px, ajustável 16–36 com A+/A−), fonte escolhida persistida em
`localStorage`. Só aparece em telas **< 1024px** (mobile + tablet).

## Decisões de design (e o porquê de cada uma)

### 1. Trigger: botão dedicado, **não** click no card

O card geralmente tem várias áreas clicáveis (poster, links, trailer, botões
de ação). Sobrecarregar "click no card" com "abrir modo leitura" cria conflito
de intenção — o usuário queria abrir o trailer, abre o modal. Botão explícito
é zero ambíguo.

### 2. Modal **por click + tamanho persistido** (não toggle global)

Não é um "modo" ON/OFF do site. Cada card é aberto deliberadamente. **MAS** o
tamanho da fonte fica em `localStorage` — próxima abertura em qualquer card
já abre confortável. Combina controle explícito com conforto persistente sem
um interruptor sempre visível.

### 3. **Só telas < 1024px** (`lg:hidden` no Tailwind)

Desktop tem tela larga e zoom do navegador disponível — a feature serve pouco
lá. No mobile o serif de 15px com line-height 1.72 fica apertado. O botão
recebe `class="lg:hidden"` (Tailwind: oculto em telas ≥ lg/1024px). Cobre
celular + iPad em retrato.

### 4. **Singleton** em vez de modal-por-card

Se cada card tivesse seu próprio `<Teleport>` ao body, abrir dois modais
empilharia overlays — usuário não sabe qual fecha primeiro. Solução: **um
único modal** renderizado uma vez no App, controlado por estado global. Abrir
outro card simplesmente troca o `currentItem`. Funcionalmente trivial,
arquiteturalmente limpo.

### 5. Modal renderiza **só o texto**, não o card inteiro

Sem repetir poster, fontes, links, trailer, botões de ação no modal. Isso
continua no card. **O modal é tela de leitura focada.** Trigger e ações ficam
na entrada (card); só o conteúdo de leitura vai pro modal.

## Arquitetura

```
┌──────────────────────────────┐
│ Card (mobile only)           │
│   ...header + badges + 📖 Ler│ ── click ──┐
└──────────────────────────────┘            │
                                            ▼
                          ┌─────────────────────────────┐
                          │ useReader (composable)      │
                          │   currentItem (ref)         │
                          │   mode (editorial|noticia)  │
                          │   fontSize (localStorage)   │
                          │   open / close              │
                          │   incFont / decFont         │
                          └────────┬────────────────────┘
                                   │ observado por
                                   ▼
                          ┌─────────────────────────────┐
                          │ ReaderModal (singleton)     │
                          │   renderizado no App.vue    │
                          │   Teleport to="body"        │
                          │   overlay + Esc + close     │
                          │   body serif, fonte dinâmica│
                          └─────────────────────────────┘
```

## Implementação — 4 arquivos

### `frontend/src/composables/useReader.js` (composable singleton)

```js
import { ref, watch } from "vue"

const STORAGE_KEY = "reader.fontSize"
const FONT_DEFAULT = 22
const FONT_MIN = 16
const FONT_MAX = 36
const FONT_STEP = 2

// Module-level refs — mesma instância em qualquer import.
const currentItem = ref(null)
const mode = ref("editorial")  // "editorial" | "noticia" | qualquer outro tipo
const fontSize = ref(_loadFontSize())

function _loadFontSize() {
  if (typeof localStorage === "undefined") return FONT_DEFAULT
  const raw = parseInt(localStorage.getItem(STORAGE_KEY), 10)
  if (!Number.isFinite(raw)) return FONT_DEFAULT
  return Math.min(FONT_MAX, Math.max(FONT_MIN, raw))
}

watch(fontSize, (v) => {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, String(v))
  }
})

export function useReader() {
  return {
    currentItem, mode, fontSize,
    open(item, m = "editorial") { mode.value = m; currentItem.value = item },
    close() { currentItem.value = null },
    incFont() { fontSize.value = Math.min(FONT_MAX, fontSize.value + FONT_STEP) },
    decFont() { fontSize.value = Math.max(FONT_MIN, fontSize.value - FONT_STEP) },
    canIncrease: () => fontSize.value < FONT_MAX,
    canDecrease: () => fontSize.value > FONT_MIN,
  }
}
```

### `frontend/src/components/ReaderModal.vue` (singleton)

Estrutura: `<Teleport to="body">` + `v-if="currentItem"` + header sticky (título,
A−/size/A+, ×) + body com `font-size: var(--reader-font-size)`. Adapte os
campos renderizados (`editorial`, `noticia`, etc.) ao schema do seu projeto.

Pontos críticos do CSS/JS:

```vue
<template>
  <Teleport to="body">
    <div v-if="currentItem"
         class="reader-overlay"
         @click.self="reader.close()"
         :style="{ '--reader-font-size': fontSize + 'px' }">
      <article class="reader-panel" role="dialog" aria-modal="true">
        <header class="reader-header"> ...título + controles + ×... </header>
        <div class="reader-body"> ...seções do item, renderizadas inline... </div>
      </article>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"
import { useReader } from "@/composables/useReader"

const reader = useReader()
const { currentItem, mode, fontSize } = reader
const closeBtn = ref(null)

function onKey(e) { if (e.key === "Escape") reader.close() }

watch(currentItem, async (it) => {
  if (it) {
    document.body.style.overflow = "hidden"     // trava scroll de fundo
    document.addEventListener("keydown", onKey) // Esc fecha
    await nextTick()
    closeBtn.value?.focus()                     // foco no fechar
  } else {
    document.body.style.overflow = ""
    document.removeEventListener("keydown", onKey)
  }
})
onBeforeUnmount(() => {                          // defesa em profundidade
  document.body.style.overflow = ""
  document.removeEventListener("keydown", onKey)
})
</script>

<style scoped>
.reader-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.75);
  display: flex; align-items: flex-start; justify-content: center;
  overflow-y: auto;
}
.reader-panel {
  background: #fff; width: 100%; max-width: 720px; min-height: 100vh;
}
@media (min-width: 640px) {
  .reader-overlay { padding: 2rem 1rem; }
  .reader-panel {
    min-height: auto; max-height: calc(100vh - 4rem);
    border-radius: .5rem; box-shadow: 0 10px 40px rgba(0,0,0,.4);
    overflow: hidden;
  }
}
.reader-header {
  position: sticky; top: 0; z-index: 2;
  display: flex; justify-content: space-between;
  background: #fff; border-bottom: 1px solid #e7e5e4; padding: .9rem 1rem;
}
.reader-body {
  flex: 1; overflow-y: auto;
  padding: 1.25rem 1.25rem 2.5rem;
  font-family: Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  font-size: var(--reader-font-size, 22px);
  line-height: 1.8;
  color: #44403c;
}
/* Labels escalam JUNTO com o body — usar `em`, não `px` */
.reader-section-label {
  font-size: 0.55em;
  text-transform: uppercase;
  letter-spacing: 0.13em;
  font-weight: 600;
  color: #92400e;
}
/* Botões com área de toque ergonômica (≥36px) */
.reader-btn-icon, .reader-btn-close {
  min-width: 36px; min-height: 36px;
}
</style>
```

### Cards: botão e CSS

No header de cada card que vai ter modo leitura, perto dos badges:

```vue
<button @click="reader.open(item, 'editorial')"  <!-- ou 'noticia', etc -->
        class="reader-trigger lg:hidden"
        aria-label="Abrir modo leitura">📖 Ler</button>
```

```js
import { useReader } from "@/composables/useReader"
const reader = useReader()
```

```css
.reader-trigger {
  font-size: 0.78rem;
  padding: 0.3rem 0.7rem;
  border: 1px solid #d6d3d1;
  background: #fafaf9;
  color: #44403c;
  border-radius: 9999px;
  font-weight: 500;
  cursor: pointer;
  min-height: 32px;
}
```

### `App.vue` — renderiza o modal **uma vez**

```vue
<template>
  <ReaderModal />
  <!-- resto do app -->
</template>

<script setup>
import ReaderModal from "@/components/ReaderModal.vue"
</script>
```

## Detalhes que importam

1. **`font-size: 0.55em` nos labels** (relativo, não absoluto). Quando o body
   sobe de 22 → 32px, o label sobe junto proporcionalmente. Sem isso a
   hierarquia visual quebra nas fontes grandes — labels minúsculos sob
   parágrafos enormes.

2. **`body.style.overflow = "hidden"` no watch** trava o scroll do fundo
   enquanto o modal está aberto. **Sempre restaurar** no `close()` E no
   `onBeforeUnmount` (defesa em profundidade — se o componente for
   desmontado de uma forma estranha, não deixa o body travado).

3. **`min-height: 36px`** em todos os botões — toque ergonômico no mobile.
   Recomendação iOS oficial é ≥44px; com padding 36+ é aceitável.

4. **Largura máx 720px** — leitura ótima fica em ~65-75 caracteres por
   linha. Mais largo cansa a vista.

5. **`line-height: 1.8`** no body (vs 1.72 ou menos do card) — leitura
   corrida pede mais respiro entre linhas.

6. **Botão focado ao abrir** (`closeBtn.value?.focus()`) — Esc-from-keyboard
   funciona imediato; ótimo a11y.

## Anti-padrões a evitar

| ❌ Anti-padrão | ✅ Por quê não |
|---|---|
| Modal por card (`<Teleport>` em cada card) | Múltiplos overlays empilhados, ninguém sabe qual fecha primeiro |
| Toggle global ON/OFF de "modo leitura" | Confunde com modo dark/light; usuário pediu "abrir card em leitura", não "ligar visualizador" |
| Reusar o componente Card dentro do modal | Entra fontes, trailer, botões duplicados. Modal vira "card maior", não tela de leitura focada |
| `font-size: 11px` (fixo) nos labels | Quando o body sobe pra 32px, labels ficam minúsculos. Use `em` relativo |
| `overflow: hidden` no body sem restaurar | Modal fecha mal, body fica travado. Sempre restaurar |
| `?reading=1` na URL pra "permalink do modal" | Overengineering — não é caso de uso real ("compartilhar a leitura que estou fazendo agora") |
| Click no card como trigger | Conflito com áreas já clicáveis. Botão dedicado é explícito |

## YAGNI deliberados

Listados e descartados após brainstorming com o usuário:

- "Marcar como lido" / bookmarks — fora de escopo
- Compartilhar permalink do modal — não é caso de uso
- Modo sépia / temas adicionais — visual cosmético, sem valor real
- Modo dark separado pro modal — o modal respeita o dark/light do site
- Ajuste de line-height ou largura pelo usuário — defaults bons cobrem

## Custo de implementação

- ~3-5 min de brainstorming (3 decisões: trigger, persistência, escopo)
- ~5 arquivos: 1 composable novo, 1 modal novo, edits em 2 cards, 1 wire no App
- ~250 linhas de Vue + CSS + JS (a maior parte é o modal)
- 1 commit, 1 build, sem mudança de pipeline backend
- **Custo de tokens LLM: zero** — feature 100% frontend client-side

## Spec original

Versão completa com o brainstorming registrado:
`docs/superpowers/specs/2026-05-23-modo-leitura-mobile-design.md`

## Commit de referência

`ec6f1d9` — `feat(ui): modo leitura nos cards (mobile/tablet) — fonte ajustável`
