export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Options = {
  method?: string
  body?: unknown
  token?: string | null
  form?: FormData
}

function detailOf(data: unknown): string | undefined {
  const detail = (data as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg).join('; ')
  return undefined
}

async function send(path: string, { method = 'GET', body, token, form }: Options): Promise<Response> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let payload: BodyInit | undefined = form
  if (!form && body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  let response: Response
  try {
    // no-cache: the browser always asks; CloudFront still answers public pages from its cache
    response = await fetch(`/api${path}`, { method, headers, body: payload, cache: 'no-cache' })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection.')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, detailOf(data) ?? `Request failed (${response.status})`)
  }
  return response
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const response = await send(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Fetch a file that needs a login and hand it to the browser as a download. */
export async function download(path: string, token: string, filename: string): Promise<void> {
  const blob = await (await send(path, { token })).blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
