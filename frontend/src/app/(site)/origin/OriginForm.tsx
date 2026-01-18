"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export default function OriginForm() {
  const router = useRouter()
  const [learningGoal, setLearningGoal] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle")
  const [step, setStep] = useState<"origin" | "skills">("origin")
  const [skills, setSkills] = useState<
    { id: string; name: string; description: string; subskills: string[]; level: number }[]
  >([])
  const [customSkill, setCustomSkill] = useState("")
  const [message, setMessage] = useState("")

  const levelLabel = useMemo(
    () => ["New", "Basic", "Comfortable", "Strong", "Advanced", "Expert"],
    []
  )

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setStatus("loading")
    setMessage("")

    try {
      const response = await fetch("/api/lesson-origin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          background: "",
          target: learningGoal,
          stage: step === "origin" ? "skills" : "plan",
          skills:
            step === "skills"
              ? skills.map((skill) => ({
                  id: skill.id,
                  name: skill.name,
                  level: levelLabel[skill.level],
                }))
              : undefined,
        }),
      })

      if (!response.ok) {
        throw new Error("Unable to generate plan")
      }

      const data = await response.json()
      if (step === "origin") {
        const nextSkills = (data.skills?.skills ?? []).map(
          (skill: { id: string; name: string; description: string; subskills: string[] }) => ({
            ...skill,
            level: 2,
          })
        )
        setSkills(nextSkills)
        setStep("skills")
        setStatus("idle")
        return
      }

      if (data.plan) {
        window.localStorage.setItem("lessonPlan", JSON.stringify(data.plan))
        setStatus("idle")
        router.push("/lessons")
      }
    } catch (error) {
      setStatus("error")
      setMessage("We couldn't generate a plan yet. Try again or refine your inputs.")
    }
  }

  const handleCustomSkill = () => {
    if (!customSkill.trim()) {
      return
    }
    setSkills((prev) => [
      ...prev,
      {
        id: `custom-${prev.length + 1}`,
        name: customSkill.trim(),
        description: "Custom focus area",
        subskills: [],
        level: 2,
      },
    ])
    setCustomSkill("")
  }

  return (
    <div className="w-full rounded-3xl border-2 border-ink/10 bg-white/70 backdrop-blur-sm p-8">
      <form onSubmit={handleSubmit} className="space-y-6">
        {step === "origin" ? (
          <>
            <div className="space-y-3">
              <label 
                htmlFor="learningGoal" 
                className="block text-sm font-semibold text-ink"
              >
                What do you want to learn?
              </label>
              <input
                id="learningGoal"
                type="text"
                value={learningGoal}
                onChange={(event) => setLearningGoal(event.target.value)}
                placeholder="Knowledge Tracing"
                required
                className="w-full text-base px-4 py-4 rounded-xl border-2 border-ink/10 bg-white/80 text-ink placeholder:text-muted/50 focus:outline-none focus:border-cobalt/50 focus:ring-4 focus:ring-cobalt/10 transition-all"
              />
            </div>
            
            <Button 
              type="submit" 
              size="lg"
              disabled={status === "loading"}
              className="w-full py-6 text-lg"
            >
              {status === "loading" ? "Generating..." : "Begin your journey →"}
            </Button>

            {message && (
              <p className="text-sm text-amber">{message}</p>
            )}
          </>
        ) : (
            <>
              <div className="space-y-2 mb-6">
                <h2 className="font-serif text-2xl text-ink">Rate your skill levels</h2>
                <p className="text-sm text-muted">Help us customize your learning path</p>
              </div>
              
              <div className="space-y-3">
                {skills.map((skill, index) => (
                  <div key={skill.id} className="rounded-xl border border-ink/10 bg-white/60 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-sm font-semibold text-ink">{skill.name}</p>
                        <p className="text-xs text-muted">{skill.description}</p>
                      </div>
                      <Badge variant="neutral">{levelLabel[skill.level]}</Badge>
                    </div>
                    {skill.subskills.length ? (
                      <p className="text-xs text-muted mb-2">
                        {skill.subskills.join(" • ")}
                      </p>
                    ) : null}
                    <input
                      type="range"
                      min={0}
                      max={5}
                      value={skill.level}
                      className="w-full accent-cobalt"
                      onChange={(event) => {
                        const value = Number(event.target.value)
                        setSkills((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, level: value } : item
                          )
                        )
                      }}
                    />
                  </div>
                ))}
              </div>

              <div className="space-y-2 mt-4">
                <label className="block text-sm font-semibold text-ink" htmlFor="customSkill">
                  Add another skill
                </label>
                <div className="flex gap-2">
                  <input
                    id="customSkill"
                    value={customSkill}
                    onChange={(event) => setCustomSkill(event.target.value)}
                    className="flex-1 h-11 rounded-xl border border-ink/10 bg-white/60 px-4 text-sm text-ink placeholder:text-muted/40 focus:outline-none focus:border-cobalt/50"
                    placeholder="e.g., Linear Algebra"
                  />
                  <Button type="button" variant="outline" onClick={handleCustomSkill}>
                    Add
                  </Button>
                </div>
              </div>
            </>
          )}

            {step === "skills" && message && (
              <p className="text-sm text-amber">{message}</p>
            )}
            
            {step === "skills" && (
              <Button type="submit" size="lg" className="w-full mt-4" disabled={status === "loading"}>
                {status === "loading" ? "Creating your path..." : "Start the journey →"}
              </Button>
            )}
      </form>
    </div>
  )
}
