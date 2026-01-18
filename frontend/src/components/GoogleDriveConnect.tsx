import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { supabase, signInWithGoogle, getGoogleSession } from '@/lib/supabase'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface GoogleDriveConnectProps {
  userId: number
  sessionId: string
  onConnect?: (connected: boolean) => void
  onDocumentsSelected?: (docs: GoogleDoc[]) => void
}

export interface GoogleDoc {
  id: string
  title: string
  url: string
  mimeType: string
  relevanceScore?: number
  content?: string  // Document content for top 3
}

export default function GoogleDriveConnect({
  userId,
  sessionId,
  onConnect,
  onDocumentsSelected,
}: GoogleDriveConnectProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [isCheckingConnection, setIsCheckingConnection] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [isFetchingContent, setIsFetchingContent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [googleEmail, setGoogleEmail] = useState<string | null>(null)
  const [selectedDocs, setSelectedDocs] = useState<GoogleDoc[]>([])
  const hasSearchedRef = useRef(false)
  const hasProcessedOAuthRef = useRef(false)

  // Check for existing connection and handle OAuth callback
  useEffect(() => {
    // Skip if userId is not available yet
    if (!userId) {
      console.log('[GoogleDrive] Waiting for userId to be available...')
      return
    }

    // First, check if we're returning from OAuth callback (URL has access_token in hash)
    const hashParams = new URLSearchParams(window.location.hash.substring(1))
    const accessToken = hashParams.get('access_token')
    const providerToken = hashParams.get('provider_token')

    if ((accessToken || providerToken) && !hasProcessedOAuthRef.current) {
      console.log('[GoogleDrive] Detected OAuth callback with tokens in URL, userId:', userId)
      hasProcessedOAuthRef.current = true
      // We have tokens from OAuth - extract and store them
      handleOAuthCallback(hashParams)
    } else if (!hasProcessedOAuthRef.current) {
      // No OAuth callback, just check connection
      checkConnectionAndSync()
    }

    // Listen for auth state changes (OAuth callback via Supabase)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('[GoogleDrive] Auth state change:', event, 'provider_token:', !!session?.provider_token)
        if (event === 'SIGNED_IN' && session?.provider_token && userId && !hasProcessedOAuthRef.current) {
          hasProcessedOAuthRef.current = true
          // User signed in with Google, store the tokens
          await storeGoogleTokens(session)
        }
      }
    )

    return () => subscription.unsubscribe()
  }, [userId, sessionId])

  // Handle OAuth callback - extract tokens from URL and store them
  const handleOAuthCallback = async (hashParams: URLSearchParams) => {
    try {
      console.log('[GoogleDrive] Processing OAuth callback...')

      // The provider_token might be in hash OR in the session
      let providerToken = hashParams.get('provider_token')

      // Get user info from Supabase session - this is where provider_token often lives
      const { data: { session } } = await supabase.auth.getSession()
      console.log('[GoogleDrive] Session retrieved, provider_token in session:', !!session?.provider_token)

      // If provider_token not in hash, try to get it from session
      if (!providerToken && session?.provider_token) {
        providerToken = session.provider_token
        console.log('[GoogleDrive] Using provider_token from session')
      }

      if (providerToken && userId) {
        console.log('[GoogleDrive] Storing provider token from OAuth callback')

        // Store tokens in backend
        const response = await fetch(`${API_BASE}/api/google-drive/connect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            access_token: providerToken,
            refresh_token: hashParams.get('refresh_token') || session?.provider_refresh_token,
            google_email: session?.user?.email || '',
            expires_at: session?.expires_at,
          }),
        })

        if (response.ok) {
          console.log('[GoogleDrive] Tokens stored successfully from callback')
          setIsConnected(true)
          setGoogleEmail(session?.user?.email || null)
          onConnect?.(true)
          setIsCheckingConnection(false)

          // Clear the hash to avoid re-processing
          window.history.replaceState(null, '', window.location.pathname + window.location.search)

          // Auto-search for documents
          if (!hasSearchedRef.current && sessionId) {
            hasSearchedRef.current = true
            handleSearchAndFetchTop3()
          }
        } else {
          console.error('[GoogleDrive] Failed to store tokens:', await response.text())
          setIsCheckingConnection(false)
        }
      } else if (!providerToken) {
        console.log('[GoogleDrive] No provider token found in hash or session')
        // Clear hash and fall back to normal connection check
        window.history.replaceState(null, '', window.location.pathname + window.location.search)
        setIsCheckingConnection(false)
        checkConnectionAndSync()
      } else {
        console.log('[GoogleDrive] No userId available yet, will retry when ready')
        setIsCheckingConnection(false)
      }
    } catch (err) {
      console.error('[GoogleDrive] OAuth callback error:', err)
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
      setIsCheckingConnection(false)
    }
  }

  // Auto-search for documents when connected
  useEffect(() => {
    if (isConnected && sessionId && !hasSearchedRef.current && selectedDocs.length === 0 && !isSearching) {
      hasSearchedRef.current = true
      handleSearchAndFetchTop3()
    }
  }, [isConnected, sessionId])

  const checkConnectionAndSync = async () => {
    try {
      // First check backend for existing connection (most reliable)
      const statusResponse = await fetch(`${API_BASE}/api/google-drive/status/${userId}`)
      if (statusResponse.ok) {
        const statusData = await statusResponse.json()
        if (statusData.connected) {
          console.log('[GoogleDrive] Already connected via backend:', statusData.email)
          setIsConnected(true)
          setGoogleEmail(statusData.email || null)
          onConnect?.(true)
          setIsCheckingConnection(false)
          return // Already connected, will auto-search via useEffect
        }
      }

      // Then check Supabase session for fresh provider token
      const session = await getGoogleSession()
      if (session?.provider_token) {
        console.log('[GoogleDrive] Found Supabase session with provider token')
        // Store tokens in backend
        await storeGoogleTokens(session)
      }
    } catch (err) {
      console.error('Error checking connection:', err)
    } finally {
      setIsCheckingConnection(false)
    }
  }

  const storeGoogleTokens = async (session: any) => {
    try {
      console.log('[GoogleDrive] Storing tokens for:', session.user?.email)
      const response = await fetch(`${API_BASE}/api/google-drive/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          access_token: session.provider_token,
          refresh_token: session.provider_refresh_token,
          google_email: session.user?.email,
          expires_at: session.expires_at,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to store Google tokens')
      }

      console.log('[GoogleDrive] Tokens stored successfully')
      setIsConnected(true)
      setGoogleEmail(session.user?.email || null)
      onConnect?.(true)

      // Auto-search after successful connection
      if (!hasSearchedRef.current && sessionId) {
        hasSearchedRef.current = true
        handleSearchAndFetchTop3()
      }
    } catch (err) {
      console.error('Error storing tokens:', err)
      setError('Failed to save Google connection')
    }
  }

  const handleConnect = async () => {
    setIsLoading(true)
    setError(null)

    try {
      await signInWithGoogle()
      // OAuth redirect will happen, callback handled by onAuthStateChange
    } catch (err) {
      setError('Failed to connect with Google')
      setIsLoading(false)
    }
  }

  // Search for relevant docs and fetch content for top 3
  const handleSearchAndFetchTop3 = async () => {
    console.log('[GoogleDrive] Starting search and fetch top 3...')
    setIsSearching(true)
    setError(null)

    try {
      // Step 1: Search for relevant documents using Claude (uses token from backend)
      console.log('[GoogleDrive] Calling search-relevant-docs API...')
      const searchResponse = await fetch(`${API_BASE}/api/google-drive/search-relevant-docs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          session_id: sessionId,
        }),
      })

      if (!searchResponse.ok) {
        const errorText = await searchResponse.text()
        console.error('[GoogleDrive] Search failed:', errorText)
        throw new Error('Failed to search documents')
      }

      const searchData = await searchResponse.json()
      const documents = searchData.documents || []
      console.log(`[GoogleDrive] Found ${documents.length} relevant documents`)

      if (documents.length === 0) {
        setSelectedDocs([])
        onDocumentsSelected?.([])
        return
      }

      // Step 2: Fetch content for top 3 documents (backend uses stored token)
      setIsFetchingContent(true)
      const top3Docs = documents.slice(0, 3)
      console.log(`[GoogleDrive] Fetching content for top ${top3Docs.length} docs...`)

      // Fetch content for each of the top 3 docs - backend will use stored access token
      const docsWithContent = await Promise.all(
        top3Docs.map(async (doc: GoogleDoc) => {
          try {
            const contentResponse = await fetch(`${API_BASE}/api/google-drive/fetch-doc-content`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                user_id: userId,
                doc_id: doc.id,
                mime_type: doc.mimeType,
                // No access_token - backend will fetch from stored connection
              }),
            })

            if (contentResponse.ok) {
              const contentData = await contentResponse.json()
              console.log(`[GoogleDrive] Fetched content for: ${doc.title} (${contentData.content?.length || 0} chars)`)
              return { ...doc, content: contentData.content }
            } else {
              console.error(`[GoogleDrive] Failed to fetch content for ${doc.title}:`, await contentResponse.text())
            }
          } catch (err) {
            console.error(`[GoogleDrive] Error fetching content for ${doc.title}:`, err)
          }
          return doc
        })
      )

      console.log(`[GoogleDrive] Completed. ${docsWithContent.filter(d => d.content).length} docs have content`)
      setSelectedDocs(docsWithContent)
      onDocumentsSelected?.(docsWithContent)
    } catch (err) {
      console.error('[GoogleDrive] Error in search and fetch:', err)
      setError('Failed to search Google Drive')
    } finally {
      setIsSearching(false)
      setIsFetchingContent(false)
    }
  }

  const handleSearchDocuments = async () => {
    if (!isConnected) return
    hasSearchedRef.current = true
    await handleSearchAndFetchTop3()
  }

  const handleDisconnect = async () => {
    try {
      await fetch(`${API_BASE}/api/google-drive/disconnect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      })

      setIsConnected(false)
      setGoogleEmail(null)
      setSelectedDocs([])
      hasSearchedRef.current = false  // Reset so it searches again on reconnect
      onConnect?.(false)
      onDocumentsSelected?.([])
    } catch (err) {
      setError('Failed to disconnect')
    }
  }

  // Show loading while checking connection status
  if (isCheckingConnection) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full"
      >
        <div className="flex items-center gap-4 p-4 rounded-xl border border-gray-200 bg-gray-50">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-6 h-6 border-2 border-gray-300 border-t-gray-600 rounded-full"
          />
          <div className="text-sm text-gray-600">Checking Google Drive connection...</div>
        </div>
      </motion.div>
    )
  }

  if (!isConnected) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full"
      >
        <button
          onClick={handleConnect}
          disabled={isLoading}
          className="w-full flex items-center gap-4 p-4 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
        >
          <div className="w-8 h-8 flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-6 h-6">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
          </div>
          <div className="flex-1">
            <div className="font-medium text-gray-800">
              {isLoading ? 'Connecting...' : 'Connect Google Drive'}
            </div>
            <div className="text-sm text-gray-500">
              Import relevant documents automatically
            </div>
          </div>
        </button>

        {error && (
          <p className="text-sm text-red-500 mt-2">{error}</p>
        )}
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full space-y-3"
    >
      {/* Connected status with checkmark */}
      <div className="flex items-center gap-3 p-4 rounded-xl bg-green-50 border border-green-200">
        <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-gray-800">Google Drive Connected</div>
          {googleEmail && (
            <div className="text-xs text-gray-500">{googleEmail}</div>
          )}
        </div>
        <button
          onClick={handleDisconnect}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          Disconnect
        </button>
      </div>

      {/* Loading state while searching/fetching */}
      {(isSearching || isFetchingContent) && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-blue-50 border border-blue-200">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-5 h-5 border-2 border-blue-300 border-t-blue-600 rounded-full"
          />
          <div className="flex-1">
            <div className="text-sm font-medium text-blue-800">
              {isFetchingContent ? 'Fetching document contents...' : 'Finding relevant documents with AI...'}
            </div>
            <div className="text-xs text-blue-600">
              {isFetchingContent ? 'Downloading top 3 documents' : 'Analyzing your Google Drive'}
            </div>
          </div>
        </div>
      )}

      {/* Search button - only show if not already searching and no docs found yet */}
      {!isSearching && !isFetchingContent && selectedDocs.length === 0 && (
        <Button
          onClick={handleSearchDocuments}
          disabled={isSearching}
          className="w-full bg-blue-600 hover:bg-blue-700"
        >
          Find Relevant Documents with AI
        </Button>
      )}

      {/* Selected documents with content status */}
      {selectedDocs.length > 0 && !isSearching && !isFetchingContent && (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          <div className="text-sm font-medium text-gray-700">
            Top {selectedDocs.length} relevant documents:
          </div>
          {selectedDocs.map((doc) => (
            <div
              key={doc.id}
              className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200"
            >
              <span className="text-sm mt-0.5">{doc.content ? '✅' : '📄'}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-700 truncate font-medium">{doc.title}</div>
                <div className="flex items-center gap-2 mt-1">
                  {doc.relevanceScore !== undefined && (
                    <span className="text-xs text-gray-500">
                      {Math.round(doc.relevanceScore * 100)}% relevant
                    </span>
                  )}
                  {doc.content && (
                    <span className="text-xs text-green-600 font-medium">
                      Content fetched
                    </span>
                  )}
                </div>
                {doc.content && (
                  <div className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {doc.content.substring(0, 150)}...
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Refresh button if docs already loaded */}
      {selectedDocs.length > 0 && !isSearching && !isFetchingContent && (
        <Button
          onClick={handleSearchDocuments}
          variant="outline"
          className="w-full"
        >
          Refresh Documents
        </Button>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </motion.div>
  )
}
