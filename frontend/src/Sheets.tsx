import { Fragment, useMemo } from 'react'
import { farClass, flagsByParagraph } from './flags'
import { highlightPieces } from './highlight'
import { isHeading } from './pages'
import type { Flag, ScanResults } from './types'

interface ParagraphProps {
  text: string
  flags: Flag[]
  selectedFlagId: string | null
  onMarkClick: (flag: Flag) => void
}

function Paragraph({ text, flags, selectedFlagId, onMarkClick }: ParagraphProps) {
  return (
    <p className={isHeading(text) ? 'h' : undefined}>
      {highlightPieces(text, flags).map(({ text: piece, flag }, index) =>
        flag ? (
          <mark
            key={index}
            className={['hl', farClass(flag), flag.id === selectedFlagId ? 'sel' : ''].filter(Boolean).join(' ')}
            data-flag-id={flag.id}
            onClick={() => onMarkClick(flag)}
          >
            {piece}
          </mark>
        ) : (
          <Fragment key={index}>{piece}</Fragment>
        ),
      )}
    </p>
  )
}

interface Props {
  results: ScanResults
  pages: number[][]
  selectedFlagId: string | null
  onMarkClick: (flag: Flag) => void
}

// The contract on letter-size sheets, with each flag highlighted in its paragraph
export function Sheets({ results, pages, selectedFlagId, onMarkClick }: Props) {
  const placed = useMemo(() => flagsByParagraph(results), [results])
  return pages.map((indexes, sheet) => (
    <div className="sheet" key={sheet}>
      {indexes.map((index) => (
        <Paragraph
          key={index}
          text={results.paragraphs[index]}
          flags={placed.get(index) ?? []}
          selectedFlagId={selectedFlagId}
          onMarkClick={onMarkClick}
        />
      ))}
      <div className="pg">{sheet + 1}</div>
    </div>
  ))
}
