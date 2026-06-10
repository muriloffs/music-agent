<template>
  <article :id="card.id"
           :class="['release-card bg-white border border-stone-200 border-l-4 rounded-r-lg rounded-l-sm',
                    'shadow-[0_1px_3px_rgba(0,0,0,0.04)] mb-5 overflow-hidden', bucketAccent(card.bucket)]">

    <!-- ── Header ─────────────────────────────────────────── -->
    <header class="flex items-start gap-4 p-5 pb-4">
      <img v-if="card.cover_image_url"
           :src="card.cover_image_url"
           :alt="`Capa de ${card.titulo}`"
           class="w-21 h-21 rounded object-cover flex-shrink-0 ring-1 ring-stone-200"
           style="width: 84px; height: 84px;"
           loading="lazy" />
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-[10px] font-semibold uppercase tracking-[0.13em] text-stone-400">
            {{ bucketShort(card.bucket) }}
          </span>
          <span v-if="card.afinidade_score"
                class="text-[10px] font-semibold uppercase tracking-[0.13em] text-amber-800">
            · afinidade {{ card.afinidade_score }}/10
          </span>
        </div>
        <h2 class="font-serif text-[1.4rem] leading-tight font-bold text-stone-900">
          {{ card.artista || 'Artista desconhecido' }}
        </h2>
        <p class="font-serif text-[1.02rem] text-stone-500 italic mt-0.5">
          {{ card.titulo }}<span class="not-italic text-stone-400 text-sm"> · {{ card.tipo }}</span>
        </p>
        <div v-if="card.label" class="text-xs text-stone-400 mt-0.5">{{ card.label }}</div>

        <!-- badges + reader trigger. Row always renders because the reader
             button is mobile-only and lives on the right; on desktop it's
             hidden via lg:hidden and the row may end up empty (harmless). -->
        <div class="flex flex-wrap items-center gap-1.5 mt-2.5">
          <span v-if="card.is_estreia"
                class="text-[10px] font-semibold tracking-wide px-2 py-0.5 bg-violet-100 text-violet-900 rounded-full border border-violet-200">
            ✨ ESTREIA
          </span>
          <!-- Álbum anunciado, ainda não lançado: mostra a data em vez de
               parecer "disco sem link". Futuro = relativo à data DA EDIÇÃO,
               não à de hoje — relatório antigo continua coerente. -->
          <span v-if="lancamentoFuturo"
                class="text-[10px] font-semibold tracking-wide px-2 py-0.5 bg-sky-100 text-sky-900 rounded-full border border-sky-200">
            📅 LANÇA EM {{ formatDate(card.data_lancamento) }}
          </span>
          <span v-for="s in selos" :key="s.fonte + s.tipo"
                :class="['text-[10px] font-semibold tracking-wide px-2 py-0.5 rounded-full border', seloColor(s.fonte)]">
            {{ seloIcon(s.fonte) }} {{ s.fonte }}: {{ s.tipo }}{{ s.nota ? ' ' + s.nota : '' }}
          </span>
          <button type="button"
                  @click.stop="reader.open(card)"
                  class="reader-trigger lg:hidden ml-auto"
                  aria-label="Abrir modo leitura">
            📖 Ler
          </button>
        </div>
      </div>
    </header>

    <!-- tags -->
    <div v-if="card.tags_estilo && card.tags_estilo.length"
         class="flex flex-wrap gap-1.5 px-5 pb-1">
      <span v-for="t in card.tags_estilo" :key="t"
            class="text-[10px] uppercase tracking-[0.08em] px-2 py-0.5 rounded bg-stone-100 text-stone-500">
        {{ t }}
      </span>
    </div>

    <!-- ── Editorial body ─────────────────────────────────── -->
    <div class="px-5 py-4 space-y-5">

      <!-- text fields, in editorial reading order -->
      <section v-for="f in textFields" :key="f.key" v-show="card[f.key]">
        <p class="field-label">{{ f.label }}</p>
        <p class="field-body">{{ card[f.key] }}</p>
      </section>

      <!-- parecido com -->
      <section v-if="card.parecido_com && card.parecido_com.length">
        <p class="field-label">Parecido com</p>
        <ul class="mt-1.5 space-y-1">
          <li v-for="p in card.parecido_com" :key="p"
              class="field-body pl-3 border-l-2 border-stone-200">{{ p }}</li>
        </ul>
      </section>

      <!-- faixas principais -->
      <section v-if="card.faixas_principais && card.faixas_principais.length">
        <p class="field-label">Comece por</p>
        <div class="flex flex-wrap gap-1.5 mt-1.5">
          <span v-for="fx in card.faixas_principais" :key="fx"
                class="text-[13px] font-serif px-2.5 py-1 rounded bg-stone-100 text-stone-700">
            {{ fx }}
          </span>
        </div>
      </section>

      <!-- citação destacada -->
      <blockquote v-if="card.citacao_destacada"
                  class="border-l-[3px] border-amber-300 bg-amber-50/50 pl-4 pr-3 py-3 rounded-r">
        <p class="font-serif text-[15px] italic leading-relaxed text-stone-800">
          “{{ card.citacao_destacada.texto }}”
        </p>
        <footer class="text-[11px] uppercase tracking-[0.1em] text-amber-800 mt-2">
          {{ card.citacao_destacada.fonte
          }}<span v-if="card.citacao_destacada.nota" class="text-stone-400"> · {{ card.citacao_destacada.nota }}</span>
        </footer>
      </blockquote>

      <!-- verso destacado -->
      <blockquote v-if="card.verso_destacado"
                  class="border-l-[3px] border-stone-300 pl-4 py-1">
        <p class="font-serif text-[15px] italic leading-relaxed text-stone-600">
          “{{ card.verso_destacado.texto }}”
        </p>
        <footer v-if="card.verso_destacado.faixa" class="text-[11px] uppercase tracking-[0.1em] text-stone-400 mt-1">
          faixa “{{ card.verso_destacado.faixa }}”
        </footer>
      </blockquote>

      <!-- o que não esperar -->
      <section v-if="card.o_que_nao_esperar"
               class="bg-amber-50 border border-amber-200 rounded px-3.5 py-3">
        <p class="text-[10px] font-semibold uppercase tracking-[0.13em] text-amber-800">⚠ O que não esperar</p>
        <p class="font-serif text-[14.5px] leading-relaxed text-amber-950 mt-1">{{ card.o_que_nao_esperar }}</p>
      </section>

      <!-- vale pra você — conclusão -->
      <section v-if="card.vale_pra_voce"
               class="border-t border-stone-200 pt-4">
        <p class="field-label">Vale pra você</p>
        <p class="font-serif text-[15.5px] leading-relaxed text-stone-900">{{ card.vale_pra_voce }}</p>
      </section>

      <!-- histórico — metadado discreto -->
      <p v-if="card.historico_cobertura"
         class="text-[11px] uppercase tracking-[0.1em] text-stone-400">
        No radar · {{ card.historico_cobertura }}
      </p>
    </div>

    <!-- ── Footer ─────────────────────────────────────────── -->
    <div class="px-5 pb-4">
      <LinksRow :links="card.links" :card="card" :relatorio-data="relatorioData" />
      <FontesFooter :fontes="card.fontes_cobertura" />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import LinksRow from './LinksRow.vue'
import FontesFooter from './FontesFooter.vue'
import { bucketAccent, bucketShort, formatDate } from '../utils/formatters.js'
import { useReader } from '../composables/useReader.js'

const reader = useReader()

const props = defineProps({
  card: { type: Object, required: true },
  relatorioData: { type: String, default: '' },
})

// Lançamento futuro RELATIVO À EDIÇÃO (não a hoje): comparação de strings
// ISO funciona lexicograficamente. Sem relatorioData (edge raro), não mostra.
const lancamentoFuturo = computed(() =>
  Boolean(
    props.card.data_lancamento
    && props.relatorioData
    && props.card.data_lancamento > props.relatorioData,
  )
)

// A selo is a prize from a *named critic house*. Gemini/Grok are our own
// search infrastructure — they surface data, they don't award anything.
// If the enrich step ever mislabels a selo's fonte as the aggregator, drop
// it here so the card never shows a meaningless "Gemini Web: Nota" badge.
const INFRA_SOURCES = /gemini|grok|web search/i
const selos = computed(() =>
  (props.card.selos_editoriais || []).filter(s => !INFRA_SOURCES.test(s.fonte || ''))
)

// Plain-text editorial fields, rendered in this reading order: each gets an
// eyebrow label + a serif body paragraph.
const textFields = [
  { key: 'resumo_critica',     label: 'A crítica' },
  { key: 'na_discografia',     label: 'Na discografia' },
  { key: 'letra_fala_sobre',   label: 'As letras' },
  { key: 'mudanca_musical',    label: 'O que muda' },
  { key: 'para_quem_gosta_de', label: 'Pra quem curte' },
  { key: 'prestar_atencao',    label: 'Preste atenção' },
  { key: 'dados_curiosos',     label: 'Bastidores' },
]

// Each selo is a prize the disc won — the icon signals which "house"
// awarded it. Pitchfork's 🏆 is the most canonizing; the rest get a
// medal/star so nothing reads as a generic afterthought.
function seloIcon(fonte) {
  const f = (fonte || '').toLowerCase()
  if (f.includes('pitchfork')) return '🏆'
  if (f.includes('quietus') || f.includes('wire')) return '🥇'
  if (f.includes('stereogum') || f.includes('bandcamp')) return '⭐'
  if (f.includes('resident advisor') || f.includes(' ra ') || f === 'ra') return '🎛️'
  if (f.includes('npr') || f.includes('kexp') || f.includes('bbc') || f.includes('nme')) return '🎯'
  if (f.includes('aoty') || f.includes('rym') || f.includes('metacritic') || f.includes('allmusic')) return '📊'
  return '🏅'
}

function seloColor(fonte) {
  const f = (fonte || '').toLowerCase()
  if (f.includes('pitchfork')) return 'bg-amber-100 text-amber-900 border-amber-200'
  if (f.includes('quietus') || f.includes('wire')) return 'bg-rose-100 text-rose-900 border-rose-200'
  if (f.includes('stereogum') || f.includes('bandcamp')) return 'bg-sky-100 text-sky-900 border-sky-200'
  if (f.includes('resident advisor') || f.includes(' ra ') || f === 'ra') return 'bg-indigo-100 text-indigo-900 border-indigo-200'
  if (f.includes('npr') || f.includes('kexp') || f.includes('bbc') || f.includes('nme')) return 'bg-emerald-100 text-emerald-900 border-emerald-200'
  if (f.includes('aoty') || f.includes('rym') || f.includes('metacritic') || f.includes('allmusic')) return 'bg-stone-100 text-stone-900 border-stone-200'
  return 'bg-violet-100 text-violet-900 border-violet-200'
}
</script>

<style scoped>
/* Eyebrow label — the kicker above each editorial field. Contrast with the
   body comes from FOUR axes at once: case, color, weight, size + the
   letter-spacing. Impossible to confuse with the serif body. */
.field-label {
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.135em;
  color: #92400e;            /* amber-800 — burnt editorial accent */
  margin-bottom: 4px;
}

/* Body — serif for comfortable long-form reading, generous leading. */
.field-body {
  font-family: theme('fontFamily.serif');
  font-size: 15px;
  line-height: 1.72;
  color: #44403c;            /* stone-700 — softer than pure black */
}

.release-card { scroll-margin-top: 5rem; }

/* Reader trigger — mobile/tablet only (lg:hidden in template). Discreet pill
   tucked at the end of the badges row; tap target ≥32px for touch ergonomics. */
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
  line-height: 1;
}
.reader-trigger:hover { background: #f5f5f4; }
</style>
