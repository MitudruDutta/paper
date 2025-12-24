'use client'

import { createContext, useContext, useState, useMemo, ReactNode } from 'react'

type AuthModal = 'sign-in' | 'sign-up' | null

interface AuthModalContextType {
  modal: AuthModal
  openSignIn: () => void
  openSignUp: () => void
  close: () => void
}

const AuthModalContext = createContext<AuthModalContextType | null>(null)

export function AuthModalProvider({ children }: { children: ReactNode }) {
  const [modal, setModal] = useState<AuthModal>(null)

  const value = useMemo(() => ({
    modal,
    openSignIn: () => setModal('sign-in'),
    openSignUp: () => setModal('sign-up'),
    close: () => setModal(null),
  }), [modal])

  return (
    <AuthModalContext.Provider value={value}>
      {children}
    </AuthModalContext.Provider>
  )
}

export function useAuthModal() {
  const context = useContext(AuthModalContext)
  if (!context) throw new Error('useAuthModal must be used within AuthModalProvider')
  return context
}
