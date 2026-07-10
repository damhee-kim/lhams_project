export default function ConfirmDialog({ open, title, message, confirmLabel = '확인', danger, onConfirm, onCancel }) {
  if (!open) return null
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{message}</p>
        <div className="modal-actions">
          <button className="ghost" onClick={onCancel}>취소</button>
          <button className={danger ? 'danger' : 'primary'} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
