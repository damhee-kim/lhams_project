import { CheckCircle2, CircleAlert } from 'lucide-react'

export default function Toast({ toasts }) {
  if (toasts.length === 0) return null
  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>
          {t.type === 'error' ? <CircleAlert size={16} /> : <CheckCircle2 size={16} />}
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  )
}
