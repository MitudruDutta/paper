'use client'

import { useEffect } from 'react'
import { X } from 'lucide-react'
import { useAuthModal } from './AuthModalContext'
import { SignInForm } from './SignInForm'
import { SignUpForm } from './SignUpForm'

export function AuthModal() {
  const { modal, close } = useAuthModal()

  useEffect(() => {
    if (modal) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [modal])

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [close])

  if (!modal) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={close}
      />
      <div className="relative bg-background rounded-2xl shadow-2xl p-8 m-4 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={close}
          className="absolute top-4 right-4 p-1 rounded-lg hover:bg-muted transition-colors"
        >
          <X className="h-5 w-5 text-muted-foreground" />
        </button>
        
        {modal === 'sign-in' ? <SignInForm /> : <SignUpForm />}
      </div>
    </div>
  )
}
