import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { PageLoadingOverlay, getContentTypeFromRoute, type ContentType } from '../components/LoadingSpinner'

interface TransitionContextType {
  isLoading: boolean
  startTransition: (callback: () => void, contentType?: ContentType) => void
  navigateWithTransition: (to: string, contentType?: ContentType) => void
}

const TransitionContext = createContext<TransitionContextType | undefined>(undefined)

export function useTransition() {
  const context = useContext(TransitionContext)
  if (!context) {
    throw new Error('useTransition must be used within a TransitionProvider')
  }
  return context
}

interface TransitionProviderProps {
  children: ReactNode
  minimumLoadingTime?: number
}

export function TransitionProvider({
  children,
  minimumLoadingTime = 800
}: TransitionProviderProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null)
  const [currentContentType, setCurrentContentType] = useState<ContentType>('lesson')
  const location = useLocation()
  const navigate = useNavigate()

  // Handle route changes
  useEffect(() => {
    if (pendingNavigation && pendingNavigation !== location.pathname) {
      // Navigation hasn't completed yet, keep loading
      return
    }

    if (pendingNavigation === location.pathname) {
      // Navigation completed, wait minimum time then hide loader
      const timer = setTimeout(() => {
        setIsLoading(false)
        setPendingNavigation(null)
      }, minimumLoadingTime)

      return () => clearTimeout(timer)
    }
  }, [location.pathname, pendingNavigation, minimumLoadingTime])

  const startTransition = useCallback((callback: () => void, contentType?: ContentType) => {
    setCurrentContentType(contentType || 'lesson')
    setIsLoading(true)
    // Small delay to ensure loading state is visible
    requestAnimationFrame(() => {
      callback()
    })
  }, [])

  const navigateWithTransition = useCallback((to: string, contentType?: ContentType) => {
    if (to === location.pathname) return

    // Auto-detect content type from destination route if not provided
    const detectedType = contentType || getContentTypeFromRoute(to)
    setCurrentContentType(detectedType)
    setIsLoading(true)
    setPendingNavigation(to)

    // Small delay to show the loading animation before navigation
    setTimeout(() => {
      navigate(to)
    }, 100)
  }, [navigate, location.pathname])

  return (
    <TransitionContext.Provider value={{ isLoading, startTransition, navigateWithTransition }}>
      <PageLoadingOverlay isLoading={isLoading} contentType={currentContentType} />
      {children}
    </TransitionContext.Provider>
  )
}
