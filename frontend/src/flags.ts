// Helpers shared by the flag cards and the highlights in the document
import type { FarStatus, Flag, ScanResults } from './types'

export const STATUS_WORDS: Record<FarStatus, string> = { OK: 'OK', C: 'Conditional', REMOVE: 'REMOVE' }

export function allFlags(results: ScanResults): Flag[] {
  return [...results.flags, ...results.far]
}

// FAR flags take the color of their acceptance status; language flags keep the default orange
export function farClass(flag: Flag) {
  return flag.kind === 'far' ? `far-${flag.status.toLowerCase()}` : ''
}

// The flags of each paragraph, by paragraph index; flags that could not be placed are left out
export function flagsByParagraph(results: ScanResults) {
  const placed = new Map<number, Flag[]>()
  for (const flag of allFlags(results)) {
    if (flag.paragraph === null || flag.paragraph >= results.paragraphs.length) continue
    placed.set(flag.paragraph, [...(placed.get(flag.paragraph) ?? []), flag])
  }
  return placed
}
