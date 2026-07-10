const TABS = [
  { key: 'dashboard', label: '대시보드' },
  { key: 'admin', label: '관리자' },
]

export default function Tabs({ active, setActive }) {
  return (
    <div className="tabs">
      {TABS.map(t => (
        <button key={t.key}
          className={active === t.key ? 'active' : ''}
          onClick={() => setActive(t.key)}>
          {t.label}
        </button>
      ))}
    </div>
  )
}
