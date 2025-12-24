'use client'

import { motion } from 'framer-motion'
import { Upload, FileText, Search, MessageSquare, AlertCircle, Table, Image } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import Link from 'next/link'

interface EmptyStateAction {
  label: string
  href?: string
  onClick?: () => void
}

interface EmptyStateItem {
  icon: React.ReactNode
  title: string
  description: string
  action?: EmptyStateAction
}

interface EmptyStateProps {
  type: 'no-documents' | 'not-indexed' | 'no-answer' | 'no-tables' | 'no-figures' | 'error'
  title?: string
  description?: string
  action?: EmptyStateAction
}

const emptyStateConfig: Record<string, EmptyStateItem> = {
  'no-documents': {
    icon: <Upload className="h-8 w-8" />,
    title: 'No documents yet',
    description: 'Upload your first PDF to get started. Paper will extract text, tables, and figures automatically.',
    action: { label: 'Upload Document', href: '/dashboard' },
  },
  'not-indexed': {
    icon: <Search className="h-8 w-8" />,
    title: 'Document not ready for questions',
    description: 'This document needs to be processed before you can ask questions. Click "Index for QA" to enable question answering.',
  },
  'no-answer': {
    icon: <MessageSquare className="h-8 w-8" />,
    title: 'No answer found',
    description: 'Paper couldn\'t find information to answer this question in the document. Try rephrasing or asking about a different topic.',
  },
  'no-tables': {
    icon: <Table className="h-8 w-8" />,
    title: 'No tables found',
    description: 'Paper didn\'t detect any tables in this document. Tables are automatically extracted during visual processing.',
  },
  'no-figures': {
    icon: <Image className="h-8 w-8" />,
    title: 'No figures found',
    description: 'Paper didn\'t detect any figures or charts in this document. Figures are automatically extracted during visual processing.',
  },
  'error': {
    icon: <AlertCircle className="h-8 w-8" />,
    title: 'Something went wrong',
    description: 'We encountered an error. Please try again or contact support if the problem persists.',
  },
}

export function EmptyState({ type, title, description, action }: EmptyStateProps) {
  const config = emptyStateConfig[type]
  const displayTitle = title || config.title
  const displayDescription = description || config.description
  const displayAction = action || config.action

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center text-center py-12 px-4"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground mb-4">
        {config.icon}
      </div>
      
      <h3 className="font-semibold text-lg mb-2">{displayTitle}</h3>
      <p className="text-sm text-muted-foreground max-w-sm mb-6">{displayDescription}</p>
      
      {displayAction && (
        displayAction.href ? (
          <Button asChild>
            <Link href={displayAction.href}>{displayAction.label}</Link>
          </Button>
        ) : displayAction.onClick ? (
          <Button onClick={displayAction.onClick}>{displayAction.label}</Button>
        ) : null
      )}
    </motion.div>
  )
}

// Inline empty state for smaller contexts
export function InlineEmptyState({ 
  icon, 
  message 
}: { 
  icon?: React.ReactNode
  message: string 
}) {
  return (
    <div className="flex items-center gap-3 text-muted-foreground py-4 px-2">
      {icon || <FileText className="h-5 w-5 shrink-0" />}
      <p className="text-sm">{message}</p>
    </div>
  )
}
