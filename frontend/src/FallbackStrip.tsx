// Shown when the AI review was configured but could not run, so the flags come from the basic matcher
export function FallbackStrip({ notice, onDismiss }: { notice: string; onDismiss: () => void }) {
  return (
    <div className="strip" id="fallback" role="status">
      <span>{notice}</span>
      <button className="x" type="button" aria-label="Dismiss" onClick={onDismiss}>
        ×
      </button>
    </div>
  )
}
