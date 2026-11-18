import { isRunning, progressPercent, stageName } from './stages'
import type { ScanEntry } from './state'

function formatDuration(seconds: number) {
  const whole = Math.round(seconds)
  if (whole < 60) return `${whole}s`
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, '0')}s`
}

function NameRow({ scan, status }: { scan: ScanEntry; status: string }) {
  return (
    <div className="n" title={scan.filename}>
      <span>{scan.filename}</span>
      <em>{status}</em>
    </div>
  )
}

function ScanItem({ scan, selected, onSelect }: { scan: ScanEntry; selected: boolean; onSelect: () => void }) {
  if (scan.stage === 'failed' || scan.stage === 'cancelled') {
    return (
      <div className="scan failed">
        <NameRow scan={scan} status={scan.stage === 'failed' ? 'Failed' : 'Cancelled'} />
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
}

export function ScanList({ scans, selectedScanId, onSelect }: Props) {
  return (
    <>
      <div className="lbl">This session</div>
      <div className="scans" id="scan-list">
        {scans.map((scan) => (
          <ScanItem key={scan.id} scan={scan} selected={scan.id === selectedScanId} onSelect={() => onSelect(scan.id)} />
        ))}
      </div>
    </>
  )
}
