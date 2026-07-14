import { useMemo } from 'react'
import { ShieldCheck, ShieldAlert, ShieldX, FolderTree, Archive, Activity, Tag } from 'lucide-react'

function basename(p) {
  if (!p) return ''
  return p.split(/[\\/]/).pop()
}

function describeEvent(e) {
  const who = e.user || '알 수 없는 사용자'
  const file = basename(e.file_path)
  switch (e.event_type) {
    case 'MOVED':
      return `${who}님이 "${file}" 파일을 "${basename(e.dest_path)}"로 교체(이동)했습니다`
    case 'DELETED':
      return `${who}님이 "${file}" 파일을 삭제했습니다`
    case 'MALWARE_DETECTED':
      return `"${file}" 파일에서 악성코드가 탐지되어 시스템이 자동으로 격리했습니다`
    case 'MODIFIED':
      return `${who}님이 "${file}" 파일을 수정했습니다`
    case 'CREATED':
      return `${who}님이 "${file}" 파일을 생성했습니다`
    default:
      return `${who}님이 "${file}" 파일에 변경을 가했습니다`
  }
}

function formatUptime(sec) {
  if (sec == null) return '—'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (d > 0) return `${d}일 ${h}시간`
  if (h > 0) return `${h}시간 ${m}분`
  return `${m}분`
}

export default function SummaryPanel({ events, agentDown, health }) {
  const counts = useMemo(() => ({
    created: events.filter(e => e.event_type === 'CREATED').length,
    modified: events.filter(e => e.event_type === 'MODIFIED').length,
    moved: events.filter(e => e.event_type === 'MOVED').length,
    deleted: events.filter(e => e.event_type === 'DELETED').length,
    malware: events.filter(e => e.event_type === 'MALWARE_DETECTED').length,
  }), [events])

  const pathErrorCount = health?.watch_paths_error ?? 0

  const status = useMemo(() => {
    if (agentDown) return 'down'
    if (counts.malware > 0 || counts.deleted > 0 || pathErrorCount > 0) return 'attention'
    return 'clean'
  }, [agentDown, counts, pathErrorCount])

  const highlights = useMemo(() => (
    events
      .filter(e => e.risk_level === 'High' || e.risk_level === 'Critical')
      .slice(0, 5)
  ), [events])

  const STATUS_INFO = {
    down: {
      icon: <ShieldX size={28} />,
      title: '감시 에이전트가 응답하지 않습니다',
      desc: '보호 기능이 잠시 중단된 상태일 수 있습니다. lhams-watchdog 서비스 상태를 확인해 주세요.',
    },
    attention: {
      icon: <ShieldAlert size={28} />,
      title: '확인이 필요한 이벤트가 있습니다',
      desc: pathErrorCount > 0
        ? `감시 경로 ${pathErrorCount}곳이 실제로는 감시되지 않고 있습니다(경로 없음). 관리자 탭에서 확인해 주세요.`
        : '삭제 또는 악성코드 탐지 이벤트가 발생했습니다. 시스템이 자동으로 차단·격리했지만, 아래 내역을 검토해 주세요.',
    },
    clean: {
      icon: <ShieldCheck size={28} />,
      title: '현재 시스템이 정상적으로 보호되고 있습니다',
      desc: '최근 감시 구간 동안 위험한 삭제나 악성코드 이벤트가 발견되지 않았습니다.',
    },
  }
  const info = STATUS_INFO[status]

  return (
    <div className="summary-panel">
      <div className={`summary-banner ${status}`}>
        {info.icon}
        <div>
          <h2>{info.title}</h2>
          <p>{info.desc}</p>
        </div>
      </div>

      <div className="summary-facts">
        <div className="summary-fact">
          <FolderTree size={18} />
          <div>
            <div className="summary-fact-value">
              {health ? `${health.watch_paths_active}/${health.watch_paths_total}` : '—'}곳
            </div>
            <div className="summary-fact-label">
              감시 중인 경로(활성/전체){pathErrorCount > 0 && ` · 오류 ${pathErrorCount}곳`}
            </div>
          </div>
        </div>
        <div className="summary-fact">
          <Archive size={18} />
          <div>
            <div className="summary-fact-value">{health?.quarantine_count ?? '—'}건</div>
            <div className="summary-fact-label">격리된 파일 {health?.quarantine_count > 0 && '(검토 필요)'}</div>
          </div>
        </div>
        <div className="summary-fact">
          <Activity size={18} />
          <div>
            <div className="summary-fact-value">{formatUptime(health?.uptime_sec)}</div>
            <div className="summary-fact-label">에이전트 가동 시간 · v{health?.version ?? '—'}</div>
          </div>
        </div>
        <div className="summary-fact">
          <Tag size={18} />
          <div>
            <div className="summary-fact-value">{health?.site_name ?? '—'}</div>
            <div className="summary-fact-label">사이트 ID: {health?.site_id ?? '—'}</div>
          </div>
        </div>
      </div>

      <section className="admin-section">
        <h2>최근 감시 구간 요약</h2>
        <p className="admin-hint">최근 수신된 이벤트 최대 200건을 기준으로 집계합니다.</p>
        <div className="summary-counts">
          <span>생성 <strong>{counts.created}</strong></span>
          <span>수정 <strong>{counts.modified}</strong></span>
          <span>파일 교체 <strong>{counts.moved}</strong></span>
          <span>삭제 <strong>{counts.deleted}</strong></span>
          <span>악성코드 자동 차단 <strong>{counts.malware}</strong></span>
        </div>
      </section>

      <section className="admin-section">
        <h2>주요 이벤트</h2>
        <p className="admin-hint">삭제·악성코드 등 확인이 필요한 이벤트를 최신순으로 보여줍니다.</p>
        {highlights.length === 0 ? (
          <div className="admin-empty">확인이 필요한 주요 이벤트가 없습니다.</div>
        ) : (
          <ul className="summary-highlights">
            {highlights.map(e => (
              <li key={e.id} className={`risk-${e.risk_level}`}>
                <span className="summary-highlight-time">{e.timestamp}</span>
                <span>{describeEvent(e)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
