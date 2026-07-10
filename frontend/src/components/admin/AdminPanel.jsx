import { useEffect, useState, useCallback } from 'react'
import WatchPathManager from './WatchPathManager.jsx'
import QuarantineManager from './QuarantineManager.jsx'
import IgnoreRulesEditor from './IgnoreRulesEditor.jsx'
import * as api from '../../api.js'

const QUARANTINE_POLL_MS = 5000

export default function AdminPanel({ pushToast }) {
  const [paths, setPaths] = useState([])
  const [suffixes, setSuffixes] = useState([])
  const [quarantine, setQuarantine] = useState([])
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

  const loadQuarantine = useCallback(async () => {
    try {
      setQuarantine(await api.listQuarantine())
    } catch (err) {
      pushToast('error', err.message)
    }
  }, [pushToast])

  useEffect(() => {
    (async () => {
      await Promise.all([loadConfig(), loadQuarantine()])
      setLoading(false)
    })()
    const id = setInterval(loadQuarantine, QUARANTINE_POLL_MS)
    return () => clearInterval(id)
  }, [loadConfig, loadQuarantine])

  const handleAdd = async (path, recursive) => {
    await api.addPath(path, recursive)
    pushToast('success', `감시 경로 추가됨: ${path}`)
    await loadConfig()
  }

  const handleToggle = async (id, patch) => {
    try {
      await api.updatePath(id, patch)
      await loadConfig()
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleRemove = async (id) => {
    try {
      await api.removePath(id)
      pushToast('success', '감시 경로가 삭제되었습니다')
      await loadConfig()
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleRestore = async (id) => {
    try {
      await api.restoreQuarantine(id)
      pushToast('success', '파일을 원래 경로로 복원했습니다')
      await loadQuarantine()
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleDelete = async (id) => {
    try {
      await api.deleteQuarantine(id)
      pushToast('success', '파일을 영구 삭제했습니다')
      await loadQuarantine()
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleSuffixChange = async (next) => {
    setSuffixes(next)
    try {
      await api.updateSettings(next)
      pushToast('success', '무시 규칙이 저장되었습니다')
    } catch (err) {
      pushToast('error', err.message)
      await loadConfig()
    }
  }

  if (loading) return <div className="admin-empty">불러오는 중…</div>

  return (
    <div className="admin-panel">
      <WatchPathManager paths={paths} onAdd={handleAdd} onToggle={handleToggle} onRemove={handleRemove} />
      <QuarantineManager entries={quarantine} onRestore={handleRestore} onDelete={handleDelete} />
      <IgnoreRulesEditor suffixes={suffixes} onChange={handleSuffixChange} />
    </div>
  )
}
