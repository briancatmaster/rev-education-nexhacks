import { useEffect, useMemo, useState } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Lesson, LessonPlan } from "@/lib/lesson-plan"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

const typeCopy: Record<Lesson["type"], string> = {
  reading: "Annotated reading",
  video: "Embedded lecture",
  problem: "Guided problem set",
  lab: "Hands-on lab",
}

type LessonSource = {
  id: string
  title: string
  type: string
  provider: string
  url?: string
  summary: string
}

type LessonActivity = {
  id: string
  title: string
  type: string
  instructions: string
  sources: LessonSource[]
  follow_ups: string[]
}

export default function LessonDetailView() {
  const params = useParams<{ lessonId: string }>()
  const navigate = useNavigate()
  const stored =
    typeof window !== "undefined" ? window.localStorage.getItem("lessonPlan") : null
  let plan: LessonPlan | null = null
  if (stored) {
    try {
      plan = JSON.parse(stored) as LessonPlan
    } catch {
      plan = null
    }
  }

  const lesson = useMemo(() => {
    if (!plan) return null
    for (const unit of plan.units) {
      const match = unit.lessons.find((item) => item.id === params.lessonId)
      if (match) {
        return { unit, lesson: match }
      }
    }
    return null
  }, [params.lessonId, plan])

  const [activity, setActivity] = useState<LessonActivity | null>(null)
  const [complete, setComplete] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const getEmbedUrl = (source: LessonSource) => {
    if (!source.url) return null
    const url = source.url
    const youtubeMatch =
      url.match(/youtu\.be\/([A-Za-z0-9_-]+)/) ||
      url.match(/youtube\.com\/watch\?v=([A-Za-z0-9_-]+)/) ||
      url.match(/youtube\.com\/embed\/([A-Za-z0-9_-]+)/)
    if (youtubeMatch) {
      return `https://www.youtube.com/embed/${youtubeMatch[1]}`
    }
    if (url.toLowerCase().endsWith(".pdf") || url.includes("/pdf")) {
      return url
    }
    return null
  }

  const embeddedSources = useMemo(() => {
    if (!activity?.sources?.length) return []
    return activity.sources
      .map((source) => ({ source, embedUrl: getEmbedUrl(source) }))
      .filter((item) => item.embedUrl)
  }, [activity])

  const flatLessons = useMemo(() => {
    if (!plan) return []
    return plan.units.flatMap((unit) =>
      unit.lessons.map((item) => ({ unit, lesson: item }))
    )
  }, [plan])

  const lessonIndex = flatLessons.findIndex((item) => item.lesson.id === params.lessonId)
  const nextLesson = lessonIndex >= 0 ? flatLessons[lessonIndex + 1] : null

  const fetchNextActivity = async (completedIds: string[]) => {
    if (!lesson) return
    const sessionId = window.localStorage.getItem("sessionId")
    if (!sessionId) {
      setError("Missing session. Restart onboarding.")
      return
    }
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/lesson/next-activity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          topic: lesson.unit.title,
          completed_activity_ids: completedIds,
        }),
      })
      const data = await res.json()
      if (data.complete) {
        setComplete(true)
        setActivity(null)
      } else {
        setComplete(false)
        setActivity(data.activity)
      }
    } catch (err) {
      setError("Failed to fetch the next activity.")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!lesson) return
    const progressRaw = window.localStorage.getItem("topicProgress")
    let progress: Record<string, { completed: string[] }> = {}
    if (progressRaw) {
      try {
        progress = JSON.parse(progressRaw)
      } catch {
        progress = {}
      }
    }
    const completed = progress[lesson.lesson.id]?.completed || []
    fetchNextActivity(completed)
  }, [lesson?.lesson.id])

  if (!plan) {
    return (
      <div className="rounded-3xl border border-peach/60 bg-white/80 p-8">
        <h1 className="font-serif text-2xl text-ink">No lesson plan found</h1>
        <p className="mt-2 text-sm text-muted">
          Create your learning origin first to generate a personalized lesson path.
        </p>
        <div className="mt-4">
          <Button asChild>
            <Link to="/onboarding">Build learning origin</Link>
          </Button>
        </div>
      </div>
    )
  }

  if (!lesson) {
    return (
      <div className="rounded-3xl border border-peach/60 bg-white/80 p-8">
        <h1 className="font-serif text-2xl text-ink">Lesson not found</h1>
        <p className="mt-2 text-sm text-muted">
          Select a lesson from the left sidebar to continue.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <Card className="bg-white/85">
        <CardHeader>
          <Badge variant="accent">{typeCopy[lesson.lesson.type]}</Badge>
          <CardTitle className="mt-4">{lesson.lesson.title}</CardTitle>
          <p className="text-sm text-muted">{lesson.unit.title}</p>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted">
          <p>
            This lesson pulls from embedded sources and guides you through the concepts
            with in-context highlights. Everything stays inside the NexHacks interface.
          </p>
          {activity?.sources?.length ? (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Embedded sources
              </p>
              {activity.sources.map((source) => (
                <div key={source.id} className="rounded-2xl border border-peach/60 bg-white/70 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-ink">{source.title}</p>
                    <Badge variant="neutral">{source.type}</Badge>
                  </div>
                  <p className="mt-2 text-xs uppercase tracking-[0.2em] text-muted">
                    {source.provider}
                  </p>
                  <p className="mt-2 text-sm text-muted">{source.summary}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-peach/60 bg-white/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Source queue
              </p>
              <p className="mt-2 text-ink">
                Sources will appear here once the first activity is loaded.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="bg-white/85">
          <CardHeader>
            <Badge>Embedded media</Badge>
            <CardTitle className="mt-4">Lecture video + annotated notes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted">
            {embeddedSources.length ? (
              <div className="space-y-4">
                {embeddedSources.map(({ source, embedUrl }) => (
                  <div
                    key={source.id}
                    className="overflow-hidden rounded-2xl border border-ink/10 bg-cream"
                  >
                    {embedUrl?.includes("youtube.com/embed") ? (
                      <iframe
                        title={source.title}
                        src={embedUrl}
                        className="h-60 w-full"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    ) : (
                      <iframe title={source.title} src={embedUrl || ""} className="h-72 w-full" />
                    )}
                    <div className="border-t border-ink/10 bg-white/80 p-3">
                      <p className="text-sm font-semibold text-ink">{source.title}</p>
                      <p className="text-xs text-muted">{source.provider}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-ink/10 bg-cream text-center text-ink">
                {activity ? "Embedded media ready" : "Video will load after the next search"}
              </div>
            )}
            <p>
              Each time you complete an activity, we search again and embed the next
              relevant lecture or lab without leaving the platform.
            </p>
          </CardContent>
        </Card>

        <Card className="bg-white/85">
          <CardHeader>
            <Badge variant="neutral">Practice from sources</Badge>
            <CardTitle className="mt-4">Embedded exercises</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted">
            <div className="rounded-xl border border-peach/50 bg-white/70 p-3">
              <p className="text-ink">
                Exercises appear here once a vetted problem set is embedded from sources.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-white/85">
        <CardHeader>
          <Badge variant="accent">Current activity</Badge>
          <CardTitle className="mt-4">
            {activity?.title || (complete ? "Topic complete" : "Loading activity")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted">
          {error ? <p className="text-amber">{error}</p> : null}
          {activity?.instructions ? (
            <p>{activity.instructions}</p>
          ) : complete ? (
            <p>We believe you are ready to move on to the next topic.</p>
          ) : (
            <p>Preparing the next activity...</p>
          )}

          {activity?.follow_ups?.length ? (
            <div className="flex flex-wrap gap-2">
              {activity.follow_ups.map((item, index) => (
                <Badge key={`${item}-${index}`} variant="neutral">
                  {item}
                </Badge>
              ))}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <Button
              disabled={isLoading || !activity}
              onClick={() => {
                if (!activity || !lesson) return
                const progressRaw = window.localStorage.getItem("topicProgress")
                let progress: Record<string, { completed: string[] }> = {}
                if (progressRaw) {
                  try {
                    progress = JSON.parse(progressRaw)
                  } catch {
                    progress = {}
                  }
                }
                const current = progress[lesson.lesson.id]?.completed || []
                const updated = Array.from(new Set([...current, activity.id]))
                progress[lesson.lesson.id] = { completed: updated }
                window.localStorage.setItem("topicProgress", JSON.stringify(progress))
                fetchNextActivity(updated)
              }}
            >
              {isLoading ? "Working..." : "Complete activity"}
            </Button>
            <Button
              variant="outline"
              disabled={!nextLesson}
              onClick={() => {
                if (!nextLesson) return
                navigate(`/lessons/${nextLesson.lesson.id}`)
              }}
            >
              Skip topic
            </Button>
            <Button
              variant="ghost"
              disabled={!complete || !nextLesson}
              onClick={() => {
                if (!nextLesson) return
                navigate(`/lessons/${nextLesson.lesson.id}`)
              }}
            >
              Next topic
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
