<template>
  <div v-if="hasAnyLink" class="flex gap-2 mt-3">
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
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { handleExternalLinkClick } from '../utils/openLink.js'

const props = defineProps({ links: { type: Object, required: true } })
const hasAnyLink = computed(() =>
  props.links && (props.links.spotify || props.links.bandcamp || props.links.apple_music || props.links.youtube)
)
</script>
