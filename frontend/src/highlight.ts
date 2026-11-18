// Splits a paragraph into plain text and highlighted pieces, one highlight per flag
import type { Flag } from './types'

export interface Piece {
  text: string
  flag: Flag | null
}

interface Range {
  flag: Flag
  start: number
  end: number
}

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function charPattern(char: string) {
  if ("'‘’".includes(char)) return "['‘’]"
  if ('"“”'.includes(char)) return '["“”]'
  return escapeRegExp(char)
}

// A flagged sentence matches regardless of case, runs of whitespace, and straight or curly quotes.
// A FAR clause number only matches on its own, so 52.204-2 does not match inside 52.204-21
// (the same rule as _clause_pattern in flag_FAR_clauses.py).
function patternFor(flag: Flag) {
  if (flag.kind === 'far') return new RegExp(`(?<![\\d.])${escapeRegExp(flag.clause)}(?!\\d)`)
  const words = flag.sentence.trim().split(/\s+/).map((word) => Array.from(word).map(charPattern).join(''))
  return new RegExp(words.join('\\s+'), 'i')
}

// The first match in the paragraph, or the whole paragraph when the text is not found in it
function rangeOf(text: string, flag: Flag): Range {
  const match = patternFor(flag).exec(text)
  if (!match || !match[0]) return { flag, start: 0, end: text.length }
  return { flag, start: match.index, end: match.index + match[0].length }
}

// Where highlights overlap the shortest one shows, so a FAR clause number inside a
// flagged sentence can still be clicked
function innermost(ranges: Range[], start: number, end: number) {
  const covering = ranges.filter((range) => range.start <= start && range.end >= end)
  covering.sort((a, b) => a.end - a.start - (b.end - b.start))
  return covering[0]?.flag ?? null
}

export function highlightPieces(text: string, flags: Flag[]): Piece[] {
  const ranges = flags.map((flag) => rangeOf(text, flag))
  const cuts = [...new Set([0, text.length, ...ranges.flatMap((range) => [range.start, range.end])])]
  cuts.sort((a, b) => a - b)
  const pieces: Piece[] = []
  for (let i = 0; i < cuts.length - 1; i++) {
    const flag = innermost(ranges, cuts[i], cuts[i + 1])
    const slice = text.slice(cuts[i], cuts[i + 1])
    const last = pieces[pieces.length - 1]
    if (last && last.flag === flag) last.text += slice
    else pieces.push({ text: slice, flag })
  }
  return pieces
}
