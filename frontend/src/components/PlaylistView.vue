<template>
  <section>
    <header class="mb-5">
      <p class="text-[11px] uppercase tracking-[0.13em] text-stone-500">Playlist da semana</p>
      <p class="font-serif text-[15px] text-stone-700 mt-1">
        Uma faixa-destaque por lançamento — <span class="font-bold">{{ items.length }}</span>
        {{ items.length === 1 ? 'faixa' : 'faixas' }} prontas pro seu Apple Music.
      </p>
    </header>

    <!-- Botão de ação principal -->
    <button
      type="button"
      @click="criar"
      :disabled="estado === 'criando' || items.length === 0"
      class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg
             bg-[#fa2d48] text-white font-semibold text-[15px]
             hover:bg-[#e0263e] disabled:opacity-50 disabled:cursor-not-allowed
             transition-colors shadow-sm">
      <span v-if="estado === 'criando'" class="animate-pulse"> Criando no Apple Music…</span>
      <span v-else> Criar no Apple Music</span>
    </button>

    <!-- Resultado de sucesso -->
    <div v-if="estado === 'pronto'"
         class="mt-4 p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-sm">
      <p class="font-semibold text-emerald-900">
        ✅ Playlist “{{ resultado.playlistName }}” criada na sua biblioteca!
      </p>
      <p class="mt-1 text-emerald-800">
        {{ resultado.created }} {{ resultado.created === 1 ? 'faixa adicionada' : 'faixas adicionadas' }}.
        Abra o app Apple Music → Biblioteca → Playlists.
      </p>
      <p v-if="resultado.skipped.length" class="mt-2 text-emerald-700/80 text-xs">
        Puladas (não estavam no seu storefront): {{ resultado.skipped.join(' · ') }}
      </p>
    </div>

    <!-- Ainda não ativado (env vars Apple ausentes) -->
    <div v-else-if="estado === 'nao_ativado'"
         class="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900">
      <p class="font-semibold">⏳ Recurso ainda não ativado</p>
      <p class="mt-1 text-amber-800">
        Falta plugar a chave da conta Apple Developer no servidor. Assim que isso
        estiver feito, este botão passa a criar a playlist de verdade.
      </p>
    </div>

    <!-- Erro genérico -->
    <div v-else-if="estado === 'erro'"
         class="mt-4 p-4 rounded-lg bg-red-50 border border-red-200 text-sm text-red-800">
      <p class="font-semibold">Não rolou desta vez.</p>
      <p class="mt-1">{{ mensagemErro }}</p>
    </div>

    <!-- Prévia da playlist: lista numerada, ordem alfabética por artista -->
    <ol class="mt-6 divide-y divide-stone-200">
      <li v-for="(it, idx) in items" :key="it.cardId"
          class="py-2.5 flex items-baseline gap-3">
        <span class="text-xs text-stone-400 w-5 flex-shrink-0 text-right tabular-nums">{{ idx + 1 }}</span>
        <p class="text-sm leading-tight min-w-0">
          <span class="font-bold text-stone-900">{{ it.artista }}</span>
          <span class="text-stone-400"> — </span>
          <span class="italic text-stone-700">{{ it.faixaPrincipal || it.titulo }}</span>
          <span v-if="it.faixaPrincipal" class="text-stone-400 text-xs ml-1">· de {{ it.titulo }}</span>
        </p>
      </li>
    </ol>
    <p v-if="items.length === 0" class="mt-6 text-stone-500 italic font-serif">
      Nenhum lançamento com link Apple Music nesta edição.
    </p>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue'
import { parseAppleUrl, createWeeklyPlaylist } from '../lib/musickit.js'
import { formatDate } from '../utils/formatters.js'

const props = defineProps({
  cards: { type: Array, default: () => [] },
  currentDate: { type: String, default: '' },
})

const estado = ref('idle')          // idle | criando | pronto | erro | nao_ativado
const resultado = ref(null)
const mensagemErro = ref('')

// Itens da playlist: cards com link Apple Music, UMA faixa cada (a principal
// do relatório), em ordem alfabética por artista — idêntico à aba Resumo.
const items = computed(() => {
  return props.cards
    .map((c) => {
      const url = c.links?.apple_music
      const parsed = parseAppleUrl(url)
      if (!parsed) return null
      return {
        cardId: c.id,
        artista: c.artista || 'Artista desconhecido',
        titulo: c.titulo,
        faixaPrincipal: (c.faixas_principais && c.faixas_principais[0]) || null,
        label: `${c.artista} — ${c.titulo}`,
        ...parsed,
      }
    })
    .filter(Boolean)
    .sort((a, b) => {
      const ar = a.artista.trim(), br = b.artista.trim()
      return ar.localeCompare(br, 'pt-BR', { sensitivity: 'base' })
    })
})

const nomePlaylist = computed(() => `Music Agent — ${formatDate(props.currentDate)}`)

async function criar() {
  estado.value = 'criando'
  try {
    resultado.value = await createWeeklyPlaylist(items.value, {
      name: nomePlaylist.value,
      description: `Os destaques da semana, curados pelo Music Agent (${items.value.length} faixas).`,
    })
    estado.value = 'pronto'
  } catch (e) {
    const msg = String(e?.message || e)
    if (msg === 'not_configured') {
      estado.value = 'nao_ativado'
    } else {
      estado.value = 'erro'
      mensagemErro.value =
        msg === 'no_tracks_resolved'
          ? 'Nenhuma faixa pôde ser resolvida no seu storefront.'
          : 'Verifique se você autorizou o acesso ao Apple Music e tente de novo.'
    }
  }
}
</script>
