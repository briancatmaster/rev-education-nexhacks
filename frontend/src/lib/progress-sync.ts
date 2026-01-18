/**
 * Progress Sync Library
 * 
 * Handles syncing lesson progress between localStorage (for speed)
 * and Supabase (for persistence across devices).
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

// Storage keys
export const STORAGE_KEYS = {
  currentActivity: "lesson_current_activity",
  topicProgress: "lesson_topic_progress",
  lessonProgress: "lesson_progress",
  lastSyncTime: "lesson_last_sync"
} as const

export type TopicProgress = {
  id: string
  topic_name: string
  mastery_level: number
  completed_at: string | null
}

export type LessonProgress = {
  session_id: string
  total_topics: number
  completed_topics: number
  average_mastery: number
  progress_percentage: number
  topics: TopicProgress[]
  last_updated: string
}

export type CurrentActivity = {
  activity_id: string
  topic_id: string
  topic_name: string
  started_at: string
}

/**
 * Save current activity to localStorage for quick access
 */
export function saveCurrentActivity(activity: CurrentActivity): void {
  try {
    localStorage.setItem(STORAGE_KEYS.currentActivity, JSON.stringify(activity))
  } catch (e) {
    console.error("[ProgressSync] Failed to save current activity:", e)
  }
}

/**
 * Get current activity from localStorage
 */
export function getCurrentActivity(): CurrentActivity | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.currentActivity)
    return stored ? JSON.parse(stored) : null
  } catch (e) {
    console.error("[ProgressSync] Failed to get current activity:", e)
    return null
  }
}

/**
 * Clear current activity from localStorage
 */
export function clearCurrentActivity(): void {
  localStorage.removeItem(STORAGE_KEYS.currentActivity)
}

/**
 * Save lesson progress to localStorage
 */
export function saveLessonProgress(progress: LessonProgress): void {
  try {
    localStorage.setItem(STORAGE_KEYS.lessonProgress, JSON.stringify({
      ...progress,
      last_updated: new Date().toISOString()
    }))
  } catch (e) {
    console.error("[ProgressSync] Failed to save lesson progress:", e)
  }
}

/**
 * Get lesson progress from localStorage
 */
export function getLessonProgress(): LessonProgress | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.lessonProgress)
    return stored ? JSON.parse(stored) : null
  } catch (e) {
    console.error("[ProgressSync] Failed to get lesson progress:", e)
    return null
  }
}

/**
 * Fetch fresh progress from Supabase and update localStorage
 */
export async function syncProgressFromServer(sessionId: string): Promise<LessonProgress | null> {
  try {
    const res = await fetch(`${API_BASE}/api/lesson/progress/${sessionId}`)
    const data = await res.json()

    if (data.success) {
      const progress: LessonProgress = {
        session_id: sessionId,
        total_topics: data.total_topics,
        completed_topics: data.completed_topics,
        average_mastery: data.average_mastery,
        progress_percentage: data.progress_percentage,
        topics: data.topics || [],
        last_updated: new Date().toISOString()
      }
      
      saveLessonProgress(progress)
      localStorage.setItem(STORAGE_KEYS.lastSyncTime, new Date().toISOString())
      
      return progress
    }
    
    return null
  } catch (e) {
    console.error("[ProgressSync] Failed to sync from server:", e)
    return null
  }
}

/**
 * Check if we need to sync (more than 5 minutes since last sync)
 */
export function needsSync(): boolean {
  const lastSync = localStorage.getItem(STORAGE_KEYS.lastSyncTime)
  if (!lastSync) return true
  
  const fiveMinutes = 5 * 60 * 1000
  const lastSyncTime = new Date(lastSync).getTime()
  return Date.now() - lastSyncTime > fiveMinutes
}

/**
 * Update topic mastery in localStorage (optimistic update)
 */
export function updateTopicMastery(topicId: string, mastery: number, completed: boolean): void {
  const progress = getLessonProgress()
  if (!progress) return
  
  const topicIndex = progress.topics.findIndex(t => t.id === topicId)
  if (topicIndex === -1) return
  
  progress.topics[topicIndex] = {
    ...progress.topics[topicIndex],
    mastery_level: mastery,
    completed_at: completed ? new Date().toISOString() : null
  }
  
  // Recalculate stats
  const completedTopics = progress.topics.filter(t => t.completed_at).length
  const totalMastery = progress.topics.reduce((sum, t) => sum + t.mastery_level, 0)
  
  progress.completed_topics = completedTopics
  progress.average_mastery = totalMastery / progress.total_topics
  progress.progress_percentage = (completedTopics / progress.total_topics) * 100
  
  saveLessonProgress(progress)
}

/**
 * Clear all progress data from localStorage
 */
export function clearAllProgress(): void {
  Object.values(STORAGE_KEYS).forEach(key => {
    localStorage.removeItem(key)
  })
}

/**
 * Get progress for a specific topic from localStorage
 */
export function getTopicProgress(topicId: string): TopicProgress | null {
  const progress = getLessonProgress()
  if (!progress) return null
  
  return progress.topics.find(t => t.id === topicId) || null
}
