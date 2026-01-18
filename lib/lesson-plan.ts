export type Lesson = {
  id: string
  title: string
  type: "reading" | "video" | "problem" | "lab"
}

export type LessonUnit = {
  id: string
  title: string
  description: string
  lessons: Lesson[]
}

export type LessonPlan = {
  id: string
  background: string
  target: string
  skills?: { id: string; name: string; level?: string }[]
  units: LessonUnit[]
}

export const demoPlan: LessonPlan = {
  id: "demo-plan",
  background: "Computational biology + linear algebra fundamentals",
  target: "Differential geometry for biophysics",
  skills: [
    { id: "skill-1", name: "Linear algebra", level: "Strong" },
    { id: "skill-2", name: "Calculus fundamentals", level: "Comfortable" },
  ],
  units: [
    {
      id: "unit-1",
      title: "Foundations in geometric intuition",
      description: "Map vectors, curvature, and manifolds to biological structure.",
      lessons: [
        { id: "lesson-1", title: "From proteins to manifolds", type: "reading" },
        { id: "lesson-2", title: "Curvature as energy landscapes", type: "video" },
        { id: "lesson-3", title: "Warm-up problem set", type: "problem" },
      ],
    },
    {
      id: "unit-2",
      title: "Differential geometry core tools",
      description: "Tensors, metrics, and geodesics with research examples.",
      lessons: [
        { id: "lesson-4", title: "Metrics and measurement", type: "reading" },
        { id: "lesson-5", title: "Geodesics lab", type: "lab" },
        { id: "lesson-6", title: "Check-in quiz", type: "problem" },
      ],
    },
    {
      id: "unit-3",
      title: "Research synthesis",
      description: "Annotated papers and embedded exercises from trusted sources.",
      lessons: [
        { id: "lesson-7", title: "Paper walk-through", type: "reading" },
        { id: "lesson-8", title: "Applied case study", type: "video" },
      ],
    },
  ],
}
