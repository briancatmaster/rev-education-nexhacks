import { useEffect, useRef, useState } from "react"

const TOP_SCHOOLS = [
  { name: "MIT", logo: "/logos/mit.png" },
  { name: "Stanford", logo: "/logos/stanford.png" },
  { name: "Harvard", logo: "/logos/harvard.png" },
  { name: "Caltech", logo: "/logos/caltech.png" },
  { name: "Princeton", logo: "/logos/princeton.png" },
  { name: "Yale", logo: "/logos/yale.png" },
  { name: "Columbia", logo: "/logos/columbia.png" },
  { name: "UC Berkeley", logo: "/logos/berkeley.png" },
  { name: "UChicago", logo: "/logos/uchicago.png" },
  { name: "Cornell", logo: "/logos/cornell.png" },
  { name: "Penn", logo: "/logos/penn.png" },
  { name: "Duke", logo: "/logos/duke.png" },
]

export default function SchoolCarousel() {
  const [offset, setOffset] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const interval = setInterval(() => {
      setOffset((prev) => prev - 1)
    }, 30)

    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (containerRef.current && offset < -containerRef.current.scrollWidth / 2) {
      setOffset(0)
    }
  }, [offset])

  const doubledSchools = [...TOP_SCHOOLS, ...TOP_SCHOOLS]

  return (
    <div className="w-full overflow-hidden py-8 border-t border-ink/10">
      <p className="text-center text-lg text-muted mb-6">Learn from the best at</p>
      <div className="relative">
        <div
          ref={containerRef}
          className="flex gap-6 items-center"
          style={{ transform: `translateX(${offset}px)` }}
        >
          {doubledSchools.map((school, index) => (
            <div
              key={`${school.name}-${index}`}
              className="flex-shrink-0 flex items-center justify-center h-16 w-28 grayscale opacity-70 hover:grayscale-0 hover:opacity-100 transition-all"
            >
              <img
                src={school.logo}
                alt={school.name}
                width={112}
                height={64}
                className="object-contain h-full w-full"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
