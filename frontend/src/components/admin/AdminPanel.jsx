import { useEffect, useState, useCallback } from 'react'
import ActorGate from './ActorGate.jsx'
import SetupChecklist from './SetupChecklist.jsx'
import WatchPathManager from './WatchPathManager.jsx'
import QuarantineManager from './QuarantineManager.jsx'
import IgnoreRulesEditor from './IgnoreRulesEditor.jsx'
import AdminAuditLog from './AdminAuditLog.jsx'
import * as api from '../../api.js'

const POLL_MS = 5000

export default function AdminPanel({ pushToast }) {
  const [actor, setActor] = useState(api.getActor())
  const [checklist, setChecklist] = useState([])
  const [paths, setPaths] = useState([])
  const [suffixes, setSuffixes] = useState([])
  const [quarantine, setQuarantine] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [loading, setLoading] = useState(true)

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await api.getConfig()
      setPaths(cfg.watch_paths)
      setSuffixes(cfg.ignore_suffixes)
    } catch (err) {
      pushToast('error', err.message)
    }
  }, [pushToast])

  const loadChecklist = useCallback(async () => {
    try {
      setChecklist(await api.listChecklist())
    } catch (err) {
      pushToast('error', err.message)
    }
  }, [pushToast])

  const loadQuarantine = useCallback(async () => {
    try {
      setQuarantine(await api.listQuarantine())
    } catch (err) {
      pushToast('error', err.message)
    }
  }, [pushToast])

  const loadAuditLog = useCallback(async () => {
    try {
      setAuditLog(await api.listAdminAudit())
    } catch (err) {
      pushToast('error', err.message)
    }
  }, [pushToast])

  const refreshAll = useCallback(
    () => Promise.all([loadConfig(), loadChecklist(), loadQuarantine(), loadAuditLog()]),
    [loadConfig, loadChecklist, loadQuarantine, loadAuditLog]
  )

  useEffect(() => {
    (async () => {
      await refreshAll()
      setLoading(false)
    })()
    const id = setInterval(() => { loadQuarantine(); loadAuditLog() }, POLL_MS)
    return () => clearInterval(id)
  }, [refreshAll, loadQuarantine, loadAuditLog])

  const requireActor = () => {
    if (!actor) {
      pushToast('error', '먼저 작업자 이름을 입력하세요')
      return false
    }
    return true
  }

  const handleToggleChecklist = async (id, done) => {
    if (!requireActor()) return
    try {
      await api.updateChecklist(id, done)
      await Promise.all([loadChecklist(), loadAuditLog()])
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleAdd = async (path, recursive) => {
    if (!requireActor()) return
    await api.addPath(path, recursive)
    pushToast('success', `감시 경로 추가됨: ${path}`)
    await Promise.all([loadConfig(), loadAuditLog()])
  }

  const handleToggle = async (id, patch) => {
    if (!requireActor()) return
    try {
      await api.updatePath(id, patch)
      await Promise.all([loadConfig(), loadAuditLog()])
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleRemove = async (id) => {
    if (!requireActor()) return
    try {
      await api.removePath(id)
      pushToast('success', '감시 경로가 삭제되었습니다')
      await Promise.all([loadConfig(), loadAuditLog()])
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleRestore = async (id) => {
    if (!requireActor()) return
    try {
      await api.restoreQuarantine(id)
      pushToast('success', '파일을 원래 경로로 복원했습니다')
      await Promise.all([loadQuarantine(), loadAuditLog()])
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!requireActor()) return
    try {
      await api.deleteQuarantine(id)
      pushToast('success', '파일을 영구 삭제했습니다')
      await Promise.all([loadQuarantine(), loadAuditLog()])
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleSuffixChange = async (next) => {
    if (!requireActor()) return
    setSuffixes(next)
    try {
      await api.updateSettings(next)
      pushToast('success', '무시 규칙이 저장되었습니다')
      await loadAuditLog()
    } catch (err) {
      pushToast('error', err.message)
      await loadConfig()
    }
  }

  if (loading) return <div className="admin-empty">불러오는 중…</div>

  return (
    <div className="admin-panel">
      <ActorGate actor={actor} onChange={setActor} />
      <SetupChecklist items={checklist} onToggle={handleToggleChecklist} />
      <WatchPathManager paths={paths} onAdd={handleAdd} onToggle={handleToggle} onRemove={handleRemove} />
      <QuarantineManager entries={quarantine} onRestore={handleRestore} onDelete={handleDelete} />
      <IgnoreRulesEditor suffixes={suffixes} onChange={handleSuffixChange} />
      <AdminAuditLog entries={auditLog} />
    </div>
  )
}
