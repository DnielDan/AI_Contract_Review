import { useEffect, useMemo, useRef, useState } from 'react'
import { downloadScan } from './api'
import { FallbackStrip } from './FallbackStrip'
import { paginate } from './pages'
import { ProgressCard } from './ProgressCard'
import { Sheets } from './Sheets'
import { isRunning } from './stages'
import { ZOOMS, type FlagSource, type ScanEntry } from './state'
import { Toolbar } from './Toolbar'
import type { Flag, ScanResults } from './types'

interface Props {
  scan: ScanEntry | null
  zoom: number
  selectedFlagId: string | null
  flagSource: FlagSource | null
  flagFocus: number
  onZoom: (zoom: number) => void
  onMarkClick: (flag: Flag) => void
  onCancel: (id: string) => void
  onDismissNotice: (id: string) => void
}

function sheetsIn(well: HTMLElement | null) {
  return Array.from(well?.querySelectorAll<HTMLElement>('.sheet') ?? [])
}

interface ContentProps {
  scan: ScanEntry | null
  results: ScanResults | null
  pages: number[][]
  selectedFlagId: string | null
  onMarkClick: (flag: Flag) => void
  onCancel: (id: string) => void
}

function WellContent({ scan, results, pages, selectedFlagId, onMarkClick, onCancel }: ContentProps) {
  if (!scan) return <p className="empty">Drop a contract on the left to start a scan.</p>
  if (isRunning(scan.stage)) return <ProgressCard scan={scan} onCancel={() => onCancel(scan.id)} />
  if (scan.stage !== 'done') return <p className="empty">{scan.error ?? 'This scan was cancelled.'}</p>
  if (!results) return <p className="empty">Loading the results…</p>
  return <Sheets results={results} pages={pages} selectedFlagId={selectedFlagId} onMarkClick={onMarkClick} />
}

// The document column. App gives it a new key for each scan, so the page and scroll position start fresh.
export function DocViewer(props: Props) {
  const { scan, zoom, selectedFlagId, flagSource, flagFocus, onZoom, onMarkClick, onCancel, onDismissNotice } = props
  const results = scan?.stage === 'done' ? scan.results : null
  const pages = useMemo(() => (results ? paginate(results.paragraphs) : []), [results])
  const [page, setPage] = useState(0)
  const currentPage = useRef(0) // the same page, for the zoom effect, which must not rerun on every scroll
  const well = useRef<HTMLDivElement>(null)

  function showPage(number: number) {
    currentPage.current = number
    setPage(number)
  }

  // The page counter follows the sheet in the middle of the well
  useEffect(() => {
    const sheets = sheetsIn(well.current)
    if (sheets.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) showPage(sheets.indexOf(entry.target as HTMLElement) + 1)
        }
      },
      { root: well.current, rootMargin: '-50% 0px -50% 0px' },
    )
    sheets.forEach((sheet) => observer.observe(sheet))
    return () => observer.disconnect()
  }, [pages])

  // After a zoom change the page being read stays in view
  useEffect(() => {
    if (currentPage.current) sheetsIn(well.current)[currentPage.current - 1]?.scrollIntoView({ block: 'start' })
  }, [zoom])

  // A card clicked in the flags panel brings its highlight into view
  useEffect(() => {
    if (flagSource !== 'card' || !selectedFlagId) return
    const mark = well.current?.querySelector(`[data-flag-id="${CSS.escape(selectedFlagId)}"]`)
    mark?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [flagFocus, flagSource, selectedFlagId])

  function goToPage(number: number) {
    const target = Math.min(Math.max(number, 1), pages.length)
    sheetsIn(well.current)[target - 1]?.scrollIntoView({ block: 'start' })
    showPage(target)
  }

  const notice = results && scan?.aiNotice && !scan.noticeDismissed ? scan.aiNotice : null
  return (
    <main className="doc">
      <Toolbar
        name={scan ? scan.filename : 'No document'}
        enabled={results !== null}
        page={pages.length ? Math.max(page, 1) : 0}
        pages={pages.length}
        zoom={zoom}
        onPage={goToPage}
        onZoom={onZoom}
        onDownload={() => scan && downloadScan(scan.id)}
      />
      {scan && notice && <FallbackStrip notice={notice} onDismiss={() => onDismissNotice(scan.id)} />}
      <div className="well" id="well" data-zoom={ZOOMS[zoom].id} ref={well}>
        <WellContent
          scan={scan}
          results={results}
          pages={pages}
          selectedFlagId={selectedFlagId}
          onMarkClick={onMarkClick}
          onCancel={onCancel}
        />
      </div>
    </main>
  )
}
