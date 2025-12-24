'use client'

import { useParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { ArrowLeft, FileText, Play, Table, Loader2, AlertCircle } from 'lucide-react'
import Link from 'next/link'
import { PDFViewer } from '../../../../components/PDFViewer'
import { ChatPanel } from '../../../../components/ChatPanel'
import { TableViewer } from '../../../../components/TableViewer'
import { useDocument, useExtractText, useIndexDocument, useExtractVisuals } from '../../../../lib/hooks'
import { formatFileSize, formatDate } from '../../../../lib/utils'

export default function DocumentDetailPage() {
  const params = useParams()
  const documentId = params.id as string

  const { data: document, isLoading, error } = useDocument(documentId)
  const extractTextMutation = useExtractText()
  const indexMutation = useIndexDocument()
  const extractVisualsMutation = useExtractVisuals()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading document...</p>
        </div>
      </div>
    )
  }

  if (error || !document) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-6"
      >
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>

        <div className="rounded-2xl border bg-card p-8 text-center">
          <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold">Document not found</h2>
          <p className="text-sm text-muted-foreground mt-1">
            This document may have been removed or doesn&apos;t exist.
          </p>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="flex h-9 w-9 items-center justify-center rounded-lg border hover:bg-muted transition-colors"
              aria-label="Back to dashboard"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <h1 className="text-xl font-semibold truncate max-w-md">
              {document.filename}
            </h1>
          </div>
          <div className="flex items-center gap-3 text-sm text-muted-foreground pl-12">
            <span>{formatFileSize(document.file_size)}</span>
            {document.page_count && (
              <>
                <span>•</span>
                <span>{document.page_count} pages</span>
              </>
            )}
            <span>•</span>
            <span>{formatDate(document.created_at)}</span>
          </div>
        </div>

        <div className={`px-3 py-1 rounded-full text-xs font-medium ${
          document.status === 'validated'
            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
            : document.status === 'failed'
            ? 'bg-destructive/10 text-destructive'
            : 'bg-muted text-muted-foreground'
        }`}>
          {document.status}
        </div>
      </div>

      {/* Processing Actions */}
      {document.status === 'validated' && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => extractTextMutation.mutate(documentId)}
              disabled={extractTextMutation.isPending}
              className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              {extractTextMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileText className="h-4 w-4" />
              )}
              Extract Text
            </button>

            <button
              onClick={() => indexMutation.mutate(documentId)}
              disabled={indexMutation.isPending}
              className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              {indexMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Index for QA
            </button>

            <button
              onClick={() => extractVisualsMutation.mutate(documentId)}
              disabled={extractVisualsMutation.isPending}
              className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              {extractVisualsMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Table className="h-4 w-4" />
              )}
              Extract Tables
            </button>
          </div>
          
          {/* Mutation feedback */}
          {extractTextMutation.isError && (
            <p className="text-sm text-destructive">Extract text failed: {(extractTextMutation.error as Error)?.message || 'Unknown error'}</p>
          )}
          {extractTextMutation.isSuccess && (
            <p className="text-sm text-green-600 dark:text-green-400">Text extracted successfully</p>
          )}
          {indexMutation.isError && (
            <p className="text-sm text-destructive">Indexing failed: {(indexMutation.error as Error)?.message || 'Unknown error'}</p>
          )}
          {indexMutation.isSuccess && (
            <p className="text-sm text-green-600 dark:text-green-400">Document indexed successfully</p>
          )}
          {extractVisualsMutation.isError && (
            <p className="text-sm text-destructive">Extract visuals failed: {(extractVisualsMutation.error as Error)?.message || 'Unknown error'}</p>
          )}
          {extractVisualsMutation.isSuccess && (
            <p className="text-sm text-green-600 dark:text-green-400">Tables extracted successfully</p>
          )}
        </div>
      )}

      {/* Error Message */}
      {document.error_message && (
        <div className="rounded-xl border border-destructive/50 bg-destructive/5 p-4">
          <p className="text-sm text-destructive">{document.error_message}</p>
        </div>
      )}

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <PDFViewer documentId={documentId} totalPages={document.page_count} />
        </div>

        <div className="lg:col-span-2">
          <ChatPanel documentIds={[documentId]} />
        </div>
      </div>

      <TableViewer documentId={documentId} />
    </motion.div>
  )
}
