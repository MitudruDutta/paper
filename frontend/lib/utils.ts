import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatDate(dateString: string, locale?: string): string {
  const date = new Date(dateString)
  
  // Validate date
  if (Number.isNaN(date.getTime())) {
    return 'Invalid date'
  }
  
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  
  // Handle future dates
  if (diffMs < 0) {
    const futureDiffMs = Math.abs(diffMs)
    const futureDiffMins = Math.floor(futureDiffMs / (1000 * 60))
    const futureDiffHours = Math.floor(futureDiffMs / (1000 * 60 * 60))
    const futureDiffDays = Math.floor(futureDiffMs / (1000 * 60 * 60 * 24))
    
    if (futureDiffMins < 60) return `In ${futureDiffMins}m`
    if (futureDiffHours < 24) return `In ${futureDiffHours}h`
    if (futureDiffDays === 1) return 'Tomorrow'
    return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
  }
  
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    if (diffHours === 0) {
      const diffMins = Math.floor(diffMs / (1000 * 60))
      return diffMins <= 1 ? 'Just now' : `${diffMins}m ago`
    }
    return `${diffHours}h ago`
  }
  
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
  })
}
