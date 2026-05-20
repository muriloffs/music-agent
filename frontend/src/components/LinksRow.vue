<template>
  <div v-if="hasAnyLink || waUrl" class="flex flex-wrap gap-2 mt-3">
    <a v-if="links.spotify" :href="links.spotify"
       @click="(e) => handleExternalLinkClick(e, links.spotify)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Spotify
    </a>
    <a v-if="links.bandcamp" :href="links.bandcamp"
       @click="(e) => handleExternalLinkClick(e, links.bandcamp)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Bandcamp
    </a>
    <a v-if="links.apple_music" :href="links.apple_music"
       @click="(e) => handleExternalLinkClick(e, links.apple_music)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Apple Music
    </a>
    <a v-if="links.youtube" :href="links.youtube"
       @click="(e) => handleExternalLinkClick(e, links.youtube)"
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
import { handleExternalLinkClick } from '../utils/openLink.js'

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

  const base = (typeof window !== 'undefined' && window.location?.origin) || 'https://music-agent-xi.vercel.app'
  lines.push(`👉 ${base}/#${c.id}`)

  const text = lines.join('\n')
  return `https://wa.me/?text=${encodeURIComponent(text)}`
})
</script>
