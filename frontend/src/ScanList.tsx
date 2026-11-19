import type { MouseEvent } from 'react'
import { isRunning, progressPercent, stageName } from './stages'
import type { ScanEntry } from './state'

function formatDuration(seconds: number) {
  const whole = Math.round(seconds)
  if (whole < 60) return `${whole}s`
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, '0')}s`
}

// The name and status of a scan; a finished scan also gets a button that removes it (a running one is
// cancelled from its progress card instead)
function NameRow({ scan, status, onRemove }: { scan: ScanEntry; status: string; onRemove: () => void }) {
  function remove(event: MouseEvent) {
    event.stopPropagation() // removing a scan must not also select it
    onRemove()
  }
  return (
    <div className="n" title={scan.filename}>
      <span>{scan.filename}</span>
      <em>{status}</em>
      {!isRunning(scan.stage) && (
        <button className="rm" type="button" aria-label={`Remove ${scan.filename}`} title="Remove" onClick={remove}>
          ×
        </button>
      )}
    </div>
  )
}

interface ItemProps {
  scan: ScanEntry
  selected: boolean
  onSelect: () => void
  onRemove: () => void
}

function ScanItem({ scan, selected, onSelect, onRemove }: ItemProps) {
  if (scan.stage === 'failed' || scan.stage === 'cancelled') {
    return (
      <div className="scan failed">
        <NameRow scan={scan} status={scan.stage === 'failed' ? 'Failed' : 'Cancelled'} onRemove={onRemove} />
        {scan.error && <div className="why">{scan.error}</div>}
      </div>
    )
  }
  const running = isRunning(scan.stage)
  return (
    <div className={selected ? 'scan sel' : 'scan'} onClick={onSelect}>
      <NameRow
        scan={scan}
        status={running ? stageName(scan.stage) : `✓ ${formatDuration(scan.elapsedSeconds)}`}
        onRemove={onRemove}
      />
      {running && (
        <div className="track">
          <div className="fill" style={{ width: `${progressPercent(scan.stage)}%` }} />
        </div>
      )}
    </div>
  )
}

interface Props {
  scans: ScanEntry[]
  selectedScanId: string | null
  onSelect: (id: string) => void
  onRemove: (id: string) => void
}

export function ScanList({ scans, selectedScanId, onSelect, onRemove }: Props) {
  return (
    <>
      <div className="lbl">This session</div>
      <div className="scans" id="scan-list">
        {scans.map((scan) => (
          <ScanItem
            key={scan.id}
            scan={scan}
            selected={scan.id === selectedScanId}
            onSelect={() => onSelect(scan.id)}
            onRemove={() => onRemove(scan.id)}
          />
        ))}
      </div>
    </>
  )
}
