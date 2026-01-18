import { useEffect, useState, useCallback } from "react"
import { motion } from "framer-motion"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import TransitionLink from "@/components/TransitionLink"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

type LessonTopic = {
  id: string
  topic_name: string
  description: string
  order_index: number
  confidence: number
  is_confirmed: boolean
  mastery_level: number
  completed_at: string | null
}

type LessonProgress = {
  total_topics: number
  completed_topics: number
  average_mastery: number
  progress_percentage: number
  topics: LessonTopic[]
}

export default function LessonOverview() {
  const [progress, setProgress] = useState<LessonProgress | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const sessionId = localStorage.getItem("sessionId")
  const centralTopic = localStorage.getItem("onboarding_topic")

  const fetchProgress = useCallback(async () => {
    if (!sessionId) {
      setIsLoading(false)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/api/lesson/progress/${sessionId}`)
      const data = await res.json()

      if (data.success) {
        setProgress({
          total_topics: data.total_topics,
          completed_topics: data.completed_topics,
          average_mastery: data.average_mastery,
          progress_percentage: data.progress_percentage,
          topics: data.topics || []
        })
      } else {
        setError(data.error || "Failed to load progress")
      }
    } catch (e) {
      setError("Failed to connect to server")
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchProgress()
  }, [fetchProgress])

  // No session - show onboarding CTA
  if (!sessionId) {
    return (
      <div className="rounded-3xl border border-peach/60 bg-white/80 p-8 shadow-float">
        <Badge>No lesson plan yet</Badge>
        <h1 className="mt-4 font-serif text-3xl text-ink">
          Create your learning path first
        </h1>
        <p className="mt-3 text-base text-muted">
          Start by building your learning path so we can generate a personalized lesson
          plan based on your background and goals.
        </p>
        <div className="mt-5">
          <Button asChild>
            <TransitionLink to="/onboarding">Build learning path</TransitionLink>
          </Button>
        </div>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-gray-200 border-t-gray-800 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading your progress...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-3xl border border-red-200 bg-red-50 p-8">
        <h1 className="font-serif text-2xl text-red-800 mb-3">Something went wrong</h1>
        <p className="text-red-600 mb-4">{error}</p>
        <Button onClick={fetchProgress}>Try Again</Button>
      </div>
    )
  }

  // No topics yet
  if (!progress || progress.total_topics === 0) {
    return (
      <div className="rounded-3xl border border-amber-200 bg-amber-50 p-8">
        <Badge className="bg-amber-100 text-amber-700">Almost there</Badge>
        <h1 className="mt-4 font-serif text-3xl text-amber-900">
          No learning topics found
        </h1>
        <p className="mt-3 text-base text-amber-700">
          Complete the onboarding process to generate your personalized learning path.
        </p>
        <div className="mt-5">
          <Button asChild>
            <TransitionLink to="/onboarding">Complete Onboarding</TransitionLink>
          </Button>
        </div>
      </div>
    )
  }

  // Find current topic (first incomplete)
  const currentTopic = progress.topics.find(t => t.is_confirmed && !t.completed_at)
  const completedCount = progress.topics.filter(t => t.completed_at).length

  return (
    <div className="space-y-8">
      {/* Header Card */}
      <div className="rounded-3xl border border-peach/60 bg-white/80 p-8 shadow-float">
        <Badge variant="accent">Your learning path</Badge>
        <h1 className="mt-4 font-serif text-3xl text-ink">
          {centralTopic || "Your Learning Journey"}
        </h1>
        
        {/* Progress Stats */}
        <div className="mt-6 grid grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 rounded-2xl">
            <p className="text-sm text-gray-500">Progress</p>
            <p className="text-2xl font-bold text-gray-800">
              {Math.round(progress.progress_percentage)}%
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-2xl">
            <p className="text-sm text-gray-500">Topics</p>
            <p className="text-2xl font-bold text-gray-800">
              {completedCount}/{progress.total_topics}
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-2xl">
            <p className="text-sm text-gray-500">Mastery</p>
            <p className="text-2xl font-bold text-gray-800">
              {Math.round(progress.average_mastery * 100)}%
            </p>
          </div>
        </div>

        {/* Overall Progress Bar */}
        <div className="mt-6">
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-green-400 to-green-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress.progress_percentage}%` }}
              transition={{ duration: 0.5, delay: 0.2 }}
            />
          </div>
        </div>

        {/* Continue Button */}
        <div className="mt-6 flex flex-wrap gap-3">
          {currentTopic ? (
            <Button asChild>
              <TransitionLink to={`/lessons/${currentTopic.id}`}>
                Continue Learning: {currentTopic.topic_name}
              </TransitionLink>
            </Button>
          ) : progress.completed_topics === progress.total_topics ? (
            <Button asChild>
              <TransitionLink to="/onboarding">Start New Learning Path</TransitionLink>
            </Button>
          ) : null}
          <Button variant="outline" asChild>
            <TransitionLink to="/onboarding">Modify Path</TransitionLink>
          </Button>
        </div>
      </div>

      {/* Topics List */}
      <div className="space-y-4">
        <h2 className="font-serif text-xl text-gray-800 px-2">Learning Topics</h2>
        
        <div className="space-y-3">
          {progress.topics.filter(t => t.is_confirmed).map((topic, index) => {
            const isComplete = !!topic.completed_at
            const isCurrent = currentTopic?.id === topic.id
            
            return (
              <motion.div
                key={topic.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <TransitionLink
                  to={`/lessons/${topic.id}`}
                  className={`
                    block p-5 rounded-2xl border transition-all
                    ${isComplete
                      ? 'bg-green-50 border-green-200'
                      : isCurrent
                        ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-200 ring-offset-2'
                        : 'bg-white border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <div className="flex items-start gap-4">
                    {/* Status Icon */}
                    <div className={`
                      w-10 h-10 rounded-full flex items-center justify-center shrink-0
                      ${isComplete
                        ? 'bg-green-500'
                        : isCurrent
                          ? 'bg-blue-500'
                          : 'bg-gray-200'
                      }
                    `}>
                      {isComplete ? (
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <span className={`text-sm font-bold ${isCurrent ? 'text-white' : 'text-gray-500'}`}>
                          {index + 1}
                        </span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-gray-800">{topic.topic_name}</h3>
                        {isCurrent && (
                          <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
                            Current
                          </span>
                        )}
                        {topic.confidence < 0.7 && !isComplete && (
                          <span className="px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded-full">
                            Optional
                          </span>
                        )}
                      </div>
                      {topic.description && (
                        <p className="text-sm text-gray-500 line-clamp-2">{topic.description}</p>
                      )}
                      
                      {/* Mastery Bar */}
                      <div className="mt-3 flex items-center gap-3">
                        <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              isComplete ? 'bg-green-400' : 'bg-blue-400'
                            }`}
                            style={{ width: `${topic.mastery_level * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400">
                          {Math.round(topic.mastery_level * 100)}%
                        </span>
                      </div>
                    </div>

                    {/* Arrow */}
                    <svg
                      className="w-5 h-5 text-gray-400 shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </TransitionLink>
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
