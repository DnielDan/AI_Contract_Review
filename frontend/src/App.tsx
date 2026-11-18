import { useEffect, useReducer, useRef } from 'react'
import { deleteScan, errorText, getConfig, startScan } from './api'
import { DocViewer } from './DocViewer'
import { allFlags } from './flags'
import { FlagsPanel } from './FlagsPanel'
import { Header } from './Header'
import { usePolling } from './polling'
import { Rail } from './Rail'
import { initialState, reducer, type FlagSource } from './state'
import type { Flag } from './types'

// The workbench: scans in the rail on the left, the selected contract in the middle, its flags on the right
export function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const rejectedUploads = useRef(0)
  usePolling(state.scans, dispatch)

  // So a new scan's progress names the right review from the start ("AI review" or "Match").
  // If the server cannot be reached, scans say so when they start.
  useEffect(() => {
    getConfig()
      .then((config) => dispatch({ type: 'config', reviewMethod: config.review_method }))
      .catch(() => null)
  }, [])

  const scan = state.scans.find((entry) => entry.id === state.selectedScanId) ?? null
  const flags = scan?.stage === 'done' && scan.results ? allFlags(scan.results) : null

  // The server checks the file type and size, so its message is shown for any upload it turns down
  async function scanFiles(files: File[]) {
    for (const file of files) {
      try {
        dispatch({ type: 'started', scan: await startScan(file) })
      } catch (error) {
        rejectedUploads.current += 1
        const id = `rejected-${rejectedUploads.current}`
        dispatch({ type: 'rejected', id, filename: file.name, error: errorText(error) })
      }
    }
  }

  async function cancelScan(id: string) {
    // The scan may have finished, or the server may have restarted; either way it is no longer running
    await deleteScan(id).catch(() => null)
    dispatch({ type: 'cancelled', id })
  }

  const selectFlag = (source: FlagSource) => (flag: Flag) => dispatch({ type: 'selectFlag', flag, source })

  return (
    <div className="app">
      <Header />
      <div className={state.panelCollapsed ? 'frame collapsed' : 'frame'} id="frame">
        <Rail
          scans={state.scans}
          selectedScanId={state.selectedScanId}
          onFiles={scanFiles}
          onSelect={(id) => dispatch({ type: 'selectScan', id })}
        />
        <DocViewer
          key={scan?.id ?? 'none'}
          scan={scan}
          zoom={state.zoom}
          selectedFlagId={state.selectedFlagId}
          flagSource={state.flagSource}
          flagFocus={state.flagFocus}
          onZoom={(zoom) => dispatch({ type: 'zoom', zoom })}
          onMarkClick={selectFlag('mark')}
          onCancel={cancelScan}
          onDismissNotice={(id) => dispatch({ type: 'dismissNotice', id })}
        />
        <FlagsPanel
          flags={flags}
          filter={state.filter}
          selectedFlagId={state.selectedFlagId}
          flagSource={state.flagSource}
          flagFocus={state.flagFocus}
          collapsed={state.panelCollapsed}
          onFilter={(filter) => dispatch({ type: 'filter', filter })}
          onSelect={selectFlag('card')}
          onToggle={() => dispatch({ type: 'togglePanel' })}
        />
      </div>
    </div>
  )
}
