// api/report.js — Vercel Edge Function serving a weekly report JSON.
//
//   /api/report                  → the most recent report
//   /api/report?date=2026-05-20  → that specific week's report (permalink)
//
// Past reports are all committed in data/, so old cards stay reachable —
// a Things task or WhatsApp share can deep-link to a card weeks later.

export const config = { runtime: 'edge' }

const GITHUB_OWNER = 'muriloffs'
const GITHUB_REPO = 'music-agent'
const GITHUB_BRANCH = 'main'
const DATA_DIR = 'data'

function jsonError(msg, status, extra = {}) {
  return new Response(JSON.stringify({ error: msg, ...extra }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export default async function handler(request) {
  try {
    const url = new URL(request.url)
    const date = url.searchParams.get('date')

    let rawUrl

    if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
      // Specific week — address the file directly on raw.githubusercontent.
      rawUrl = `https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${GITHUB_BRANCH}/${DATA_DIR}/relatorio-${date}.json`
    } else {
      // Latest — list data/ and pick the newest by filename.
      const listUrl = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${DATA_DIR}?ref=${GITHUB_BRANCH}`
      const listResp = await fetch(listUrl, {
        headers: { 'User-Agent': 'music-agent-vercel', 'Accept': 'application/vnd.github.v3+json' },
      })
      if (!listResp.ok) return jsonError('list failed', 502, { status: listResp.status })
      const files = await listResp.json()
      const reports = files
        .filter(f => f.name.startsWith('relatorio-') && f.name.endsWith('.json'))
        .sort((a, b) => b.name.localeCompare(a.name))
      if (reports.length === 0) return jsonError('no reports yet', 404)
      rawUrl = reports[0].download_url
    }

    const rawResp = await fetch(rawUrl)
    if (!rawResp.ok) {
      return jsonError('report not found', rawResp.status === 404 ? 404 : 502, { status: rawResp.status })
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
    return jsonError(String(e), 500)
  }
}
