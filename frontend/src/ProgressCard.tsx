import { progressPercent, STEP_LABELS, stepIndex } from './stages'
import type { ScanEntry } from './state'

function formatClock(seconds: number) {
  const whole = Math.floor(seconds)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(Math.floor(whole / 60))}:${pad(whole % 60)}`
}

function pillClass(index: number, current: number) {
  if (index < current) return 'pill done'
  return index === current ? 'pill active' : 'pill'
}

// Shows the step the server reports and the time taken so far; the server reports no finer progress
export function ProgressCard({ scan, onCancel }: { scan: ScanEntry; onCancel: () => void }) {
  const labels = STEP_LABELS
  const current = stepIndex(scan.stage)
  return (
    <div className="pcard">
      <h2>Scanning {scan.filename}</h2>
      <div className="pills">
        {labels.map((label, index) => (
          <span key={label} className={pillClass(index, current)}>
            {label}
          </span>
        ))}
      </div>
      <div className="track">
        <div className="fill" style={{ width: `${progressPercent(scan.stage)}%` }} />
      </div>
      <div className="pmeta">
        <span>{current < 0 ? 'Waiting…' : `Step ${current + 1} of ${labels.length}`}</span>
        <span>{formatClock(scan.elapsedSeconds)}</span>
      </div>
      <button className="cancel" type="button" onClick={onCancel}>
        Cancel scan
      </button>
    </div>
  )
}
