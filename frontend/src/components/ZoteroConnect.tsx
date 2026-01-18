import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ZoteroConnectProps {
  userId: number
  onConnect?: (connected: boolean) => void
  onLibraryLoaded?: (items: ZoteroItem[]) => void
  onSelectionChange?: (selectedItems: ZoteroItem[]) => void
}

export interface ZoteroItem {
  key: string
  title: string
  itemType: string
  creators?: string[]
  date?: string
  url?: string
  DOI?: string
  abstractNote?: string
}

export default function ZoteroConnect({
  userId,
  onConnect,
  onLibraryLoaded,
  onSelectionChange,
}: ZoteroConnectProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isFetchingItems, setIsFetchingItems] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [items, setItems] = useState<ZoteroItem[]>([])
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())

  // Check for existing connection on mount
  useEffect(() => {
    checkConnection()

    // Listen for OAuth callback via URL params or postMessage
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'ZOTERO_OAUTH_SUCCESS') {
        setIsConnected(true)
        setUsername(event.data.username || null)
        onConnect?.(true)
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [userId])

  const checkConnection = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/zotero/status/${userId}`)
      if (response.ok) {
        const data = await response.json()
        if (data.connected) {
          setIsConnected(true)
          setUsername(data.username || null)
          onConnect?.(true)
          // Fetch items after confirming connection
          await fetchItems()
        }
      }
    } catch (err) {
      console.error('Error checking Zotero connection:', err)
    }
  }

  const fetchItems = async () => {
    setIsFetchingItems(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/api/zotero/items/${userId}`)
      if (!response.ok) {
        throw new Error('Failed to fetch Zotero items')
      }

      const data = await response.json()
      setItems(data.items || [])
      onLibraryLoaded?.(data.items || [])
    } catch (err) {
      console.error('Error fetching Zotero items:', err)
      setError('Failed to load library items')
    } finally {
      setIsFetchingItems(false)
    }
  }

  const toggleItemSelection = (key: string) => {
    setSelectedItems(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      // Notify parent of selection change
      const selected = items.filter(item => next.has(item.key))
      onSelectionChange?.(selected)
      return next
    })
  }

  const selectAll = () => {
    const allKeys = new Set(items.map(item => item.key))
    setSelectedItems(allKeys)
    onSelectionChange?.(items)
  }

  const deselectAll = () => {
    setSelectedItems(new Set())
    onSelectionChange?.([])
  }

  const getSelectedItems = (): ZoteroItem[] => {
    return items.filter(item => selectedItems.has(item.key))
  }

  const handleConnect = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Initiate OAuth flow
      const response = await fetch(`${API_BASE}/api/zotero/oauth/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      })

      if (!response.ok) {
        throw new Error('Failed to initiate Zotero OAuth')
      }

      const data = await response.json()

      // Store state in localStorage for the callback to use (localStorage is shared across windows)
      localStorage.setItem('zotero_oauth_state', data.state)

      // Open Zotero authorization in a popup
      const width = 600
      const height = 700
      const left = window.screenX + (window.innerWidth - width) / 2
      const top = window.screenY + (window.innerHeight - height) / 2

      const popup = window.open(
        data.authorization_url,
        'Zotero Authorization',
        `width=${width},height=${height},left=${left},top=${top}`
      )

      // Poll for popup close and check connection
      const checkPopup = setInterval(async () => {
        if (!popup || popup.closed) {
          clearInterval(checkPopup)
          setIsLoading(false)
          // Check if connection was successful
          await checkConnection()
        }
      }, 500)
    } catch (err) {
      console.error('Error connecting to Zotero:', err)
      setError('Failed to connect with Zotero')
      setIsLoading(false)
    }
  }

  const handleDisconnect = async () => {
    try {
      await fetch(`${API_BASE}/api/zotero/disconnect/${userId}`, {
        method: 'DELETE',
      })

      setIsConnected(false)
      setUsername(null)
      onConnect?.(false)
    } catch (err) {
      setError('Failed to disconnect')
    }
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
            <svg viewBox="0 0 32 32" className="w-6 h-6">
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
          <div className="flex-1">
            <div className="font-medium text-gray-800">
              {isLoading ? 'Connecting...' : 'Connect Zotero'}
            </div>
            <div className="text-sm text-gray-500">
              Import papers from your library
            </div>
          </div>
        </button>

        {error && <p className="text-sm text-red-500 mt-2">{error}</p>}
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full space-y-3"
    >
      {/* Connected status */}
      <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200">
        <div className="w-8 h-8 flex items-center justify-center">
          <svg viewBox="0 0 32 32" className="w-6 h-6">
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
        <div className="flex-1">
          <div className="text-sm font-medium text-gray-800">Zotero Connected</div>
          {username && <div className="text-xs text-gray-500">{username}</div>}
        </div>
        <button
          onClick={handleDisconnect}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          Disconnect
        </button>
      </div>

      {/* Loading items */}
      {isFetchingItems && (
        <div className="flex items-center gap-2 p-3 text-sm text-gray-500">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full"
          />
          Loading library...
        </div>
      )}

      {/* Items list */}
      {!isFetchingItems && items.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">
              {selectedItems.size} of {items.length} selected
            </span>
            <div className="flex gap-2">
              <button
                onClick={selectAll}
                className="text-blue-600 hover:text-blue-700"
              >
                Select all
              </button>
              <button
                onClick={deselectAll}
                className="text-gray-500 hover:text-gray-600"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="max-h-48 overflow-y-auto space-y-1 border rounded-lg p-2">
            {items.map(item => (
              <label
                key={item.key}
                className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                  selectedItems.has(item.key)
                    ? 'bg-red-50 border border-red-200'
                    : 'hover:bg-gray-50'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedItems.has(item.key)}
                  onChange={() => toggleItemSelection(item.key)}
                  className="mt-1 rounded border-gray-300 text-red-600 focus:ring-red-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-800 truncate">{item.title}</div>
                  {item.creators && item.creators.length > 0 && (
                    <div className="text-xs text-gray-500 truncate">
                      {item.creators.slice(0, 3).join(', ')}
                      {item.creators.length > 3 && ` +${item.creators.length - 3} more`}
                    </div>
                  )}
                </div>
                <span className="text-xs text-gray-400 shrink-0">{item.itemType}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* No items */}
      {!isFetchingItems && items.length === 0 && isConnected && (
        <div className="text-sm text-gray-500 text-center py-4">
          No items found in your Zotero library
        </div>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}
    </motion.div>
  )
}
