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
    alinhado: '🎯 Alinhados ao gosto',
    media_afinidade: '🔍 Vale explorar',
    consensus: '🏆 Aclamados da semana',
    br: '🇧🇷 BR da semana',
  }
  return labels[bucket] || bucket
}

export function bucketColor(bucket) {
  const colors = {
    alinhado: 'bg-emerald-50 text-emerald-900 border-emerald-200',
    media_afinidade: 'bg-amber-50 text-amber-900 border-amber-200',
    consensus: 'bg-violet-50 text-violet-900 border-violet-200',
    br: 'bg-yellow-50 text-yellow-900 border-yellow-200',
  }
  return colors[bucket] || 'bg-stone-50 text-stone-900 border-stone-200'
}
