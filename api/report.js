// api/report.js — Vercel Edge Function returning latest report JSON from GitHub raw

export const config = { runtime: 'edge' }

const GITHUB_OWNER = 'muriloffs'
const GITHUB_REPO = 'music-agent'
const GITHUB_BRANCH = 'main'
const DATA_DIR = 'data'

export default async function handler(request) {
  try {
    // List files in data/ via GitHub contents API
    const listUrl = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${DATA_DIR}?ref=${GITHUB_BRANCH}`
    const listResp = await fetch(listUrl, {
      headers: { 'User-Agent': 'music-agent-vercel', 'Accept': 'application/vnd.github.v3+json' },
    })
    if (!listResp.ok) {
      return new Response(JSON.stringify({ error: 'list failed', status: listResp.status }), { status: 502, headers: { 'Content-Type': 'application/json' } })
    }
    const files = await listResp.json()
    const reports = files
      .filter(f => f.name.startsWith('relatorio-') && f.name.endsWith('.json'))
      .sort((a, b) => b.name.localeCompare(a.name))
    if (reports.length === 0) {
      return new Response(JSON.stringify({ error: 'no reports yet' }), { status: 404, headers: { 'Content-Type': 'application/json' } })
    }
    const latest = reports[0]
    const rawResp = await fetch(latest.download_url)
    if (!rawResp.ok) {
      return new Response(JSON.stringify({ error: 'fetch raw failed', status: rawResp.status }), { status: 502, headers: { 'Content-Type': 'application/json' } })
    }
    const body = await rawResp.text()
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    })
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: { 'Content-Type': 'application/json' } })
  }
}
