"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { demoPlan, type LessonPlan } from "@/lib/lesson-plan"

export default function LessonOverview() {
  const [plan, setPlan] = useState<LessonPlan>(demoPlan)

  useEffect(() => {
    const stored = window.localStorage.getItem("lessonPlan")
    if (stored) {
      try {
        setPlan(JSON.parse(stored) as LessonPlan)
      } catch {
        setPlan(demoPlan)
      }
    }
  }, [])

  const primaryUnit = plan.units[0]

  return (
    <div className="space-y-8">
      <div className="rounded-3xl border border-peach/60 bg-white/80 p-8 shadow-float">
        <Badge variant="accent">Your path is ready</Badge>
        <h1 className="mt-4 font-serif text-3xl text-ink">
          {plan.target}
        </h1>
        <p className="mt-3 text-base text-muted">
          Built from your background in {plan.background}. We embedded trusted sources,
          annotated key ideas, and sequenced the material into a lesson flow you can
          navigate without leaving the platform.
        </p>
        {plan.skills?.length ? (
          <div className="mt-4 flex flex-wrap gap-2 text-xs uppercase tracking-[0.2em] text-muted">
            {plan.skills.map((skill) => (
              <span
                key={skill.id}
                className="rounded-full border border-peach/60 bg-white/70 px-3 py-1"
              >
                {skill.name}{skill.level ? ` · ${skill.level}` : ""}
              </span>
            ))}
          </div>
        ) : null}
        <div className="mt-5 flex flex-wrap gap-3">
          <Button asChild>
            <Link href={`/lessons/${primaryUnit?.lessons[0]?.id ?? "lesson-1"}`}>
              Start first lesson
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/origin">Refine learning origin</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {plan.units.map((unit, index) => (
          <Card key={unit.id} className="bg-white/85">
            <CardHeader>
              <Badge>Unit {index + 1}</Badge>
              <CardTitle className="mt-4">{unit.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted">
              <p>{unit.description}</p>
              <div className="space-y-2">
                {unit.lessons.map((lesson) => (
                  <Link
                    key={lesson.id}
                    href={`/lessons/${lesson.id}`}
                    className="flex items-center justify-between rounded-xl border border-peach/50 bg-white/70 px-3 py-2 text-sm text-ink hover:border-ink/40"
                  >
                    <span>{lesson.title}</span>
                    <span className="text-xs uppercase tracking-[0.2em] text-muted">
                      {lesson.type}
                    </span>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
