import { NextResponse } from "next/server"

export async function POST(request: Request) {
  const payload = await request.json()
  const stage = payload.stage ?? "skills"
  const apiBase = process.env.LESSON_ORIGIN_API_URL

  if (!apiBase) {
    return NextResponse.json(
      {
        success: false,
        error: "Backend API not configured. Please set LESSON_ORIGIN_API_URL environment variable.",
      },
      { status: 503 }
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
