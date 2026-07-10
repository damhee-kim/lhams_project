import { useState } from 'react'
import { X, Filter } from 'lucide-react'

export default function IgnoreRulesEditor({ suffixes, onChange }) {
  const [input, setInput] = useState('')

  const add = (e) => {
    e.preventDefault()
    const v = input.trim()
    if (!v || suffixes.includes(v)) return
    onChange([...suffixes, v])
    setInput('')
  }

  const remove = (s) => onChange(suffixes.filter(x => x !== s))

  return (
    <section className="admin-section">
      <h2><Filter size={16} /> 무시할 확장자 / 패턴</h2>
      <p className="admin-hint">
        파일 경로가 이 목록의 문자열로 끝나면 이벤트를 기록하지 않습니다 (에디터 임시 파일 등).
      </p>

      <form className="tag-form" onSubmit={add}>
        <input
          placeholder="예: .bak"
          value={input}
          onChange={e => setInput(e.target.value)}
        />
        <button type="submit" className="primary">추가</button>
      </form>

      <div className="tag-list">
        {suffixes.map(s => (
          <span key={s} className="tag">
            {s}
            <button className="tag-remove" onClick={() => remove(s)}><X size={12} /></button>
          </span>
        ))}
      </div>
    </section>
  )
}
