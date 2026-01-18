"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"

export default function OriginForm() {
  const router = useRouter()
  const [background, setBackground] = useState("")
  const [target, setTarget] = useState("")
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
          background,
          target,
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
    <Card className="bg-white/85">
      <CardHeader>
        <Badge variant="accent">Learning Origin</Badge>
        <CardTitle className="mt-4">
          {step === "origin"
            ? "Tell us what you know and where you want to go."
            : "Rate your current skill levels before we build the path."}
        </CardTitle>
        <p className="text-sm text-muted">
          {step === "origin"
            ? "The more context you share, the more precise the lesson path. Mention your strongest domains, tools, and the types of resources you trust."
            : "We start with the foundations. Tell us which prerequisites are solid and which need reinforcement so we can sequence the lessons correctly."}
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {step === "origin" ? (
            <>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-ink" htmlFor="background">
                  Your specialty + background
                </label>
                <Textarea
                  id="background"
                  value={background}
                  onChange={(event) => setBackground(event.target.value)}
                  placeholder=""
                  required
                />
                <p className="text-xs text-muted">
                  Include coursework, research domains, programming stacks, and papers you
                  already understand.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-ink" htmlFor="target">
                  What do you want to learn next?
                </label>
                <Textarea
                  id="target"
                  value={target}
                  onChange={(event) => setTarget(event.target.value)}
                  placeholder=""
                  required
                />
                <p className="text-xs text-muted">
                  Be specific about the topic and how you want the material framed.
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-4">
                {skills.map((skill, index) => (
                  <div key={skill.id} className="rounded-2xl border border-peach/60 bg-white/70 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-ink">{skill.name}</p>
                        <p className="text-xs text-muted">{skill.description}</p>
                      </div>
                      <Badge variant="neutral">{levelLabel[skill.level]}</Badge>
                    </div>
                    {skill.subskills.length ? (
                      <p className="mt-2 text-xs text-muted">
                        Subskills: {skill.subskills.join(", ")}
                      </p>
                    ) : null}
                    <input
                      type="range"
                      min={0}
                      max={5}
                      value={skill.level}
                      className="mt-3 w-full"
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

              <div className="space-y-2">
                <label className="text-sm font-semibold text-ink" htmlFor="customSkill">
                  Add another prerequisite you want to work on
                </label>
                <div className="flex flex-wrap gap-2">
                  <input
                    id="customSkill"
                    value={customSkill}
                    onChange={(event) => setCustomSkill(event.target.value)}
                    className="h-11 flex-1 rounded-xl border border-peach/80 bg-paper px-4 text-sm text-ink"
                    placeholder=""
                  />
                  <Button type="button" variant="outline" onClick={handleCustomSkill}>
                    Add skill
                  </Button>
                </div>
                <p className="text-xs text-muted">
                  We will search for sources whenever you move into a new skill unit.
                </p>
              </div>
            </>
          )}

          {message ? <p className="text-xs text-amber">{message}</p> : null}

          <Button type="submit" size="lg" disabled={status === "loading"}>
            {status === "loading"
              ? "Working..."
              : step === "origin"
              ? "Map my prerequisites"
              : "Start the journey"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
