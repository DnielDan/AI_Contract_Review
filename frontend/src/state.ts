// The workbench's state, changed only through reducer() (used by App with useReducer)
import type { Flag, ReviewMethod, ScanResults, ScanStarted, ScanStatus, Stage } from './types'

export const ZOOMS = [
  { id: 'fit', label: 'Fit width' },
  { id: '100', label: '100%' },
  { id: '150', label: '150%' },
]

export type Filter = 'all' | 'language' | 'far'
// Where a flag was selected from, so the other side can scroll to it
export type FlagSource = 'card' | 'mark'

export interface ScanEntry {
  id: string
  filename: string
  stage: Stage
  reviewMethod: ReviewMethod
  elapsedSeconds: number
  aiNotice: string | null
  error: string | null
  results: ScanResults | null
  noticeDismissed: boolean
}

export interface State {
  scans: ScanEntry[]
  selectedScanId: string | null
  selectedFlagId: string | null
  flagSource: FlagSource | null
  flagFocus: number // counts selections, so selecting the same flag again scrolls to it again
  panelCollapsed: boolean
  filter: Filter
  zoom: number
  reviewMethod: ReviewMethod // how the server reviews language, until a scan reports its own
}

export type Action =
  | { type: 'started'; scan: ScanStarted }
  | { type: 'rejected'; id: string; filename: string; error: string }
  | { type: 'status'; status: ScanStatus }
  | { type: 'results'; id: string; results: ScanResults }
  | { type: 'lost'; id: string; error: string }
  | { type: 'cancelled'; id: string }
  | { type: 'selectScan'; id: string }
  | { type: 'selectFlag'; flag: Flag; source: FlagSource }
  | { type: 'filter'; filter: Filter }
  | { type: 'togglePanel' }
  | { type: 'zoom'; zoom: number }
  | { type: 'dismissNotice'; id: string }
  | { type: 'config'; reviewMethod: ReviewMethod }

export const initialState: State = {
  scans: [],
  selectedScanId: null,
  selectedFlagId: null,
  flagSource: null,
  flagFocus: 0,
  panelCollapsed: false,
  filter: 'all',
  zoom: 0,
  reviewMethod: 'matcher',
}

// Adds a scan the server has just accepted or turned down. Its steps are named after the review
// the server is set up for until the scan's first progress report.
function addScan(state: State, id: string, filename: string, stage: Stage, error: string | null = null): State {
  const scan: ScanEntry = {
    id, filename, stage, error,
    reviewMethod: state.reviewMethod, elapsedSeconds: 0, aiNotice: null, results: null, noticeDismissed: false,
  }
  return { ...state, scans: [...state.scans, scan] }
}

function updateScan(state: State, id: string, change: (scan: ScanEntry) => Partial<ScanEntry>): State {
  return { ...state, scans: state.scans.map((scan) => (scan.id === id ? { ...scan, ...change(scan) } : scan)) }
}

// A reply that arrives after the reviewer cancelled the scan must not bring it back
function unlessCancelled(state: State, id: string, change: Partial<ScanEntry>): State {
  return updateScan(state, id, (scan) => (scan.stage === 'cancelled' ? {} : change))
}

function selectScan(state: State, id: string | null): State {
  return { ...state, selectedScanId: id, selectedFlagId: null, flagSource: null }
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'started': {
      const { id, filename, stage } = action.scan
      return selectScan(addScan(state, id, filename, stage), id)
    }
    case 'rejected':
      return addScan(state, action.id, action.filename, 'failed', action.error)
    case 'status': {
      const { id, stage, review_method, elapsed_seconds, ai_notice, error } = action.status
      return unlessCancelled(state, id, {
        stage, reviewMethod: review_method, elapsedSeconds: elapsed_seconds, aiNotice: ai_notice, error,
      })
    }
    case 'results':
      return updateScan(state, action.id, () => ({ results: action.results }))
    case 'lost':
      return unlessCancelled(state, action.id, { stage: 'failed', error: action.error })
    case 'cancelled': {
      const cancelled = updateScan(state, action.id, () => ({ stage: 'cancelled' }))
      return state.selectedScanId === action.id ? selectScan(cancelled, null) : cancelled
    }
    case 'selectScan':
      return selectScan(state, action.id)
    case 'selectFlag': {
      const hidden = state.filter !== 'all' && state.filter !== action.flag.kind
      return {
        ...state,
        selectedFlagId: action.flag.id,
        flagSource: action.source,
        flagFocus: state.flagFocus + 1,
        filter: hidden ? 'all' : state.filter,
      }
    }
    case 'filter':
      return { ...state, filter: action.filter }
    case 'togglePanel':
      return { ...state, panelCollapsed: !state.panelCollapsed }
    case 'zoom':
      return { ...state, zoom: Math.min(Math.max(action.zoom, 0), ZOOMS.length - 1) }
    case 'dismissNotice':
      return updateScan(state, action.id, () => ({ noticeDismissed: true }))
    case 'config':
      return { ...state, reviewMethod: action.reviewMethod }
  }
}
