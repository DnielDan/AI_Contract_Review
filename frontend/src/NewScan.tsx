export function NewScan({ onClick }: { onClick: () => void }) {
  return (
    <button className="newscan" id="new-scan" type="button" onClick={onClick}>
      + New scan
    </button>
  )
}
