// 관리자 API 래퍼 — /api는 vite(dev)/nginx(prod)가 8787 Flask로 프록시
async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 204) return null
  let body = null
  try { body = await res.json() } catch { /* 본문 없음 */ }
  if (!res.ok) throw new Error(body?.error || `요청 실패 (${res.status})`)
  return body
}

export const getConfig = () => request('/config')

export const addPath = (path, recursive = true) =>
  request('/paths', { method: 'POST', body: JSON.stringify({ path, recursive }) })

export const updatePath = (id, patch) =>
  request(`/paths/${id}`, { method: 'PATCH', body: JSON.stringify(patch) })

export const removePath = (id) =>
  request(`/paths/${id}`, { method: 'DELETE' })

export const listQuarantine = () => request('/quarantine')

export const restoreQuarantine = (id) =>
  request(`/quarantine/${id}/restore`, { method: 'POST' })

export const deleteQuarantine = (id) =>
  request(`/quarantine/${id}`, { method: 'DELETE' })

export const updateSettings = (ignoreSuffixes) =>
  request('/settings', { method: 'PUT', body: JSON.stringify({ ignore_suffixes: ignoreSuffixes }) })
