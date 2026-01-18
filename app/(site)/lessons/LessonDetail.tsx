"use client"

import { useMemo } from "react"
import { useParams } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { demoPlan, type Lesson, type LessonPlan } from "@/lib/lesson-plan"

const typeCopy: Record<Lesson["type"], string> = {
  reading: "Annotated reading",
  video: "Embedded lecture",
  problem: "Guided problem set",
  lab: "Hands-on lab",
}

export default function LessonDetail() {
  const params = useParams<{ lessonId: string }>()
  const stored =
    typeof window !== "undefined" ? window.localStorage.getItem("lessonPlan") : null
  let plan: LessonPlan = demoPlan
  if (stored) {
    try {
      plan = JSON.parse(stored) as LessonPlan
    } catch {
      plan = demoPlan
    }
  }

  const lesson = useMemo(() => {
    for (const unit of plan.units) {
      const match = unit.lessons.find((item) => item.id === params.lessonId)
      if (match) {
        return { unit, lesson: match }
      }
    }
    return null
  }, [params.lessonId, plan.units])

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
          <div className="rounded-2xl border border-peach/60 bg-white/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
              Source excerpt
            </p>
            <p className="mt-2 text-ink">
              “The curvature of a manifold provides a compact way to describe how local
              geometry deviates from Euclidean space.”
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="bg-white/85">
          <CardHeader>
            <Badge>Embedded media</Badge>
            <CardTitle className="mt-4">Lecture video + annotated notes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted">
            <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-ink/10 bg-cream text-center text-ink">
              Video will load after the next source search
            </div>
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
                Exercises appear here once a vetted problem set is embedded.
              </p>
              <Button size="sm" className="mt-3">
                Fetch exercises
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
