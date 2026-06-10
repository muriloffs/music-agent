<template>
  <div v-if="hasAnyLink || waUrl || thingsUrl" class="flex flex-wrap gap-2 mt-3">
    <!-- Music/WhatsApp links all go through handleExternalLinkClick. On iOS
         the helper recognizes these hosts (APP_PREFERRED_HOSTS) and uses
         window.open so iOS Universal Links route to the native app; on
         desktop/Android it's a no-op and the <a> opens normally. Single
         choke point keeps the exception list in one place. -->
    <a v-if="links.spotify" :href="links.spotify"
       target="_blank" rel="noopener"
       @click.stop="handleExternalLinkClick($event, links.spotify)"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Spotify
    </a>
    <a v-if="links.bandcamp" :href="links.bandcamp"
       target="_blank" rel="noopener"
       @click.stop="handleExternalLinkClick($event, links.bandcamp)"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Bandcamp
    </a>
    <!-- apple_music_tipo === 'single': o álbum ainda não está no catálogo
         (anunciado); o link aponta pra lead track. O rótulo avisa. -->
    <a v-if="links.apple_music" :href="links.apple_music"
       target="_blank" rel="noopener"
       @click.stop="handleExternalLinkClick($event, links.apple_music)"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Apple Music{{ links.apple_music_tipo === 'single' ? ' · single' : '' }}
    </a>
    <a v-if="links.youtube" :href="links.youtube"
       target="_blank" rel="noopener"
       @click.stop="handleExternalLinkClick($event, links.youtube)"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      YouTube
    </a>
    <!-- Things deep-link uses a custom scheme (things:///). Plain <a href>
         is the cleanest path — iOS resolves the registered scheme directly.
         The handler isn't useful here (would fall into the non-http branch
         and risk popup-blocker friction with window.open on a custom scheme). -->
    <a v-if="thingsUrl" :href="thingsUrl"
       class="text-xs px-2 py-1 rounded bg-sky-600 text-white hover:bg-sky-700">
      ✓ Things
    </a>
    <a v-if="waUrl" :href="waUrl" target="_blank" rel="noopener"
       @click.stop="handleExternalLinkClick($event, waUrl)"
       class="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700">
      💬 WhatsApp
    </a>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { handleExternalLinkClick } from '../utils/openLink.js'

const props = defineProps({
  links: { type: Object, required: true },
  card: { type: Object, default: () => null },
  // relatorio_data of the report this card belongs to — used to build a
  // permalink that survives past this week (?r=YYYY-MM-DD#card_id).
  relatorioData: { type: String, default: '' },
})

const hasAnyLink = computed(() =>
  props.links && (props.links.spotify || props.links.bandcamp || props.links.apple_music || props.links.youtube)
)

// Permalink to this exact card, addressable even weeks later: the site
// reads ?r= and loads that week's archived report, then scrolls to #card.
function cardPermalink(c) {
  const base = (typeof window !== 'undefined' && window.location?.origin) || 'https://music-agent-xi.vercel.app'
  const r = props.relatorioData ? `?r=${props.relatorioData}` : ''
  return `${base}/${r}#${c.id}`
}

// Things 3 to-do via URL scheme (Apple-native, same pattern as sibling
// agents). Pre-fills title + notes; the note carries a brief blurb, the
// Apple Music link, and the card permalink. Routed into the "music"
// project (list=) as an Anytime task (when=) — the project must already
// exist in Things, otherwise the task silently falls back to the Inbox.
const thingsUrl = computed(() => {
  if (!props.card) return null
  const c = props.card
  const title = `🎵 ${c.artista || 'Artista'} — ${c.titulo || ''}`.trim()
  const lines = []
  const blurb = c.vale_pra_voce || c.resumo_critica || ''
  if (blurb) lines.push(blurb.length > 260 ? blurb.slice(0, 260) + '…' : blurb)
  if (props.links && props.links.apple_music) {
    lines.push(`🎧 Apple Music: ${props.links.apple_music}`)
  }
  lines.push(`🔗 Card: ${cardPermalink(c)}`)
  const q = [
    `title=${encodeURIComponent(title)}`,
    `notes=${encodeURIComponent(lines.join('\n\n'))}`,
    `list=${encodeURIComponent('music')}`,
    `when=anytime`,
  ]
  return `things:///add?${q.join('&')}`
})

// WhatsApp share — prefilled message ending in the Apple Music link
// (recipient opens straight into the music) or the card permalink.
const waUrl = computed(() => {
  if (!props.card) return null
  const c = props.card
  const lines = []
  lines.push(`🎵 ${c.artista || 'Artista desconhecido'} — ${c.titulo || ''}`)

  const badges = []
  if (c.is_estreia) badges.push('✨ Estreia')
  // Skip selos mislabeled with our search infra (Gemini/Grok) as the fonte —
  // a selo is a prize from a named critic house, see ReleaseCard.vue.
  const realSelos = (c.selos_editoriais || []).filter(s => !/gemini|grok|web search/i.test(s.fonte || ''))
  for (const s of realSelos.slice(0, 2)) {
    const nota = s.nota ? ` ${s.nota}` : ''
    badges.push(`🏆 ${s.fonte}: ${s.tipo}${nota}`)
  }
  if (badges.length) lines.push(badges.join(' · '))

  if (c.para_quem_gosta_de) lines.push(c.para_quem_gosta_de)

  const appleMusic = (props.links && props.links.apple_music) || null
  if (appleMusic) {
    lines.push(`🎧 Ouvir: ${appleMusic}`)
  } else {
    lines.push(`👉 ${cardPermalink(c)}`)
  }

  return `https://wa.me/?text=${encodeURIComponent(lines.join('\n'))}`
})
</script>
