import { EVENT_LABELS } from '../constants/eventLabels.js'

export default function EventTable({ events }) {
  return (
    <div className="event-table">
      <table>
        <thead>
          <tr>
            <th>시각</th>
            <th>이벤트</th>
            <th>파일 경로</th>
            <th>행위자 (auditd)</th>
            <th>프로세스</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 && (
            <tr><td colSpan={5} className="empty">
              표시할 이벤트가 없습니다. 감시 디렉토리에 파일을 생성해 보세요.
            </td></tr>
          )}
          {events.map(e => (
            <tr key={e.id} className={`risk-${e.risk_level}`}>
              <td className="time">{e.timestamp}</td>
              <td>
                <span className={`badge ${e.event_type}`}>{EVENT_LABELS[e.event_type] || e.event_type}</span>
                {e.quarantined && <div className="quarantined">→ 격리됨</div>}
              </td>
              <td className="path">
                {e.event_type === 'MOVED' && e.dest_path ? (
                  <div className="replace-path">
                    <div className="replace-before"><span className="replace-tag">교체 전</span>{e.file_path}</div>
                    <div className="replace-after"><span className="replace-tag">교체 후</span>{e.dest_path}</div>
                  </div>
                ) : (
                  <>
                    {e.file_path}
                    {e.dest_path && <div className="dest">→ {e.dest_path}</div>}
                  </>
                )}
              </td>
              <td className="user">
                {e.user || 'unknown'}
                {e.owner && e.owner !== e.user &&
                  <div className="proc">owner: {e.owner}</div>}
              </td>
              <td className="proc">{e.process || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
