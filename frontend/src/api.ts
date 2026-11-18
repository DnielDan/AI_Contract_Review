// Calls to the Python server's API (main.py). Every failed call throws an
// ApiError carrying the server's message, which can be shown to the reviewer.
import type { ScanResults, ScanStarted, ScanStatus, ServerConfig, SubcontractScan } from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return (response.status === 204 ? null : await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // Not an error from the API itself, for example a proxy's error page
  }
  return `The server returned an unexpected error (${response.status}).`
}

// The message to show the reviewer for a failed call
export function errorText(error: unknown) {
  return error instanceof ApiError ? error.message : 'Could not reach the server. Check that it is running.'
}

function upload(file: File): RequestInit {
  const form = new FormData()
  form.append('file', file)
  return { method: 'POST', body: form }
}

const scanPath = (id: string) => `/api/scans/${encodeURIComponent(id)}`

export const startScan = (file: File) => request<ScanStarted>('/api/scans', upload(file))
export const getScan = (id: string) => request<ScanStatus>(scanPath(id))
export const getResults = (id: string) => request<ScanResults>(`${scanPath(id)}/results`)
export const deleteScan = (id: string) => request<null>(scanPath(id), { method: 'DELETE' })
export const getConfig = () => request<ServerConfig>('/api/config')
export const scanSubcontract = (file: File) =>
  request<SubcontractScan>('/api/subcontract-scans', upload(file))

// Fetches the annotated copy and has the browser save it. Fetching it first, rather than opening the
// download link, means a failure (for example a scan the server no longer keeps) throws an ApiError the
// workbench can show, instead of the browser leaving the workbench for an error page and losing the session.
export async function downloadScan(id: string, fallbackName: string) {
  const response = await fetch(`${scanPath(id)}/download`)
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = attachmentName(response) ?? fallbackName
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// The filename the server gives the annotated copy (main.download_scan), or null
function attachmentName(response: Response) {
  const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')
  return match ? match[1] : null
}
