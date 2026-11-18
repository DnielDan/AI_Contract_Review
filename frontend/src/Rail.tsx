import { useRef, type ChangeEvent } from 'react'
import { DropZone } from './DropZone'
import { NewScan } from './NewScan'
import { ScanList } from './ScanList'
import type { ScanEntry } from './state'

interface Props {
  scans: ScanEntry[]
  selectedScanId: string | null
  onFiles: (files: File[]) => void
  onSelect: (id: string) => void
  onRemove: (id: string) => void
}

export function Rail({ scans, selectedScanId, onFiles, onSelect, onRemove }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const openPicker = () => input.current?.click()

  function onPicked(event: ChangeEvent<HTMLInputElement>) {
    onFiles(Array.from(event.target.files ?? []))
    event.target.value = ''
  }

  return (
    <aside className="rail">
      <DropZone onClick={openPicker} onFiles={onFiles} />
      <input ref={input} type="file" id="file-input" accept=".docx,.doc,.pdf" hidden onChange={onPicked} />
      <NewScan onClick={openPicker} />
      <ScanList scans={scans} selectedScanId={selectedScanId} onSelect={onSelect} onRemove={onRemove} />
    </aside>
  )
}
