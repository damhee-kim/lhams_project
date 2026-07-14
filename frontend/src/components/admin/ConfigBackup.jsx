import { useRef, useState } from 'react'
import { Download, Upload, DatabaseBackup } from 'lucide-react'
import ConfirmDialog from '../common/ConfirmDialog.jsx'
import * as api from '../../api.js'

export default function ConfigBackup({ onImported, pushToast, requireActor }) {
  const fileRef = useRef(null)
  const [pending, setPending] = useState(null) // 가져오기 확인 대기 중인 파싱된 설정

  const handleExport = async () => {
    try {
      const config = await api.exportConfig()
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
      a.href = url
      a.download = `lhams-config-${stamp}.json`
      a.click()
      URL.revokeObjectURL(url)
      pushToast('success', '설정을 내보냈습니다')
    } catch (err) {
      pushToast('error', err.message)
    }
  }

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!Array.isArray(parsed.watch_paths) || !Array.isArray(parsed.ignore_suffixes)) {
        throw new Error('올바른 LHAMS 설정 파일이 아닙니다')
      }
      setPending(parsed)
    } catch (err) {
      pushToast('error', `파일을 읽을 수 없습니다: ${err.message}`)
    }
  }

  const confirmImport = async () => {
    try {
      await api.importConfig(pending)
      pushToast('success', '설정을 가져왔습니다 — 감시 경로가 새 설정으로 교체되었습니다')
      await onImported()
    } catch (err) {
      pushToast('error', err.message)
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="admin-section">
      <h2><DatabaseBackup size={16} /> 설정 백업 / 이전</h2>
      <p className="admin-hint">
        여러 서버·고객사에 동일한 감시 설정을 배포하거나, 장애 복구 시 이전 상태로 되돌릴 때 사용합니다.
        변경할 때마다 서버에 자동으로 백업본이 남습니다(<code>data/config_backups/</code>, 최근 20개 보관).
      </p>

      <div className="config-backup-actions">
        <button type="button" className="ghost" onClick={handleExport}>
          <Download size={14} /> 현재 설정 내보내기
        </button>
        <button type="button" className="ghost" onClick={() => { if (requireActor()) fileRef.current?.click() }}>
          <Upload size={14} /> 설정 파일 가져오기
        </button>
        <input ref={fileRef} type="file" accept="application/json" hidden onChange={handleFileSelect} />
      </div>

      <ConfirmDialog
        open={!!pending}
        title="설정 가져오기"
        message={pending
          ? `감시 경로 ${pending.watch_paths.length}개, 무시 규칙 ${pending.ignore_suffixes.length}개로 현재 설정을 완전히 교체합니다. 계속할까요?`
          : ''}
        confirmLabel="교체"
        danger
        onCancel={() => setPending(null)}
        onConfirm={confirmImport}
      />
    </section>
  )
}
