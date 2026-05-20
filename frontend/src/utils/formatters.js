const GENRE_MAP = [
  { key: 'jazz',       label: '🎷 Jazz',           match: ['jazz', 'avant', 'free improv', 'spiritual jazz'] },
  { key: 'electronic', label: '🎹 Eletrônica',      match: ['electronic', 'eletrôn', 'techno', 'house', 'ambient', 'idm', 'club', 'leftfield'] },
  { key: 'folk',       label: '🌾 Folk',            match: ['folk', 'americana', 'alt-country', 'singer-songwriter'] },
  { key: 'rock',       label: '🎸 Rock / Punk',     match: ['rock', 'punk', 'post-punk', 'shoegaze', 'noise', 'garage'] },
  { key: 'pop',        label: '✦ Pop / Dream Pop',  match: ['pop', 'dream pop', 'bedroom', 'synth'] },
  { key: 'hiphop',     label: '🎤 Hip-hop',         match: ['hip-hop', 'hip hop', 'rap', 'trap'] },
]

export function cardGenres(card) {
  const tags = (card.tags_estilo || []).map(t => (t || '').toLowerCase())
  const genres = new Set()
  for (const g of GENRE_MAP) {
    if (tags.some(t => g.match.some(m => t.includes(m)))) genres.add(g.key)
  }
  return genres
}

export function genreLabel(key) {
  const g = GENRE_MAP.find(x => x.key === key)
  return g ? g.label : key
}

export const GENRE_KEYS = GENRE_MAP.map(g => g.key)

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
