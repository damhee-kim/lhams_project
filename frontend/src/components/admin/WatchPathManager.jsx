import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import Toggle from '../common/Toggle.jsx'
import ConfirmDialog from '../common/ConfirmDialog.jsx'

export default function WatchPathManager({ paths, onAdd, onToggle, onRemove }) {
  const [path, setPath] = useState('')
  const [recursive, setRecursive] = useState(true)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [removeTarget, setRemoveTarget] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!path.trim()) return
    setPending(true)
    setError('')
    try {
      await onAdd(path.trim(), recursive)
      setPath('')
      setRecursive(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="admin-section">
      <h2>감시 경로</h2>
      <p className="admin-hint">등록된 경로는 재시작 없이 즉시 감시가 시작/중지됩니다.</p>

      <form className="path-form" onSubmit={submit}>
        <input
          placeholder="예: D:\dev\lhams_project\data\test_monitor"
          value={path}
          onChange={e => setPath(e.target.value)}
        />
        <label className="recursive-check">
          <input type="checkbox" checked={recursive} onChange={e => setRecursive(e.target.checked)} />
          하위 폴더 포함
        </label>
        <button type="submit" className="primary" disabled={pending}>
          {pending ? '추가 중…' : '+ 경로 추가'}
        </button>
      </form>
      {error && <div className="admin-error">{error}</div>}

      <div className="path-list">
        {paths.length === 0 && <div className="admin-empty">등록된 감시 경로가 없습니다.</div>}
        {paths.map(p => (
          <div key={p.id} className={`path-row ${p.enabled ? '' : 'disabled'}`}>
            <Toggle checked={p.enabled} onChange={v => onToggle(p.id, { enabled: v })} />
            <div className="path-info">
              <div className="path-text">{p.path}</div>
              <div className="path-meta">
                <span className={`badge-mini ${p.recursive ? 'on' : ''}`}>
                  {p.recursive ? '하위 폴더 포함' : '단일 폴더'}
                </span>
              </div>
            </div>
            <button className="icon-btn danger" title="삭제" onClick={() => setRemoveTarget(p)}>
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={!!removeTarget}
        title="감시 경로 삭제"
        message={removeTarget ? `"${removeTarget.path}" 경로 감시를 중단하고 목록에서 삭제할까요?` : ''}
        confirmLabel="삭제"
        danger
        onCancel={() => setRemoveTarget(null)}
        onConfirm={async () => {
          await onRemove(removeTarget.id)
          setRemoveTarget(null)
        }}
      />
    </section>
  )
}
