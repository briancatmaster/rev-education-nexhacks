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
