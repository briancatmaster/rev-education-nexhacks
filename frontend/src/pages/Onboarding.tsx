"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"

type KnowledgeNode = {
  label: string
  domain?: string
  type?: string
  confidence?: number
  mastery_estimate?: number
  relevance_to_topic?: string
  parent_node?: string
  source_papers?: number[]
}

type Scene = "topic" | "background" | "papers"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

export default function OnboardingPage() {
  const navigate = useNavigate()
  
  // User & session state
  const [userId, setUserId] = useState<number | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [centralTopic, setCentralTopic] = useState("")
  
  // Scene state
  const [scene, setScene] = useState<Scene>("topic")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Knowledge graph state
  const [nodes, setNodes] = useState<KnowledgeNode[]>([])
  
  // Background scene state
  const [backgroundChoice, setBackgroundChoice] = useState<"cv" | "describe" | "skip" | null>(null)
  const [description, setDescription] = useState("")
  const cvRef = useRef<HTMLInputElement>(null)
  const [cvFile, setCvFile] = useState<File | null>(null)
  
  // Papers scene state
  const [paperLinks, setPaperLinks] = useState<string[]>([])
  const [currentLink, setCurrentLink] = useState("")

  // Initialize user on mount
  const [userReady, setUserReady] = useState(false)
  
  useEffect(() => {
    const initUser = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/user/new`, { method: "POST" })
        const data = await res.json()
        setUserId(data.user_id)
        setUserReady(true)
      } catch (e) {
        console.error("Failed to create user:", e)
        setError("Failed to connect to server. Is the backend running?")
      }
    }
    initUser()
  }, [])

  // Scene 1: Topic submission
  const handleTopicSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!centralTopic.trim()) return
    
    // If user not ready yet, show loading and wait
    if (!userId) {
      setError("Initializing... please try again in a moment.")
      return
    }
    
    setIsLoading(true)
    setError(null)
    
    try {
      const res = await fetch(`${API_BASE}/api/session/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, central_topic: centralTopic })
      })
      const data = await res.json()
      setSessionId(data.session_id)
      window.localStorage.setItem("sessionId", data.session_id)
      window.localStorage.setItem("centralTopic", centralTopic)
      window.localStorage.setItem("userId", String(userId))
      window.localStorage.removeItem("lessonPlan")
      window.localStorage.removeItem("orderedPrereqs")
      window.localStorage.removeItem("topicProgress")
      
      // Add central topic as first node
      setNodes([{ label: centralTopic, type: "concept", confidence: 1.0 }])
      setScene("background")
    } catch (e) {
      setError("Failed to create session. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  // Scene 2: Background submission
  const handleCVUpload = async () => {
    if (!cvFile || !sessionId || !userId) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      const formData = new FormData()
      formData.append("file", cvFile)
      formData.append("session_id", sessionId)
      formData.append("user_id", userId.toString())
      
      const res = await fetch(`${API_BASE}/api/profile/cv`, {
        method: "POST",
        body: formData
      })
      const data = await res.json()
      
      if (data.success) {
        setNodes(prev => [...prev, ...data.nodes])
        setScene("papers")
      } else {
        setError(data.error || "Failed to process CV")
      }
    } catch (e) {
      setError("Failed to upload CV. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleDescriptionSubmit = async () => {
    if (!description.trim() || !sessionId || !userId) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      const res = await fetch(`${API_BASE}/api/profile/background`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description,
          session_id: sessionId,
          user_id: userId
        })
      })
      const data = await res.json()
      
      if (data.success) {
        setNodes(prev => [...prev, ...data.nodes])
        setScene("papers")
      } else {
        setError(data.error || "Failed to process background")
      }
    } catch (e) {
      setError("Failed to submit background. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSkipBackground = () => {
    setScene("papers")
  }

  // Scene 3: Papers submission
  const addPaperLink = () => {
    if (currentLink.trim()) {
      setPaperLinks(prev => [...prev, currentLink.trim()])
      setCurrentLink("")
    }
  }

  const removePaperLink = (index: number) => {
    setPaperLinks(prev => prev.filter((_, i) => i !== index))
  }

  const handlePapersSubmit = async () => {
    if (paperLinks.length === 0 || !sessionId || !userId) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      const res = await fetch(`${API_BASE}/api/profile/papers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          papers: paperLinks.map(url => ({ url, title: url })),
          session_id: sessionId,
          user_id: userId
        })
      })
      const data = await res.json()
      
      if (data.success) {
        setNodes(prev => [...prev, ...data.nodes])
        // Navigate to lessons or graph view
        navigate("/prereqs")
      } else {
        setError(data.error || "Failed to process papers")
      }
    } catch (e) {
      setError("Failed to submit papers. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSkipPapers = () => {
    navigate("/prereqs")
  }

  // Render knowledge graph visualization (simplified)
  const renderGraph = useCallback(() => {
    if (nodes.length === 0) return null
    
    return (
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {/* Ambient background nodes */}
        {nodes.map((node, i) => {
          const angle = (i / nodes.length) * Math.PI * 2
          const radius = 150 + (i * 20)
          const x = 50 + Math.cos(angle) * (radius / 5)
          const y = 50 + Math.sin(angle) * (radius / 8)
          const opacity = scene === "topic" ? 0.15 : 0.4 + (node.confidence || 0.5) * 0.4
          const scale = 0.8 + (node.mastery_estimate || node.confidence || 0.5) * 0.4
          
          return (
            <div
              key={i}
              className="absolute transition-all duration-1000 ease-out"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                transform: `translate(-50%, -50%) scale(${scale})`,
                opacity
              }}
            >
              <div className={`
                px-3 py-1.5 rounded-full text-xs font-medium
                ${node.type === "domain" ? "bg-cobalt/20 text-cobalt border border-cobalt/30" : ""}
                ${node.type === "concept" ? "bg-lime/20 text-ink border border-lime/30" : ""}
                ${node.type === "method" ? "bg-amber/20 text-ink border border-amber/30" : ""}
                ${node.type === "theory" ? "bg-purple-500/20 text-purple-700 border border-purple-500/30" : ""}
                ${node.type === "tool" ? "bg-cyan-500/20 text-cyan-700 border border-cyan-500/30" : ""}
                ${!node.type ? "bg-ink/10 text-ink/70 border border-ink/20" : ""}
              `}>
                {node.label}
              </div>
            </div>
          )
        })}
      </div>
    )
  }, [nodes, scene])

  return (
    <main className="relative min-h-screen bg-hero overflow-hidden">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-28 right-[-8%] h-72 w-72 rounded-full bg-cobalt/20 blur-[120px]" />
        <div className="absolute bottom-[-18%] left-[-10%] h-96 w-96 rounded-full bg-lime/35 blur-[140px]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(10,15,31,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(10,15,31,0.04)_1px,transparent_1px)] bg-[size:72px_72px]" />
      </div>

      {/* Knowledge graph visualization */}
      {renderGraph()}

      {/* Scene 1: Topic Entry */}
      {scene === "topic" && (
        <div className="relative flex items-center justify-center min-h-screen px-8">
          <div className="w-full max-w-2xl text-center space-y-8">
            <h1 className="font-serif text-4xl sm:text-5xl text-ink leading-tight">
              What question is driving your research?
            </h1>
            
            <form onSubmit={handleTopicSubmit} className="space-y-4">
              <input
                type="text"
                value={centralTopic}
                onChange={(e) => setCentralTopic(e.target.value)}
                placeholder="e.g., How can we improve knowledge tracing in adaptive learning systems?"
                className="w-full text-lg px-6 py-4 rounded-2xl border-2 border-ink/10 bg-white/80 backdrop-blur-sm text-ink placeholder:text-muted/50 focus:outline-none focus:border-cobalt/50 focus:ring-4 focus:ring-cobalt/10 transition-all"
                autoFocus
                disabled={isLoading}
              />
              
              <p className="text-sm text-muted">
                {userReady ? "Press Enter to continue" : "Connecting to server..."}
              </p>
              
              {error && <p className="text-sm text-red-500">{error}</p>}
              
              {isLoading && (
                <div className="flex items-center justify-center gap-2 text-muted">
                  <div className="w-4 h-4 border-2 border-cobalt/30 border-t-cobalt rounded-full animate-spin" />
                  <span>Creating your knowledge space...</span>
                </div>
              )}
            </form>
          </div>
        </div>
      )}

      {/* Scene 2: Background Collection */}
      {scene === "background" && (
        <div className="relative flex items-end justify-center min-h-screen pb-12">
          <div className={`
            w-full max-w-xl mx-8 p-8 rounded-3xl border-2 border-ink/10 bg-white/90 backdrop-blur-md
            transform transition-all duration-500 ease-out
            ${backgroundChoice ? "translate-y-0" : "translate-y-4"}
          `}>
            <h2 className="font-serif text-2xl text-ink mb-2">What's your background?</h2>
            <p className="text-muted text-sm mb-6">Help us understand your existing knowledge</p>
            
            {!backgroundChoice ? (
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => {
                    setBackgroundChoice("cv")
                    cvRef.current?.click()
                  }}
                  className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-ink/10 hover:border-cobalt/40 hover:bg-cobalt/5 transition-all"
                >
                  <span className="text-2xl">📄</span>
                  <span className="text-sm font-medium text-ink">Upload CV</span>
                </button>
                
                <button
                  onClick={() => setBackgroundChoice("describe")}
                  className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-ink/10 hover:border-lime/40 hover:bg-lime/5 transition-all"
                >
                  <span className="text-2xl">✍️</span>
                  <span className="text-sm font-medium text-ink">I'll describe it</span>
                </button>
                
                <button
                  onClick={handleSkipBackground}
                  className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-ink/10 hover:border-ink/20 transition-all"
                >
                  <span className="text-2xl">⏭️</span>
                  <span className="text-sm font-medium text-muted">Skip</span>
                </button>
              </div>
            ) : backgroundChoice === "cv" ? (
              <div className="space-y-4">
                <input
                  type="file"
                  ref={cvRef}
                  accept=".pdf,.doc,.docx"
                  onChange={(e) => setCvFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                
                {cvFile ? (
                  <div className="flex items-center gap-3 p-4 rounded-xl bg-lime/10 border border-lime/30">
                    <span className="text-2xl">✅</span>
                    <span className="flex-1 text-sm text-ink truncate">{cvFile.name}</span>
                    <button onClick={() => setCvFile(null)} className="text-muted hover:text-ink">✕</button>
                  </div>
                ) : (
                  <button
                    onClick={() => cvRef.current?.click()}
                    className="w-full p-6 rounded-xl border-2 border-dashed border-ink/20 hover:border-cobalt/40 transition-all text-muted"
                  >
                    Click to select a file
                  </button>
                )}
                
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setBackgroundChoice(null)
                      setCvFile(null)
                    }}
                  >
                    Back
                  </Button>
                  <Button
                    onClick={handleCVUpload}
                    disabled={!cvFile || isLoading}
                    className="flex-1"
                  >
                    {isLoading ? "Processing..." : "Continue"}
                  </Button>
                </div>
              </div>
            ) : backgroundChoice === "describe" ? (
              <div className="space-y-4">
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe your academic background, research experience, courses taken, skills..."
                  rows={5}
                  className="w-full px-4 py-3 rounded-xl border-2 border-ink/10 bg-white/80 text-ink placeholder:text-muted/50 focus:outline-none focus:border-cobalt/50 resize-none"
                  autoFocus
                />
                
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setBackgroundChoice(null)
                      setDescription("")
                    }}
                  >
                    Back
                  </Button>
                  <Button
                    onClick={handleDescriptionSubmit}
                    disabled={!description.trim() || isLoading}
                    className="flex-1"
                  >
                    {isLoading ? "Analyzing..." : "Continue"}
                  </Button>
                </div>
              </div>
            ) : null}
            
            {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
          </div>
        </div>
      )}

      {/* Scene 3: Paper Ingestion */}
      {scene === "papers" && (
        <div className="relative flex items-center justify-center min-h-screen px-8">
          <div className="w-full max-w-2xl p-8 rounded-3xl border-2 border-ink/10 bg-white/90 backdrop-blur-md">
            <h2 className="font-serif text-2xl text-ink mb-2">Add papers you've already internalized</h2>
            <p className="text-muted text-sm mb-6">Paste arXiv/DOI links or paper titles</p>
            
            <div className="space-y-4">
              {/* Paper input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={currentLink}
                  onChange={(e) => setCurrentLink(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addPaperLink()}
                  placeholder="https://arxiv.org/abs/... or paper title"
                  className="flex-1 px-4 py-3 rounded-xl border-2 border-ink/10 bg-white/80 text-ink placeholder:text-muted/50 focus:outline-none focus:border-cobalt/50"
                />
                <Button onClick={addPaperLink} disabled={!currentLink.trim()}>
                  Add
                </Button>
              </div>
              
              {/* Paper list */}
              {paperLinks.length > 0 && (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {paperLinks.map((link, i) => (
                    <div key={i} className="flex items-center gap-2 p-3 rounded-lg bg-ink/5">
                      <span className="text-sm text-cobalt">📄</span>
                      <span className="flex-1 text-sm text-ink truncate">{link}</span>
                      <button
                        onClick={() => removePaperLink(i)}
                        className="text-muted hover:text-ink"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="flex gap-3 pt-4">
                <Button variant="outline" onClick={handleSkipPapers}>
                  Skip for now
                </Button>
                <Button
                  onClick={handlePapersSubmit}
                  disabled={paperLinks.length === 0 || isLoading}
                  className="flex-1"
                >
                  {isLoading ? "Analyzing papers..." : `Continue with ${paperLinks.length} paper${paperLinks.length !== 1 ? "s" : ""}`}
                </Button>
              </div>
              
              {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
            </div>
          </div>
        </div>
      )}

      {/* Node count indicator */}
      {nodes.length > 1 && (
        <div className="fixed bottom-6 right-6 px-4 py-2 rounded-full bg-white/90 backdrop-blur-sm border border-ink/10 shadow-lg">
          <span className="text-sm text-muted">
            <strong className="text-ink">{nodes.length}</strong> knowledge nodes
          </span>
        </div>
      )}
    </main>
  )
}
