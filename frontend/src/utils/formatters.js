export function formatDate(isoDate) {
  if (!isoDate) return ''
  try {
    const d = new Date(isoDate)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return isoDate
  }
}

// A arquitetura de buckets mudou em 2026-06-08. Os antigos (alinhado /
// media_afinidade / consensus) classificavam por proximidade INFERIDA com
// o gosto do leitor — falha estrutural: o LLM puxava ambient/jazz/
// electronic indiscriminadamente. Os novos:
//
//   - meus_artistas       — whitelist explícita (det., sem LLM)
//   - destaque_editorial  — selo nomeado, nota >= 7.5, ou cobertura >= 2 fontes
//   - noise               — sem sinal
//
// Relatórios antigos ainda têm buckets legados; normalizeBucket() mapeia
// pra os novos pra que a navegação funcione across-edition sem migração.
const LEGACY_TO_NEW = {
  alinhado: 'destaque_editorial',
  media_afinidade: 'destaque_editorial',
  consensus: 'destaque_editorial',
}
export function normalizeBucket(bucket) {
  return LEGACY_TO_NEW[bucket] || bucket
}

export function bucketLabel(bucket) {
  const labels = {
    meus_artistas: '⭐ Dos seus artistas',
    destaque_editorial: '🏆 Destaques editoriais',
    // legacy — só aparecem se alguém pegar bucketLabel direto sem normalizar
    alinhado: '🏆 Destaques editoriais',
    media_afinidade: '🏆 Destaques editoriais',
    consensus: '🏆 Destaques editoriais',
  }
  return labels[bucket] || bucket
}

// Left-edge accent stripe per bucket — the editorial card is a white body
// with a 4px colored left border carrying the bucket identity.
export function bucketAccent(bucket) {
  const accents = {
    meus_artistas: 'border-l-amber-500',         // âmbar quente — destaque pessoal
    destaque_editorial: 'border-l-violet-600',   // violeta — sinal crítico
    // legacy continuam com a cor original pra relatórios antigos lerem bem
    alinhado: 'border-l-emerald-600',
    media_afinidade: 'border-l-amber-500',
    consensus: 'border-l-violet-600',
  }
  return accents[bucket] || 'border-l-stone-400'
}

// Short human label for the bucket, shown as a small tag on the card.
export function bucketShort(bucket) {
  const s = {
    meus_artistas: 'Seu artista',
    destaque_editorial: 'Destaque',
    // legacy
    alinhado: 'Destaque',
    media_afinidade: 'Destaque',
    consensus: 'Destaque',
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
  consequence: 'Consequence',
  brooklyn_vegan: 'BrooklynVegan',
  guardian_music: 'The Guardian',
  paste_music: 'Paste Magazine',
  fader: 'The FADER',
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
