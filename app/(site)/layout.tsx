import type { ReactNode } from "react"

import SiteNav from "@/components/site-nav"

export default function SiteLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <SiteNav />
      {children}
    </div>
  )
}
