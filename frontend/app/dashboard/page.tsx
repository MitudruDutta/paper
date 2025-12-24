'use client'

import { motion } from 'framer-motion'
import { Upload, FileText, MessageSquare } from 'lucide-react'
import { DocumentUpload } from '@/components/DocumentUpload'

export default function AppDashboard() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Upload documents and start asking questions
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
          className="rounded-2xl border bg-card p-6 space-y-4"
        >
          <h2 className="text-lg font-semibold">How it works</h2>
          
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Upload className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-medium">1. Upload</h3>
                <p className="text-sm text-muted-foreground">
                  Drop your PDF documents. We support native and scanned PDFs.
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
                  Extract text, index content, and analyze tables automatically.
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
                  Ask questions in natural language and get cited answers.
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
