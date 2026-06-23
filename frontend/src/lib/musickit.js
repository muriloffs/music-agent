// musickit.js — integração MusicKit JS v3 pra criar a "Playlist da semana"
// na biblioteca Apple Music do usuário.
//
// Fluxo: carrega o SDK da CDN da Apple → configura com o Developer Token
// (vindo de /api/musickit-token) → usuário autoriza (1x) → pra cada
// lançamento da semana resolve UMA faixa (a principal, ou a 1ª do álbum) →
// POST /v1/me/library/playlists com as faixas.
//
// Nada aqui funciona até as env vars APPLE_* existirem na Vercel; antes
// disso getMusicKit() rejeita com Error('not_configured'), que a aba trata
// como "ainda não ativado".

const MUSICKIT_CDN = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js'

let _instance = null
let _loadPromise = null

// Injeta o <script> do MusicKit uma única vez e resolve quando o SDK avisa
// que carregou (evento 'musickitloaded').
function loadSdk() {
  if (_loadPromise) return _loadPromise
  _loadPromise = new Promise((resolve, reject) => {
    if (typeof window !== 'undefined' && window.MusicKit) return resolve()
    const script = document.createElement('script')
    script.src = MUSICKIT_CDN
    script.async = true
    document.addEventListener('musickitloaded', () => resolve(), { once: true })
    script.onerror = () => reject(new Error('musickit_load_failed'))
    document.head.appendChild(script)
  })
  return _loadPromise
}

// Carrega o SDK, busca o Developer Token e devolve a instância configurada
// (memoizada). Lança Error('not_configured') se as env vars Apple não
// estiverem setadas ainda.
export async function getMusicKit() {
  if (_instance) return _instance
  await loadSdk()

  const resp = await fetch('/api/musickit-token')
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    if (body.error === 'apple_music_not_configured') {
      throw new Error('not_configured')
    }
    throw new Error('token_failed')
  }
  const { token } = await resp.json()

  await window.MusicKit.configure({
    developerToken: token,
    app: { name: 'Music Agent', build: '1.0.0' },
  })
  _instance = window.MusicKit.getInstance()
  return _instance
}

// Normaliza nome de faixa pra casar "Faixa-título" / acentos / sufixos
// entre o que o relatório guardou e o que o catálogo BR devolve.
function normalize(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')   // tira acentos
    .replace(/\(.*?\)/g, '')           // tira "(faixa-título)", "(remix)" etc.
    .replace(/[^a-z0-9]/g, '')
    .trim()
}

// Extrai de uma URL Apple Music o que precisamos pra resolver UMA faixa:
//   song:  .../album/<slug>/<collId>?i=<trackId>  → songId (catálogo)
//   album: .../album/<slug>/<collId>              → albumId (resolve depois)
export function parseAppleUrl(url) {
  if (!url) return null
  const track = /[?&]i=(\d+)/.exec(url)
  if (track) return { songId: track[1] }
  const album = /\/(?:album|song)\/[^/]+\/(\d+)/.exec(url)
  if (album) return { albumId: album[1] }
  return null
}

// Resolve o catalog song ID de UM item. Item já vem com songId OU albumId
// (+ faixaPrincipal opcional). Pra álbum, busca as faixas no storefront do
// usuário e escolhe a principal por nome; sem match, pega a 1ª faixa.
async function resolveSongId(mk, storefront, item) {
  if (item.songId) return String(item.songId)
  if (!item.albumId) return null

  const res = await mk.api.music(
    `v1/catalog/${storefront}/albums/${item.albumId}`,
    { include: 'tracks' },
  )
  const album = res?.data?.data?.[0]
  const tracks = album?.relationships?.tracks?.data || []
  if (tracks.length === 0) return null

  if (item.faixaPrincipal) {
    const alvo = normalize(item.faixaPrincipal)
    const match = tracks.find((t) => {
      const nome = normalize(t.attributes?.name)
      return nome && (nome.includes(alvo) || alvo.includes(nome))
    })
    if (match) return match.id
  }
  return tracks[0].id  // fallback determinístico: 1ª faixa do álbum
}

// Cria a playlist na biblioteca do usuário. `items` é a lista já ordenada
// ({ label, songId?, albumId?, faixaPrincipal? }). Devolve quantas faixas
// entraram, quais foram puladas, e a resposta crua da API.
export async function createWeeklyPlaylist(items, { name, description }) {
  const mk = await getMusicKit()
  if (!mk.isAuthorized) await mk.authorize()  // pop-up de login Apple (1x)
  const storefront = mk.storefrontId || 'us'

  const ids = []
  const skipped = []
  // Resolução sequencial: simples e evita rajada de chamadas ao catálogo.
  for (const item of items) {
    try {
      const id = await resolveSongId(mk, storefront, item)
      if (id) ids.push(id)
      else skipped.push(item.label)
    } catch {
      skipped.push(item.label)
    }
  }
  if (ids.length === 0) throw new Error('no_tracks_resolved')

  const body = {
    attributes: { name, description },
    relationships: {
      tracks: { data: ids.map((id) => ({ id, type: 'songs' })) },
    },
  }
  const res = await mk.api.music('v1/me/library/playlists', {}, {
    fetchOptions: { method: 'POST', body: JSON.stringify(body) },
  })

  // A resposta traz o id da playlist na biblioteca; montamos um link pra abrir.
  const playlist = res?.data?.data?.[0]
  return {
    created: ids.length,
    skipped,
    playlistName: playlist?.attributes?.name || name,
  }
}
