import OriginForm from "./OriginForm"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

export default function OriginPage() {
  return (
    <main className="mx-auto max-w-6xl px-[8vw] py-14">
      <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <Badge>Start here</Badge>
          <h1 className="font-serif text-4xl text-ink">
            Build a learning origin that captures your expertise.
          </h1>
          <p className="text-base text-muted">
            NexHacks doesn’t replace teachers. We assemble the best existing materials
            and embed them into a guided flow. Your origin tells us which sources to
            prioritize and how to translate new topics into your language.
          </p>
          <div className="grid gap-4">
            <Card className="bg-white/80">
              <CardContent className="p-5 text-sm text-muted">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">What we embed</p>
                <p className="mt-2 text-ink">
                  MIT OCW, peer-reviewed papers, annotated problem sets, labs, and
                  curated lectures — all displayed inside the platform.
                </p>
              </CardContent>
            </Card>
            <Card className="bg-white/80">
              <CardContent className="p-5 text-sm text-muted">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">How it adapts</p>
                <p className="mt-2 text-ink">
                  We tune the sequence based on your math fluency, coding comfort, and
                  domain vocabulary, so every unit feels mapped to your expertise.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
        <OriginForm />
      </div>
    </main>
  )
}
