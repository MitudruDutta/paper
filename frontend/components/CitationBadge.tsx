'use client'

import { ReactNode } from 'react'
import * as Tooltip from '@radix-ui/react-tooltip'
import { Source } from '../lib/api'
import { useUIStore } from '../lib/store'

interface CitationBadgeProps {
  source: Source
  icon?: ReactNode
}

export function CitationBadge({ source, icon }: CitationBadgeProps) {
  const { setSelectedPage } = useUIStore()

  // Backend uses 0-indexed pages, PDF viewer uses 1-indexed
  const displayPageStart = source.page_start + 1
  const displayPageEnd = source.page_end + 1

  const pageLabel = displayPageStart === displayPageEnd
    ? `Page ${displayPageStart}`
    : `Pages ${displayPageStart}-${displayPageEnd}`

  const handleClick = () => {
    // Set 1-indexed page for PDF viewer
    setSelectedPage(displayPageStart)
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            onClick={handleClick}
            className="inline-flex items-center gap-1.5 rounded-lg bg-muted px-2.5 py-1.5 text-xs font-medium hover:bg-muted/80 transition-colors focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {icon}
            <span>{pageLabel}</span>
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="z-50 rounded-lg bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg border animate-in fade-in-0 zoom-in-95"
            sideOffset={5}
          >
            <div className="space-y-1">
              <p className="font-medium">{source.document_name}</p>
              <p className="text-muted-foreground">{pageLabel}</p>
              <p className="text-muted-foreground text-[10px]">Click to jump to page</p>
            </div>
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
