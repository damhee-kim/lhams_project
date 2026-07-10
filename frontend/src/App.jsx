import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import StatCards from './components/StatCards.jsx'
import FilterBar from './components/FilterBar.jsx'
import EventTable from './components/EventTable.jsx'
import Tabs from './components/Tabs.jsx'
import SummaryPanel from './components/SummaryPanel.jsx'
import AdminPanel from './components/admin/AdminPanel.jsx'
import Toast from './components/common/Toast.jsx'

const POLL_MS = 3000
const TOAST_MS = 3500

export default function App() {
  const [tab, setTab] = useState('summary')
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('ALL')
  const [query, setQuery] = useState('')
  const [lastFetch, setLastFetch] = useState(null)
  const [error, setError] = useState(false)
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
          <h1>LHAMS<span>_</span>AUDIT</h1>
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

      {tab === 'summary' && <SummaryPanel events={events} agentDown={error} />}

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

      <Toast toasts={toasts} />
    </div>
  )
}
