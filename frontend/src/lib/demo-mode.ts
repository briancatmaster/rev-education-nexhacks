import { STORAGE_KEYS } from "./progress-sync"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

const DEMO_RUN_KEY = "demo_run_id"
const DEMO_MODE_KEY = "demo_mode"

const RESET_KEYS = [
  "sessionId",
  "onboarding_scene",
  "onboarding_nodes",
  "onboarding_topic",
  "onboarding_userId",
  "learningPath",
]

export async function syncDemoMode(): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/api/demo/status`)
    if (!res.ok) return

    const data = await res.json()
    if (!data?.demo_mode) return

    const runId = data.demo_run_id
    const storedRunId = localStorage.getItem(DEMO_RUN_KEY)

    if (storedRunId !== runId) {
      RESET_KEYS.forEach((key) => localStorage.removeItem(key))
      Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key))
      localStorage.setItem(DEMO_RUN_KEY, runId)
      localStorage.setItem(DEMO_MODE_KEY, "true")
    }
  } catch {
    // No-op: if demo status can't be fetched, don't block app load.
  }
}
