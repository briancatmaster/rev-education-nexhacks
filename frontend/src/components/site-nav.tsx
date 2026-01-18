"use client"

import { useEffect, useState } from "react"
import Link from "next/link"

import { Button } from "@/components/ui/button"

const navLinks = [
  { href: "/onboarding", label: "Learning Origin" },
  { href: "/lessons", label: "Lessons" },
]

export default function SiteNav() {
  const [isScrolled, setIsScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10)
    }
    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  return (
    <header className={`sticky top-0 z-50 transition-all duration-300 ${
      isScrolled 
        ? "border-b border-peach/60 bg-paper/80 backdrop-blur shadow-sm" 
        : ""
    }`}>
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-[8vw] py-4">
        <div className="flex items-center gap-4">
          <p className="text-sm font-semibold text-ink">
            arXlearn PhD level learning in half the time
          </p>
        </div>

        <nav className="flex items-center gap-6 text-sm font-semibold text-ink">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="hover:text-cobalt">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
