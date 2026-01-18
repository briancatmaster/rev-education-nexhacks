import { useLocation } from "react-router-dom"
import { useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import TransitionLink from "@/components/TransitionLink"
import type { LessonPlan } from "@/lib/lesson-plan"

const lessonTypeLabel = {
  reading: "Reading",
  video: "Video",
  problem: "Problem",
  lab: "Lab",
}

export default function LessonSidebar({ compact = false }: { compact?: boolean }) {
  const location = useLocation()
  const [plan, setPlan] = useState<LessonPlan | null>(null)

  useEffect(() => {
    const stored = window.localStorage.getItem("lessonPlan")
    if (stored) {
      try {
        setPlan(JSON.parse(stored) as LessonPlan)
      } catch {
        setPlan(null)
      }
    }
  }, [])

  const activeLessonId = useMemo(() => {
    if (!plan) return null
    const parts = location.pathname.split("/").filter(Boolean)
    return parts[parts.length - 1] === "lessons" ? plan.units[0]?.lessons[0]?.id : parts.at(-1)
  }, [location.pathname, plan])

  const containerClass = compact
    ? "w-full overflow-y-auto rounded-2xl border border-peach/60 bg-paper/80 p-4"
    : "sticky top-20 h-[calc(100vh-5rem)] w-full overflow-y-auto border-r border-peach/60 bg-paper/80 p-6"

  if (!plan) {
    return (
      <aside className={containerClass}>
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cobalt">
            Lesson track
          </p>
          <h2 className="mt-2 text-lg font-semibold text-ink">No plan yet</h2>
          <p className="text-xs text-muted">Create your learning path to get started.</p>
        </div>
      </aside>
    )
  }

  return (
    <aside className={containerClass}>
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cobalt">
          Lesson track
        </p>
        <h2 className="mt-2 text-lg font-semibold text-ink">{plan.target}</h2>
        <p className="text-xs text-muted">Built from: {plan.background}</p>
      </div>

      <div className="space-y-6">
        {plan.units.map((unit, unitIndex) => (
          <div key={unit.id} className="space-y-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Unit {unitIndex + 1}
              </p>
              <h3 className="text-sm font-semibold text-ink">{unit.title}</h3>
              <p className="text-xs text-muted">{unit.description}</p>
            </div>
            <div className="space-y-2">
              {unit.lessons.map((lesson) => {
                const isActive = lesson.id === activeLessonId
                return (
                  <TransitionLink
                    key={lesson.id}
                    to={`/lessons/${lesson.id}`}
                    className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm transition ${
                      isActive
                        ? "border-ink bg-white shadow-float"
                        : "border-peach/60 bg-white/60 hover:border-ink/40"
                    }`}
                  >
                    <span className="text-ink">{lesson.title}</span>
                    <Badge variant={isActive ? "accent" : "neutral"}>
                      {lessonTypeLabel[lesson.type]}
                    </Badge>
                  </TransitionLink>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
