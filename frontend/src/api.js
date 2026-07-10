// 관리자 API 래퍼 — /api는 vite(dev)/nginx(prod)가 8787 Flask로 프록시
const ACTOR_KEY = 'lhams_admin_actor'

export const getActor = () => localStorage.getItem(ACTOR_KEY) || ''
export const setActor = (name) => localStorage.setItem(ACTOR_KEY, name.trim())

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

// 변경(mutating) 요청은 모두 actor를 함께 실어 보내 "누가 바꿨는지"를 서버 감사로그에 남긴다.
const withActor = (body = {}) => JSON.stringify({ ...body, actor: getActor() })

export const getConfig = () => request('/config')

export const addPath = (path, recursive = true) =>
  request('/paths', { method: 'POST', body: withActor({ path, recursive }) })

export const updatePath = (id, patch) =>
  request(`/paths/${id}`, { method: 'PATCH', body: withActor(patch) })

export const removePath = (id) =>
  request(`/paths/${id}`, { method: 'DELETE', body: withActor() })

export const listQuarantine = () => request('/quarantine')

export const restoreQuarantine = (id) =>
  request(`/quarantine/${id}/restore`, { method: 'POST', body: withActor() })

export const deleteQuarantine = (id) =>
  request(`/quarantine/${id}`, { method: 'DELETE', body: withActor() })

export const updateSettings = (ignoreSuffixes) =>
  request('/settings', { method: 'PUT', body: withActor({ ignore_suffixes: ignoreSuffixes }) })

export const listChecklist = () => request('/checklist')

export const updateChecklist = (id, done) =>
  request(`/checklist/${id}`, { method: 'PATCH', body: withActor({ done }) })

export const listAdminAudit = () => request('/admin-audit')
