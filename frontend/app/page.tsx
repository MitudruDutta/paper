'use client'

import Link from 'next/link'
import { useUser, SignOutButton } from '@clerk/nextjs'
import { FileText, Sparkles, Shield, Zap, Search, MessageSquare, Table2, LogOut } from 'lucide-react'
import { useAuthModal } from '@/components/auth/AuthModalContext'
import { Hero } from '@/components/ui/hero'
import { Button } from '@/components/ui/Button'

export default function LandingPage() {
  const { isSignedIn, isLoaded, user } = useUser()
  const { openSignUp } = useAuthModal()

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="fixed top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold text-xl">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <FileText className="h-5 w-5" />
            </div>
            <span>paper</span>
          </Link>
          
          <nav className="flex items-center gap-4">
            <HeaderActions />
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <Hero
        title={
          <>
            Understand your documents{' '}
            <span className="text-primary">in seconds</span>
          </>
        }
        subtitle="Upload PDFs, ask questions, and get accurate answers with citations. Paper uses advanced AI to analyze your documents while keeping your data secure."
        titleClassName="text-5xl md:text-6xl lg:text-7xl font-extrabold"
        subtitleClassName="text-lg md:text-xl max-w-[600px]"
        className="pt-16"
      >
        <div className="flex gap-4 mt-8">
          {isLoaded && isSignedIn ? (
            <Button asChild>
              <Link href="/dashboard">Open Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button variant="outline" asChild>
                <Link href="#features">Learn More</Link>
              </Button>
              <Button onClick={openSignUp}>Start Free</Button>
            </>
          )}
        </div>
      </Hero>

      {/* Features Section */}
      <section id="features" className="container mx-auto px-4 py-24">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-1.5 text-sm mb-4">
            <Sparkles className="h-4 w-4 text-primary" />
            <span>Powerful Features</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to understand your documents
          </h2>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <FeatureCard
            icon={<Zap className="h-6 w-6 text-primary" />}
            title="Instant Answers"
            description="Ask questions in natural language and get accurate answers with page citations in seconds."
          />
          <FeatureCard
            icon={<FileText className="h-6 w-6 text-primary" />}
            title="Multi-Document QA"
            description="Query across multiple documents at once and compare information seamlessly."
          />
          <FeatureCard
            icon={<Shield className="h-6 w-6 text-primary" />}
            title="Zero Hallucinations"
            description="Every answer includes citations. No made-up information, only verified facts from your documents."
          />
          <FeatureCard
            icon={<Search className="h-6 w-6 text-primary" />}
            title="Semantic Search"
            description="Find relevant information using meaning, not just keywords. Powered by vector embeddings."
          />
          <FeatureCard
            icon={<Table2 className="h-6 w-6 text-primary" />}
            title="Table & Figure Analysis"
            description="Extract and query tables and figures. Perform calculations on tabular data automatically."
          />
          <FeatureCard
            icon={<MessageSquare className="h-6 w-6 text-primary" />}
            title="Conversation Memory"
            description="Ask follow-up questions naturally. Paper understands context from your conversation."
          />
        </div>
      </section>

      {/* How It Works */}
      <section className="border-t bg-muted/30 py-24">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">
              How Paper Works
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              From upload to insight in three simple steps
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3 max-w-4xl mx-auto">
            <StepCard
              step="1"
              title="Upload"
              description="Drop your PDF documents. Paper handles native text and scanned documents with OCR."
            />
            <StepCard
              step="2"
              title="Process"
              description="Documents are chunked, embedded, and indexed for semantic search automatically."
            />
            <StepCard
              step="3"
              title="Ask"
              description="Ask questions and get answers with citations. Query single or multiple documents."
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-4 py-24 text-center">
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">
          Ready to understand your documents?
        </h2>
        <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
          Start analyzing your PDFs today. No credit card required.
        </p>
        {isLoaded && isSignedIn ? (
          <Button size="lg" asChild>
            <Link href="/dashboard">Go to Dashboard</Link>
          </Button>
        ) : (
          <Button size="lg" onClick={openSignUp}>
            Get Started Free
          </Button>
        )}
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          © 2025 Paper. Built with care.
        </div>
      </footer>
    </div>
  )
}

function HeaderActions() {
  const { isSignedIn, isLoaded, user } = useUser()
  const { openSignIn, openSignUp } = useAuthModal()

  if (!isLoaded) return null

  if (isSignedIn) {
    const email = user?.primaryEmailAddress?.emailAddress
    const masked = maskEmail(email)
    return (
      <div className="flex items-center gap-3">
        <span 
          className="text-sm text-muted-foreground hidden sm:inline"
          aria-label={`Signed in as ${masked}`}
        >
          {masked}
        </span>
        <Button asChild>
          <Link href="/dashboard">Dashboard</Link>
        </Button>
        <SignOutButton>
          <Button variant="ghost" size="icon">
            <LogOut className="h-4 w-4" />
          </Button>
        </SignOutButton>
      </div>
    )
  }

  return (
    <>
      <Button variant="ghost" onClick={openSignIn}>Sign in</Button>
      <Button onClick={openSignUp}>Get Started</Button>
    </>
  )
}

/**
 * Mask email for display to reduce PII exposure.
 * e.g., "john.doe@example.com" -> "j***@example.com"
 */
function maskEmail(email: string | undefined): string {
  if (!email) return ''
  const [local, domain] = email.split('@')
  if (!domain) return '***@***'
  if (local.length <= 1) return `${local}***@${domain}`
  return `${local[0]}***@${domain}`
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="rounded-2xl border bg-card p-6 space-y-3">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
        {icon}
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

function StepCard({ step, title, description }: { step: string; title: string; description: string }) {
  return (
    <div className="text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold text-lg mx-auto mb-4">
        {step}
      </div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
