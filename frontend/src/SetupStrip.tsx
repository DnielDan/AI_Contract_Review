// Shown under the header while the AI review is not set up on the server, which then turns down every
// upload. It stays until the server is set up and the page is reloaded, so it has no dismiss button.
export function SetupStrip({ problem }: { problem: string }) {
  return (
    <div className="strip" id="setup" role="alert">
      <span>{problem}</span>
    </div>
  )
}
