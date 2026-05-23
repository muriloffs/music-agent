// api/reports.js — Vercel Edge Function listing dates of every committed
// weekly report. Powers the "Edicoes anteriores" dropdown in the frontend.

export const config = { runtime: 'edge' }

const GITHUB_OWNER = 'muriloffs'
const GITHUB_REPO = 'music-agent'
const GITHUB_BRANCH = 'main'
const DATA_DIR = 'data'

export default async function handler() {
  try {
    const listUrl = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${DATA_DIR}?ref=${GITHUB_BRANCH}`
    const listResp = await fetch(listUrl, {
      headers: { 'User-Agent': 'music-agent-vercel', 'Accept': 'application/vnd.github.v3+json' },
    })
    if (!listResp.ok) {
      return new Response(
        JSON.stringify({ error: 'list failed', status: listResp.status }),
        { status: 502, headers: { 'Content-Type': 'application/json' } },
      )
    }
    const files = await listResp.json()
    const dates = files
      .map((f) => /^relatorio-(\d{4}-\d{2}-\d{2})\.json$/.exec(f.name))
      .filter(Boolean)
      .map((m) => m[1])
      .sort((a, b) => b.localeCompare(a))
    return new Response(JSON.stringify({ dates }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    })
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String(e) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    )
  }
}
