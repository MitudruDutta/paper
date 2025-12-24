'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, FileText, Table, Image, AlertCircle, Info, Copy, Check } from 'lucide-react'
import { Source } from '../lib/api'
import { CitationBadge } from './CitationBadge'
import { ConfidenceMeter } from './ConfidenceMeter'
import { cn } from '../lib/utils'
import { sanitizeText } from '../lib/security'

interface AnswerCardProps {
  content: string
  sources?: Source[]
  confidence?: number
  isError?: boolean
}

// Format page range for display (0-indexed to 1-indexed)
function formatPageRange(source: Source): string {
  const start = source.page_start + 1
  const end = source.page_end + 1
  return start === end ? `Page ${start}` : `Pages ${start}-${end}`
}

export function AnswerCard({ content, sources, confidence, isError }: AnswerCardProps) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false)
  const [copied, setCopied] = useState<'success' | 'error' | null>(null)

  // Check if this is a refusal/not-found response
  const isRefusal = content.toLowerCase().includes('cannot find') || 
                    content.toLowerCase().includes('not found') ||
                    content.toLowerCase().includes('no information')

  // Sanitize and render content (XSS prevention)
  const sanitizedContent = sanitizeText(content)

  const getSourceIcon = (type?: string) => {
    switch (type) {
      case 'table':
        return <Table className="h-3.5 w-3.5" />
      case 'figure':
        return <Image className="h-3.5 w-3.5" />
      default:
        return <FileText className="h-3.5 w-3.5" />
    }
  }

  const handleCopy = async () => {
    let text = sanitizedContent
    if (confidence !== undefined) {
      const level = confidence >= 0.7 ? 'High' : confidence >= 0.4 ? 'Medium' : 'Low'
      text += `\n\nConfidence: ${level} (${Math.round(confidence * 100)}%)`
    }
    if (sources && sources.length > 0) {
      text += '\n\nSources:\n'
      sources.forEach((source) => {
        text += `• ${source.document_name || 'Document'}: ${formatPageRange(source)}\n`
      })
    }
    
    try {
      await navigator.clipboard.writeText(text)
      setCopied('success')
      setTimeout(() => setCopied(null), 2000)
    } catch {
      setCopied('error')
      setTimeout(() => setCopied(null), 2000)
    }
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-destructive">Something went wrong</p>
            <p className="text-sm text-muted-foreground">{sanitizedContent}</p>
            <p className="text-xs text-muted-foreground mt-2">
              Try again or rephrase your question.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (isRefusal) {
    return (
      <div className="rounded-xl border bg-muted/50 p-4">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
          <div className="space-y-2">
            <p className="text-sm">{sanitizedContent}</p>
            <p className="text-xs text-muted-foreground">
              This document may not contain the information you&apos;re looking for. Try rephrasing your question or check if the topic is covered.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      {/* Answer content */}
      <div className="text-sm leading-relaxed whitespace-pre-wrap">
        {sanitizedContent}
      </div>

      {/* Confidence */}
      {confidence !== undefined && (
        <ConfidenceMeter confidence={confidence} />
      )}

      {/* Actions row */}
      <div className="flex items-center justify-between pt-2 border-t">
        {/* Sources toggle */}
        {sources && sources.length > 0 ? (
          <button
            onClick={() => setSourcesExpanded(!sourcesExpanded)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform',
                sourcesExpanded && 'rotate-180'
              )}
            />
            <span>
              {sources.length === 1 
                ? formatPageRange(sources[0])
                : `${sources.length} sources`}
            </span>
          </button>
        ) : (
          <div />
        )}

        {/* Copy button */}
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied === 'success' ? (
            <>
              <Check className="h-3.5 w-3.5 text-green-500" />
              Copied
            </>
          ) : copied === 'error' ? (
            <>
              <AlertCircle className="h-3.5 w-3.5 text-destructive" />
              Failed
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Sources expanded */}
      <AnimatePresence>
        {sourcesExpanded && sources && sources.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="flex flex-wrap gap-2 pt-2">
              {sources.map((source) => (
                <CitationBadge
                  key={source.chunk_id || `${source.document_id}-${source.page_start}-${source.page_end}`}
                  source={source}
                  icon={getSourceIcon(source.source_type)}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
