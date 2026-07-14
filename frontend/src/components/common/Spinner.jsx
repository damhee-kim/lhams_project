export default function Spinner({ label }) {
  return (
    <div className="spinner-wrap">
      <span className="spinner" />
      {label && <span>{label}</span>}
    </div>
  )
}
