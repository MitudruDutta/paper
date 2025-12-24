'use client'

import Link from 'next/link'
import { FileText, Clock, CheckCircle, XCircle, Eye } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card'
import { Badge } from './ui/Badge'
import { useDocuments } from '../lib/hooks'
import { formatFileSize, formatDate } from '../lib/utils'
import { Document } from '../lib/api'

function getStatusIcon(status: Document['status']) {
  switch (status) {
    case 'validated':
      return <CheckCircle className="h-4 w-4 text-green-600" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-600" />
    default:
      return <Clock className="h-4 w-4 text-yellow-600" />
  }
}

function getStatusVariant(status: Document['status']) {
  switch (status) {
    case 'validated':
      return 'default' as const
    case 'failed':
      return 'destructive' as const
    default:
      return 'secondary' as const
  }
}

export function DocumentList() {
  const { data: documents, isLoading, error } = useDocuments()

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="space-y-3">
                <div className="h-4 bg-muted animate-pulse rounded w-3/4" />
                <div className="h-3 bg-muted animate-pulse rounded w-1/2" />
                <div className="h-3 bg-muted animate-pulse rounded w-1/4" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <XCircle className="mx-auto h-12 w-12 text-destructive mb-4" />
          <p className="text-lg font-medium">Failed to load documents</p>
          <p className="text-sm text-muted-foreground">Please check your connection and try again</p>
        </CardContent>
      </Card>
    )
  }

  if (!documents || documents.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-lg font-medium">No documents yet</p>
          <p className="text-sm text-muted-foreground">Upload your first PDF to get started</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {documents.map((document) => (
        <Card key={document.id} className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {document.filename}
                </CardTitle>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>{formatFileSize(document.file_size)}</span>
                  {document.page_count && <span>{document.page_count} pages</span>}
                  <span>{formatDate(document.created_at)}</span>
                </div>
              </div>
              <Badge variant={getStatusVariant(document.status)} className="flex items-center gap-1">
                {getStatusIcon(document.status)}
                {document.status}
              </Badge>
            </div>
          </CardHeader>
          
          <CardContent className="pt-0">
            {document.error_message && (
              <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                <p className="text-sm text-destructive">{document.error_message}</p>
              </div>
            )}
            
            <div className="flex justify-end">
              <Link 
                href={`/documents/${document.id}`}
                className="inline-flex items-center justify-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Eye className="h-4 w-4" />
                View Document
              </Link>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
