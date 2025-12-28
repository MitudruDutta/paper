const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Token getter - set by auth provider
let getAuthToken: (() => Promise<string | null>) | null = null

export function setAuthTokenGetter(getter: () => Promise<string | null>) {
  getAuthToken = getter
}

export interface Document {
  id: string
  filename: string
  status: 'uploaded' | 'validated' | 'failed'
  file_size: number
  page_count?: number
  created_at: string
  error_message?: string
}

export interface UploadResponse {
  document_id: string
  filename: string
  status: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  confidence?: number
  isError?: boolean
}

export interface Source {
  document_id: string
  document_name: string
  page_start: number
  page_end: number
  chunk_id: string
  source_type?: 'text' | 'table' | 'figure'
}

export interface TableData {
  id: string
  page_number: number
  title?: string
  row_count: number
  column_count: number
  markdown: string
}

export interface FigureData {
  id: string
  page_number: number
  figure_type: string
  description: string
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: HeadersInit = { ...options.headers }
  
  // Only set Content-Type for non-FormData requests
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  // Add auth token if available
  if (getAuthToken) {
    const token = await getAuthToken()
    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`
    }
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errorMessage: string
    try {
      const errorData = await response.json()
      errorMessage = errorData.detail || JSON.stringify(errorData)
    } catch {
      errorMessage = await response.text() || `HTTP ${response.status}`
    }
    throw new ApiError(response.status, errorMessage)
  }

  // Safely parse JSON response
  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) {
    try {
      return await response.json()
    } catch {
      return await response.text() as unknown as T
    }
  }
  return await response.text() as unknown as T
}

export const api = {
  async uploadDocument(file: File, onProgress?: (progress: number) => void, options?: { timeout?: number }): Promise<{ promise: Promise<UploadResponse>; abort: () => void }> {
    const formData = new FormData()
    formData.append('file', file)
    
    // Get auth token before creating XHR
    let authToken: string | null = null
    if (getAuthToken) {
      authToken = await getAuthToken()
    }
    
    const xhr = new XMLHttpRequest()
    
    const promise = new Promise<UploadResponse>((resolve, reject) => {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      })
      
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText))
          } catch {
            reject(new ApiError(xhr.status, 'Invalid response'))
          }
        } else {
          let errorMsg = 'Upload failed'
          try {
            const err = JSON.parse(xhr.responseText)
            errorMsg = err.detail || errorMsg
          } catch {}
          reject(new ApiError(xhr.status, errorMsg))
        }
      })
      
      xhr.addEventListener('error', () => {
        reject(new ApiError(0, 'Network error'))
      })
      
      xhr.addEventListener('timeout', () => {
        reject(new ApiError(0, 'Upload timed out'))
      })
      
      if (options?.timeout) {
        xhr.timeout = options.timeout
      }
      
      xhr.open('POST', `${API_BASE}/documents/upload`)
      if (authToken) {
        xhr.setRequestHeader('Authorization', `Bearer ${authToken}`)
      }
      xhr.send(formData)
    })
    
    return { promise, abort: () => xhr.abort() }
  },

  async getDocuments(): Promise<Document[]> {
    return apiRequest('/documents')
  },

  async getDocument(id: string): Promise<Document> {
    return apiRequest(`/documents/${id}`)
  },

  async extractText(id: string): Promise<{ status: string }> {
    return apiRequest(`/documents/${id}/extract-text?sync=true`, { method: 'POST' })
  },

  async indexDocument(id: string): Promise<{ status: string }> {
    return apiRequest(`/documents/${id}/index?sync=true`, { method: 'POST' })
  },

  async extractVisuals(id: string): Promise<{ status: string }> {
    return apiRequest(`/documents/${id}/extract-visuals?sync=true`, { 
      method: 'POST',
      body: JSON.stringify({ force: false })
    })
  },

  async askQuestion(question: string, documentIds: string[], conversationId?: string): Promise<{
    answer: string
    confidence: number
    sources: Source[]
    conversation_id: string
  }> {
    return apiRequest('/ask', {
      method: 'POST',
      body: JSON.stringify({
        question,
        document_ids: documentIds,
        conversation_id: conversationId,
      }),
    })
  },

  async getTables(documentId: string): Promise<TableData[]> {
    return apiRequest(`/documents/${documentId}/tables`)
  },

  async getFigures(documentId: string): Promise<FigureData[]> {
    return apiRequest(`/documents/${documentId}/figures`)
  },

  getPdfUrl(documentId: string): string {
    return `${API_BASE}/documents/${documentId}/pdf`
  },

  async checkHealth(): Promise<{ status: string }> {
    return apiRequest('/health')
  },
}
