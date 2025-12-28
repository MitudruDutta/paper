'use client'

import { useState } from 'react'
import { useTheme } from 'next-themes'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { SignedIn } from '@clerk/nextjs'
import { UserMenu } from '@/components/auth/UserMenu'
import { ApiAuthProvider } from '@/components/providers/ApiAuthProvider'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Moon,
  Sun,
  FileText,
  Search,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react'
import { useDocuments } from '../../lib/hooks'
import { cn, formatFileSize, formatDate } from '../../lib/utils'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [search, setSearch] = useState('')
  const { theme, setTheme } = useTheme()
  const pathname = usePathname()
  const { data: documents, isLoading } = useDocuments()

  const filteredDocs = documents?.filter((doc) =>
    doc.filename.toLowerCase().includes(search.toLowerCase())
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
    <SignedIn>
      <ApiAuthProvider>
      <div className="min-h-screen bg-background">
        {/* Top Navigation */}
        <header className="fixed top-0 left-0 right-0 z-40 h-14 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex h-full items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors"
                aria-label="Toggle sidebar"
              >
                {sidebarOpen ? (
                  <PanelLeftClose className="h-5 w-5" />
                ) : (
                  <PanelLeft className="h-5 w-5" />
                )}
              </button>

              <Link href="/" className="flex items-center gap-2 font-semibold text-lg">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <FileText className="h-4 w-4" />
                </div>
                <span>paper</span>
              </Link>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="relative flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors"
                aria-label="Toggle theme"
              >
                <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              </button>

              <UserMenu />
            </div>
          </div>
        </header>

        <div className="flex pt-14">
          {/* Sidebar */}
          <AnimatePresence mode="wait">
            {sidebarOpen && (
              <motion.aside
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 280, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: 'easeInOut' }}
                className="fixed left-0 top-14 bottom-0 z-30 border-r bg-card overflow-hidden"
              >
                <div className="flex h-full w-[280px] flex-col">
                  <div className="p-4 space-y-3">
                    <Link href="/dashboard">
                      <button className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">
                        <Plus className="h-4 w-4" />
                        Upload Document
                      </button>
                    </Link>

                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search documents..."
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
                      <div className="px-4 py-8 text-center">
                        <p className="text-sm text-muted-foreground mb-1">
                          {search ? 'No documents match your search' : 'No documents yet'}
                        </p>
                        {!search && (
                          <p className="text-xs text-muted-foreground">
                            Upload a PDF to get started
                          </p>
                        )}
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
              </motion.aside>
            )}
          </AnimatePresence>

          {/* Main Content */}
          <main
            className={cn(
              'flex-1 min-h-[calc(100vh-3.5rem)] transition-all duration-200',
              sidebarOpen ? 'ml-[280px]' : 'ml-0'
            )}
          >
            <div className="container max-w-7xl mx-auto p-6">
              {children}
            </div>
          </main>
        </div>
      </div>
      </ApiAuthProvider>
    </SignedIn>
  )
}
