'use client'

import Link from 'next/link'
import { useUser } from '@clerk/nextjs'
import { FileText, Sparkles, Shield, Zap } from 'lucide-react'
import { useAuthModal } from '@/components/auth/AuthModalContext'

export default function LandingPage() {
  const { isSignedIn, isLoaded } = useUser()
  const { openSignIn, openSignUp } = useAuthModal()

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2 font-semibold text-xl">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <FileText className="h-5 w-5" />
            </div>
            <span>paper</span>
          </div>
          
          <nav className="flex items-center gap-4">
            {isLoaded && isSignedIn ? (
              <Link
                href="/dashboard"
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Open App
              </Link>
            ) : (
              <>
                <button
                  onClick={openSignIn}
                  className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Sign in
                </button>
                <button
                  onClick={openSignUp}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  Get Started
                </button>
              </>
            )}
          </nav>
        </div>
      </header>

      <main>
        <section className="container mx-auto px-4 py-24 text-center">
          <div className="mx-auto max-w-3xl space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-1.5 text-sm">
              <Sparkles className="h-4 w-4 text-primary" />
              <span>AI-Powered Document Intelligence</span>
            </div>
            
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
              Understand your documents
              <span className="block text-primary">in seconds</span>
            </h1>
            
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
              Upload PDFs, ask questions, and get accurate answers with citations. 
              Paper uses advanced AI to analyze your documents while keeping your data secure.
            </p>
            
            <div className="flex items-center justify-center gap-4 pt-4">
              {isLoaded && isSignedIn ? (
                <Link
                  href="/dashboard"
                  className="rounded-xl bg-primary px-8 py-3 text-base font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  Open Dashboard
                </Link>
              ) : (
                <button
                  onClick={openSignUp}
                  className="rounded-xl bg-primary px-8 py-3 text-base font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  Start Free
                </button>
              )}
            </div>
          </div>
        </section>

        <section className="container mx-auto px-4 py-16">
          <div className="grid gap-8 md:grid-cols-3">
            <div className="rounded-2xl border bg-card p-6 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <Zap className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">Instant Answers</h3>
              <p className="text-sm text-muted-foreground">
                Ask questions in natural language and get accurate answers with page citations.
              </p>
            </div>
            
            <div className="rounded-2xl border bg-card p-6 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <FileText className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">Multi-Document</h3>
              <p className="text-sm text-muted-foreground">
                Query across multiple documents at once and compare information seamlessly.
              </p>
            </div>
            
            <div className="rounded-2xl border bg-card p-6 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">Trustworthy</h3>
              <p className="text-sm text-muted-foreground">
                Every answer includes citations. No hallucinations, only verified information.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          © 2025 Paper. Built with care.
        </div>
      </footer>
    </div>
  )
}
