import Link from "next/link"
import { Button } from "@/components/ui/button"
import SchoolCarousel from "@/components/school-carousel"

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-hero px-[8vw] py-8 text-ink sm:py-10 flex flex-col">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-28 right-[-8%] h-72 w-72 rounded-full bg-cobalt/20 blur-[120px]" />
        <div className="absolute bottom-[-18%] left-[-10%] h-96 w-96 rounded-full bg-lime/35 blur-[140px]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(10,15,31,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(10,15,31,0.04)_1px,transparent_1px)] bg-[size:72px_72px]" />
      </div>
      <section className="mx-auto max-w-6xl flex-1 flex items-center">
        <div className="max-w-3xl space-y-6">
          <h1 className="font-serif text-4xl leading-tight sm:text-6xl">
            Curate the world's best research into a lesson built for your mind.
          </h1>
          <p className="text-lg leading-relaxed text-muted">
            We ingest MIT OpenCourseWare, peer-reviewed papers, and problem sets, then
            embed them into an interactive flow. AI annotates and sequences what already
            exists so learning stays rigorous without leaving the platform.
          </p>
          <div className="pt-4">
            <Link href="/origin">
              <Button size="lg">Begin learning</Button>
            </Link>
          </div>
        </div>
      </section>
      <SchoolCarousel />
    </main>
  )
}
