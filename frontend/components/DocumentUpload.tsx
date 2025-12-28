'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, CheckCircle, AlertCircle, AlertTriangle, X } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { cn, formatFileSize } from '../lib/utils'

interface UploadState {
  id: string
  file: File
  progress: number
  status: 'uploading' | 'success' | 'partial' | 'error'
  error?: string
  documentId?: string
}

function generateUploadId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function DocumentUpload() {
  const [uploads, setUploads] = useState<UploadState[]>([])
  const router = useRouter()
  const mountedRef = useRef(true)
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map())
  const redirectTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      // Abort all in-flight uploads
      abortControllersRef.current.forEach(controller => controller.abort())
      abortControllersRef.current.clear()
      // Clear redirect timer
      if (redirectTimerRef.current) {
        clearTimeout(redirectTimerRef.current)
      }
    }
  }, [])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const isSingleFile = acceptedFiles.length === 1

    // Upload files in parallel
    const uploadPromises = acceptedFiles.map(async (file) => {
      const uploadId = generateUploadId()
      const abortController = new AbortController()
      abortControllersRef.current.set(uploadId, abortController)
      
      const uploadState: UploadState = {
        id: uploadId,
        file,
        progress: 0,
        status: 'uploading',
      }

      if (!mountedRef.current) return { success: false, documentId: null }
      setUploads((prev) => [...prev, uploadState])

      let onAbort: (() => void) | null = null

      try {
        const { promise, abort } = await api.uploadDocument(file, (progress) => {
          if (!mountedRef.current) return
          setUploads((prev) =>
            prev.map((u) =>
              u.id === uploadId ? { ...u, progress: Math.min(progress, 50) } : u
            )
          )
        })
        
        // Wire abort controller to upload abort
        onAbort = abort
        abortController.signal.addEventListener('abort', onAbort)
        
        const result = await promise

        if (!mountedRef.current) return { success: false, documentId: result.document_id }

        // Auto-process: extract text and index
        setUploads((prev) =>
          prev.map((u) =>
            u.id === uploadId ? { ...u, progress: 60, documentId: result.document_id } : u
          )
        )

        // Extract text with specific error handling
        try {
          await api.extractText(result.document_id)
          if (!mountedRef.current) return { success: false, documentId: result.document_id }
          setUploads((prev) =>
            prev.map((u) => u.id === uploadId ? { ...u, progress: 80 } : u)
          )
        } catch (extractErr) {
          if (!mountedRef.current) return { success: false, documentId: result.document_id }
          const errMsg = extractErr instanceof ApiError ? extractErr.message : 'Unknown error'
          setUploads((prev) =>
            prev.map((u) => u.id === uploadId ? { 
              ...u, 
              progress: 100, 
              status: 'partial',
              error: `Text extraction failed: ${errMsg}`
            } : u)
          )
          return { success: false, documentId: result.document_id }
        }

        // Index with specific error handling
        try {
          await api.indexDocument(result.document_id)
          if (!mountedRef.current) return { success: false, documentId: result.document_id }
          setUploads((prev) =>
            prev.map((u) => u.id === uploadId ? { ...u, progress: 100, status: 'success' } : u)
          )
          return { success: true, documentId: result.document_id }
        } catch (indexErr) {
          if (!mountedRef.current) return { success: false, documentId: result.document_id }
          const errMsg = indexErr instanceof ApiError ? indexErr.message : 'Unknown error'
          setUploads((prev) =>
            prev.map((u) => u.id === uploadId ? { 
              ...u, 
              progress: 100, 
              status: 'partial',
              error: `Indexing failed: ${errMsg}`
            } : u)
          )
          return { success: false, documentId: result.document_id }
        }
      } catch (err) {
        if (!mountedRef.current) return { success: false, documentId: null }
        const errorMessage = err instanceof ApiError
          ? err.message
          : 'Upload failed. Please try again.'

        setUploads((prev) =>
          prev.map((u) =>
            u.id === uploadId ? { ...u, status: 'error', error: errorMessage } : u
          )
        )
        return { success: false, documentId: null }
      } finally {
        // Clean up abort listener
        if (onAbort) {
          abortController.signal.removeEventListener('abort', onAbort)
        }
        abortControllersRef.current.delete(uploadId)
      }
    })

    const results = await Promise.allSettled(uploadPromises)
    
    // Only redirect for single successful file upload
    if (isSingleFile && mountedRef.current) {
      const result = results[0]
      if (result.status === 'fulfilled' && result.value?.success && result.value.documentId) {
        redirectTimerRef.current = setTimeout(() => {
          if (mountedRef.current) {
            router.push(`/dashboard/documents/${result.value.documentId}`)
          }
        }, 500)
      }
    }
  }, [router])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
  })

  const removeUpload = (id: string) => {
    // Abort if still uploading
    const controller = abortControllersRef.current.get(id)
    if (controller) {
      controller.abort()
      abortControllersRef.current.delete(id)
    }
    setUploads((prev) => prev.filter((u) => u.id !== id))
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          'relative rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-all',
          isDragActive
            ? 'border-primary bg-primary/5'
            : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'
        )}
      >
        <input {...getInputProps()} />
        
        <motion.div
          animate={{ scale: isDragActive ? 1.02 : 1 }}
          className="space-y-4"
        >
          <div className="flex justify-center">
            <div className={cn(
              'flex h-16 w-16 items-center justify-center rounded-2xl transition-colors',
              isDragActive ? 'bg-primary/10' : 'bg-muted'
            )}>
              <Upload className={cn(
                'h-8 w-8 transition-colors',
                isDragActive ? 'text-primary' : 'text-muted-foreground'
              )} />
            </div>
          </div>

          <div>
            <p className="text-base font-medium">
              {isDragActive ? 'Drop your PDF here' : 'Drop PDF files here'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              or click to browse • Max 50 MB
            </p>
          </div>
        </motion.div>
      </div>

      {/* Upload Progress */}
      <AnimatePresence>
        {uploads.map((upload) => (
          <motion.div
            key={upload.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="rounded-xl border bg-card p-4"
          >
            <div className="flex items-start gap-3">
              <div className={cn(
                'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                upload.status === 'success' ? 'bg-green-500/10' :
                upload.status === 'partial' ? 'bg-yellow-500/10' :
                upload.status === 'error' ? 'bg-destructive/10' : 'bg-muted'
              )}>
                {upload.status === 'success' ? (
                  <CheckCircle className="h-5 w-5 text-green-500" />
                ) : upload.status === 'partial' ? (
                  <AlertTriangle className="h-5 w-5 text-yellow-500" />
                ) : upload.status === 'error' ? (
                  <AlertCircle className="h-5 w-5 text-destructive" />
                ) : (
                  <FileText className="h-5 w-5 text-muted-foreground" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium truncate">{upload.file.name}</p>
                  <button
                    onClick={() => removeUpload(upload.id)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Remove"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                
                <p className="text-xs text-muted-foreground">
                  {formatFileSize(upload.file.size)}
                </p>

                {upload.status === 'uploading' && (
                  <div className="mt-2">
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${upload.progress}%` }}
                        className="h-full rounded-full bg-primary"
                      />
                    </div>
                  </div>
                )}

                {upload.status === 'error' && upload.error && (
                  <p className="text-xs text-destructive mt-1">{upload.error}</p>
                )}

                {upload.status === 'partial' && (
                  <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
                    {upload.error}
                  </p>
                )}

                {upload.status === 'success' && (
                  <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                    Uploaded and processed successfully
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
