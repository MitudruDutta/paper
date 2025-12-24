'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Loader2, MessageSquare, AlertCircle, RefreshCw } from 'lucide-react'
import { api, ChatMessage, ApiError } from '../lib/api'
import { AnswerCard } from './AnswerCard'
import { cn } from '../lib/utils'

interface ChatPanelProps {
  documentIds: string[]
}

interface MessageWithId extends ChatMessage {
  id: string
}

export function ChatPanel({ documentIds }: ChatPanelProps) {
  const [messages, setMessages] = useState<MessageWithId[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const messageIdCounterRef = useRef(0)

  const generateMessageId = (): string => {
    return `msg-${Date.now()}-${++messageIdCounterRef.current}`
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const question = input.trim()
    setInput('')
    setError(null)

    const userMessage: MessageWithId = { id: generateMessageId(), role: 'user', content: question }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await api.askQuestion(question, documentIds, conversationId)
      
      const assistantMessage: MessageWithId = {
        id: generateMessageId(),
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
        confidence: response.confidence,
      }
      
      setMessages((prev) => [...prev, assistantMessage])
      setConversationId(response.conversation_id)
    } catch (err) {
      const errorMessage = err instanceof ApiError 
        ? err.message 
        : 'Something went wrong. Please try again.'
      
      setMessages((prev) => [
        ...prev,
        { id: generateMessageId(), role: 'assistant', content: errorMessage, isError: true },
      ])
      setError(errorMessage)
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleRetry = () => {
    // Find the index of the last user message
    let lastUserIndex = -1
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        lastUserIndex = i
        break
      }
    }
    
    if (lastUserIndex >= 0) {
      const lastUserMessage = messages[lastUserIndex]
      // Remove all messages after the last user message
      setMessages(prev => prev.slice(0, lastUserIndex))
      setInput(lastUserMessage.content)
      setError(null)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="flex flex-col h-[600px] rounded-2xl border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b bg-muted/30">
        <MessageSquare className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">Ask Questions</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 mb-4">
              <MessageSquare className="h-6 w-6 text-primary" />
            </div>
            <h3 className="font-medium">Ask a question</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-xs">
              Ask anything about this document. Paper will find relevant sections and cite its sources.
            </p>
            <div className="mt-4 space-y-2">
              <p className="text-xs text-muted-foreground">Try asking:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {['What is this about?', 'Key findings?', 'Any statistics?'].map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    className="text-xs px-3 py-1.5 rounded-full bg-muted hover:bg-muted/80 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className={cn(
                  'flex',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                {message.role === 'user' ? (
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary text-primary-foreground px-4 py-2.5">
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  </div>
                ) : (
                  <div className="max-w-[95%] w-full">
                    <AnswerCard
                      content={message.content}
                      sources={message.sources}
                      confidence={message.confidence}
                      isError={message.isError}
                    />
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        )}

        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-muted-foreground"
          >
            <div className="flex gap-1">
              <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:-0.3s]" />
              <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce [animation-delay:-0.15s]" />
              <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce" />
            </div>
            <span className="text-sm">Thinking...</span>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error retry */}
      {error && !isLoading && (
        <div className="px-4 pb-2">
          <button
            onClick={handleRetry}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry last question
          </button>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t bg-muted/30">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question..."
              disabled={isLoading}
              rows={1}
              className="w-full resize-none rounded-xl border bg-background px-4 py-3 pr-12 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Send message"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
