// Asks the server for the progress of every running scan once a second, and fetches
// each scan's results once when it finishes
import { useEffect, type Dispatch } from 'react'
import { errorText, getResults, getScan } from './api'
import { isRunning } from './stages'
import type { Action, ScanEntry } from './state'

const POLL_MS = 1000

async function refresh(id: string, dispatch: Dispatch<Action>) {
  try {
    const status = await getScan(id)
    dispatch({ type: 'status', status })
    if (status.stage === 'done') dispatch({ type: 'results', id, results: await getResults(id) })
  } catch (error) {
    dispatch({ type: 'lost', id, error: errorText(error) })
  }
}

export function usePolling(scans: ScanEntry[], dispatch: Dispatch<Action>) {
  // A string, so the effect restarts only when a scan starts or stops running
  const running = scans.filter((scan) => isRunning(scan.stage)).map((scan) => scan.id).join(' ')

  useEffect(() => {
    if (!running) return
    let stopped = false
    let timer = 0
    const tick = async () => {
      await Promise.all(running.split(' ').map((id) => refresh(id, dispatch)))
      if (!stopped) timer = window.setTimeout(tick, POLL_MS)
    }
    timer = window.setTimeout(tick, POLL_MS)
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [running, dispatch])
}
