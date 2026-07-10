import { CheckCircle2, Circle, ListChecks } from 'lucide-react'

export default function SetupChecklist({ items, onToggle }) {
  const done = items.filter(i => i.done).length
  const pct = items.length ? Math.round((done / items.length) * 100) : 0

  return (
    <section className="admin-section">
      <div className="section-head">
        <h2><ListChecks size={16} /> 설치 체크리스트</h2>
        <span className="checklist-progress-label">{done}/{items.length} 완료</span>
      </div>
      <p className="admin-hint">
        신규 서버 구축 시 이 순서대로 진행하세요. 완료 표시는 팀 전체에 공유되며 완료자·시각이 함께 기록됩니다.
      </p>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="checklist">
        {items.map(item => (
          <label key={item.id} className={`checklist-row ${item.done ? 'done' : ''}`}>
            <button
              type="button"
              className="checklist-check"
              onClick={() => onToggle(item.id, !item.done)}
            >
              {item.done ? <CheckCircle2 size={20} /> : <Circle size={20} />}
            </button>
            <div className="checklist-info">
              <div className="checklist-label">{item.label}</div>
              <div className="checklist-desc">{item.desc}</div>
              {item.done && (
                <div className="checklist-meta">완료: {item.done_by} · {item.done_at}</div>
              )}
            </div>
          </label>
        ))}
      </div>
    </section>
  )
}
