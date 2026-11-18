// The shapes the Python server returns (main.py and scan_results.py)

export type Stage = 'queued' | 'extract' | 'review' | 'annotate' | 'done' | 'failed' | 'cancelled'
export type ReviewMethod = 'llm' | 'matcher'
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
  review_method: ReviewMethod
  elapsed_seconds: number
  flagged_count: number
  ai_notice: string | null
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
  review_method: ReviewMethod
  ai_notice: string | null
}

export interface ServerConfig {
  review_method: ReviewMethod
  provider: string | null
  model: string | null
}

export interface SubcontractScan {
  flagged: boolean
}
