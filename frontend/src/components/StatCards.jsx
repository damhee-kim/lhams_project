import { Activity, FilePlus2, Trash2, ShieldAlert } from 'lucide-react'

export default function StatCards({ stats }) {
  const cards = [
    { key: 'clean',    icon: <Activity size={18} />,   label: '전체 이벤트',   value: stats.total },
    { key: 'warn',     icon: <FilePlus2 size={18} />,  label: '생성',          value: stats.created },
    { key: 'high',     icon: <Trash2 size={18} />,     label: '삭제 (High)',   value: stats.deleted },
    { key: 'critical', icon: <ShieldAlert size={18} />,label: '악성코드 격리', value: stats.malware },
  ]
  return (
    <div className="stats">
      {cards.map(c => (
        <div key={c.label} className={`stat-card ${c.key}`}>
          <div className="icon">{c.icon}</div>
          <div>
            <div className="label">{c.label}</div>
            <div className="value">{c.value}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
