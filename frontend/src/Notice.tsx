// A yellow strip with a message for the reviewer. Without onDismiss it stays: the AI-not-set-up notice under
// the header lasts until the server is set up and the page is reloaded. With onDismiss it has a close button.
export function Notice({ message, id, onDismiss }: { message: string; id: string; onDismiss?: () => void }) {
  return (
    <div className="strip" id={id} role="alert">
      <span>{message}</span>
      {onDismiss && (
        <button className="x" type="button" aria-label="Dismiss" onClick={onDismiss}>
          ×
        </button>
      )}
    </div>
  )
}
