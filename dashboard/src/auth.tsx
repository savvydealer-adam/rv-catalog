import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'

interface AuthState {
  user: { email: string; name: string; picture: string } | null
  token: string | null
  loading: boolean
  signOut: () => void
}

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  loading: true,
  signOut: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

/** Wrap all fetch calls to include the auth token */
export function authFetch(token: string | null) {
  return (url: string, opts?: RequestInit) => {
    const headers: Record<string, string> = {
      ...(opts?.headers as Record<string, string> || {}),
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    return fetch(url, { ...opts, headers })
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthState['user']>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [clientId, setClientId] = useState<string | null>(null)
  const [isDev, setIsDev] = useState(false)

  // Fetch OAuth config from backend
  useEffect(() => {
    fetch('/api/auth/config')
      .then(r => r.json())
      .then(config => {
        setClientId(config.client_id)
        setIsDev(config.environment === 'development')
        if (config.environment === 'development') {
          // Dev mode: skip sign-in
          setUser({ email: 'dev@savvydealer.com', name: 'Dev User', picture: '' })
          setToken('dev')
          setLoading(false)
        }
      })
      .catch(() => setLoading(false))
  }, [])

  // Initialize Google Sign-In
  useEffect(() => {
    if (!clientId || isDev) return

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: clientId,
        callback: handleCredentialResponse,
        auto_select: true,
      })

      // Check for stored token
      const stored = sessionStorage.getItem('rv_catalog_token')
      if (stored) {
        tryToken(stored)
      } else {
        // Prompt sign-in
        window.google?.accounts.id.prompt()
        setLoading(false)
      }
    }
    document.head.appendChild(script)

    return () => {
      document.head.removeChild(script)
    }
  }, [clientId, isDev])

  const tryToken = useCallback(async (idToken: string) => {
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${idToken}` },
      })
      if (res.ok) {
        const data = await res.json()
        setUser({
          email: data.email,
          name: data.name || data.email,
          picture: data.picture || '',
        })
        setToken(idToken)
        sessionStorage.setItem('rv_catalog_token', idToken)
      } else {
        sessionStorage.removeItem('rv_catalog_token')
      }
    } catch {
      sessionStorage.removeItem('rv_catalog_token')
    }
    setLoading(false)
  }, [])

  const handleCredentialResponse = useCallback((response: { credential: string }) => {
    tryToken(response.credential)
  }, [tryToken])

  // Make handleCredentialResponse available globally for Google callback
  useEffect(() => {
    (window as any).__handleGoogleCredential = handleCredentialResponse
  }, [handleCredentialResponse])

  const signOut = useCallback(() => {
    setUser(null)
    setToken(null)
    sessionStorage.removeItem('rv_catalog_token')
    window.google?.accounts.id.disableAutoSelect()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) {
    return <SignInPage clientId={clientId} />
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

function SignInPage({ clientId }: { clientId: string | null }) {
  useEffect(() => {
    if (!clientId) return
    // Render the Google Sign-In button
    window.google?.accounts.id.renderButton(
      document.getElementById('google-signin-btn')!,
      {
        theme: 'filled_blue',
        size: 'large',
        text: 'signin_with',
        shape: 'rectangular',
        width: 300,
      }
    )
  }, [clientId])

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-10 text-center max-w-md">
        <h1 className="text-2xl font-bold text-white mb-2">RV Catalog</h1>
        <p className="text-slate-400 mb-8">Sign in with your SavvyDealer account to continue</p>
        <div id="google-signin-btn" className="flex justify-center" />
        <p className="text-xs text-slate-600 mt-6">
          Only @savvydealer.com accounts are authorized
        </p>
      </div>
    </div>
  )
}

// Type declaration for Google Identity Services
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: any) => void
          prompt: (callback?: any) => void
          renderButton: (element: HTMLElement, config: any) => void
          disableAutoSelect: () => void
        }
      }
    }
  }
}
