import type { Filter } from './state'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'language', label: 'Language' },
  { id: 'far', label: 'FAR' },
]

export function Chips({ filter, onFilter }: { filter: Filter; onFilter: (filter: Filter) => void }) {
  return (
    <div className="chips" id="chips">
      {FILTERS.map(({ id, label }) => (
        <button key={id} className={id === filter ? 'chip on' : 'chip'} type="button" onClick={() => onFilter(id)}>
          {label}
        </button>
      ))}
    </div>
  )
}
