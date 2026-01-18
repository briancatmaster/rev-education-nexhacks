import { useMemo } from 'react'
import { motion } from 'framer-motion'

// All available icons for random selection
export const allIcons = [
  '/research_beaker.png',
  '/professor_like.png',
  '/macbook_pro.png',
  '/college_campus.png',
  '/brainhere\'s_tightened.png',
  '/database_cylinder,.png',
  '/paperclip_normal.png',
  '/black_graduation.png',
]

// Content type to icon mapping
export type ContentType =
  | 'research'      // Papers, research materials
  | 'lesson'        // Lessons, teaching content
  | 'video'         // Video lectures, multimedia
  | 'problems'      // Problem sets, exercises
  | 'onboarding'    // Onboarding, setup
  | 'data'          // Data processing, loading
  | 'documents'     // Attachments, files
  | 'overview'      // Course overview, home
  | 'graduation'    // Completion, achievements
  | 'thinking'      // AI processing, generating
  | 'random'        // Random icon selection

export const contentTypeIcons: Record<ContentType, string> = {
  research: '/research_beaker.png',
  lesson: '/professor_like.png',
  video: '/macbook_pro.png',
  problems: '/college_campus.png',
  onboarding: '/brainhere\'s_tightened.png',
  data: '/database_cylinder,.png',
  documents: '/paperclip_normal.png',
  overview: '/college_campus.png',
  graduation: '/black_graduation.png',
  thinking: '/brainhere\'s_tightened.png',
  random: '/research_beaker.png', // Fallback, actual random happens in component
}

// Get a random icon
export function getRandomIcon(): string {
  return allIcons[Math.floor(Math.random() * allIcons.length)]
}

// Route to content type mapping
export function getContentTypeFromRoute(path: string): ContentType {
  if (path.includes('/onboarding')) return 'random' // Random for onboarding
  if (path.includes('/lessons/') && path.includes('video')) return 'video'
  if (path.includes('/lessons/') && path.includes('problem')) return 'problems'
  if (path.includes('/lessons/') && path.includes('reading')) return 'research'
  if (path.includes('/lessons/') && path.includes('lab')) return 'research'
  if (path.includes('/lessons')) return 'lesson'
  if (path.includes('/learn')) return 'thinking'
  if (path === '/' || path === '') return 'overview'
  return 'lesson'
}

interface LoadingSpinnerProps {
  icon?: string
  contentType?: ContentType
  size?: number
  className?: string
  random?: boolean
  isProcessing?: boolean
}

export default function LoadingSpinner({
  icon,
  contentType = 'lesson',
  size = 64,
  className = '',
  random = false,
  isProcessing = true
}: LoadingSpinnerProps) {
  // Pick random icon on mount if random mode
  const randomIcon = useMemo(() => getRandomIcon(), [])

  const iconSrc = icon || (random || contentType === 'random' ? randomIcon : contentTypeIcons[contentType])

  return (
    <div className={`flex items-center justify-center ${className}`}>
      <motion.div
        style={{ width: size, height: size }}
        animate={isProcessing ? { rotateY: 360 } : { rotateY: 0 }}
        transition={isProcessing ? {
          duration: 1.2,
          ease: "linear",
          repeat: Infinity,
        } : {
          duration: 0.3,
          ease: "easeOut"
        }}
      >
        <img
          src={iconSrc}
          alt="Loading"
          style={{
            width: size,
            height: size,
            borderRadius: 28,
            boxShadow: '0 12px 40px rgba(0, 0, 0, 0.15), 0 4px 12px rgba(0, 0, 0, 0.1)'
          }}
        />
      </motion.div>
    </div>
  )
}

// Full page loading overlay for route transitions
export function PageLoadingOverlay({
  isLoading,
  contentType = 'lesson'
}: {
  isLoading: boolean
  contentType?: ContentType
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: isLoading ? 1 : 0 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      style={{ pointerEvents: isLoading ? 'auto' : 'none' }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-hero/90 backdrop-blur-sm"
    >
      <LoadingSpinner size={120} contentType={contentType} isProcessing={isLoading} />
    </motion.div>
  )
}
