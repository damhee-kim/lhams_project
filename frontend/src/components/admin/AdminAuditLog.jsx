import { History } from 'lucide-react'

const ACTION_LABEL = {
  PATH_ADD: '경로 추가',
  PATH_UPDATE: '경로 수정',
  PATH_REMOVE: '경로 삭제',
  SETTINGS_UPDATE: '무시 규칙 변경',
  QUARANTINE_RESTORE: '격리 복원',
  QUARANTINE_DELETE: '격리 영구삭제',
  CHECKLIST_DONE: '체크리스트 완료',
  CHECKLIST_UNDONE: '체크리스트 되돌림',
}

export default function AdminAuditLog({ entries }) {
  return (
    <section className="admin-section">
      <h2><History size={16} /> 관리자 변경 이력</h2>
      <p className="admin-hint">
        감시 경로·격리소·설정·체크리스트에 대한 모든 변경이 작업자 이름과 함께 남습니다.
      </p>

      <div className="audit-log">
        {entries.length === 0 && <div className="admin-empty">아직 기록된 변경이 없습니다.</div>}
        {entries.map(e => (
          <div key={e.id} className="audit-row">
            <span className="audit-time">{e.timestamp}</span>
            <span className="audit-actor">{e.actor}</span>
            <span className="audit-action">{ACTION_LABEL[e.action] || e.action}</span>
            <span className="audit-target">
              {e.target}
              {e.detail && <span className="audit-detail"> — {e.detail}</span>}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
