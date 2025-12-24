'use client'

import { HelpCircle } from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'

interface ConfidenceTooltipProps {
  confidence: number
  className?: string
}

export function ConfidenceTooltip({ confidence, className }: ConfidenceTooltipProps) {
  const percentage = Math.round(confidence * 100)

  const getExplanation = () => {
    if (percentage >= 70) {
      return {
        level: 'High',
        meaning: 'Well-supported by multiple relevant sections.',
        advice: 'Verify important facts by checking citations.',
      }
    }
    if (percentage >= 40) {
      return {
        level: 'Medium',
        meaning: 'Based on relevant content, but coverage may be limited.',
        advice: 'Check cited pages for full context.',
      }
    }
    return {
      level: 'Low',
      meaning: 'Limited relevant content found.',
      advice: 'Verify carefully or rephrase your question.',
    }
  }

  const { level, meaning, advice } = getExplanation()

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            className={`text-muted-foreground hover:text-foreground transition-colors ${className}`}
            aria-label="What does confidence mean?"
          >
            <HelpCircle className="h-4 w-4" />
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="z-50 w-64 rounded-lg bg-popover border p-3 text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95"
            sideOffset={5}
            side="top"
            align="end"
            collisionPadding={8}
          >
            <div className="space-y-2 text-xs">
              <p className="font-semibold">Confidence: {level}</p>
              <p className="text-muted-foreground">{meaning}</p>
              <p className="text-muted-foreground">
                <span className="font-medium">Tip:</span> {advice}
              </p>
            </div>
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
