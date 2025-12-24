/**
 * Security utilities for XSS prevention and content sanitization.
 */

import DOMPurify from 'dompurify'

/**
 * Sanitize HTML content to prevent XSS attacks.
 * Removes all HTML tags by default (plain text only).
 */
export function sanitizeText(content: string): string {
  return DOMPurify.sanitize(content, { ALLOWED_TAGS: [] })
}

/**
 * Sanitize HTML content while allowing safe formatting tags.
 * Use this for markdown-rendered content.
 */
export function sanitizeHtml(content: string): string {
  return DOMPurify.sanitize(content, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre'],
    ALLOWED_ATTR: [],
  })
}

/**
 * Escape HTML entities to prevent XSS in plain text contexts.
 * Uses DOMPurify with no allowed tags for consistent protection.
 */
export function escapeHtml(text: string): string {
  return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] })
}

/**
 * Sanitize a URL to prevent javascript:, data:, vbscript:, and blob: protocol attacks.
 */
export function sanitizeUrl(url: string): string {
  const trimmed = url.trim().toLowerCase()
  if (
    trimmed.startsWith('javascript:') ||
    trimmed.startsWith('data:') ||
    trimmed.startsWith('vbscript:') ||
    trimmed.startsWith('blob:')
  ) {
    return ''
  }
  return url
}
