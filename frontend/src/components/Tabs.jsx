import { Gauge, LayoutDashboard, ShieldCheck } from 'lucide-react'

const TABS = [
  { key: 'summary', label: '요약', icon: Gauge },
  { key: 'dashboard', label: '대시보드', icon: LayoutDashboard },
  { key: 'admin', label: '관리자', icon: ShieldCheck },
]

export default function Tabs({ active, setActive }) {
  return (
    <div className="tabs">
      {TABS.map(t => (
        <button key={t.key}
          className={active === t.key ? 'active' : ''}
          onClick={() => setActive(t.key)}>
          <t.icon size={14} />
          {t.label}
        </button>
      ))}
    </div>
  )
}
