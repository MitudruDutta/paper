'use client'

import { useUser, useClerk } from '@clerk/nextjs'
import { useState, useRef, useEffect, useId } from 'react'
import { LogOut, Settings, User } from 'lucide-react'
import Image from 'next/image'

export function UserMenu() {
  const { user } = useUser()
  const { signOut } = useClerk()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const menuId = useId()

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  if (!user) return null

  const initials = user.firstName?.[0] || user.emailAddresses[0]?.emailAddress[0] || '?'

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
      >
        {user.imageUrl ? (
          <Image src={user.imageUrl} alt={user.firstName || 'User avatar'} width={32} height={32} className="rounded-full" />
        ) : (
          initials.toUpperCase()
        )}
      </button>

      {open && (
        <div id={menuId} role="menu" aria-label="User menu" className="absolute right-0 top-full mt-2 w-56 rounded-lg border bg-card shadow-lg z-50">
          <div className="p-3 border-b">
            <p className="font-medium text-sm truncate">
              {user.firstName || 'User'}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {user.emailAddresses[0]?.emailAddress}
            </p>
          </div>

          <div className="p-1">
            <button
              role="menuitem"
              onClick={() => signOut({ redirectUrl: '/' })}
              className="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
