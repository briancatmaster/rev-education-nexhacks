import { useMemo, useEffect, useState, useCallback } from "react"
import { useParams } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import TransitionLink from "@/components/TransitionLink"
import type { Lesson, LessonPlan } from "@/lib/lesson-plan"
import { supabase, getMaterialContent, type MaterialContent, type ImageRef } from "@/lib/supabase"

const typeCopy: Record<Lesson["type"], string> = {
  reading: "Annotated reading",
  video: "Embedded lecture",
  problem: "Guided problem set",
  lab: "Hands-on lab",
}

type MaterialData = {
  id: string
  title?: string
  url?: string
  material_type: string
  extracted_concepts?: Array<{ label: string; type: string }>
}

export default function LessonDetailView() {
  const params = useParams<{ lessonId: string }>()
  const [materials, setMaterials] = useState<MaterialData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [materialContents, setMaterialContents] = useState<Map<string, MaterialContent>>(new Map())
  const [isLoadingContent, setIsLoadingContent] = useState(false)

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

  // Fetch materials from Supabase
  useEffect(() => {
    const fetchMaterials = async () => {
      setIsLoading(true)
      try {
        // Get session_id from localStorage or URL params
        const sessionId = localStorage.getItem("sessionId")
        if (sessionId) {
          const { data, error } = await supabase
            .from("academia_materials")
            .select("*")
            .eq("session_id", sessionId)
            .order("created_at", { ascending: false })

          if (error) {
            console.error("Error fetching materials:", error)
          } else if (data) {
            setMaterials(data)
          }
        }
      } catch (e) {
        console.error("Failed to fetch materials:", e)
      } finally {
        setIsLoading(false)
      }
    }

    fetchMaterials()
  }, [])

  // Fetch content from storage for materials that have been processed
  useEffect(() => {
    const fetchMaterialContents = async () => {
      if (materials.length === 0) return

      setIsLoadingContent(true)
      const newContents = new Map<string, MaterialContent>()

      try {
        // Fetch content for each processed material in parallel
        const contentPromises = materials.map(async (material) => {
          try {
            const content = await getMaterialContent(material.id)
            if (content) {
              newContents.set(material.id, content)
            }
          } catch (e) {
            console.error(`Failed to fetch content for material ${material.id}:`, e)
          }
        })

        await Promise.all(contentPromises)
        setMaterialContents(newContents)
      } catch (e) {
        console.error("Failed to fetch material contents:", e)
      } finally {
        setIsLoadingContent(false)
      }
    }

    fetchMaterialContents()
  }, [materials])

  if (!plan) {
    return (
      <div className="rounded-3xl border border-peach/60 bg-white/80 p-8">
        <h1 className="font-serif text-2xl text-ink">No lesson plan found</h1>
        <p className="mt-2 text-sm text-muted">
          Create your learning path first to generate a personalized lesson plan.
        </p>
        <div className="mt-4">
          <Button asChild>
            <TransitionLink to="/learn">Build learning path</TransitionLink>
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

  // Get relevant materials for this lesson type
  const relevantMaterials = materials.filter(m => {
    if (lesson.lesson.type === "reading") return m.material_type === "paper_read"
    if (lesson.lesson.type === "problem") return m.material_type === "educational_problems"
    return true
  })

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
            This lesson pulls from your uploaded materials and guides you through the concepts
            with in-context highlights. Everything stays inside the arXlearn interface.
          </p>

          {/* Show relevant materials if any */}
          {relevantMaterials.length > 0 && (
            <div className="rounded-2xl border border-peach/60 bg-white/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted mb-3">
                Related Materials
              </p>
              <div className="space-y-2">
                {relevantMaterials.slice(0, 3).map((material) => (
                  <div key={material.id} className="flex items-start gap-2">
                    <span className="text-ink font-medium">{material.title || "Untitled"}</span>
                    {material.url && (
                      <a
                        href={material.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-500 hover:underline"
                      >
                        View
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {relevantMaterials.length === 0 && !isLoading && (
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500 mb-2">
                No materials yet
              </p>
              <p className="text-gray-600">
                Add relevant papers or resources in the onboarding to see them here.
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
            <div className="min-h-[220px] rounded-2xl border border-ink/10 bg-cream text-ink overflow-hidden">
              {isLoading || isLoadingContent ? (
                <div className="flex items-center justify-center h-full p-4">
                  Loading content...
                </div>
              ) : relevantMaterials.length > 0 ? (
                <div className="p-4 space-y-4">
                  {/* Show images from storage if available */}
                  {relevantMaterials.some(m => materialContents.has(m.id)) ? (
                    <div className="space-y-4">
                      {relevantMaterials.map((material) => {
                        const content = materialContents.get(material.id)
                        if (!content) return null

                        return (
                          <div key={material.id} className="space-y-3">
                            <p className="font-medium text-sm">{material.title || "Untitled"}</p>

                            {/* Display images from storage */}
                            {content.image_refs && content.image_refs.length > 0 && (
                              <div className="grid grid-cols-2 gap-2">
                                {content.image_refs.slice(0, 4).map((img) => (
                                  <div key={img.index} className="relative aspect-video overflow-hidden rounded-lg border border-gray-200">
                                    {img.url ? (
                                      <img
                                        src={img.url}
                                        alt={img.alt || img.description || `Figure ${img.index}`}
                                        className="w-full h-full object-contain bg-white"
                                        loading="lazy"
                                      />
                                    ) : (
                                      <div className="flex items-center justify-center h-full bg-gray-100 text-gray-400 text-xs">
                                        Image unavailable
                                      </div>
                                    )}
                                    {(img.alt || img.description) && (
                                      <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 truncate">
                                        {img.alt || img.description}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Show compressed text preview */}
                            {content.text && (
                              <p className="text-xs text-gray-600 line-clamp-3">
                                {content.text.slice(0, 300)}...
                              </p>
                            )}

                            {/* Show metadata */}
                            {content.metadata && (
                              <div className="flex gap-2 text-xs text-gray-500">
                                <span>{content.metadata.compressed_tokens} tokens</span>
                                <span>•</span>
                                <span>{content.metadata.figure_count} figures</span>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="text-sm text-gray-600 mb-2">
                        Content will be generated from your {relevantMaterials.length} uploaded material(s)
                      </p>
                      <Button size="sm">Generate lesson content</Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full p-4">
                  Add materials to generate lesson content
                </div>
              )}
            </div>
            <p>
              Each time you complete an activity, we search your materials and embed the next
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
              {materials.filter(m => m.material_type === "educational_problems").length > 0 ? (
                <>
                  <p className="text-ink">
                    {materials.filter(m => m.material_type === "educational_problems").length} problem set(s) available
                  </p>
                  <Button size="sm" className="mt-3">
                    Load exercises
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-ink">
                    No problem sets uploaded yet. Add educational materials in onboarding.
                  </p>
                  <Button size="sm" className="mt-3" asChild>
                    <TransitionLink to="/onboarding">Add materials</TransitionLink>
                  </Button>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Show extracted concepts if available */}
      {materials.some(m => m.extracted_concepts && m.extracted_concepts.length > 0) && (
        <Card className="bg-white/85">
          <CardHeader>
            <Badge variant="neutral">Knowledge Graph</Badge>
            <CardTitle className="mt-4">Concepts extracted from your materials</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {materials
                .flatMap(m => m.extracted_concepts || [])
                .slice(0, 20)
                .map((concept, i) => (
                  <span
                    key={i}
                    className="px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700 border border-gray-200"
                  >
                    {concept.label}
                  </span>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
