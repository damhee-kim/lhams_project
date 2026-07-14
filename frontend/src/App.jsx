import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import StatCards from './components/StatCards.jsx'
import FilterBar from './components/FilterBar.jsx'
import EventTable from './components/EventTable.jsx'
import Tabs from './components/Tabs.jsx'
import SummaryPanel from './components/SummaryPanel.jsx'
import AdminPanel from './components/admin/AdminPanel.jsx'
import Toast from './components/common/Toast.jsx'
import * as api from './api.js'

const POLL_MS = 3000
const HEALTH_POLL_MS = 5000
const TOAST_MS = 3500

export default function App() {
  const [tab, setTab] = useState('summary')
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('ALL')
  const [query, setQuery] = useState('')
  const [lastFetch, setLastFetch] = useState(null)
  const [error, setError] = useState(false)
  const [health, setHealth] = useState(null)
  const [toasts, setToasts] = useState([])
  const toastId = useRef(0)

  const pushToast = useCallback((type, message) => {
    const id = ++toastId.current
    setToasts(t => [...t, { id, type, message }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), TOAST_MS)
  }, [])

  // Watchdog 에이전트가 적재하는 JSON을 3초마다 폴링
  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const res = await fetch(`/lhams_audit.json?t=${Date.now()}`)
        if (!res.ok) throw new Error(res.status)
        const data = await res.json()
        if (alive) {
          setEvents(Array.isArray(data) ? data : [])
          setLastFetch(new Date())
          setError(false)
        }
      } catch {
        if (alive) setError(true)
      }
    }
    load()
    const id = setInterval(load, POLL_MS)
    return () => { alive = false; clearInterval(id) }
  }, [])

  // 관리 API의 시스템 진단(사이트명/가동시간/경로 상태) 폴링 — 없어도 파일 감사 자체엔 영향 없음
  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const h = await api.getHealth()
        if (alive) setHealth(h)
      } catch {
        if (alive) setHealth(null)
      }
    }
    load()
    const id = setInterval(load, HEALTH_POLL_MS)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const filtered = useMemo(() => {
    return events.filter(e => {
      const okType =
        filter === 'ALL' ? true :
        filter === 'RISK' ? ['High', 'Critical'].includes(e.risk_level) :
        e.event_type === filter
      const q = query.trim().toLowerCase()
      const okQuery = !q ||
        (e.file_path || '').toLowerCase().includes(q) ||
        (e.user || '').toLowerCase().includes(q) ||
        (e.process || '').toLowerCase().includes(q)
      return okType && okQuery
    })
  }, [events, filter, query])

  const stats = useMemo(() => ({
    total: events.length,
    created: events.filter(e => e.event_type === 'CREATED').length,
    moved: events.filter(e => e.event_type === 'MOVED').length,
    deleted: events.filter(e => e.event_type === 'DELETED').length,
    malware: events.filter(e => e.event_type === 'MALWARE_DETECTED').length,
  }), [events])

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>
            LHAMS<span>_</span>AUDIT
            {health && <span className="site-badge">{health.site_name} · {health.site_id}</span>}
          </h1>
          <p className="subtitle">
            리눅스 하이브리드 메일 감사 시스템 · 누가, 언제, 무엇을 변경했는가
          </p>
        </div>
        <div className={`ticker ${error ? 'stale' : ''}`}>
          <span className="dot" />
          {error
            ? '에이전트 응답 없음 — lhams-watchdog 서비스 확인'
            : <>실시간 감시 중 · 마지막 수신 <strong>
                {lastFetch ? lastFetch.toLocaleTimeString('ko-KR') : '—'}
              </strong></>}
        </div>
      </header>

      <Tabs active={tab} setActive={setTab} />

      <div className="tab-content" key={tab}>
        {tab === 'summary' && <SummaryPanel events={events} agentDown={error} health={health} />}

        {tab === 'dashboard' && (
          <>
            <StatCards stats={stats} />
            <FilterBar filter={filter} setFilter={setFilter}
                       query={query} setQuery={setQuery} />
            <EventTable events={filtered} />

            <p className="footer-note">
              source: inotify + auditd + clamd · 최근 200건 유지 ·
              전체 이력은 /mail/lhams_project/data/logs (일별 로테이션)
            </p>
          </>
        )}

        {tab === 'admin' && <AdminPanel pushToast={pushToast} />}
      </div>

      <Toast toasts={toasts} />
    </div>
  )
}
