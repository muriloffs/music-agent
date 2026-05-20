<template>
  <div v-if="hasAnyLink || waUrl" class="flex flex-wrap gap-2 mt-3">
    <!-- Music service links open as plain <a> — NOT through openLink.js.
         music.apple.com / open.spotify.com etc have native deep links that
         the OS resolves to the installed app. Routing them through the
         googlechromes:// scheme (lesson 4) BREAKS that on iOS. The Chrome
         workaround is only for editorial/review links (see FontesFooter). -->
    <a v-if="links.spotify" :href="links.spotify"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Spotify
    </a>
    <a v-if="links.bandcamp" :href="links.bandcamp"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Bandcamp
    </a>
    <a v-if="links.apple_music" :href="links.apple_music"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Apple Music
    </a>
    <a v-if="links.youtube" :href="links.youtube"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      YouTube
    </a>
    <a v-if="waUrl" :href="waUrl" target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700">
      💬 WhatsApp
    </a>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  links: { type: Object, required: true },
  card: { type: Object, default: () => null },
})

const hasAnyLink = computed(() =>
  props.links && (props.links.spotify || props.links.bandcamp || props.links.apple_music || props.links.youtube)
)

const waUrl = computed(() => {
  if (!props.card) return null
  const c = props.card
  const lines = []
  const artist = c.artista || 'Artista desconhecido'
  const title = c.titulo || ''
  lines.push(`🎵 ${artist} — ${title}`)

  const badges = []
  if (c.is_estreia) badges.push('✨ Estreia')
  for (const s of (c.selos_editoriais || []).slice(0, 2)) {
    const nota = s.nota ? ` ${s.nota}` : ''
    badges.push(`🏆 ${s.fonte}: ${s.tipo}${nota}`)
  }
  if (badges.length) lines.push(badges.join(' · '))

  if (c.para_quem_gosta_de) lines.push(c.para_quem_gosta_de)

  // Link: prefer Apple Music (recipient opens straight into the music),
  // fall back to the card anchor on the site.
  const appleMusic = (props.links && props.links.apple_music) || null
  if (appleMusic) {
    lines.push(`🎧 Ouvir: ${appleMusic}`)
  } else {
    const base = (typeof window !== 'undefined' && window.location?.origin) || 'https://music-agent-xi.vercel.app'
    lines.push(`👉 ${base}/#${c.id}`)
  }

  const text = lines.join('\n')
  return `https://wa.me/?text=${encodeURIComponent(text)}`
})
</script>
