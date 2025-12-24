'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion } from 'framer-motion'
import { Search, FileText, Upload, CheckCircle, XCircle, Clock, Plus } from 'lucide-react'
import { useDocuments } from '../../lib/hooks'
import { cn, formatFileSize, formatDate } from '../../lib/utils'
import { Button } from '../ui/Button'

export function Sidebar() {
  const [search, setSearch] = useState('')
  const pathname = usePathname()
  const { data: documents, isLoading } = useDocuments()

  const filteredDocs = documents?.filter((doc) =>
    (doc.filename || '').toLowerCase().includes(search.toLowerCase())
  )

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'validated':
        return <CheckCircle className="h-3.5 w-3.5 text-green-500" />
      case 'failed':
        return <XCircle className="h-3.5 w-3.5 text-destructive" />
      default:
        return <Clock className="h-3.5 w-3.5 text-muted-foreground" />
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="p-4 space-y-3">
        <Link href="/app">
          <Button className="w-full justify-start gap-2" size="sm">
            <Plus className="h-4 w-4" />
            Upload Document
          </Button>
        </Link>
        
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="sidebar-search"
            type="text"
            placeholder="Search documents..."
            aria-label="Search documents"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border bg-background px-9 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-4">
        <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Documents ({filteredDocs?.length || 0})
        </div>
        
        {isLoading ? (
          <div className="space-y-2 px-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : filteredDocs?.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            {search ? 'No documents match your search' : 'No documents yet'}
          </div>
        ) : (
          <nav className="space-y-1">
            {filteredDocs?.map((doc) => {
              const isActive = pathname === `/dashboard/documents/${doc.id}`
              return (
                <Link key={doc.id} href={`/dashboard/documents/${doc.id}`}>
                  <motion.div
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    className={cn(
                      'group relative flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted text-foreground'
                    )}
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted group-hover:bg-background">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate text-sm font-medium">
                          {doc.filename}
                        </span>
                        {getStatusIcon(doc.status)}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span>•</span>
                        <span>{formatDate(doc.created_at)}</span>
                      </div>
                    </div>
                  </motion.div>
                </Link>
              )
            })}
          </nav>
        )}
      </div>
    </div>
  )
}
