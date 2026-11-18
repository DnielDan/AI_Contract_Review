// The shapes the Python server returns (main.py and scan_results.py)

export type Stage = 'queued' | 'extract' | 'review' | 'annotate' | 'done' | 'failed' | 'cancelled'
export type FarStatus = 'OK' | 'C' | 'REMOVE'

export interface ScanStarted {
  id: string
  filename: string
  stage: Stage
}

export interface ScanStatus {
  id: string
  filename: string
  stage: Stage
  elapsed_seconds: number
  flagged_count: number
  error: string | null
}

export interface LanguageFlag {
  id: string
  kind: 'language'
  paragraph: number | null
  sentence: string
  category: string | null
  why: string | null
  preferred: string | null
  response: string | null
  ai_justification: string | null
  ai_suggested: string | null
  confidence: number | string | null
}

export interface FarFlag {
  id: string
  kind: 'far'
  clause: string
  status: FarStatus
  title: string | null
  criteria: string | null
  request: string | null
  paragraph: number | null
}

export type Flag = LanguageFlag | FarFlag

export interface ScanResults {
  paragraphs: string[]
  flags: LanguageFlag[]
  far: FarFlag[]
  review_label: string
}

// Whether the AI review is set up; while it is not, the server turns down uploads and `problem` says why
export interface ServerConfig {
  ai_ready: boolean
  problem: string | null
  provider: string | null
  model: string | null
}

export interface SubcontractScan {
  flagged: boolean
}
