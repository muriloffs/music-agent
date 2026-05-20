<template>
  <div class="mt-3 pt-3 border-t border-stone-200 text-xs text-stone-600">
    <span class="font-medium">Fontes:</span>
    <a v-for="(f, idx) in fontes" :key="f.id + idx"
       :href="f.url"
       @click="(e) => handleExternalLinkClick(e, f.url)"
       target="_blank" rel="noopener"
       class="ml-2 underline hover:text-stone-900">
      {{ sourceLabel(f.id) }}<span v-if="f.nota"> ({{ f.nota }})</span>
    </a>
  </div>
</template>

<script setup>
import { handleExternalLinkClick } from '../utils/openLink.js'
import { sourceLabel } from '../utils/formatters.js'

defineProps({ fontes: { type: Array, default: () => [] } })
</script>
