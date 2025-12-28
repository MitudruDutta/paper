'use client'

import { useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { setAuthTokenGetter } from '@/lib/api'

export function ApiAuthProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth()

  useEffect(() => {
    setAuthTokenGetter(async () => {
      try {
        return await getToken()
      } catch {
        return null
      }
    })
  }, [getToken])

  return <>{children}</>
}
