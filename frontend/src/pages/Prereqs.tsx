import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

type Prerequisite = {
  id: string
  name: string
  specification: string
  relation: string
}

type ScoredPrerequisite = Prerequisite & {
  mastery_score: number
}

export default function PrereqsPage() {
  const navigate = useNavigate()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [keep, setKeep] = useState<ScoredPrerequisite[]>([])
  const [confirm, setConfirm] = useState<ScoredPrerequisite[]>([])
  const [dropped, setDropped] = useState<ScoredPrerequisite[]>([])
  const [selectedConfirm, setSelectedConfirm] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const stored = window.localStorage.getItem("sessionId")
    if (!stored) {
      setError("Missing session. Restart onboarding.")
      setLoading(false)
      return
    }
    setSessionId(stored)
  }, [])

  useEffect(() => {
    if (!sessionId) return

    const run = async () => {
      try {
        setLoading(true)
        setError(null)
        const prereqRes = await fetch(`${API_BASE}/api/analysis/prerequisites`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        })
        const prereqData = await prereqRes.json()
        const prerequisites: Prerequisite[] = prereqData.prerequisites || []

        const refineRes = await fetch(`${API_BASE}/api/analysis/prerequisites/refine`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, prerequisites }),
        })
        const refineData = await refineRes.json()

        setKeep(refineData.keep || [])
        setConfirm(refineData.confirm || [])
        setDropped(refineData.dropped || [])

        const defaults: Record<string, boolean> = {}
        ;(refineData.confirm || []).forEach((item: ScoredPrerequisite) => {
          defaults[item.id] = true
        })
        setSelectedConfirm(defaults)
      } catch (err) {
        setError("Failed to generate prerequisites. Please try again.")
      } finally {
        setLoading(false)
      }
    }

    run()
  }, [sessionId])

  const confirmList = useMemo(
    () => confirm.filter((item) => selectedConfirm[item.id]),
    [confirm, selectedConfirm]
  )

  const handleFinalize = async () => {
    if (!sessionId) return
    const finalList = [...keep, ...confirmList].map(({ mastery_score, ...rest }) => rest)

    try {
      setLoading(true)
      const orderRes = await fetch(`${API_BASE}/api/analysis/prerequisites/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, prerequisites: finalList }),
      })
      const orderData = await orderRes.json()
      const ordered: Prerequisite[] = orderData.prerequisites || []

      const plan = {
        id: `plan-${sessionId}`,
        background: "Personalized profile",
        target: window.localStorage.getItem("centralTopic") || "Learning path",
        units: ordered.map((item, index) => ({
          id: `unit-${index + 1}`,
          title: item.name,
          description: `${item.specification} ${item.relation}`,
          lessons: [
            {
              id: `lesson-${index + 1}`,
              title: item.name,
              type: "reading",
            },
          ],
        })),
      }

      window.localStorage.setItem("lessonPlan", JSON.stringify(plan))
      window.localStorage.setItem("orderedPrereqs", JSON.stringify(ordered))
      window.localStorage.setItem("topicProgress", JSON.stringify({}))
      navigate("/lessons")
    } catch (err) {
      setError("Failed to order prerequisites. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-16">
        <Card className="bg-white/85">
          <CardContent className="p-8 text-center text-muted">
            Building your prerequisite map...
          </CardContent>
        </Card>
      </main>
    )
  }

  if (error) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-16">
        <Card className="bg-white/85">
          <CardContent className="p-8 text-center text-amber">{error}</CardContent>
        </Card>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <div className="mb-8">
        <Badge variant="accent">Prerequisite check</Badge>
        <h1 className="mt-4 font-serif text-3xl text-ink">
          Review what you should learn first.
        </h1>
        <p className="mt-2 text-sm text-muted">
          We filtered prerequisites based on your profile. Confirm the mid-range topics
          you still want to cover before we launch the lessons.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="bg-white/85">
          <CardHeader>
            <CardTitle>Included prerequisites</CardTitle>
            <p className="text-sm text-muted">These are required based on your profile.</p>
          </CardHeader>
          <CardContent className="space-y-4">
            {keep.length === 0 ? (
              <p className="text-sm text-muted">None required.</p>
            ) : (
              keep.map((item) => (
                <div key={item.id} className="rounded-2xl border border-peach/60 bg-white/70 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-ink">{item.name}</p>
                    <Badge variant="neutral">{item.mastery_score.toFixed(2)}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted">{item.specification}</p>
                  <p className="mt-2 text-xs text-muted">{item.relation}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="bg-white/85">
          <CardHeader>
            <CardTitle>Confirm or skip</CardTitle>
            <p className="text-sm text-muted">
              These are mid-range. Decide if you want to learn them.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {confirm.length === 0 ? (
              <p className="text-sm text-muted">No topics need confirmation.</p>
            ) : (
              confirm.map((item) => (
                <div key={item.id} className="rounded-2xl border border-peach/60 bg-white/70 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-ink">{item.name}</p>
                    <label className="flex items-center gap-2 text-xs text-muted">
                      <input
                        type="checkbox"
                        checked={Boolean(selectedConfirm[item.id])}
                        onChange={(event) =>
                          setSelectedConfirm((prev) => ({
                            ...prev,
                            [item.id]: event.target.checked,
                          }))
                        }
                      />
                      Include
                    </label>
                  </div>
                  <p className="mt-2 text-xs text-muted">{item.specification}</p>
                  <p className="mt-2 text-xs text-muted">{item.relation}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {dropped.length ? (
        <Card className="mt-6 bg-white/85">
          <CardHeader>
            <CardTitle>Already mastered</CardTitle>
            <p className="text-sm text-muted">We will skip these for now.</p>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {dropped.map((item) => (
              <div key={item.id} className="rounded-2xl border border-peach/60 bg-white/70 p-3">
                <p className="text-sm font-semibold text-ink">{item.name}</p>
                <p className="text-xs text-muted">Score {item.mastery_score.toFixed(2)}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted">
          {confirmList.length + keep.length} topics will be included in your lesson path.
        </p>
        <Button onClick={handleFinalize} disabled={loading}>
          Start lessons
        </Button>
      </div>
    </main>
  )
}
