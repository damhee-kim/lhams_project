const FILTERS = [
  { key: 'ALL', label: '전체' },
  { key: 'RISK', label: '위험만' },
  { key: 'CREATED', label: '생성' },
  { key: 'MODIFIED', label: '수정' },
  { key: 'MOVED', label: '이동' },
  { key: 'DELETED', label: '삭제' },
  { key: 'MALWARE_DETECTED', label: '악성코드' },
]

export default function FilterBar({ filter, setFilter, query, setQuery }) {
  return (
    <div className="filter-bar">
      {FILTERS.map(f => (
        <button key={f.key}
          className={filter === f.key ? 'active' : ''}
          onClick={() => setFilter(f.key)}>
          {f.label}
        </button>
      ))}
      <input
        placeholder="경로 / 사용자 / 프로세스 검색"
        value={query}
        onChange={e => setQuery(e.target.value)}
      />
    </div>
  )
}
