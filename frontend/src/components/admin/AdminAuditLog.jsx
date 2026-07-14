import {
  History, FolderPlus, FolderCog, FolderMinus, Filter,
  RotateCcw, Trash2, CheckCircle2, Circle, Upload,
} from 'lucide-react'

const ACTION_META = {
  PATH_ADD:            { label: '경로 추가',       icon: FolderPlus },
  PATH_UPDATE:         { label: '경로 수정',       icon: FolderCog },
  PATH_REMOVE:         { label: '경로 삭제',       icon: FolderMinus },
  SETTINGS_UPDATE:     { label: '무시 규칙 변경',  icon: Filter },
  QUARANTINE_RESTORE:  { label: '격리 복원',       icon: RotateCcw },
  QUARANTINE_DELETE:   { label: '격리 영구삭제',   icon: Trash2 },
  CHECKLIST_DONE:      { label: '체크리스트 완료', icon: CheckCircle2 },
  CHECKLIST_UNDONE:    { label: '체크리스트 되돌림', icon: Circle },
  CONFIG_IMPORT:       { label: '설정 가져오기',   icon: Upload },
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
        {entries.map(e => {
          const meta = ACTION_META[e.action]
          const Icon = meta?.icon
          return (
            <div key={e.id} className="audit-row">
              <span className="audit-time">{e.timestamp}</span>
              <span className="audit-actor">{e.actor}</span>
              <span className="audit-action">
                {Icon && <Icon size={13} />} {meta?.label || e.action}
              </span>
              <span className="audit-target">
                {e.target}
                {e.detail && <span className="audit-detail"> — {e.detail}</span>}
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
