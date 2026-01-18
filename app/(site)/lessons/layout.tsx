import type { ReactNode } from "react"

import LessonSidebar from "@/components/lesson-sidebar"

export default function LessonsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl gap-6 px-[6vw] py-10 lg:px-[8vw]">
      <div className="hidden w-[280px] shrink-0 lg:block">
        <LessonSidebar />
      </div>
      <div className="flex-1">
        <div className="mb-6 lg:hidden">
          <LessonSidebar compact />
        </div>
        {children}
      </div>
    </div>
  )
}
