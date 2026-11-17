import { farClass, STATUS_WORDS } from './flags'
import type { FarFlag, Flag, LanguageFlag } from './types'

const QUOTE_CHARS = 70

function truncate(text: string, max: number) {
  return text.length <= max ? text : `${text.slice(0, max).trimEnd()}…`
}

function Labeled({ label, text }: { label: string; text: string | null }) {
  if (!text) return null
  return (
    <p>
      <b>{label}</b>
      {text}
    </p>
  )
}

function formatConfidence(confidence: number | string) {
  return typeof confidence === 'number' ? confidence.toFixed(2) : confidence
}

// The matrix guidance first, then the AI review's own lines when the AI review produced the flag
function LanguageDetail({ flag }: { flag: LanguageFlag }) {
  return (
    <div className="more">
      <Labeled label="Why" text={flag.why} />
      <Labeled label="Auburn's preferred language" text={flag.preferred} />
      <Labeled label="1st response to Sponsor" text={flag.response} />
      <Labeled label="AI justification" text={flag.ai_justification} />
      <Labeled label="AI suggested change" text={flag.ai_suggested} />
      {flag.confidence !== null && <p className="muted">Confidence: {formatConfidence(flag.confidence)}</p>}
    </div>
  )
}

function FarDetail({ flag }: { flag: FarFlag }) {
  if (!flag.criteria && !flag.request) return null
  return (
    <div className="more">
      <Labeled label="Acceptance criteria" text={flag.criteria} />
      <Labeled label="Request to Sponsor" text={flag.request} />
    </div>
  )
}

// The card face: the category of a language flag, or the clause number and status of a FAR clause.
// In the collapsed panel the "FAR " prefix is dropped so the clause number stays visible.
function CardFace({ flag, collapsed }: { flag: Flag; collapsed: boolean }) {
  if (flag.kind === 'far') {
    return (
      <>
        <div className="h">
          <span>{collapsed ? flag.clause : `FAR ${flag.clause}`}</span>
          <span>{STATUS_WORDS[flag.status]}</span>
        </div>
        {flag.title && <div className="q">{flag.title}</div>}
      </>
    )
  }
  return (
    <>
      <div className="h">
        <span>{flag.category ?? 'Problem language'}</span>
      </div>
      <div className="q">“{truncate(flag.sentence, QUOTE_CHARS)}”</div>
    </>
  )
}

interface Props {
  flag: Flag
  selected: boolean
  collapsed: boolean
  onSelect: () => void
}

export function FlagCard({ flag, selected, collapsed, onSelect }: Props) {
  const className = ['flag', farClass(flag), selected ? 'sel' : ''].filter(Boolean).join(' ')
  return (
    <div className={className} data-flag-id={flag.id} onClick={onSelect}>
      <CardFace flag={flag} collapsed={collapsed} />
      {selected && (flag.kind === 'far' ? <FarDetail flag={flag} /> : <LanguageDetail flag={flag} />)}
    </div>
  )
}
