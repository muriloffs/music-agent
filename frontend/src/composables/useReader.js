// useReader.js — module-level singleton state for the "modo leitura" modal.
// Adapted from culture-agent's manual (docs/manuais/modo-leitura-mobile-manual.md).
// Music-agent has one card flavor that needs this (ReleaseCard), so there's no
// `mode` switch — every call opens a release in the reader.

import { ref, watch } from "vue"

const STORAGE_KEY = "reader.fontSize"
const FONT_DEFAULT = 22
const FONT_MIN = 16
const FONT_MAX = 36
const FONT_STEP = 2

// Module-level refs — same instance across every `useReader()` import.
const currentItem = ref(null)
const fontSize = ref(_loadFontSize())

function _loadFontSize() {
  if (typeof localStorage === "undefined") return FONT_DEFAULT
  const raw = parseInt(localStorage.getItem(STORAGE_KEY), 10)
  if (!Number.isFinite(raw)) return FONT_DEFAULT
  return Math.min(FONT_MAX, Math.max(FONT_MIN, raw))
}

watch(fontSize, (v) => {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, String(v))
  }
})

export function useReader() {
  return {
    currentItem,
    fontSize,
    open(card) { currentItem.value = card },
    close() { currentItem.value = null },
    incFont() { fontSize.value = Math.min(FONT_MAX, fontSize.value + FONT_STEP) },
    decFont() { fontSize.value = Math.max(FONT_MIN, fontSize.value - FONT_STEP) },
    canIncrease: () => fontSize.value < FONT_MAX,
    canDecrease: () => fontSize.value > FONT_MIN,
  }
}
