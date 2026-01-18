import OriginForm from "./OriginForm"
import { Badge } from "@/components/ui/badge"

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
            arXlearn doesn't replace teachers. We assemble the best existing materials
            and embed them into a guided flow. Your origin tells us which sources to
            prioritize and how to translate new topics into your language.
          </p>
        </div>
        <OriginForm />
      </div>
    </main>
  )
}
