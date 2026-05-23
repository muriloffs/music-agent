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

// Internal fetcher ids → the publication's real name. The pipeline tags
// each coverage entry with an id like "pitchfork_reviews"; that id must
// never reach the reader. pitchfork_news + pitchfork_reviews both collapse
// to "Pitchfork" — the reader cares about the outlet, not which feed.
const SOURCE_NAMES = {
  stereogum: 'Stereogum',
  quietus: 'The Quietus',
  bandcamp_daily: 'Bandcamp Daily',
  aquarium_drunkard: 'Aquarium Drunkard',
  scream_yell: 'Scream & Yell',
  the_wire: 'The Wire',
  line_of_best_fit: 'The Line of Best Fit',
  npr_music: 'NPR Music',
  gorilla_vs_bear: 'Gorilla vs. Bear',
  loud_and_quiet: 'Loud and Quiet',
  fact_mag: 'FACT',
  crack_magazine: 'Crack Magazine',
  pitchfork_news: 'Pitchfork',
  pitchfork_reviews: 'Pitchfork',
  hearing_things: 'Hearing Things',
  diy_mag: 'DIY Magazine',
  volume_morto: 'Volume Morto',
  gemini_web: 'Busca web',
  grok_x: 'X',
  lastfm: 'Last.fm',
}

export function sourceLabel(id) {
  if (!id) return ''
  if (SOURCE_NAMES[id]) return SOURCE_NAMES[id]
  // Unknown id: de-snake-case and Title Case it rather than leak the raw id.
  return String(id).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
