# Manual: Modo Compacto nos cards (densidade + expandir no clique)

> Compartilhe com outros agentes (culture, music, etc.) que tenham cards
> editoriais **altos/densos** num feed longo. Reproduz a feature implementada
> no cardiology-agent em commit `25a00c2` (2026-06-10).

## O problema

Cards ricos (com muitas seções abertas) deixam o feed **muito alto**. Quando
o relatório tem 20+ itens, escanear vira um scroll interminável — especialmente
no mobile. O usuário quer **bater o olho** e decidir em segundos o que vale ler.

## A solução em uma frase

Cards começam **compactos** (só o essencial: título + 1 informação de veredito
+ tag de tema); **clicar expande** as seções detalhadas inline. Um toggle global
"Compacto/Completo" no topo, persistido em `localStorage`, controla o default.

## ⚠️ DECISÃO POR-AGENTE (pergunte ao usuário ANTES de codar)

**Esta é a parte que muda de projeto pra projeto.** O que fica visível no estado
compacto é específico do domínio. ANTES de implementar, pergunte ao usuário:

> "No modo compacto, ANTES de expandir, o que você quer ver em cada card?"

No cardiology-agent o usuário escolheu: **título + veredito (conclusão em uma
frase) + tema (patologia)**. A regra que guiou: *"qual é a única informação que
responde 'vale eu abrir isso?'"*. Para um artigo científico, é o veredito
(positivo/negativo/neutro). Para outros domínios muda:

- **Filme/série (culture):** título + nota + 1 frase de "vale a pena?"
- **Música (music):** título + artista + nota/selo + 1 frase de recomendação
- **Notícia:** título + "por que importa" em 1 linha

**Regra de ouro:** o compacto deve ter **o título + UMA informação de decisão**
(a que responde "abro ou pulo?"). Nem mais (vira card cheio), nem menos (vira
lista de títulos sem contexto). Pergunte e implemente conforme a resposta.

## Decisões de design (e o porquê)

### 1. Uma informação de "veredito" SEMPRE visível, mesmo compacto

O título diz o *tema*; o veredito diz o *desfecho*. Com os dois, o usuário
escaneia e expande só o que importa. Esconder o veredito junto com o resto
transformaria o compacto numa lista de títulos sem poder de decisão.

### 2. Clique no card expande/recolhe (não abre fonte externa)

O comportamento mais intuitivo de um card colapsável é: clicar = abrir/fechar.
A fonte externa abre por um **botão explícito** ("🔗 Ler") no rodapé, com
`@click.stop`. No cardiology, ANTES o clique no card abria a URL externa — era
redundante com o botão Ler. Trocamos: clique = expandir, botão = sair.

### 3. Toggle global + estado por-card

Há um toggle "Compacto/Completo" que muda TODOS de uma vez (preferência salva
em `localStorage`, gruda entre sessões). MAS cada card também pode ser
aberto/fechado individualmente. Quando o global muda, todos seguem (via `watch`
na prop). Combina "controle de massa" com "ajuste fino".

### 4. Default = compacto

O ponto da feature é escanear rápido. Default compacto entrega isso já no
primeiro load. A preferência do usuário (se ele trocar pra completo) persiste.

### 5. Affordance explícita além do clique-no-card

Um botão "▼ ver análise completa / ▲ recolher" no rodapé deixa claro que há
mais. Sozinho, "clicar no card expande" não é descobrível. Esconda esse botão
se o item não tem seções detalhadas (degradação graciosa — ver `hasDetails`).

## Implementação — 1 componente de card + 1 edit no App

### `components/XCard.vue` (o card que vai ficar colapsável)

**Template — estrutura:**

```vue
<template>
  <div @click="expanded = !expanded" class="card cursor-pointer group">
    <!-- SEMPRE VISÍVEL (compacto): header + título + veredito + tema -->
    <header> ...emoji, título, badges... </header>

    <!-- 1 informação de veredito — SEMPRE visível mesmo compacto -->
    <div v-if="item.conclusao"> ⚡ {{ item.conclusao }} </div>

    <!-- SEÇÕES DETALHADAS — só quando expandido -->
    <template v-if="expanded">
      <section v-if="item.contexto"> ... </section>
      <section v-if="item.resultados"> ... </section>
      <!-- ...todas as seções densas aqui dentro... -->
    </template>

    <!-- Affordance de expandir/recolher -->
    <button v-if="hasDetails" @click.stop="expanded = !expanded"
            class="w-full text-center text-xs text-gray-400 hover:text-gray-600 py-1">
      {{ expanded ? '▲ recolher' : '▼ ver mais' }}
    </button>

    <!-- Rodapé: SEMPRE visível. Botão de fonte externa com @click.stop -->
    <footer>
      <span>{{ item.tema }}</span>
      <a :href="item.url" target="_blank" @click.stop="handleExternalLinkClick($event, item.url)">
        🔗 Ler
      </a>
    </footer>
  </div>
</template>
```

**Script:**

```vue
<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  item: Object,
  // Estado inicial vindo do toggle global no App.vue
  expandedDefault: { type: Boolean, default: false },
})

// Estado de expansão local — cada card abre/fecha individualmente.
// Inicializa do default global; segue o global quando ele muda.
const expanded = ref(props.expandedDefault)
watch(() => props.expandedDefault, (v) => { expanded.value = v })

// Esconde o botão "ver mais" em itens sem seções detalhadas (degradação graciosa)
const hasDetails = computed(() => {
  const a = props.item
  return Boolean(a?.contexto || a?.resultados /* ...outros campos densos... */)
})
</script>
```

### `App.vue` — toggle global + passar a prop

```vue
<template>
  <!-- No topo da lista -->
  <div class="flex items-center justify-between mb-3">
    <p>{{ filtered.length }} itens</p>
    <button @click="toggleExpanded"
            class="text-xs px-3 py-1.5 rounded-full border ...">
      {{ expandedAll ? '📖 Completo' : '📑 Compacto' }}
    </button>
  </div>

  <XCard
    v-for="item in filtered" :key="item.id"
    :item="item"
    :expanded-default="expandedAll"
  />
</template>

<script setup>
import { ref } from 'vue'

// Persistido em localStorage para a preferência grudar entre sessões
const expandedAll = ref(localStorage.getItem('cardsExpanded') === '1')
function toggleExpanded() {
  expandedAll.value = !expandedAll.value
  localStorage.setItem('cardsExpanded', expandedAll.value ? '1' : '0')
}
</script>
```

## Detalhes que importam

1. **`watch` na prop, não só inicialização.** Se você só fizer
   `ref(props.expandedDefault)`, o card não reage quando o toggle global muda.
   O `watch(() => props.expandedDefault, ...)` faz todos seguirem o global.

2. **`@click.stop` em TUDO que é clicável dentro do card** (botão Ler, Share,
   reader, botão "ver mais"). Sem isso, clicar nesses botões também
   expande/recolhe o card — comportamento confuso.

3. **Veredito FORA do `<template v-if="expanded">`.** Ele tem que ficar visível
   no compacto. Estruture: header + veredito SEMPRE; seções densas DENTRO do
   `v-if`.

4. **`hasDetails` evita botão morto.** Itens finos (só título + veredito) não
   têm o que expandir — esconda o "ver mais" neles.

5. **Default compacto, mas persistir a escolha.** `localStorage.getItem(...)
   === '1'` lê a preferência salva; default `false` (compacto) quando nunca foi
   setado.

## Anti-padrões a evitar

| ❌ Anti-padrão | ✅ Por quê não |
|---|---|
| Esconder o veredito junto com o resto no compacto | Vira lista de títulos sem poder de decisão |
| Clique no card abre fonte externa E expande | Conflito de intenção; escolha um (clique=expande, botão=fonte) |
| Só `ref(props.expandedDefault)` sem `watch` | Toggle global não afeta cards já renderizados |
| Esquecer `@click.stop` nos botões internos | Clicar em "Ler" também colapsa o card |
| Mostrar TODAS as seções no compacto "pra não perder nada" | Anula a feature — volta a ser feed alto |
| Não persistir a preferência | Usuário troca pra completo, recarrega, volta pro compacto — irritante |
| `v-show` em vez de `v-if` nas seções densas | `v-show` renderiza tudo (DOM pesado); `v-if` não monta o que está oculto |

## YAGNI deliberados

- **Animação de expand/collapse** (height transition) — bonito mas custa
  complexidade (precisa medir altura). Toggle instantâneo é suficiente.
- **Lembrar quais cards específicos foram expandidos** entre sessões — só o
  default global persiste; estado por-card é efêmero.
- **Modo "compacto" em todas as abas de uma vez** — comece pela aba mais densa
  (no cardiology, Artigos). Replique para outras só se a dor existir lá.
- **Três níveis (mínimo/médio/completo)** — dois estados (compacto/completo)
  cobrem o caso real. Três confunde.

## Custo de implementação

- ~1-2h: edits no componente de card + 1 toggle no App
- ~60 linhas no total (a maioria é mover seções pra dentro do `v-if`)
- **Custo de tokens LLM: zero** — feature 100% frontend client-side
- Build sem mudança de pipeline

## Como testar

1. Force-refresh (cache do JS antigo).
2. A lista deve abrir **compacta** — cada card ~3-4 linhas (título + veredito +
   tema + ações).
3. Clique num card → expande inline com as seções densas. Clique de novo →
   recolhe.
4. Botão de fonte externa ("Ler") → abre a fonte, NÃO expande.
5. Toggle "Compacto/Completo" no topo → muda todos. Recarregue → preferência
   manteve.

## Commit de referência

`25a00c2` (cardiology-agent) — `feat(ui): modo compacto nos cards de artigo`

## Manuais irmãos

- `docs/manuais/modo-leitura-mobile-manual.md` — modal de leitura para texto denso
- `docs/manuais/links-ios-chrome-manual.md` — abrir links no Chrome em iOS
- `docs/manuais/modo-pesquisa-historico-manual.md` — busca textual no histórico
