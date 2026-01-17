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
      <main className="relative min-h-screen overflow-hidden bg-hero px-[8vw] py-16 text-ink sm:py-20">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-32 right-[-12%] h-80 w-80 rounded-full bg-teal/15 blur-[120px]" />
          <div className="absolute bottom-[-20%] left-[-12%] h-96 w-96 rounded-full bg-amber/20 blur-[140px]" />
          <div className="absolute left-1/2 top-20 h-px w-[60%] -translate-x-1/2 bg-peach/70" />
        </div>
        <section className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-teal">
                NexHacks Learning
              </p>
              <span className="h-px flex-1 bg-peach/80" />
            </div>
            <h1 className="font-serif text-4xl leading-tight sm:text-5xl">
              Learn any domain by translating it into the language you already know.
            </h1>
            <p className="text-lg leading-relaxed text-muted">
              We build a custom, LLM-augmented learning path that maps new ideas to your
              existing strengths in math, vocabulary, and field expertise. Instead of
              generating content, we aggregate and annotate the best resources into a
              guided, interactive literature review.
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
              Create your custom PhD profile and start learning in-context.
            </p>
            <div className="flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-muted">
              <span className="rounded-full border border-peach/70 bg-white/70 px-3 py-1">
                Annotate, don’t replace
              </span>
              <span className="rounded-full border border-peach/70 bg-white/70 px-3 py-1">
                Context-aware problems
              </span>
            </div>
          </div>

          <div className="relative grid place-items-center">
            <div className="absolute h-60 w-60 rounded-full border border-ink/10 border-dashed animate-spinSlow" />
            <Card className="w-full max-w-sm bg-gradient-to-br from-white via-paper to-peach/30 animate-float">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber">
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
              Read, highlight, and pull definitions without leaving the flow.
            </h2>
            <p className="text-base leading-relaxed text-muted">
              Instead of a chat box, learners explore curated sources with inline help.
              Highlight any unfamiliar phrase to get a definition, related paper, or a
              quick transfer example from their own field.
            </p>
            <div className="rounded-2xl border border-peach/50 bg-white/70 p-6 shadow-float">
              <p className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-amber">
                Common misconception
              </p>
              <p className="text-base leading-relaxed text-ink">
                Knowledge tracing simply counts how many questions a student gets right or
                wrong. It misses the deeper structure in how understanding evolves.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            <Card className="bg-white/90">
              <CardHeader>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal">
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
                      <span className="cursor-help rounded-md bg-amber/20 px-2 py-1 font-semibold text-ink ring-1 ring-amber/30">
                        deep learning architectures
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      Neural networks that model sequential student interactions and infer
                      latent mastery over time.
                    </TooltipContent>
                  </Tooltip>
                  . We highlight terms like this and attach quick definitions or a paper
                  recommendation.
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

            <div className="rounded-2xl border border-teal/20 bg-teal/5 p-6">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-teal">
                In-context prompt
              </p>
              <p className="mt-3 text-base text-ink">
                "Map this to my bioinformatics background and suggest a 3-step refresher on
                differential equations before proceeding."
              </p>
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
      </main>
    </TooltipProvider>
  )
}
