import Link from "next/link"

import { Button } from "@/components/ui/button"

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/origin", label: "Learning Origin" },
  { href: "/lessons", label: "Lessons" },
]

export default function SiteNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-peach/60 bg-paper/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-[8vw] py-4">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-ink/10 bg-white shadow-float">
            <span className="text-xl font-black text-ink">a</span>
          </div>
          <div>
            <p className="text-xs font-semibold text-cobalt">
              arXlearn
            </p>
            <p className="text-xs text-muted">PhD level learning in half the time</p>
          </div>
        </div>

        <nav className="hidden items-center gap-6 text-sm font-semibold text-ink md:flex">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="hover:text-cobalt">
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <Link href="/origin" className="hidden text-sm font-semibold text-ink/70 md:inline">
            Start the journey
          </Link>
          <Button size="sm">Join waitlist</Button>
        </div>
      </div>
    </header>
  )
}
