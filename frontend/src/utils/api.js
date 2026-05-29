// api.js — thin wrappers around the existing Vercel edge functions.
//
// The search composable expects `fetchIndex()` and `fetchReportByDate(date)`.
// Music-agent already has /api/reports and /api/report?date= from the
// archive-dropdown feature, so this file just adapts their shapes.

export async function fetchIndex() {
  const resp = await fetch('/api/reports')
  if (!resp.ok) throw new Error(`/api/reports: HTTP ${resp.status}`)
  const data = await resp.json()
  return Array.isArray(data.dates) ? data.dates : []
}

export async function fetchReportByDate(date) {
  if (!date) throw new Error('fetchReportByDate: missing date')
  const resp = await fetch(`/api/report?date=${encodeURIComponent(date)}`)
  if (!resp.ok) throw new Error(`/api/report?date=${date}: HTTP ${resp.status}`)
  return await resp.json()
}
