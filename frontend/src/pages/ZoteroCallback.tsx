import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function ZoteroCallbackPage() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [message, setMessage] = useState('Processing Zotero authorization...')

  useEffect(() => {
    const handleCallback = async () => {
      const oauthToken = searchParams.get('oauth_token')
      const oauthVerifier = searchParams.get('oauth_verifier')
      const state = localStorage.getItem('zotero_oauth_state')

      if (!oauthToken || !oauthVerifier) {
        setStatus('error')
        setMessage('Missing OAuth parameters. Please try connecting again.')
        return
      }

      if (!state) {
        setStatus('error')
        setMessage('OAuth state expired. Please try connecting again.')
        return
      }

      try {
        // URL-encode all parameters to handle special characters
        const params = new URLSearchParams({
          oauth_token: oauthToken,
          oauth_verifier: oauthVerifier,
          state: state,
        })
        const response = await fetch(
          `${API_BASE}/api/zotero/oauth/callback?${params.toString()}`
        )

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Failed to complete authorization')
        }

        const data = await response.json()

        // Clear the state
        localStorage.removeItem('zotero_oauth_state')

        setStatus('success')
        setMessage(`Successfully connected as ${data.username || 'Zotero user'}!`)

        // Notify the opener window
        if (window.opener) {
          window.opener.postMessage(
            {
              type: 'ZOTERO_OAUTH_SUCCESS',
              zoteroUserId: data.zotero_user_id,
              username: data.username,
            },
            window.location.origin
          )

          // Close the popup after a brief delay
          setTimeout(() => {
            window.close()
          }, 1500)
        }
      } catch (err) {
        console.error('Zotero OAuth callback error:', err)
        setStatus('error')
        setMessage(err instanceof Error ? err.message : 'Failed to connect to Zotero')
      }
    }

    handleCallback()
  }, [searchParams])

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full mx-4 text-center">
        <div className="mb-6">
          <svg viewBox="0 0 32 32" className="w-16 h-16 mx-auto">
            <rect width="32" height="32" rx="4" fill="#CC2936" />
            <text
              x="16"
              y="22"
              textAnchor="middle"
              fill="white"
              fontSize="16"
              fontWeight="bold"
              fontFamily="serif"
            >
              Z
            </text>
          </svg>
        </div>

        {status === 'processing' && (
          <>
            <div className="w-8 h-8 border-4 border-gray-200 border-t-red-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600">{message}</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg
                className="w-6 h-6 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <p className="text-gray-800 font-medium">{message}</p>
            <p className="text-gray-500 text-sm mt-2">This window will close automatically...</p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg
                className="w-6 h-6 text-red-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <p className="text-red-600 font-medium">{message}</p>
            <button
              onClick={() => window.close()}
              className="mt-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 transition-colors"
            >
              Close Window
            </button>
          </>
        )}
      </div>
    </main>
  )
}
