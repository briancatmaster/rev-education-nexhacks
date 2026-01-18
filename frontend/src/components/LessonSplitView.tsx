import { useEffect, useState, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import "katex/dist/katex.min.css"
import { Button } from "@/components/ui/button"
import TransitionLink from "@/components/TransitionLink"
import { useConfusionDetection } from "@/hooks/useConfusionDetection"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

/**
 * Preprocesses content to normalize LaTeX delimiters for remark-math.
 * Converts various LaTeX formats to the standard $ and $$ delimiters.
 * Also strips any code fence wrappers that the AI might add.
 */
function preprocessLatex(content: string): string {
  if (!content) return content

  let processed = content.trim()

  // FIRST: Aggressively strip any code fence wrappers
  // The AI sometimes wraps the entire response in code fences
  // Match code fences at start: ```markdown, ```md, ```text, ```json, or just ```
  processed = processed.replace(/^```(?:markdown|md|text|json)?\s*\n/i, '')
  // Match code fences at end
  processed = processed.replace(/\n```\s*$/i, '')

  // Handle case where content starts with code block on same line as ```
  processed = processed.replace(/^```[a-z]*\s*/gi, '')
  // Handle trailing ``` that might not have newline
  processed = processed.replace(/```\s*$/gi, '')

  // Strip again in case there were multiple layers
  processed = processed.trim()
  if (processed.startsWith('```')) {
    processed = processed.replace(/^```[a-z]*\s*\n?/gi, '')
  }
  if (processed.endsWith('```')) {
    processed = processed.replace(/\n?```\s*$/gi, '')
  }

  // First, unescape any JSON-escaped content
  // Sometimes the API returns content with extra escaping
  try {
    // Check if content looks like it was double-escaped
    if (processed.includes('\\n') && !processed.includes('\n')) {
      processed = processed.replace(/\\n/g, '\n')
    }
    if (processed.includes('\\"')) {
      processed = processed.replace(/\\"/g, '"')
    }
    if (processed.includes('\\\\')) {
      // Be careful not to break LaTeX commands
      // Only unescape \\\\ to \\ when not followed by a letter (LaTeX command)
      processed = processed.replace(/\\\\(?![a-zA-Z])/g, '\\')
    }
  } catch (e) {
    console.error("Error unescaping content:", e)
  }

  // Convert \[...\] to $$...$$ (display math)
  processed = processed.replace(/\\\[([\s\S]*?)\\\]/g, '\n$$\n$1\n$$\n')

  // Convert \(...\) to $...$ (inline math)
  processed = processed.replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$')

  // Handle escaped dollar signs that might break things
  // Convert \$ to a placeholder, then back after processing
  processed = processed.replace(/\\\$/g, '\\DOLLAR')

  // Clean up any double-escaped backslashes in LaTeX commands
  // Sometimes content has \\frac instead of \frac
  processed = processed.replace(/\\\\([a-zA-Z]+)/g, '\\$1')

  // Restore escaped dollar signs
  processed = processed.replace(/\\DOLLAR/g, '\\$')

  // Ensure display math has proper spacing
  processed = processed.replace(/\$\$\s*([\s\S]*?)\s*\$\$/g, '\n$$\n$1\n$$\n')

  return processed.trim()
}

type MathProblem = {
  problem: string
  hints: string[]
  solution: string
  answer: string
  source: string
  source_url: string
  difficulty: string
  latex_content: boolean
}

type VideoEmbed = {
  video_id: string
  title: string
  source: string
  embed_url: string
}

type LessonContent = {
  topic_name: string
  lesson_content: string
  video?: VideoEmbed
  problems: MathProblem[]
}

type TopicInfo = {
  id: string
  topic_name: string
  mastery_level: number
  order_index: number
}

export default function LessonSplitView() {
  const [lessonContent, setLessonContent] = useState<LessonContent | null>(null)
  const [currentTopic, setCurrentTopic] = useState<TopicInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingContent, setIsLoadingContent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [courseComplete, setCourseComplete] = useState(false)

  // Problem interaction state
  const [selectedProblem, setSelectedProblem] = useState<number>(-1)
  const [showHints, setShowHints] = useState(false)
  const [showSolution, setShowSolution] = useState(false)
  const [currentHintIndex, setCurrentHintIndex] = useState(0)
  const [isCompleting, setIsCompleting] = useState(false)

  // Confusion detection and simplify state
  const [showSimplifyButton, setShowSimplifyButton] = useState(false)
  const [isSimplifying, setIsSimplifying] = useState(false)
  const [currentAbstractionLevel, setCurrentAbstractionLevel] = useState(3) // Default: intermediate
  const [simplifyDismissed, setSimplifyDismissed] = useState(false)

  // Confusion detection hook
  const {
    isConfused,
    cameraEnabled,
    cameraError,
    toggleCamera,
    clearConfusion,
  } = useConfusionDetection()

  const sessionId = localStorage.getItem("sessionId")
  const userId = localStorage.getItem("onboarding_userId")

  // Show simplify button when confusion is detected
  useEffect(() => {
    if (isConfused && !simplifyDismissed) {
      setShowSimplifyButton(true)
    }
  }, [isConfused, simplifyDismissed])

  // Reset dismiss state when changing topics
  useEffect(() => {
    setSimplifyDismissed(false)
    setShowSimplifyButton(false)
    setCurrentAbstractionLevel(3)
  }, [currentTopic?.id])

  // Fetch current topic
  const fetchCurrentTopic = useCallback(async () => {
    if (!sessionId) {
      setError("No session found. Please complete onboarding first.")
      setIsLoading(false)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/api/lesson/current-topic/${sessionId}`)
      const data = await res.json()

      if (data.success) {
        if (data.course_complete) {
          setCourseComplete(true)
        } else if (data.topic) {
          setCurrentTopic(data.topic)
        }
      } else {
        setError(data.error || "Failed to load topic")
      }
    } catch (e) {
      setError("Failed to connect to server")
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  // Fetch lesson content (non-blocking)
  const fetchLessonContent = useCallback(async () => {
    if (!sessionId || !userId) return

    setIsLoadingContent(true)

    try {
      const res = await fetch(`${API_BASE}/api/lesson/content`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_id: parseInt(userId, 10)
        })
      })
      const data = await res.json()

      if (data.success) {
        setLessonContent({
          topic_name: data.topic_name,
          lesson_content: data.lesson_content,
          video: data.video || undefined,
          problems: data.problems || []
        })
      }
    } catch (e) {
      console.error("Failed to load lesson content:", e)
    } finally {
      setIsLoadingContent(false)
    }
  }, [sessionId, userId])

  // Initial fetch
  useEffect(() => {
    fetchCurrentTopic()
  }, [fetchCurrentTopic])

  // Fetch content when topic is available
  useEffect(() => {
    if (currentTopic) {
      fetchLessonContent()
    }
  }, [currentTopic, fetchLessonContent])

  // Complete topic and move to next
  const handleCompleteTopic = async () => {
    if (!sessionId || !userId || !currentTopic) return

    setIsCompleting(true)

    try {
      // Mark topic complete via skip (which sets mastery based on interaction)
      const res = await fetch(
        `${API_BASE}/api/lesson/skip-topic?session_id=${sessionId}&user_id=${userId}`,
        { method: "POST" }
      )
      const data = await res.json()

      if (data.success) {
        // Reset state for next topic
        setLessonContent(null)
        setSelectedProblem(-1)
        setShowHints(false)
        setShowSolution(false)
        setCurrentHintIndex(0)

        // Fetch next topic
        fetchCurrentTopic()
      }
    } catch (e) {
      setError("Failed to complete topic")
    } finally {
      setIsCompleting(false)
    }
  }

  // Handle simplify content request
  const handleSimplify = async () => {
    if (!sessionId || isSimplifying) return

    setIsSimplifying(true)
    clearConfusion()

    // Calculate new abstraction level (go down by 1, minimum 1)
    const newLevel = Math.max(1, currentAbstractionLevel - 1)

    try {
      const res = await fetch(`${API_BASE}/api/lesson/simplify-content`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          target_abstraction_level: newLevel,
          current_content: lessonContent?.lesson_content || null,
        }),
      })
      const data = await res.json()

      if (data.success) {
        setLessonContent(prev => prev ? {
          ...prev,
          lesson_content: data.simplified_content,
        } : null)
        setCurrentAbstractionLevel(newLevel)
        setShowSimplifyButton(false)
      }
    } catch (e) {
      console.error("Failed to simplify content:", e)
    } finally {
      setIsSimplifying(false)
    }
  }

  // Dismiss simplify button
  const handleDismissSimplify = () => {
    setShowSimplifyButton(false)
    setSimplifyDismissed(true)
    clearConfusion()
  }

  // Course complete view
  if (courseComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8 bg-gradient-to-br from-gray-50 to-gray-100">
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
          <Button asChild className="w-full">
            <TransitionLink to="/onboarding">Start New Learning Path</TransitionLink>
          </Button>
        </motion.div>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
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
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md w-full p-8 bg-white rounded-3xl shadow-lg text-center">
          <h2 className="font-serif text-xl text-gray-800 mb-2">Oops!</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <Button asChild className="w-full">
            <TransitionLink to="/onboarding">Go to Onboarding</TransitionLink>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Top Header */}
      <div className="sticky top-0 z-10 bg-white/80 backdrop-blur-sm border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <span className="text-sm text-gray-500">
              Topic {currentTopic ? currentTopic.order_index + 1 : 1}
            </span>
            <h1 className="font-serif text-xl text-gray-800">
              {lessonContent?.topic_name || currentTopic?.topic_name || "Loading..."}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            {/* Abstraction Level Indicator */}
            {currentAbstractionLevel < 3 && (
              <div className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                Simplified (Level {currentAbstractionLevel})
              </div>
            )}

            {/* Camera Toggle for Confusion Detection */}
            <div className="relative group">
              <button
                onClick={toggleCamera}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
                  cameraEnabled
                    ? "bg-green-50 hover:bg-green-100"
                    : "bg-gray-100 hover:bg-gray-200"
                }`}
              >
                {/* Status indicator dot */}
                <span className={`w-2 h-2 rounded-full ${
                  cameraEnabled
                    ? "bg-green-500 animate-pulse"
                    : "bg-red-400"
                }`} />
                <span className={`text-xs font-medium ${
                  cameraEnabled ? "text-green-700" : "text-gray-500"
                }`}>
                  {cameraEnabled ? "Monitoring" : "Camera Off"}
                </span>
                {cameraEnabled ? (
                  <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3l18 18" />
                  </svg>
                )}
              </button>

              {/* Tooltip Popup */}
              <div className="absolute top-full right-0 mt-2 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                <div className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <p className="font-semibold mb-1">Confusion Detection</p>
                    <p className="text-gray-300 leading-relaxed">
                      {cameraEnabled
                        ? "Your webcam is analyzing your facial expressions. If you look confused, we'll offer to simplify the content for you."
                        : "Enable your webcam to detect when you're confused. We'll automatically offer simpler explanations when needed."
                      }
                    </p>
                  </div>
                </div>
                {/* Arrow */}
                <div className="absolute -top-1 right-6 w-2 h-2 bg-gray-900 rotate-45" />
              </div>
            </div>

            <div className="text-sm text-gray-500">
              {currentTopic && (
                <span>{Math.round(currentTopic.mastery_level * 100)}% Mastery</span>
              )}
            </div>
            <Button
              onClick={handleCompleteTopic}
              disabled={isCompleting}
              className="bg-gray-800 hover:bg-gray-700"
            >
              {isCompleting ? "Completing..." : "Complete & Next"}
            </Button>
          </div>
        </div>
      </div>

      {/* Camera Error Notification */}
      {cameraError && (
        <div className="max-w-7xl mx-auto px-6 pt-2">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            {cameraError}
          </div>
        </div>
      )}

      {/* Floating Simplify Button */}
      <AnimatePresence>
        {showSimplifyButton && !isSimplifying && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50"
          >
            <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 p-4 flex items-center gap-4">
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div className="flex-1">
                <p className="font-medium text-gray-900">Looking confused?</p>
                <p className="text-sm text-gray-500">We can simplify this explanation for you.</p>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleSimplify}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  Simplify
                </Button>
                <button
                  onClick={handleDismissSimplify}
                  className="p-2 text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Simplifying Overlay */}
      <AnimatePresence>
        {isSimplifying && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-white/80 backdrop-blur-sm z-40 flex items-center justify-center"
          >
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4" />
              <p className="text-gray-700 font-medium">Simplifying content...</p>
              <p className="text-sm text-gray-500">Making this easier to understand</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Split View */}
      <div className="max-w-7xl mx-auto flex gap-6 p-6">
        {/* Left: Lesson Content */}
        <div className="flex-1 min-w-0 space-y-6">
          {/* Video Embed */}
          {isLoadingContent && !lessonContent?.video ? (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="relative w-full aspect-video bg-gray-100 flex items-center justify-center">
                <div className="text-center">
                  <div className="w-8 h-8 border-3 border-gray-200 border-t-red-500 rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-sm text-gray-500">Finding video...</p>
                </div>
              </div>
            </div>
          ) : lessonContent?.video ? (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="relative w-full aspect-video bg-black">
                <iframe
                  src={lessonContent.video.embed_url}
                  title={lessonContent.video.title}
                  className="absolute inset-0 w-full h-full"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  loading="lazy"
                />
              </div>
              <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
                <p className="text-sm font-medium text-gray-800 truncate">{lessonContent.video.title}</p>
                <p className="text-xs text-gray-500 mt-0.5">YouTube • Educational Video</p>
              </div>
            </div>
          ) : null}

          {/* Lesson Text Content */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
            {isLoadingContent && !lessonContent ? (
              <div className="flex items-center justify-center py-16">
                <div className="text-center">
                  <div className="w-10 h-10 border-4 border-gray-200 border-t-gray-600 rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-gray-500">Generating lesson content...</p>
                </div>
              </div>
            ) : lessonContent?.lesson_content ? (
              <div className="lesson-content max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    h1: ({ children }) => <h1 className="text-3xl font-bold text-gray-900 mb-6 mt-8 first:mt-0 pb-2 border-b border-gray-200">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-2xl font-bold text-gray-800 mb-4 mt-8">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-xl font-semibold text-gray-800 mb-3 mt-6">{children}</h3>,
                    h4: ({ children }) => <h4 className="text-lg font-semibold text-gray-700 mb-2 mt-4">{children}</h4>,
                    p: ({ children }) => <p className="text-gray-700 leading-relaxed mb-4">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-6 mb-4 space-y-2">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-6 mb-4 space-y-2">{children}</ol>,
                    li: ({ children }) => <li className="text-gray-700 leading-relaxed">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                    em: ({ children }) => <em className="italic text-gray-700">{children}</em>,
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-blue-400 pl-4 py-2 my-4 bg-blue-50 rounded-r-lg italic text-gray-700">
                        {children}
                      </blockquote>
                    ),
                    code: ({ className, children }) => {
                      const isInline = !className
                      return isInline ? (
                        <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono text-pink-600">{children}</code>
                      ) : (
                        <code className="block p-4 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto text-sm font-mono my-4">{children}</code>
                      )
                    },
                    pre: ({ children }) => <pre className="my-4">{children}</pre>,
                    a: ({ href, children }) => (
                      <a href={href} className="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                    hr: () => <hr className="my-8 border-gray-200" />,
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-4">
                        <table className="min-w-full border-collapse border border-gray-200">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => <th className="border border-gray-200 px-4 py-2 bg-gray-50 font-semibold text-left">{children}</th>,
                    td: ({ children }) => <td className="border border-gray-200 px-4 py-2">{children}</td>,
                  }}
                >
                  {preprocessLatex(lessonContent.lesson_content)}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-16 text-gray-500">
                <p>No lesson content available yet.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: LaTeX Problem Set */}
        <div className="w-[420px] shrink-0">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 sticky top-24">
            {/* LaTeX Document Header */}
            <div className="p-5 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h2 className="font-serif text-lg text-gray-800">Problem Set</h2>
              </div>
              <p className="text-xs text-gray-500 font-mono">
                {lessonContent?.problems?.length || 0} problems aggregated from Paul's Math Notes, MIT OCW, AoPS
              </p>
            </div>

            {/* LaTeX-style Problem Document */}
            <div className="p-6 max-h-[calc(100vh-14rem)] overflow-y-auto font-serif">
              {isLoadingContent && (!lessonContent?.problems || lessonContent.problems.length === 0) ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <div className="w-10 h-10 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin mb-4" />
                  <p className="text-sm text-gray-500 italic">Aggregating problems from educational sources...</p>
                </div>
              ) : lessonContent?.problems && lessonContent.problems.length > 0 ? (
                <div className="space-y-8">
                  {/* Document Title */}
                  <div className="text-center border-b border-gray-200 pb-4 mb-6">
                    <h3 className="text-xl font-bold text-gray-800">{lessonContent.topic_name}</h3>
                    <p className="text-sm text-gray-500 mt-1">Practice Problems</p>
                  </div>

                  {/* All Problems */}
                  {lessonContent.problems.map((problem, index) => (
                    <div key={index} className="problem-block">
                      {/* Problem Header */}
                      <div className="flex items-baseline gap-2 mb-3">
                        <span className="font-bold text-gray-800">Problem {index + 1}.</span>
                        <span className={`
                          px-2 py-0.5 text-xs rounded font-sans
                          ${problem.difficulty === 'easy' ? 'bg-green-100 text-green-700' : ''}
                          ${problem.difficulty === 'medium' ? 'bg-amber-100 text-amber-700' : ''}
                          ${problem.difficulty === 'hard' ? 'bg-red-100 text-red-700' : ''}
                        `}>
                          {problem.difficulty}
                        </span>
                        {problem.source && (
                          <span className="text-xs text-gray-400 font-sans ml-auto">
                            [{problem.source}]
                          </span>
                        )}
                      </div>

                      {/* Problem Statement - LaTeX rendered */}
                      <div className="pl-4 mb-4 text-gray-700 leading-relaxed prose prose-sm max-w-none">
                        <ReactMarkdown
                          remarkPlugins={[remarkMath]}
                          rehypePlugins={[rehypeKatex]}
                        >
                          {preprocessLatex(problem.problem)}
                        </ReactMarkdown>
                      </div>

                      {/* Collapsible Solution */}
                      <div className="pl-4">
                        <button
                          onClick={() => {
                            if (selectedProblem === index && showSolution) {
                              setShowSolution(false)
                            } else {
                              setSelectedProblem(index)
                              setShowSolution(true)
                              setShowHints(false)
                            }
                          }}
                          className="text-xs font-sans text-blue-600 hover:text-blue-800 underline"
                        >
                          {selectedProblem === index && showSolution ? "Hide Solution" : "Show Solution"}
                        </button>

                        {/* Hints Toggle */}
                        {problem.hints && problem.hints.length > 0 && (
                          <button
                            onClick={() => {
                              if (selectedProblem === index && showHints) {
                                setShowHints(false)
                              } else {
                                setSelectedProblem(index)
                                setShowHints(true)
                                setShowSolution(false)
                                setCurrentHintIndex(0)
                              }
                            }}
                            className="text-xs font-sans text-amber-600 hover:text-amber-800 underline ml-4"
                          >
                            {selectedProblem === index && showHints ? "Hide Hints" : `Hints (${problem.hints.length})`}
                          </button>
                        )}

                        {/* Expanded Hints */}
                        <AnimatePresence>
                          {selectedProblem === index && showHints && problem.hints && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="mt-3 p-3 bg-amber-50 rounded-lg border-l-4 border-amber-400 overflow-hidden"
                            >
                              <p className="text-xs font-sans font-semibold text-amber-700 mb-2">HINTS:</p>
                              {problem.hints.slice(0, currentHintIndex + 1).map((hint, i) => (
                                <div key={i} className="text-sm text-amber-800 mb-2">
                                  <span className="font-semibold">({i + 1})</span>{" "}
                                  <ReactMarkdown
                                    remarkPlugins={[remarkMath]}
                                    rehypePlugins={[rehypeKatex]}
                                  >
                                    {preprocessLatex(hint)}
                                  </ReactMarkdown>
                                </div>
                              ))}
                              {currentHintIndex < problem.hints.length - 1 && (
                                <button
                                  onClick={() => setCurrentHintIndex(prev => prev + 1)}
                                  className="text-xs font-sans text-amber-600 hover:text-amber-800"
                                >
                                  → Next hint
                                </button>
                              )}
                            </motion.div>
                          )}
                        </AnimatePresence>

                        {/* Expanded Solution */}
                        <AnimatePresence>
                          {selectedProblem === index && showSolution && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="mt-3 p-4 bg-green-50 rounded-lg border-l-4 border-green-500 overflow-hidden"
                            >
                              <p className="text-xs font-sans font-semibold text-green-700 mb-3">SOLUTION:</p>
                              <div className="prose prose-sm max-w-none text-green-900">
                                <ReactMarkdown
                                  remarkPlugins={[remarkMath]}
                                  rehypePlugins={[rehypeKatex]}
                                >
                                  {preprocessLatex(problem.solution)}
                                </ReactMarkdown>
                              </div>
                              {problem.answer && (
                                <div className="mt-4 pt-3 border-t border-green-300">
                                  <span className="font-bold text-green-800">Answer: </span>
                                  <span className="text-green-900">
                                    <ReactMarkdown
                                      remarkPlugins={[remarkMath]}
                                      rehypePlugins={[rehypeKatex]}
                                    >
                                      {preprocessLatex(problem.answer)}
                                    </ReactMarkdown>
                                  </span>
                                </div>
                              )}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                      {/* Problem Separator */}
                      {index < lessonContent.problems.length - 1 && (
                        <div className="mt-6 border-b border-dashed border-gray-300" />
                      )}
                    </div>
                  ))}

                  {/* Document Footer */}
                  <div className="text-center pt-4 border-t border-gray-200 mt-8">
                    <p className="text-xs text-gray-400 font-sans">
                      Problems aggregated from educational sources
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <p className="italic">No problems available for this topic.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
