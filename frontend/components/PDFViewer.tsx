'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Loader2, AlertCircle } from 'lucide-react'
import { useUIStore } from '../lib/store'
import { api } from '../lib/api'
import { cn } from '../lib/utils'
import 'react-pdf/dist/esm/Page/AnnotationLayer.css'
import 'react-pdf/dist/esm/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

interface PDFViewerProps {
  documentId: string
  totalPages?: number
  className?: string
}

export function PDFViewer({ documentId, totalPages, className }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(totalPages || 0)
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [scale, setScale] = useState<number>(1.0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [highlightedPage, setHighlightedPage] = useState<number | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  const { selectedPage, setSelectedPage } = useUIStore()
  const pdfUrl = api.getPdfUrl(documentId)

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages)
    setIsLoading(false)
    setError(null)
  }, [])

  const onDocumentLoadError = useCallback(() => {
    setError('Unable to load PDF')
    setIsLoading(false)
  }, [])

  useEffect(() => {
    if (selectedPage === null) return
    if (selectedPage < 1 || (numPages > 0 && selectedPage > numPages)) {
      setSelectedPage(null)
      return
    }

    // Wait for document to be loaded before trying to scroll
    if (numPages === 0) return

    const pageElement = pageRefs.current.get(selectedPage)
    if (pageElement) {
      pageElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setCurrentPage(selectedPage)
      setHighlightedPage(selectedPage)
      const timer = setTimeout(() => setHighlightedPage(null), 2000)
      return () => clearTimeout(timer)
    }
    // If page ref not found but document is loaded, page doesn't exist
    // Don't reset selectedPage if refs might still be populating
  }, [selectedPage, numPages, setSelectedPage])

  const goToPage = useCallback((page: number) => {
    if (page >= 1 && page <= numPages) {
      setCurrentPage(page)
      const pageElement = pageRefs.current.get(page)
      if (pageElement) {
        pageElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [numPages])

  const setPageRef = useCallback((pageNum: number) => (el: HTMLDivElement | null) => {
    if (el) pageRefs.current.set(pageNum, el)
    else pageRefs.current.delete(pageNum)
  }, [])

  if (error) {
    return (
      <div className={cn('rounded-2xl border bg-card', className)}>
        <div className="flex flex-col items-center justify-center h-96 p-6 text-center">
          <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="font-medium">Unable to load PDF</p>
          <p className="text-sm text-muted-foreground mt-1">
            The document may be unavailable or corrupted.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('rounded-2xl border bg-card overflow-hidden', className)}>
      {/* Controls */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1 || isLoading}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <span className="text-sm font-medium min-w-[100px] text-center">
            {isLoading ? 'Loading...' : `${currentPage} / ${numPages}`}
          </span>

          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= numPages || isLoading}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setScale((s) => Math.max(s - 0.2, 0.5))}
            disabled={scale <= 0.5}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
            aria-label="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>

          <span className="text-sm font-medium min-w-[4rem] text-center">
            {Math.round(scale * 100)}%
          </span>

          <button
            onClick={() => setScale((s) => Math.min(s + 0.2, 3.0))}
            disabled={scale >= 3.0}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
            aria-label="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* PDF Content */}
      <div ref={containerRef} className="overflow-auto max-h-[600px] bg-muted/20 scrollbar-thin">
        {isLoading && (
          <div className="flex items-center justify-center h-96">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        )}

        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={null}
          className="flex flex-col items-center space-y-4 p-4"
        >
          {numPages > 0 && Array.from({ length: numPages }, (_, index) => {
            const pageNumber = index + 1
            return (
              <motion.div
                key={pageNumber}
                ref={setPageRef(pageNumber)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className={cn(
                  'shadow-lg rounded-lg overflow-hidden transition-all duration-300',
                  highlightedPage === pageNumber && 'ring-4 ring-primary/50'
                )}
              >
                <Page
                  pageNumber={pageNumber}
                  scale={scale}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  loading={
                    <div className="flex items-center justify-center h-[800px] w-[600px] bg-background">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  }
                />
              </motion.div>
            )
          })}
        </Document>
      </div>
    </div>
  )
}
