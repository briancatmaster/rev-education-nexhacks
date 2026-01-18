import { useEffect, useState, useCallback, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import "katex/dist/katex.min.css"
import { Button } from "@/components/ui/button"
import TransitionLink from "@/components/TransitionLink"
import {
  saveCurrentActivity,
  getLessonProgress,
  syncProgressFromServer,
  needsSync,
  updateTopicMastery,
  STORAGE_KEYS
} from "@/lib/progress-sync"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

// Markdown renderer component with LaTeX support
function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
        h1: ({ children }) => <h1 className="text-2xl font-bold mb-4 mt-6">{children}</h1>,
        h2: ({ children }) => <h2 className="text-xl font-bold mb-3 mt-5">{children}</h2>,
        h3: ({ children }) => <h3 className="text-lg font-semibold mb-2 mt-4">{children}</h3>,
        ul: ({ children }) => <ul className="list-disc pl-6 mb-4 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-6 mb-4 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="text-gray-700">{children}</li>,
        code: ({ className, children }) => {
          const isInline = !className
          return isInline ? (
            <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono text-pink-600">{children}</code>
          ) : (
            <code className="block p-4 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto text-sm font-mono mb-4">{children}</code>
          )
        },
        pre: ({ children }) => <pre className="mb-4">{children}</pre>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-blue-400 pl-4 italic text-gray-600 mb-4">{children}</blockquote>
        ),
        strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

type Activity = {
  id: string
  topic_id: string
  topic_name: string
  activity_type: "video" | "reading" | "problem" | "lab"
  title: string
  embed_url: string
  content?: string  // For inline markdown/text content
  source_type: string
  source_title?: string
  duration_minutes?: number
  order_index: number
  is_problem: boolean
  problem_data?: {
    problem: string
    hints: string[]
    solution: string
    answer: string
  }
}

type TopicProgress = {
  topic_name: string
  mastery_level: number
  order_index: number
}

type LessonProgress = {
  total_topics: number
  completed_topics: number
  average_mastery: number
  progress_percentage: number
}

export default function LessonDetailView() {
  const navigate = useNavigate()
  const [activity, setActivity] = useState<Activity | null>(null)
  const [topicProgress, setTopicProgress] = useState<TopicProgress | null>(null)
  const [lessonProgress, setLessonProgress] = useState<LessonProgress | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isCompleting, setIsCompleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isTopicComplete, setIsTopicComplete] = useState(false)
  const [isCourseComplete, setIsCourseComplete] = useState(false)
  
  // Problem state
  const [userAnswer, setUserAnswer] = useState("")
  const [showHints, setShowHints] = useState(false)
  const [showSolution, setShowSolution] = useState(false)
  const [currentHintIndex, setCurrentHintIndex] = useState(0)
  
  // Feedback state
  const [feedbackGiven, setFeedbackGiven] = useState<"confused" | "too_easy" | null>(null)
  
  // Embed refs to prevent reload
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [embedKey, setEmbedKey] = useState(0)

  const sessionId = localStorage.getItem("sessionId")
  const userId = localStorage.getItem("onboarding_userId")

  // Load from localStorage on mount
  useEffect(() => {
    const cached = localStorage.getItem(STORAGE_KEYS.currentActivity)
    if (cached) {
      try {
        const parsed = JSON.parse(cached)
        setActivity(parsed.activity)
        setTopicProgress(parsed.topicProgress)
      } catch (e) {
        console.error("Failed to parse cached activity:", e)
      }
    }
    
    // Try to load cached progress first
    const cachedProgress = getLessonProgress()
    if (cachedProgress) {
      setLessonProgress({
        total_topics: cachedProgress.total_topics,
        completed_topics: cachedProgress.completed_topics,
        average_mastery: cachedProgress.average_mastery,
        progress_percentage: cachedProgress.progress_percentage
      })
    }
    
    // Sync from server if needed
    if (sessionId && needsSync()) {
      syncProgressFromServer(sessionId).then(progress => {
        if (progress) {
          setLessonProgress({
            total_topics: progress.total_topics,
            completed_topics: progress.completed_topics,
            average_mastery: progress.average_mastery,
            progress_percentage: progress.progress_percentage
          })
        }
      })
    }
  }, [sessionId])

  // Fetch next activity from API
  const fetchNextActivity = useCallback(async () => {
    if (!sessionId || !userId) {
      setError("Session not found. Please complete onboarding first.")
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)
    setIsTopicComplete(false)
    setIsCourseComplete(false)

    try {
      const res = await fetch(
        `${API_BASE}/api/lesson/next-activity?session_id=${sessionId}&user_id=${userId}`
      )
      const data = await res.json()

      if (data.success) {
        if (data.is_course_complete) {
          setIsCourseComplete(true)
          setActivity(null)
          localStorage.removeItem(STORAGE_KEYS.currentActivity)
        } else if (data.is_topic_complete) {
          setIsTopicComplete(true)
          setTopicProgress(data.topic_progress)
          // Automatically fetch next topic's activity
          setTimeout(() => fetchNextActivity(), 1500)
        } else if (data.activity) {
          setActivity(data.activity)
          setTopicProgress(data.topic_progress)
          setEmbedKey(prev => prev + 1) // Force new embed
          
          // Cache to localStorage
          localStorage.setItem(STORAGE_KEYS.currentActivity, JSON.stringify({
            activity: data.activity,
            topicProgress: data.topic_progress
          }))
          
          // Also save current activity for quick access
          saveCurrentActivity({
            activity_id: data.activity.id,
            topic_id: data.activity.topic_id,
            topic_name: data.activity.topic_name,
            started_at: new Date().toISOString()
          })
          
          // Reset problem state
          setUserAnswer("")
          setShowHints(false)
          setShowSolution(false)
          setCurrentHintIndex(0)
          setFeedbackGiven(null)
        }
      } else {
        setError(data.error || "Failed to load activity")
      }
    } catch (e) {
      setError("Failed to connect to server")
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, userId])

  // Fetch lesson progress
  const fetchLessonProgress = useCallback(async () => {
    if (!sessionId) return

    try {
      const progress = await syncProgressFromServer(sessionId)
      
      if (progress) {
        setLessonProgress({
          total_topics: progress.total_topics,
          completed_topics: progress.completed_topics,
          average_mastery: progress.average_mastery,
          progress_percentage: progress.progress_percentage
        })
      }
    } catch (e) {
      console.error("Failed to fetch progress:", e)
    }
  }, [sessionId])

  // Initial fetch
  useEffect(() => {
    fetchNextActivity()
    fetchLessonProgress()
  }, [fetchNextActivity, fetchLessonProgress])

  // Complete current activity
  const handleCompleteActivity = async () => {
    if (!activity || !sessionId || !userId) return

    setIsCompleting(true)

    try {
      const res = await fetch(`${API_BASE}/api/lesson/complete-activity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_id: parseInt(userId, 10),
          activity_id: activity.id,
          user_response: activity.is_problem ? userAnswer : undefined,
          feedback: feedbackGiven
        })
      })
      const data = await res.json()

      if (data.success) {
        // Optimistic update to localStorage
        if (activity.topic_id) {
          updateTopicMastery(activity.topic_id, data.new_mastery_level, data.topic_complete)
        }
        
        // Update progress from server
        fetchLessonProgress()
        
        if (data.topic_complete) {
          setIsTopicComplete(true)
          setTopicProgress(prev => prev ? { ...prev, mastery_level: data.new_mastery_level } : null)
          setTimeout(() => fetchNextActivity(), 1500)
        } else {
          // Fetch next activity
          fetchNextActivity()
        }
      } else {
        setError(data.error || "Failed to complete activity")
      }
    } catch (e) {
      setError("Failed to save progress")
    } finally {
      setIsCompleting(false)
    }
  }

  // Skip current topic
  const handleSkipTopic = async () => {
    if (!sessionId || !userId) return

    setIsLoading(true)

    try {
      const res = await fetch(
        `${API_BASE}/api/lesson/skip-topic?session_id=${sessionId}&user_id=${userId}`,
        { method: "POST" }
      )
      const data = await res.json()

      if (data.success) {
        fetchNextActivity()
        fetchLessonProgress()
        }
      } catch (e) {
      setError("Failed to skip topic")
      } finally {
        setIsLoading(false)
      }
    }

  // Render embed based on activity type
  const renderEmbed = () => {
    if (!activity) return null

    if (activity.is_problem && activity.problem_data) {
      return (
        <div className="space-y-6">
          {/* Problem Statement */}
          <div className="p-6 bg-white rounded-2xl border border-gray-200">
            <h3 className="font-medium text-gray-800 mb-4">Problem</h3>
            <div className="text-gray-700 prose prose-gray max-w-none">
              <MarkdownContent content={activity.problem_data.problem} />
            </div>
          </div>

          {/* Answer Input */}
          <div className="p-6 bg-white rounded-2xl border border-gray-200">
            <label className="block font-medium text-gray-800 mb-3">Your Answer</label>
            <textarea
              value={userAnswer}
              onChange={(e) => setUserAnswer(e.target.value)}
              placeholder="Type your answer here... (supports LaTeX with $...$ or $$...$$)"
              rows={4}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-gray-400 resize-none font-mono text-sm"
            />
          </div>

          {/* Hints */}
          {activity.problem_data.hints && activity.problem_data.hints.length > 0 && (
            <div className="p-6 bg-amber-50 rounded-2xl border border-amber-200">
              <button
                onClick={() => setShowHints(!showHints)}
                className="flex items-center gap-2 font-medium text-amber-700"
              >
                <span>{showHints ? "Hide" : "Show"} Hints</span>
                <span className="text-sm">({activity.problem_data.hints.length} available)</span>
              </button>
              
              <AnimatePresence>
                {showHints && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="mt-4 space-y-3 overflow-hidden"
                  >
                    {activity.problem_data.hints.slice(0, currentHintIndex + 1).map((hint, i) => (
                      <div key={i} className="text-amber-800 text-sm">
                        <span className="font-medium">Hint {i + 1}:</span>{" "}
                        <MarkdownContent content={hint} />
                      </div>
                    ))}
                    {currentHintIndex < activity.problem_data.hints.length - 1 && (
                      <button
                        onClick={() => setCurrentHintIndex(prev => prev + 1)}
                        className="text-sm text-amber-600 hover:text-amber-700"
                      >
                        Show next hint →
                      </button>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Solution */}
          <div className="p-6 bg-green-50 rounded-2xl border border-green-200">
            <button
              onClick={() => setShowSolution(!showSolution)}
              className="flex items-center gap-2 font-medium text-green-700"
            >
              <span>{showSolution ? "Hide" : "Show"} Solution</span>
            </button>
            
            <AnimatePresence>
              {showSolution && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-4 overflow-hidden"
                >
                  <div className="text-green-800 text-sm prose prose-green max-w-none">
                    <MarkdownContent content={activity.problem_data.solution} />
                  </div>
                  <div className="mt-3 p-3 bg-green-100 rounded-lg">
                    <span className="font-medium text-green-700">Answer: </span>
                    <span className="text-green-800">
                      <MarkdownContent content={activity.problem_data.answer} />
                    </span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      )
    }

    if (activity.activity_type === "video" && activity.embed_url) {
      return (
        <div className="relative w-full aspect-video bg-black rounded-2xl overflow-hidden">
          <iframe
            key={embedKey}
            ref={iframeRef}
            src={activity.embed_url}
            title={activity.title}
            className="absolute inset-0 w-full h-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            loading="lazy"
          />
        </div>
      )
    }

    if (activity.activity_type === "reading") {
      // Check for inline content field first
      if (activity.content) {
        return (
          <div className="p-6 bg-white rounded-2xl border border-gray-200 max-h-[700px] overflow-y-auto">
            <div className="prose prose-gray max-w-none">
              <MarkdownContent content={activity.content} />
            </div>
          </div>
        )
      }
      
      if (!activity.embed_url) {
        return (
          <div className="p-8 bg-gray-100 rounded-2xl text-center">
            <p className="text-gray-600">No content available for this reading.</p>
          </div>
        )
      }
      
      // Check if it's markdown content (data URL or plain markdown)
      const isMarkdownContent = 
        activity.embed_url.startsWith("data:text/markdown") ||
        activity.embed_url.startsWith("data:text/plain") ||
        activity.embed_url.startsWith("#") ||
        activity.embed_url.startsWith("##") ||
        activity.embed_url.includes("\n#") ||
        (!activity.embed_url.startsWith("http") && !activity.embed_url.endsWith(".pdf"))
      
      if (isMarkdownContent) {
        // Extract content from data URL or use directly
        let markdownContent = activity.embed_url
        if (activity.embed_url.startsWith("data:")) {
          try {
            const base64Match = activity.embed_url.match(/base64,(.*)/)
            if (base64Match) {
              markdownContent = atob(base64Match[1])
            } else {
              const commaIndex = activity.embed_url.indexOf(",")
              if (commaIndex !== -1) {
                markdownContent = decodeURIComponent(activity.embed_url.slice(commaIndex + 1))
              }
            }
          } catch (e) {
            console.error("Failed to decode markdown content:", e)
          }
        }
        
        return (
          <div className="p-6 bg-white rounded-2xl border border-gray-200 max-h-[700px] overflow-y-auto">
            <div className="prose prose-gray max-w-none">
              <MarkdownContent content={markdownContent} />
            </div>
          </div>
        )
      }
      
      // For PDFs or web pages
      if (activity.embed_url.endsWith(".pdf") || activity.source_type === "openalex") {
        return (
          <div className="relative w-full h-[600px] bg-gray-100 rounded-2xl overflow-hidden">
            <iframe
              key={embedKey}
              src={activity.embed_url}
              title={activity.title}
              className="absolute inset-0 w-full h-full"
              loading="lazy"
            />
          </div>
        )
      }
      
      // For web articles
      return (
        <div className="relative w-full h-[600px] bg-white rounded-2xl overflow-hidden border border-gray-200">
          <iframe
            key={embedKey}
            src={activity.embed_url}
            title={activity.title}
            className="absolute inset-0 w-full h-full"
            sandbox="allow-scripts allow-same-origin"
            loading="lazy"
          />
        </div>
      )
    }

    return (
      <div className="p-8 bg-gray-100 rounded-2xl text-center">
        <p className="text-gray-600">Content type not supported for embedding</p>
        <a
          href={activity.embed_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-blue-500 hover:underline"
        >
          Open in new tab →
        </a>
      </div>
    )
  }

  // Course complete view
  if (isCourseComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full p-8 bg-white rounded-3xl shadow-lg text-center"
        >
          <div className="w-20 h-20 mx-auto mb-6 bg-green-100 rounded-full flex items-center justify-center">
            <svg className="w-10 h-10 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="font-serif text-3xl text-gray-800 mb-3">Congratulations!</h1>
          <p className="text-gray-600 mb-6">
            You've completed all the topics in your learning path.
          </p>
          {lessonProgress && (
            <div className="p-4 bg-gray-50 rounded-xl mb-6">
              <p className="text-sm text-gray-500">Final Stats</p>
              <p className="text-2xl font-bold text-gray-800">
                {lessonProgress.completed_topics}/{lessonProgress.total_topics} Topics
              </p>
              <p className="text-sm text-gray-500">
                {Math.round(lessonProgress.average_mastery * 100)}% Average Mastery
              </p>
            </div>
          )}
          <Button asChild className="w-full">
            <TransitionLink to="/onboarding">Start New Learning Path</TransitionLink>
          </Button>
        </motion.div>
      </div>
    )
  }

  // Topic complete transition
  if (isTopicComplete && topicProgress) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full p-8 bg-white rounded-3xl shadow-lg text-center"
        >
          <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>
          <h2 className="font-serif text-2xl text-gray-800 mb-2">Topic Complete!</h2>
          <p className="text-gray-600 mb-4">
            You've mastered <span className="font-medium">{topicProgress.topic_name}</span>
          </p>
          <div className="p-3 bg-green-50 rounded-xl">
            <p className="text-sm text-green-700">
              Mastery: {Math.round(topicProgress.mastery_level * 100)}%
            </p>
          </div>
          <p className="mt-4 text-sm text-gray-400">Loading next topic...</p>
        </motion.div>
      </div>
    )
  }

  // Loading state
  if (isLoading && !activity) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-gray-200 border-t-gray-800 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading your lesson...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error && !activity) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md w-full p-8 bg-white rounded-3xl shadow-lg text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="font-serif text-xl text-gray-800 mb-2">Oops!</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <div className="space-y-3">
            <Button onClick={fetchNextActivity} className="w-full">
              Try Again
            </Button>
            <Button variant="outline" asChild className="w-full">
              <TransitionLink to="/onboarding">Go to Onboarding</TransitionLink>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Top Progress Bar */}
      {lessonProgress && (
        <div className="fixed top-0 left-0 right-0 h-1 bg-gray-200 z-50">
          <motion.div
            className="h-full bg-green-500"
            initial={{ width: 0 }}
            animate={{ width: `${lessonProgress.progress_percentage}%` }}
            transition={{ duration: 0.5 }}
          />
            </div>
          )}

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Topic Header */}
        {topicProgress && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">
                Topic {topicProgress.order_index + 1}
              </span>
              <span className="text-sm text-gray-500">
                {Math.round(topicProgress.mastery_level * 100)}% Mastery
              </span>
            </div>
            <h1 className="font-serif text-2xl text-gray-800">{topicProgress.topic_name}</h1>
            <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-blue-500 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${topicProgress.mastery_level * 100}%` }}
                transition={{ duration: 0.3 }}
              />
                                  </div>
                              </div>
                            )}

        {/* Activity Card */}
        {activity && (
          <motion.div
            key={activity.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-3xl shadow-lg overflow-hidden"
          >
            {/* Activity Header */}
            <div className="p-6 border-b border-gray-100">
              <div className="flex items-center gap-3 mb-2">
                <span className={`
                  px-3 py-1 text-xs font-medium rounded-full
                  ${activity.activity_type === "video" ? "bg-red-100 text-red-700" : ""}
                  ${activity.activity_type === "reading" ? "bg-blue-100 text-blue-700" : ""}
                  ${activity.activity_type === "problem" ? "bg-purple-100 text-purple-700" : ""}
                  ${activity.activity_type === "lab" ? "bg-green-100 text-green-700" : ""}
                `}>
                  {activity.activity_type.charAt(0).toUpperCase() + activity.activity_type.slice(1)}
                </span>
                {activity.source_title && (
                  <span className="text-xs text-gray-400">{activity.source_title}</span>
                )}
                {activity.duration_minutes && (
                  <span className="text-xs text-gray-400">~{activity.duration_minutes} min</span>
                            )}
                          </div>
              <h2 className="font-medium text-lg text-gray-800">{activity.title}</h2>
                    </div>

            {/* Activity Content */}
            <div className="p-6">
              {renderEmbed()}
            </div>

{/* Activity Actions */}
            <div className="p-6 bg-gray-50 border-t border-gray-100">
              {/* Feedback buttons */}
              <div className="flex items-center justify-center gap-3 mb-4">
                <button
                  onClick={() => setFeedbackGiven(feedbackGiven === "confused" ? null : "confused")}
                  className={`
                    flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all
                    ${feedbackGiven === "confused"
                      ? "bg-orange-500 text-white"
                      : "bg-orange-100 text-orange-700 hover:bg-orange-200"
                    }
                  `}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  I'm confused
                </button>
                <button
                  onClick={() => setFeedbackGiven(feedbackGiven === "too_easy" ? null : "too_easy")}
                  className={`
                    flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all
                    ${feedbackGiven === "too_easy"
                      ? "bg-emerald-500 text-white"
                      : "bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
                    }
                  `}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Too easy
                </button>
              </div>
              
              {/* Feedback messages */}
              <AnimatePresence>
                {feedbackGiven && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-4 overflow-hidden"
                  >
                    <div className={`
                      p-3 rounded-xl text-sm text-center
                      ${feedbackGiven === "confused" ? "bg-orange-50 text-orange-700" : "bg-emerald-50 text-emerald-700"}
                    `}>
                      {feedbackGiven === "confused" 
                        ? "Got it! We'll add more foundational content to help you understand."
                        : "Great! We'll skip ahead to more challenging material."
                      }
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex items-center justify-between">
                <Button
                  variant="outline"
                  onClick={handleSkipTopic}
                  disabled={isCompleting}
                  className="text-gray-600"
                >
                  Skip Topic
                  </Button>
                <div className="flex gap-3">
                  <Button
                    onClick={handleCompleteActivity}
                    disabled={isCompleting}
                    className="bg-gray-800 hover:bg-gray-700"
                  >
                    {isCompleting ? (
                      <span className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Saving...
                      </span>
                    ) : (
                      "Next"
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Error Toast */}
        <AnimatePresence>
          {error && activity && (
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 50 }}
              className="fixed bottom-6 left-1/2 -translate-x-1/2 px-6 py-3 bg-red-500 text-white rounded-xl shadow-lg"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
