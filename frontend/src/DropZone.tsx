import { useEffect, useState, type DragEvent } from 'react'

function preventDefault(event: Event) {
  event.preventDefault()
}

export function DropZone({ onClick, onFiles }: { onClick: () => void; onFiles: (files: File[]) => void }) {
  const [over, setOver] = useState(false)

  // A file dropped anywhere else would make the browser leave the workbench to open it
  useEffect(() => {
    window.addEventListener('dragover', preventDefault)
    window.addEventListener('drop', preventDefault)
    return () => {
      window.removeEventListener('dragover', preventDefault)
      window.removeEventListener('drop', preventDefault)
    }
  }, [])

  function onDragOver(event: DragEvent) {
    event.preventDefault()
    setOver(true)
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setOver(false)
    onFiles(Array.from(event.dataTransfer.files))
  }

  return (
    <div
      className={over ? 'drop over' : 'drop'}
      id="drop"
      onClick={onClick}
      onDragOver={onDragOver}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      ⬆ Drop a contract here
      <small>
        or click to browse
        <br />
        .docx · .doc · .pdf · up to 25 MB
      </small>
    </div>
  )
}
