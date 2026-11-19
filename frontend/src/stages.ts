// The steps of a scan as the server reports them (main.py), and how the workbench names them
import type { Stage } from './types'

const STEPS: Stage[] = ['extract', 'review', 'annotate']
export const STEP_LABELS = ['Extract', 'AI review', 'Annotate']

export function isRunning(stage: Stage) {
  return stage === 'queued' || STEPS.includes(stage)
}

// The step in progress, from 0; -1 while the scan waits to start
export function stepIndex(stage: Stage) {
  return STEPS.indexOf(stage)
}

// The share of steps already finished, so the bar only moves when the server reports progress
export function progressPercent(stage: Stage) {
  return (100 * Math.max(stepIndex(stage), 0)) / STEPS.length
}

export function stageName(stage: Stage) {
  return stage === 'queued' ? 'Queued' : STEP_LABELS[stepIndex(stage)]
}
