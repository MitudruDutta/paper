'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, FileText, Table, Image, AlertCircle, Info } from 'lucide-react'
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

export function AnswerCard({ content, sources, confidence, isError }: AnswerCardProps) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false)

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

  if (isError) {
    return (
      <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-destructive">Unable to get answer</p>
            <p className="text-sm text-muted-foreground">{sanitizedContent}</p>
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
              Try rephrasing your question or check if the document contains this information.
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

      {/* Sources */}
      {sources && sources.length > 0 && (
        <div className="pt-2 border-t">
          <button
            onClick={() => setSourcesExpanded(!sourcesExpanded)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full"
          >
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform',
                sourcesExpanded && 'rotate-180'
              )}
            />
            <span>{sources.length} source{sources.length !== 1 ? 's' : ''}</span>
          </button>

          <AnimatePresence>
            {sourcesExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="flex flex-wrap gap-2 pt-3">
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
      )}
    </div>
  )
}
