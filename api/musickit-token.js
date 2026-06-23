// api/musickit-token.js — Vercel Edge Function que emite o Apple Music
// Developer Token (JWT ES256) usado pelo MusicKit JS no navegador.
//
// O token identifica o SEU app/time Apple e autoriza acesso ao catálogo +
// a criação de playlists na biblioteca de quem autorizar. Ele é público por
// design (vai pro front). O que é secreto é a chave privada .p8, que mora
// só aqui como env var e nunca chega ao navegador.
//
// Env vars necessárias (Vercel → Settings → Environment Variables):
//   APPLE_TEAM_ID      — 10 chars, o Team ID da conta Apple Developer
//   APPLE_KEY_ID       — 10 chars, o Key ID da chave MusicKit (.p8)
//   APPLE_PRIVATE_KEY  — conteúdo do arquivo .p8 (PEM, com -----BEGIN...)
//
// Enquanto as três não estiverem setadas, devolve 503 com
// {error:'apple_music_not_configured'} — o front trata isso como
// "ainda não ativado" em vez de quebrar.

export const config = { runtime: 'edge' }

// base64url de uma string ASCII ou de bytes (Uint8Array).
function b64url(input) {
  let bin
  if (typeof input === 'string') {
    bin = input
  } else {
    bin = ''
    for (const byte of input) bin += String.fromCharCode(byte)
  }
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

// PEM (.p8 PKCS#8) → ArrayBuffer dos bytes DER, pra importKey.
function pemToArrayBuffer(pem) {
  const b64 = pem
    .replace(/-----BEGIN [^-]+-----/, '')
    .replace(/-----END [^-]+-----/, '')
    .replace(/\s+/g, '')
  const bin = atob(b64)
  const buf = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i)
  return buf.buffer
}

export default async function handler() {
  const teamId = process.env.APPLE_TEAM_ID
  const keyId = process.env.APPLE_KEY_ID
  let pem = process.env.APPLE_PRIVATE_KEY

  if (!teamId || !keyId || !pem) {
    return new Response(
      JSON.stringify({ error: 'apple_music_not_configured' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } },
    )
  }

  // Vercel costuma guardar quebras de linha como "\n" literal — restaura.
  pem = pem.replace(/\\n/g, '\n')

  try {
    const now = Math.floor(Date.now() / 1000)
    // Apple permite até ~6 meses (15777000s). Usamos 180 dias.
    const exp = now + 60 * 60 * 24 * 180

    const header = { alg: 'ES256', kid: keyId }
    const payload = { iss: teamId, iat: now, exp }
    const signingInput =
      `${b64url(JSON.stringify(header))}.${b64url(JSON.stringify(payload))}`

    const key = await crypto.subtle.importKey(
      'pkcs8',
      pemToArrayBuffer(pem),
      { name: 'ECDSA', namedCurve: 'P-256' },
      false,
      ['sign'],
    )
    // Web Crypto devolve a assinatura ECDSA já no formato r||s (IEEE P1363),
    // que é exatamente o que o JWS ES256 espera — sem conversão DER.
    const sigBuf = await crypto.subtle.sign(
      { name: 'ECDSA', hash: 'SHA-256' },
      key,
      new TextEncoder().encode(signingInput),
    )
    const token = `${signingInput}.${b64url(new Uint8Array(sigBuf))}`

    return new Response(JSON.stringify({ token }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        // Token vale 180 dias; pode cachear pesado na borda.
        'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=604800',
      },
    })
  } catch (e) {
    return new Response(
      JSON.stringify({ error: 'token_signing_failed', detail: String(e) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    )
  }
}
