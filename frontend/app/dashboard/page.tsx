'use client'

import { motion } from 'framer-motion'
import { Upload, FileText, MessageSquare, Shield } from 'lucide-react'
import { DocumentUpload } from '@/components/DocumentUpload'
import { useDocuments } from '@/lib/hooks'

export default function AppDashboard() {
  const { data: documents } = useDocuments()
  const hasDocuments = documents && documents.length > 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          {hasDocuments 
            ? 'Upload more documents or select one from the sidebar to ask questions'
            : 'Upload your first document to get started'}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <DocumentUpload />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="space-y-6"
        >
          {/* How it works */}
          <div className="rounded-2xl border bg-card p-6 space-y-4">
            <h2 className="text-lg font-semibold">How Paper Works</h2>
            
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Upload className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-medium">1. Upload</h3>
                  <p className="text-sm text-muted-foreground">
                    Drop any PDF. Paper handles both native text and scanned documents.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-medium">2. Process</h3>
                  <p className="text-sm text-muted-foreground">
                    Text, tables, and figures are extracted and indexed automatically.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <MessageSquare className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-medium">3. Ask</h3>
                  <p className="text-sm text-muted-foreground">
                    Ask questions naturally and get answers with page citations.
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t">
              <div className="flex items-start gap-3 text-sm">
                <Shield className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                <p className="text-muted-foreground">
                  Every answer is grounded in your document. Paper refuses to guess—if it can&apos;t find the answer, it will tell you.
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
