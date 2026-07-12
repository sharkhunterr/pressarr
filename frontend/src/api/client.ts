const BASE_URL = '/api/v1'

function getApiKey(): string | null {
  return localStorage.getItem('pressarr_api_key')
}

export function setApiKey(key: string): void {
  localStorage.setItem('pressarr_api_key', key)
}

export function clearApiKey(): void {
  localStorage.removeItem('pressarr_api_key')
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

let apiKeyPromptResolve: ((key: string | null) => void) | null = null
let apiKeyPromptVisible = false

export function isApiKeyPromptVisible(): boolean {
  return apiKeyPromptVisible
}

export function onApiKeyPromptResult(key: string | null): void {
  if (apiKeyPromptResolve) {
    apiKeyPromptResolve(key)
    apiKeyPromptResolve = null
  }
  apiKeyPromptVisible = false
}

function promptForApiKey(): Promise<string | null> {
  apiKeyPromptVisible = true
  return new Promise<string | null>((resolve) => {
    apiKeyPromptResolve = resolve
    window.dispatchEvent(new CustomEvent('pressarr:api-key-prompt'))
  })
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string>) || {}),
  }

  const apiKey = getApiKey()
  if (apiKey) {
    headers['X-Api-Key'] = apiKey
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    // Prompt user for API key
    const newKey = await promptForApiKey()
    if (newKey) {
      setApiKey(newKey)
      // Retry with the new key
      headers['X-Api-Key'] = newKey
      const retryResponse = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers,
      })

      if (!retryResponse.ok) {
        const body = await retryResponse.text()
        throw new ApiError(retryResponse.status, body)
      }

      if (retryResponse.status === 204) {
        return undefined as T
      }

      return retryResponse.json()
    } else {
      throw new ApiError(401, 'Authentication required')
    }
  }

  if (!response.ok) {
    const body = await response.text()
    throw new ApiError(response.status, body)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}
