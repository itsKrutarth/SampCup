export type ApiStatus = 'online' | 'offline'

export async function fetchApiStatus(signal?: AbortSignal): Promise<ApiStatus> {
  try {
    const response = await fetch('/api/health', { signal })
    return response.ok ? 'online' : 'offline'
  } catch {
    return 'offline'
  }
}
