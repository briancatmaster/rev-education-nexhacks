import OriginForm from "./OriginForm"

export default function OriginPage() {
  return (
    <main className="relative min-h-screen bg-hero px-[8vw] py-14">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-28 right-[-8%] h-72 w-72 rounded-full bg-cobalt/20 blur-[120px]" />
        <div className="absolute bottom-[-18%] left-[-10%] h-96 w-96 rounded-full bg-lime/35 blur-[140px]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(10,15,31,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(10,15,31,0.04)_1px,transparent_1px)] bg-[size:72px_72px]" />
      </div>
      <div className="relative mx-auto max-w-6xl">
        <div className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr] items-start">
          <div className="space-y-6 lg:sticky lg:top-20">
            <h1 className="font-serif text-4xl sm:text-5xl leading-tight text-ink">
              Learn the Fundamentals from World-Class Papers, Professors, and Companies
            </h1>
            <p className="text-lg leading-relaxed text-muted">
              Instead of requiring you to spend semesters learning prerequisite knowledge that is not directly applicable to your research, arXlearn combines your previous experience, publications, and classes and compiles a customized curricula to help you perform better research.
            </p>
          </div>
          <OriginForm />
        </div>
      </div>
    </main>
  )
}
