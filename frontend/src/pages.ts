// Splits the contract into letter-size sheets. Page fill estimate at fit width: ~88 characters
// per line, ~33 lines per sheet, and each paragraph gap costs a fraction of a line.
const LINE_CHARS = 88
const PAGE_LINES = 33
const PARAGRAPH_GAP = 0.4

function paragraphLines(text: string) {
  return Math.max(1, Math.ceil(text.length / LINE_CHARS)) + PARAGRAPH_GAP
}

// Returns the paragraph indexes on each sheet
export function paginate(paragraphs: string[]): number[][] {
  const pages: number[][] = [[]]
  let used = 0
  paragraphs.forEach((text, index) => {
    const lines = paragraphLines(text)
    if (used > 0 && used + lines > PAGE_LINES) {
      pages.push([])
      used = 0
    }
    pages[pages.length - 1].push(index)
    used += lines
  })
  return pages
}

export function isHeading(text: string) {
  return text.length < 80 && /[A-Z]/.test(text) && text === text.toUpperCase()
}
