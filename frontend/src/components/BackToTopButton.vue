<template>
  <transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-200"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0">
    <button v-show="visible"
            @click="scrollToTop"
            aria-label="Voltar pro topo"
            class="fixed bottom-4 right-4 z-50 w-12 h-12 rounded-full
                   bg-stone-900 hover:bg-stone-800 active:bg-stone-700
                   text-stone-50 text-xl shadow-lg
                   flex items-center justify-center
                   transition-colors">
      ↑
    </button>
  </transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

// Same pattern as culture-agent's BackToTopButton (lesson 4 sibling — reuse what works)
const visible = ref(false)
const THRESHOLD = 400 // px scrolled before button appears

function onScroll() {
  visible.value = window.scrollY > THRESHOLD
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll() // check initial state
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>
