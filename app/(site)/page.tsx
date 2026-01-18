import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export default function Home() {
  return (
    <TooltipProvider>
      <main className="relative min-h-screen overflow-hidden bg-hero px-[8vw] py-8 text-ink sm:py-10">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-28 right-[-8%] h-72 w-72 rounded-full bg-cobalt/20 blur-[120px]" />
          <div className="absolute bottom-[-18%] left-[-10%] h-96 w-96 rounded-full bg-lime/35 blur-[140px]" />
          <div className="absolute left-1/2 top-16 h-px w-[70%] -translate-x-1/2 bg-peach/70" />
          <div className="absolute left-[12%] top-[22%] h-28 w-28 rounded-full border border-ink/10 bg-white/50" />
          <div className="absolute right-[22%] top-[42%] h-3 w-3 rounded-full bg-cobalt/70" />
          <div className="absolute inset-0 bg-[linear-gradient(rgba(10,15,31,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(10,15,31,0.04)_1px,transparent_1px)] bg-[size:72px_72px]" />
        </div>
        <section className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <p className="text-xs font-semibold text-cobalt">
                arXlearn
              </p>
              <span className="h-px flex-1 bg-peach/80" />
            </div>
            <p className="text-lg font-medium text-ink/80">PhD level learning in half the time</p>
            <h1 className="font-serif text-4xl leading-tight sm:text-6xl">
              Curate the world's best research into a lesson built for your mind.
            </h1>
            <p className="text-lg leading-relaxed text-muted">
              We ingest MIT OpenCourseWare, peer-reviewed papers, and problem sets, then
              embed them into an interactive flow. AI annotates and sequences what already
              exists so learning stays rigorous without leaving the platform.
            </p>
            <form className="flex flex-wrap gap-3">
              <Input
                aria-label="Email address"
                name="email"
                type="email"
                placeholder="you@university.edu"
                required
                className="min-w-[220px] flex-1"
              />
              <Button type="submit" size="lg">
                Join now
              </Button>
            </form>
            <p className="text-sm text-muted">
              Create your custom researcher profile and start learning in-context.
            </p>
            <div className="flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-muted">
              <span className="rounded-full border border-peach/70 bg-white/80 px-3 py-1">
                Aggregate, don’t generate
              </span>
              <span className="rounded-full border border-peach/70 bg-white/80 px-3 py-1">
                Embedded problem sets
              </span>
            </div>
          </div>

          <div className="relative grid place-items-center">
            <div className="absolute h-64 w-64 rounded-full border border-ink/10 border-dashed animate-spinSlow" />
            <Card className="w-full max-w-sm bg-gradient-to-br from-white via-paper to-peach/40 animate-float">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cobalt">
                  Your Translation Map
                </p>
                <CardTitle>Biophysics → Differential Geometry</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted">
                <p>Skill baseline: Linear algebra 82%</p>
                <p>New topic path: 14 steps</p>
                <p>Contextual problems: 36</p>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="mx-auto mt-20 grid max-w-6xl gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <Badge variant="accent">Interactive lesson preview</Badge>
            <h2 className="font-serif text-3xl">
              Read, highlight, and explore sources without leaving the flow.
            </h2>
            <p className="text-base leading-relaxed text-muted">
              Instead of a chat box, learners explore curated sources with inline help.
              Highlight any unfamiliar phrase to get a definition, a related paper, or a
              transfer example from their own field.
            </p>
            <div className="rounded-2xl border border-peach/50 bg-white/70 p-6 shadow-float">
              <p className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-cobalt">
                Embedded source pack
              </p>
              <div className="space-y-3 text-sm text-muted">
                <div className="flex items-center justify-between rounded-xl border border-peach/40 bg-white/80 px-4 py-3">
                  <div>
                    <p className="text-ink">MIT OCW: Knowledge Tracing Lecture</p>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted">Lecture notes</p>
                  </div>
                  <Badge>Integrated</Badge>
                </div>
                <div className="flex items-center justify-between rounded-xl border border-peach/40 bg-white/80 px-4 py-3">
                  <div>
                    <p className="text-ink">Nature: Deep Learning for Education</p>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted">Research paper</p>
                  </div>
                  <Badge variant="accent">Annotated</Badge>
                </div>
                <div className="flex items-center justify-between rounded-xl border border-peach/40 bg-white/80 px-4 py-3">
                  <div>
                    <p className="text-ink">Codeacademy: Sequence Models Lab</p>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted">Hands-on lab</p>
                  </div>
                  <Badge>Embedded</Badge>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <Card className="bg-white/90">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cobalt">
                  Annotated reading
                </p>
                <CardTitle>Adaptive knowledge tracing</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-muted">
                <p>
                  Different models exist for knowledge tracing, from statistical approaches
                  to more complex
                  {" "}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="cursor-help rounded-md bg-lime/70 px-2 py-1 font-semibold text-ink ring-1 ring-lime/60">
                        deep learning architectures
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      Neural networks that model sequential student interactions and infer
                      latent mastery over time.
                    </TooltipContent>
                  </Tooltip>
                  . We highlight terms like this and attach definitions, diagrams, or a
                  source excerpt.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm">
                    Simplify
                  </Button>
                  <Button variant="outline" size="sm">
                    Go deeper
                  </Button>
                  <Button variant="ghost" size="sm">
                    Show papers
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="rounded-2xl border border-cobalt/20 bg-cobalt/5 p-6">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cobalt">
                Lesson sequencer
              </p>
              <p className="mt-3 text-base text-ink">
                The AI sequences the best sources, then injects embedded problems and
                checks for understanding without asking you to leave the page.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs uppercase tracking-[0.2em] text-muted">
                <span className="rounded-full border border-cobalt/20 bg-white/80 px-3 py-1">
                  Problem set
                </span>
                <span className="rounded-full border border-cobalt/20 bg-white/80 px-3 py-1">
                  Code lab
                </span>
                <span className="rounded-full border border-cobalt/20 bg-white/80 px-3 py-1">
                  Reflection
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-20 grid max-w-6xl gap-8 lg:grid-cols-3">
          <Card className="bg-white/85">
            <CardHeader>
              <Badge>Checkpoint question</Badge>
              <CardTitle className="mt-4">Why do LSTMs help model learning over time?</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted">
              Short answer boxes keep the learner active, then we score for strength vs.
              improvement before the next resource appears.
            </CardContent>
          </Card>
          <Card className="bg-white/85">
            <CardHeader>
              <Badge variant="accent">Skill calibration</Badge>
              <CardTitle className="mt-4">We tune difficulty by your profile</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted">
              Math fluency, coding, and domain vocabulary inform which problems appear and
              which terms get annotated.
            </CardContent>
          </Card>
          <Card className="bg-white/85">
            <CardHeader>
              <Badge variant="neutral">Aggregated sources</Badge>
              <CardTitle className="mt-4">Literature review in one timeline</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted">
              AI curates existing papers, lectures, and notes, then annotates the through
              line instead of replacing them.
            </CardContent>
          </Card>
        </section>

        <section className="mx-auto mt-20 max-w-6xl">
          <div className="rounded-3xl border border-peach/60 bg-[length:200%_200%] bg-nebula p-8 text-ink shadow-float animate-shimmer">
            <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-3">
                <Badge variant="accent">How it really works</Badge>
                <h3 className="font-serif text-2xl">
                  AI curates the learning path and embeds the best sources directly into
                  the lesson.
                </h3>
                <p className="text-sm text-muted">
                  We are not asking AI to replace instructors. It chooses reputable sources
                  and stitches them into an interactive sequence with annotations, prompts,
                  and embedded exercises that live inside the platform.
                </p>
              </div>
              <div className="space-y-3 text-sm text-muted">
                <div className="rounded-2xl border border-white/60 bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted">Source mix</p>
                  <p className="mt-2 text-ink">MIT OCW, arXiv, Nature, code labs, problem sets</p>
                </div>
                <div className="rounded-2xl border border-white/60 bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted">Your role</p>
                  <p className="mt-2 text-ink">Highlight, answer, and iterate with targeted checks.</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </TooltipProvider>
  )
}
