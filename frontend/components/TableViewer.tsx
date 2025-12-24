'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Table, ChevronDown, Copy, Check, FileText } from 'lucide-react'
import { useTables } from '../lib/hooks'
import { cn } from '../lib/utils'

interface TableViewerProps {
  documentId: string
}

export function TableViewer({ documentId }: TableViewerProps) {
  const { data: tables, isLoading } = useTables(documentId)
  const [expandedTable, setExpandedTable] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [copyError, setCopyError] = useState<string | null>(null)

  const copyToClipboard = async (markdown: string, id: string) => {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopiedId(id)
      setCopyError(null)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Clipboard write failed:', err)
      // Fallback for browsers that block clipboard API
      try {
        const textArea = document.createElement('textarea')
        textArea.value = markdown
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
        setCopiedId(id)
        setCopyError(null)
        setTimeout(() => setCopiedId(null), 2000)
      } catch {
        setCopyError('Failed to copy')
        setTimeout(() => setCopyError(null), 2000)
      }
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-2xl border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Table className="h-5 w-5 text-primary" />
          <span className="font-medium">Tables</span>
        </div>
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-muted animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (!tables || tables.length === 0) {
    return null
  }

  return (
    <div className="rounded-2xl border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Table className="h-5 w-5 text-primary" />
        <span className="font-medium">Extracted Tables ({tables.length})</span>
      </div>

      <div className="space-y-3">
        {tables.map((table) => (
          <div key={table.id} className="rounded-xl border overflow-hidden">
            <button
              onClick={() => setExpandedTable(expandedTable === table.id ? null : table.id)}
              className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium">
                    {table.title || `Table on Page ${table.page_number}`}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {table.row_count} rows × {table.column_count} columns
                  </p>
                </div>
              </div>
              <ChevronDown
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  expandedTable === table.id && 'rotate-180'
                )}
              />
            </button>

            <AnimatePresence>
              {expandedTable === table.id && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="border-t p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">
                        Page {table.page_number}
                      </span>
                      <button
                        onClick={() => copyToClipboard(table.markdown, table.id)}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {copiedId === table.id ? (
                          <>
                            <Check className="h-3.5 w-3.5" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            Copy
                          </>
                        )}
                      </button>
                    </div>

                    <div className="overflow-x-auto scrollbar-thin">
                      <div
                        className="prose prose-sm dark:prose-invert max-w-none [&_table]:w-full [&_th]:bg-muted [&_th]:px-3 [&_th]:py-2 [&_td]:px-3 [&_td]:py-2 [&_th]:text-left [&_th]:font-medium [&_th]:text-sm [&_td]:text-sm [&_tr]:border-b"
                        dangerouslySetInnerHTML={{
                          __html: markdownToHtml(table.markdown),
                        }}
                      />
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </div>
  )
}

function markdownToHtml(markdown: string): string {
  const lines = markdown.trim().split('\n')
  if (lines.length < 2) return ''

  const headers = lines[0].split('|').filter(Boolean).map((h) => h.trim())
  const rows = lines.slice(2).map((line) =>
    line.split('|').filter(Boolean).map((c) => c.trim())
  )

  const headerHtml = headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')
  const rowsHtml = rows
    .map((row) => `<tr>${row.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`)
    .join('')

  return `<table><thead><tr>${headerHtml}</tr></thead><tbody>${rowsHtml}</tbody></table>`
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
