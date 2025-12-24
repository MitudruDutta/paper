'use client'

import { motion } from 'framer-motion'
import { cn } from '../lib/utils'

interface ConfidenceMeterProps {
  confidence: number
  className?: string
}

export function ConfidenceMeter({ confidence, className }: ConfidenceMeterProps) {
  const percentage = Math.round(confidence * 100)
  
  const getLevel = () => {
    if (percentage >= 70) return { label: 'High', color: 'bg-green-500' }
    if (percentage >= 40) return { label: 'Medium', color: 'bg-yellow-500' }
    return { label: 'Low', color: 'bg-orange-500' }
  }

  const { label, color } = getLevel()

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className={cn('h-full rounded-full', color)}
        />
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {label} ({percentage}%)
      </span>
    </div>
  )
}
