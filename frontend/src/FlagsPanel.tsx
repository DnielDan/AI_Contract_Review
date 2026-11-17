import { useEffect, useRef } from 'react'
import { Chips } from './Chips'
import { FlagCard } from './FlagCard'
import type { Filter, FlagSource } from './state'
import type { Flag } from './types'

const NOTHING_FOUND: Record<Filter, string> = {
  all: 'Nothing was flagged in this contract.',
  language: 'No problem language was flagged.',
  far: 'No FAR clauses were found.',
}

interface CardsProps {
  flags: Flag[] | null // null until the selected scan has finished
  filter: Filter
  selectedFlagId: string | null
  collapsed: boolean
  onSelect: (flag: Flag) => void
}

function Cards({ flags, filter, selectedFlagId, collapsed, onSelect }: CardsProps) {
  if (!flags) return <p className="none">Flags appear when a scan finishes.</p>
  const shown = flags.filter((flag) => filter === 'all' || flag.kind === filter)
  if (shown.length === 0) return <p className="none">{NOTHING_FOUND[filter]}</p>
  return shown.map((flag) => (
    <FlagCard
      key={flag.id}
      flag={flag}
      selected={flag.id === selectedFlagId}
      collapsed={collapsed}
      onSelect={() => onSelect(flag)}
    />
  ))
}

interface Props extends CardsProps {
  flagSource: FlagSource | null
  flagFocus: number
  onFilter: (filter: Filter) => void
  onToggle: () => void
}

export function FlagsPanel({ flagSource, flagFocus, onFilter, onToggle, ...cardsProps }: Props) {
  const { selectedFlagId, collapsed, filter } = cardsProps
  const cards = useRef<HTMLDivElement>(null)

  // A highlight clicked in the document brings its card into view
  useEffect(() => {
    if (flagSource !== 'mark' || !selectedFlagId) return
    const card = cards.current?.querySelector(`[data-flag-id="${CSS.escape(selectedFlagId)}"]`)
    card?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [flagFocus, flagSource, selectedFlagId])

  return (
    <aside className="side">
      <div className="hd">
        <span>Flags</span>
        <button
          className="ic"
          id="chevron"
          type="button"
          aria-label={collapsed ? 'Expand flags panel' : 'Collapse flags panel'}
          aria-expanded={!collapsed}
          onClick={onToggle}
        >
          <svg viewBox="0 0 24 24">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </button>
      </div>
      <div className="list">
        <Chips filter={filter} onFilter={onFilter} />
        <div className="cards" id="flag-list" ref={cards}>
          <Cards {...cardsProps} />
        </div>
      </div>
    </aside>
  )
}
