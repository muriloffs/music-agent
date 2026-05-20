export function formatDate(isoDate) {
  if (!isoDate) return ''
  try {
    const d = new Date(isoDate)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return isoDate
  }
}

export function bucketLabel(bucket) {
  const labels = {
    alinhado: '🎯 Preferidos',
    media_afinidade: '🔍 Vale explorar',
    consensus: '🏆 Aclamados',
  }
  return labels[bucket] || bucket
}

// Left-edge accent stripe per bucket — the editorial card is a white body
// with a 4px colored left border carrying the bucket identity (a full
// pastel fill competes with long text; a stripe doesn't).
export function bucketAccent(bucket) {
  const accents = {
    alinhado: 'border-l-emerald-600',
    media_afinidade: 'border-l-amber-500',
    consensus: 'border-l-violet-600',
  }
  return accents[bucket] || 'border-l-stone-400'
}

// Short human label for the bucket, shown as a small tag on the card.
export function bucketShort(bucket) {
  const s = {
    alinhado: 'Preferido',
    media_afinidade: 'Vale explorar',
    consensus: 'Aclamado',
  }
  return s[bucket] || bucket
}
