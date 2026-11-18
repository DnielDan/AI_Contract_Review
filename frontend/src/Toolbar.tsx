import { useEffect, useState } from 'react'
import { ZOOMS } from './state'

interface Props {
  name: string
  enabled: boolean
  page: number
  pages: number
  zoom: number
  onPage: (page: number) => void
  onZoom: (zoom: number) => void
  onDownload: () => void
}

function Icon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24">
      <path d={path} />
    </svg>
  )
}

function ZoomMenu({ zoom, onZoom }: { zoom: number; onZoom: (zoom: number) => void }) {
  const [open, setOpen] = useState(false)

  // Closes on Escape or on a click anywhere outside the menu
  useEffect(() => {
    if (!open) return
    const onClick = (event: MouseEvent) => {
      if (!(event.target as Element).closest('.zoomwrap')) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('click', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function pick(index: number) {
    setOpen(false)
    onZoom(index)
  }

  return (
    <div className="zoomwrap">
      <button
        className="zoom"
        id="zoom-button"
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {ZOOMS[zoom].label} ▾
      </button>
      {open && (
        <div className="menu zmenu" role="menu">
          {ZOOMS.map((option, index) => (
            <button key={option.id} type="button" role="menuitem" onClick={() => pick(index)}>
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function Toolbar({ name, enabled, page, pages, zoom, onPage, onZoom, onDownload }: Props) {
  return (
    <div className={enabled ? 'tool' : 'tool off'} id="toolbar">
      <div className="l">{name}</div>
      <div className="r">
        <span className="pager">
          <button
            className="ic"
            type="button"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            <Icon path="M15 18l-6-6 6-6" />
          </button>
          <span>
            {page} / {pages}
          </span>
          <button
            className="ic"
            type="button"
            aria-label="Next page"
            disabled={page >= pages}
            onClick={() => onPage(page + 1)}
          >
            <Icon path="M9 6l6 6-6 6" />
          </button>
        </span>
        <span className="sep" />
        <button className="ic" type="button" aria-label="Zoom out" disabled={zoom === 0} onClick={() => onZoom(zoom - 1)}>
          <Icon path="M5 12h14" />
        </button>
        <ZoomMenu zoom={zoom} onZoom={onZoom} />
        <button
          className="ic"
          type="button"
          aria-label="Zoom in"
          disabled={zoom === ZOOMS.length - 1}
          onClick={() => onZoom(zoom + 1)}
        >
          <Icon path="M12 5v14M5 12h14" />
        </button>
        <span className="sep" />
        <button
          className="ic dl"
          id="download"
          type="button"
          title="Download annotated .docx"
          aria-label="Download annotated .docx"
          onClick={onDownload}
        >
          <Icon path="M12 3v12M7 10l5 5 5-5M4 19h16" />
        </button>
      </div>
    </div>
  )
}
