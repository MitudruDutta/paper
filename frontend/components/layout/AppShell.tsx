'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sidebar } from './Sidebar'
import { TopNav } from './TopNav'
import { cn } from '../../lib/utils'

// Shared constant for TopNav height
export const TOP_NAV_HEIGHT = '3.5rem'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  // Initialize with stable server-safe value
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Set correct state after hydration and sync with screen size changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 768px)')
    setSidebarOpen(mediaQuery.matches)
    
    const handler = (e: MediaQueryListEvent) => setSidebarOpen(e.matches)
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  return (
    <div className="min-h-screen bg-background">
      <TopNav onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
      
      <div className="flex" style={{ paddingTop: TOP_NAV_HEIGHT }}>
        <AnimatePresence mode="wait">
          {sidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 280, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className="fixed left-0 bottom-0 z-30 border-r bg-card overflow-hidden"
              style={{ top: TOP_NAV_HEIGHT }}
            >
              <Sidebar />
            </motion.aside>
          )}
        </AnimatePresence>
        
        <main
          className={cn(
            'flex-1 transition-[margin] duration-200',
            sidebarOpen ? 'ml-[280px]' : 'ml-0'
          )}
          style={{ minHeight: `calc(100vh - ${TOP_NAV_HEIGHT})` }}
        >
          <div className="container max-w-7xl mx-auto p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
