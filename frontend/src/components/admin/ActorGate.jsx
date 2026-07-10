import { useState } from 'react'
import { UserCircle2, Pencil, Check } from 'lucide-react'
import * as api from '../../api.js'

export default function ActorGate({ actor, onChange }) {
  const [editing, setEditing] = useState(!actor)
  const [input, setInput] = useState(actor)

  const save = (e) => {
    e.preventDefault()
    const name = input.trim()
    if (!name) return
    api.setActor(name)
    onChange(name)
    setEditing(false)
  }

  if (editing) {
    return (
      <form className="actor-gate editing" onSubmit={save}>
        <UserCircle2 size={18} />
        <input
          autoFocus
          placeholder="이름 또는 사번을 입력하세요"
          value={input}
          onChange={e => setInput(e.target.value)}
        />
        <button type="submit" className="primary">
          <Check size={14} /> 확인
        </button>
      </form>
    )
  }

  return (
    <div className="actor-gate">
      <UserCircle2 size={18} />
      <span>
        현재 작업자 <strong>{actor}</strong> · 이 페이지의 모든 변경은 이 이름으로 기록됩니다
      </span>
      <button type="button" className="ghost" onClick={() => { setInput(actor); setEditing(true) }}>
        <Pencil size={12} /> 변경
      </button>
    </div>
  )
}
