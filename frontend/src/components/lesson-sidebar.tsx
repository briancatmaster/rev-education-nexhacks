import { useEffect, useState, useCallback } from "react"
import { motion } from "framer-motion"

import { Badge } from "@/components/ui/badge"
import TransitionLink from "@/components/TransitionLink"
import { getLessonProgress, syncProgressFromServer, needsSync } from "@/lib/progress-sync"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

type LessonTopic = {
  id: string
  topic_name: string
  description: string
  order_index: number
  mastery_level: number
  completed_at: string | null
  is_confirmed: boolean
}

export default function LessonSidebar({ compact = false }: { compact?: boolean }) {
  const [topics, setTopics] = useState<LessonTopic[]>([])
  const [isLoading, setIsLoading] = useState(true)
  
  const sessionId = localStorage.getItem("sessionId")
  const centralTopic = localStorage.getItem("onboarding_topic")

  const fetchTopics = useCallback(async () => {
    if (!sessionId) {
      setIsLoading(false)
      return
    }

    // Try localStorage first
    const cached = getLessonProgress()
    if (cached?.topics) {
      setTopics(cached.topics as LessonTopic[])
      setIsLoading(false)
    }

    // Sync from server if needed
    if (needsSync()) {
      const progress = await syncProgressFromServer(sessionId)
      if (progress?.topics) {
        setTopics(progress.topics as LessonTopic[])
      }
    }
    
    setIsLoading(false)
  }, [sessionId])

  useEffect(() => {
    fetchTopics()
  }, [fetchTopics])

  const containerClass = compact
    ? "w-full overflow-y-auto rounded-2xl border border-peach/60 bg-paper/80 p-4"
    : "sticky top-20 h-[calc(100vh-5rem)] w-full overflow-y-auto border-r border-peach/60 bg-paper/80 p-6"

  // No session
  if (!sessionId) {
    return (
      <aside className={containerClass}>
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cobalt">
            Learning Path
          </p>
          <h2 className="mt-2 text-lg font-semibold text-ink">No path yet</h2>
          <p className="text-xs text-muted">Complete onboarding to get started.</p>
        </div>
        <TransitionLink
          to="/onboarding"
          className="block w-full px-4 py-2 text-center text-sm bg-gray-800 text-white rounded-xl hover:bg-gray-700"
        >
          Start Onboarding
        </TransitionLink>
      </aside>
    )
  }

  // Loading
  if (isLoading) {
    return (
      <aside className={containerClass}>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-24" />
          <div className="h-6 bg-gray-200 rounded w-full" />
          <div className="space-y-2">
            <div className="h-10 bg-gray-100 rounded-xl" />
            <div className="h-10 bg-gray-100 rounded-xl" />
            <div className="h-10 bg-gray-100 rounded-xl" />
          </div>
        </div>
      </aside>
    )
  }

  // No topics
  if (topics.length === 0) {
    return (
      <aside className={containerClass}>
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cobalt">
            Learning Path
          </p>
          <h2 className="mt-2 text-lg font-semibold text-ink">No topics found</h2>
          <p className="text-xs text-muted">Complete onboarding to generate your path.</p>
        </div>
        <TransitionLink
          to="/onboarding"
          className="block w-full px-4 py-2 text-center text-sm bg-gray-800 text-white rounded-xl hover:bg-gray-700"
        >
          Go to Onboarding
        </TransitionLink>
      </aside>
    )
  }

  const confirmedTopics = topics.filter(t => t.is_confirmed)
  const completedCount = confirmedTopics.filter(t => t.completed_at).length
  const currentTopic = confirmedTopics.find(t => !t.completed_at)

  return (
    <aside className={containerClass}>
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cobalt">
          Learning Path
        </p>
        <h2 className="mt-2 text-lg font-semibold text-ink line-clamp-2">
          {centralTopic || "Your Topics"}
        </h2>
        <p className="text-xs text-muted mt-1">
          {completedCount}/{confirmedTopics.length} topics completed
        </p>
        
        {/* Progress bar */}
        <div className="mt-3 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-green-500 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${(completedCount / confirmedTopics.length) * 100}%` }}
          />
        </div>
      </div>

      <div className="space-y-2">
        {confirmedTopics.map((topic, index) => {
          const isComplete = !!topic.completed_at
          const isCurrent = currentTopic?.id === topic.id

          return (
            <TransitionLink
              key={topic.id}
              to={`/lessons/${topic.id}`}
              className={`
                flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition
                ${isComplete
                  ? 'border-green-200 bg-green-50'
                  : isCurrent
                    ? 'border-blue-300 bg-blue-50 ring-1 ring-blue-200'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }
              `}
            >
              {/* Status indicator */}
              <div className={`
                w-6 h-6 rounded-full flex items-center justify-center shrink-0
                ${isComplete
                  ? 'bg-green-500'
                  : isCurrent
                    ? 'bg-blue-500'
                    : 'bg-gray-200'
                }
              `}>
                {isComplete ? (
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <span className={`text-xs font-bold ${isCurrent ? 'text-white' : 'text-gray-500'}`}>
                    {index + 1}
                  </span>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <span className={`block truncate ${isComplete ? 'text-green-800' : 'text-gray-800'}`}>
                  {topic.topic_name}
                </span>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isComplete ? 'bg-green-400' : 'bg-blue-400'}`}
                      style={{ width: `${topic.mastery_level * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400">
                    {Math.round(topic.mastery_level * 100)}%
                  </span>
                </div>
              </div>

              {isCurrent && (
                <Badge className="bg-blue-100 text-blue-700 text-xs">
                  Current
                </Badge>
              )}
            </TransitionLink>
          )
        })}
      </div>

      <div className="mt-6 pt-4 border-t border-gray-100">
        <TransitionLink
          to="/onboarding"
          className="block w-full px-3 py-2 text-center text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50"
        >
          Modify Learning Path
        </TransitionLink>
      </div>
    </aside>
  )
}
