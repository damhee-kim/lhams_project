import { useState } from 'react'
import { RotateCcw, Trash2, ShieldAlert } from 'lucide-react'
import ConfirmDialog from '../common/ConfirmDialog.jsx'

export default function QuarantineManager({ entries, onRestore, onDelete }) {
  const [deleteTarget, setDeleteTarget] = useState(null)

  return (
    <section className="admin-section">
      <div className="section-head">
        <h2><ShieldAlert size={16} /> 격리소 (Quarantine)</h2>
        {entries.length > 0 && <span className="badge-mini">{entries.length}건</span>}
      </div>
      <p className="admin-hint">악성코드로 탐지되어 격리된 파일 목록입니다. 오탐인 경우 원래 경로로 복원할 수 있습니다.</p>

      <div className="quarantine-list">
        {entries.length === 0 && <div className="admin-empty">격리된 파일이 없습니다.</div>}
        {entries.map(q => (
          <div key={q.id} className="quarantine-row">
            <div className="q-info">
              <div className="q-file">{q.filename}</div>
              <div className="q-meta">
                원본: {q.original_path} · {q.quarantined_at} · 사유: {q.reason}
              </div>
            </div>
            <div className="q-actions">
              <button className="icon-btn" title="복원" onClick={() => onRestore(q.id)}>
                <RotateCcw size={16} />
              </button>
              <button className="icon-btn danger" title="영구 삭제" onClick={() => setDeleteTarget(q)}>
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="영구 삭제"
        message={deleteTarget ? `"${deleteTarget.filename}" 파일을 완전히 삭제할까요? 이 작업은 되돌릴 수 없습니다.` : ''}
        confirmLabel="영구 삭제"
        danger
        onCancel={() => setDeleteTarget(null)}
        onConfirm={async () => {
          await onDelete(deleteTarget.id)
          setDeleteTarget(null)
        }}
      />
    </section>
  )
}
