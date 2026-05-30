<template>
  <Transition name="back-bar">
    <button v-if="show"
            @click="goBack"
            class="back-bar"
            :aria-label="`Voltar pra ${previousTabLabel}`">
      <span class="back-arrow">←</span>
      <span class="back-text">
        Voltar pra
        <strong class="back-strong">{{ previousTabLabel }}</strong>
      </span>
    </button>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { useTabHistory } from '../composables/useTabHistory.js'
import { useSearch } from '../composables/useSearch.js'

const { previousTab, previousTabLabel, activeTab, goBack } = useTabHistory()
const { isActive: searchActive } = useSearch()

// Abas que TÊM links de navegação cruzada — clicar num item delas leva
// pra um card em outra aba. Quando o usuário veio de uma dessas, o botão
// Voltar precisa aparecer no destino. Estreias/Preferidos/Vale Explorar/
// Aclamados não entram aqui porque só mostram cards próprios, sem links
// pra outras abas.
const CROSS_TAB_NAVIGATION_SOURCES = ['lista', 'pulso']

// Botão aparece SÓ quando:
//   - o usuário veio de uma aba que faz navegação cruzada (Resumo ou Pulso);
//   - a aba atual NÃO é a origem (senão fica órfão em cima da própria origem);
//   - a busca textual NÃO está ativa (quando search está aberta, a view
//     normal de cards está escondida; um "Voltar pra X" boiando em cima
//     dos resultados de busca não faz sentido).
const show = computed(() =>
  CROSS_TAB_NAVIGATION_SOURCES.includes(previousTab.value)
  && activeTab.value !== previousTab.value
  && !searchActive.value,
)
</script>

<style scoped>
/* Pousa logo abaixo do header sticky (SearchBar tem altura ~52px com z-40).
   z-30 fica sob a SearchBar e acima do conteúdo. BucketTabs (z-10, top-0)
   está atrás visualmente — não competimos com ele. */
.back-bar {
  position: sticky;
  top: 56px;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  margin-left: -1rem;
  margin-right: -1rem;
  padding: 0.55rem 1rem;
  background: rgb(255 255 255 / 0.95);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid rgb(231 229 228);
  font-size: 0.875rem;
  color: rgb(68 64 60);              /* stone-700 */
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.back-bar:hover  { background: rgb(245 245 244 / 0.95); }
.back-bar:active { background: rgb(231 229 228 / 0.95); }

.back-arrow {
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1;
  color: rgb(146 64 14);             /* amber-800 — bate com o acento editorial */
  flex-shrink: 0;
}
.back-text {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.back-strong {
  font-weight: 600;
  color: rgb(28 25 23);              /* stone-900 */
}

/* Transição suave de entrada/saída — slide do topo + fade. */
.back-bar-enter-active,
.back-bar-leave-active {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.back-bar-enter-from,
.back-bar-leave-to { transform: translateY(-100%); opacity: 0; }
</style>
