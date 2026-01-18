import { NextResponse } from "next/server"

import { demoPlan } from "@/lib/lesson-plan"

export async function POST(request: Request) {
  const payload = await request.json()
  const stage = payload.stage ?? "skills"
  const apiBase = process.env.LESSON_ORIGIN_API_URL

  if (!apiBase) {
    if (stage === "skills") {
      return NextResponse.json(
        {
          success: true,
          skills: {
            skills: [
              {
                id: "skill-1",
                name: "Optimization basics",
                description: "Gradient-based learning foundations.",
                subskills: ["Gradient descent", "Loss functions", "Regularization"],
              },
              {
                id: "skill-2",
                name: "Neural network mechanics",
                description: "Core architecture and training loops.",
                subskills: ["Backpropagation", "Activation functions", "Initialization"],
              },
            ],
          },
          source: "demo",
        },
        { status: 200 }
      )
    }

    return NextResponse.json(
      {
        success: true,
        plan: {
          ...demoPlan,
          background: payload.background ?? demoPlan.background,
          target: payload.target ?? demoPlan.target,
          skills: payload.skills ?? [],
        },
        source: "demo",
      },
      { status: 200 }
    )
  }

  const endpoint =
    stage === "skills" ? `${apiBase}/generate-skills` : `${apiBase}/generate-plan`

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })

    const data = await response.json()

    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: "Unable to reach lesson origin service.",
      },
      { status: 502 }
    )
  }
}
