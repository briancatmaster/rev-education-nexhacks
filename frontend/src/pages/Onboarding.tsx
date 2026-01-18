"use client"

import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
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

// Predefined decorative nodes for the background
const DECORATIVE_NODES = [
  { label: "Neurophysiology", x: 8, y: 12, z: 1, color: "blue" },
  { label: "Cognitive Neuroscience", x: 25, y: 8, z: 2, color: "green" },
  { label: "Brain Function", x: 15, y: 35, z: 1, color: "gray" },
  { label: "The importance of sleep on the brain", x: 5, y: 55, z: 3, color: "blue" },
  { label: "Memory Formation", x: 35, y: 22, z: 2, color: "green" },
  { label: "Neural Plasticity", x: 12, y: 75, z: 1, color: "gray" },
  { label: "Synaptic Transmission", x: 42, y: 45, z: 3, color: "blue" },
  { label: "Cortical Mapping", x: 28, y: 65, z: 2, color: "green" },
  { label: "Behavioral Psychology", x: 8, y: 88, z: 1, color: "gray" },
  { label: "Learning Theory", x: 48, y: 78, z: 2, color: "blue" },
  { label: "Motor Control", x: 55, y: 15, z: 1, color: "green" },
  { label: "Sensory Processing", x: 52, y: 55, z: 3, color: "gray" },
  { label: "Attention Networks", x: 18, y: 48, z: 2, color: "blue" },
  { label: "Executive Function", x: 38, y: 85, z: 1, color: "green" },
]

// Floating node component
function FloatingNode({ 
  label, 
  x, 
  y, 
  z, 
  color, 
  delay,
  isUserNode = false 
}: { 
  label: string
  x: number
  y: number
  z: number
  color: string
  delay: number
  isUserNode?: boolean
}) {
  const colorClasses = {
    blue: "bg-[#e3edf7] text-[#5a7a9a] border-[#d0e0ef]",
    green: "bg-[#e8f5ec] text-[#5a8a6a] border-[#d0eadb]",
    gray: "bg-[#f0f2f5] text-[#6a7a8a] border-[#e0e5eb]",
    user: "bg-white text-[#3a4a5a] border-[#c0d0e0] shadow-md"
  }

  const scaleByZ = 0.7 + (z * 0.15)
  const opacityByZ = isUserNode ? 0.95 : 0.4 + (z * 0.15)
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, y: 20 }}
      animate={{ 
        opacity: opacityByZ,
        scale: scaleByZ,
        y: 0,
      }}
      transition={{ 
        duration: 0.8, 
        delay: delay,
        ease: "easeOut"
      }}
      className="absolute pointer-events-none select-none"
      style={{ 
        left: `${x}%`, 
        top: `${y}%`,
        zIndex: z 
      }}
    >
      <motion.div
        animate={{
          y: [0, -6, 0],
          rotate: [-0.5, 0.5, -0.5]
        }}
        transition={{
          duration: 4 + z * 2,
          repeat: Infinity,
          ease: "easeInOut",
          delay: delay
        }}
      >
        <div 
          className={`
            px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap
            border backdrop-blur-sm
            ${isUserNode ? colorClasses.user : colorClasses[color as keyof typeof colorClasses]}
          `}
          style={{
            boxShadow: isUserNode 
              ? '0 4px 20px rgba(0,0,0,0.08)' 
              : '0 2px 8px rgba(0,0,0,0.04)'
          }}
        >
          {label}
        </div>
      </motion.div>
    </motion.div>
  )
}

// Connection lines between nodes (very subtle)
function ConnectionLines() {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
      <defs>
        <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#d0e0ef" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#d0eadb" stopOpacity="0.3" />
        </linearGradient>
      </defs>
      {/* Subtle connecting lines */}
      <motion.path
        d="M 100 80 Q 200 120 280 140"
        stroke="url(#lineGradient)"
        strokeWidth="1"
        fill="none"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 2, delay: 0.5 }}
      />
      <motion.path
        d="M 150 250 Q 250 200 350 180"
        stroke="url(#lineGradient)"
        strokeWidth="1"
        fill="none"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 2, delay: 0.8 }}
      />
      <motion.path
        d="M 80 400 Q 180 350 300 320"
        stroke="url(#lineGradient)"
        strokeWidth="1"
        fill="none"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 2, delay: 1.1 }}
      />
    </svg>
  )
}

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
  const [paperFiles, setPaperFiles] = useState<File[]>([])
  const paperFileRef = useRef<HTMLInputElement>(null)

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

  const addPaperFiles = (files: FileList | null) => {
    if (files) {
      setPaperFiles(prev => [...prev, ...Array.from(files)])
    }
  }

  const removePaperFile = (index: number) => {
    setPaperFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handlePapersSubmit = async () => {
    if ((paperLinks.length === 0 && paperFiles.length === 0) || !sessionId || !userId) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      let allNodes: KnowledgeNode[] = []
      
      if (paperLinks.length > 0) {
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
        
        if (data.success && data.nodes) {
          allNodes = [...allNodes, ...data.nodes]
        } else if (!data.success) {
          throw new Error(data.error || "Failed to process paper links")
        }
      }
      
      for (const file of paperFiles) {
        const formData = new FormData()
        formData.append("file", file)
        formData.append("session_id", sessionId)
        formData.append("user_id", userId.toString())
        formData.append("title", file.name.replace(/\.[^/.]+$/, ""))
        
        const res = await fetch(`${API_BASE}/api/profile/paper-file`, {
          method: "POST",
          body: formData
        })
        const data = await res.json()
        
        if (data.success && data.nodes) {
          allNodes = [...allNodes, ...data.nodes]
        }
      }
      
      if (allNodes.length > 0) {
        setNodes(prev => [...prev, ...allNodes])
      }
      
      navigate("/lessons")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit papers. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSkipPapers = () => {
    navigate("/lessons")
  }

  // Generate user nodes with positions
  const userNodes = useMemo(() => {
    return nodes.map((node, i) => ({
      ...node,
      x: 15 + (i % 3) * 18,
      y: 25 + Math.floor(i / 3) * 15 + (i % 2) * 8,
      z: 2 + (i % 2),
      delay: 0.3 + i * 0.15
    }))
  }, [nodes])

  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Soft gradient background */}
      <div 
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(135deg, #e8f4f8 0%, #eef6f4 40%, #e8f8f0 100%)'
        }}
      />
      
      {/* Subtle texture overlay */}
      <div 
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage: `radial-gradient(circle at 20% 30%, rgba(200, 220, 240, 0.4) 0%, transparent 50%),
                           radial-gradient(circle at 70% 70%, rgba(200, 240, 220, 0.3) 0%, transparent 50%)`
        }}
      />

      {/* Left 2/3: Knowledge Graph Visualization */}
      <div className="absolute inset-y-0 left-0 w-2/3 overflow-hidden">
        <ConnectionLines />
        
        {/* Decorative background nodes */}
        {DECORATIVE_NODES.map((node, i) => (
          <FloatingNode
            key={`decorative-${i}`}
            label={node.label}
            x={node.x}
            y={node.y}
            z={node.z}
            color={node.color}
            delay={0.1 + i * 0.08}
          />
        ))}
        
        {/* User-generated nodes */}
        <AnimatePresence>
          {userNodes.map((node, i) => (
            <FloatingNode
              key={`user-${i}-${node.label}`}
              label={node.label}
              x={node.x}
              y={node.y}
              z={node.z}
              color="user"
              delay={node.delay}
              isUserNode={true}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Right 1/3: Interactive Panel */}
      <div className="absolute inset-y-0 right-0 w-1/3 flex items-center justify-center p-8">
        <AnimatePresence mode="wait">
          {/* Scene 1: Topic Entry */}
          {scene === "topic" && (
            <motion.div
              key="topic"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.4 }}
              className="w-full max-w-md"
            >
              <div 
                className="p-8 rounded-2xl bg-white/95 backdrop-blur-sm border border-gray-100"
                style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.06)' }}
              >
                <h1 className="font-serif text-2xl text-gray-800 mb-2 leading-tight">
                  What question is driving your research?
                </h1>
                <p className="text-gray-500 text-sm mb-6">
                  Start building your knowledge graph
                </p>
                
                <form onSubmit={handleTopicSubmit} className="space-y-4">
                  <input
                    type="text"
                    value={centralTopic}
                    onChange={(e) => setCentralTopic(e.target.value)}
                    placeholder="e.g., How does sleep affect memory consolidation?"
                    className="w-full text-base px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 focus:ring-2 focus:ring-gray-100 transition-all"
                    autoFocus
                    disabled={isLoading}
                  />
                  
                  <Button
                    type="submit"
                    disabled={!centralTopic.trim() || isLoading || !userReady}
                    className="w-full bg-gray-800 hover:bg-gray-700 text-white py-3 rounded-xl transition-colors"
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                          className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
                        />
                        Creating...
                      </span>
                    ) : userReady ? (
                      "Continue"
                    ) : (
                      "Connecting..."
                    )}
                  </Button>
                  
                  {error && (
                    <p className="text-sm text-red-500 text-center">{error}</p>
                  )}
                </form>
              </div>
            </motion.div>
          )}

          {/* Scene 2: Background Collection */}
          {scene === "background" && (
            <motion.div
              key="background"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.4 }}
              className="w-full max-w-md"
            >
              <div 
                className="p-8 rounded-2xl bg-white/95 backdrop-blur-sm border border-gray-100"
                style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.06)' }}
              >
                <h2 className="font-serif text-2xl text-gray-800 mb-2">
                  What's your background?
                </h2>
                <p className="text-gray-500 text-sm mb-6">
                  Help us understand your existing knowledge
                </p>
                
                {!backgroundChoice ? (
                  <div className="space-y-3">
                    <button
                      onClick={() => {
                        setBackgroundChoice("cv")
                        cvRef.current?.click()
                      }}
                      className="w-full flex items-center gap-4 p-4 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
                    >
                      <span className="text-xl">📄</span>
                      <div>
                        <div className="font-medium text-gray-800">Upload CV</div>
                        <div className="text-sm text-gray-500">PDF or Word document</div>
                      </div>
                    </button>
                    
                    <button
                      onClick={() => setBackgroundChoice("describe")}
                      className="w-full flex items-center gap-4 p-4 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
                    >
                      <span className="text-xl">✍️</span>
                      <div>
                        <div className="font-medium text-gray-800">Describe it</div>
                        <div className="text-sm text-gray-500">Write a brief summary</div>
                      </div>
                    </button>
                    
                    <button
                      onClick={handleSkipBackground}
                      className="w-full flex items-center justify-center gap-2 p-3 text-gray-500 hover:text-gray-700 transition-colors"
                    >
                      <span>Skip for now</span>
                      <span>→</span>
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
                      <div className="flex items-center gap-3 p-4 rounded-xl bg-green-50 border border-green-200">
                        <span className="text-lg">✅</span>
                        <span className="flex-1 text-sm text-gray-700 truncate">{cvFile.name}</span>
                        <button 
                          onClick={() => setCvFile(null)} 
                          className="text-gray-400 hover:text-gray-600"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => cvRef.current?.click()}
                        className="w-full p-8 rounded-xl border-2 border-dashed border-gray-300 hover:border-gray-400 transition-all text-gray-500 hover:text-gray-600"
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
                        className="flex-1"
                      >
                        Back
                      </Button>
                      <Button
                        onClick={handleCVUpload}
                        disabled={!cvFile || isLoading}
                        className="flex-1 bg-gray-800 hover:bg-gray-700"
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
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 resize-none"
                      autoFocus
                    />
                    
                    <div className="flex gap-3">
                      <Button
                        variant="outline"
                        onClick={() => {
                          setBackgroundChoice(null)
                          setDescription("")
                        }}
                        className="flex-1"
                      >
                        Back
                      </Button>
                      <Button
                        onClick={handleDescriptionSubmit}
                        disabled={!description.trim() || isLoading}
                        className="flex-1 bg-gray-800 hover:bg-gray-700"
                      >
                        {isLoading ? "Analyzing..." : "Continue"}
                      </Button>
                    </div>
                  </div>
                ) : null}
                
                {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
              </div>
            </motion.div>
          )}

          {/* Scene 3: Paper Ingestion */}
          {scene === "papers" && (
            <motion.div
              key="papers"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.4 }}
              className="w-full max-w-md"
            >
              <div 
                className="p-8 rounded-2xl bg-white/95 backdrop-blur-sm border border-gray-100"
                style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.06)' }}
              >
                <h2 className="font-serif text-2xl text-gray-800 mb-2">
                  Add papers you've read
                </h2>
                <p className="text-gray-500 text-sm mb-6">
                  Paste arXiv/DOI links or upload PDFs
                </p>
                
                <div className="space-y-4">
                  {/* Paper link input */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={currentLink}
                      onChange={(e) => setCurrentLink(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPaperLink())}
                      placeholder="https://arxiv.org/abs/..."
                      className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 text-sm"
                    />
                    <Button 
                      onClick={addPaperLink} 
                      disabled={!currentLink.trim()}
                      variant="outline"
                    >
                      Add
                    </Button>
                  </div>
                  
                  {/* File upload */}
                  <input
                    type="file"
                    ref={paperFileRef}
                    accept=".pdf"
                    multiple
                    onChange={(e) => addPaperFiles(e.target.files)}
                    className="hidden"
                  />
                  <button
                    onClick={() => paperFileRef.current?.click()}
                    className="w-full p-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-gray-400 transition-all text-gray-500 hover:text-gray-600 flex items-center justify-center gap-2"
                  >
                    <span>📎</span>
                    <span>Upload PDF files</span>
                  </button>
                  
                  {/* Paper links list */}
                  {paperLinks.length > 0 && (
                    <div className="space-y-2 max-h-24 overflow-y-auto">
                      {paperLinks.map((link, i) => (
                        <div key={`link-${i}`} className="flex items-center gap-2 p-3 rounded-lg bg-gray-50">
                          <span className="text-sm text-blue-500">🔗</span>
                          <span className="flex-1 text-sm text-gray-700 truncate">{link}</span>
                          <button
                            onClick={() => removePaperLink(i)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Paper files list */}
                  {paperFiles.length > 0 && (
                    <div className="space-y-2 max-h-24 overflow-y-auto">
                      {paperFiles.map((file, i) => (
                        <div key={`file-${i}`} className="flex items-center gap-2 p-3 rounded-lg bg-green-50 border border-green-200">
                          <span className="text-sm">📄</span>
                          <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                          <span className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                          <button
                            onClick={() => removePaperFile(i)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className="flex gap-3 pt-2">
                    <Button variant="outline" onClick={handleSkipPapers} className="flex-1">
                      Skip
                    </Button>
                    <Button
                      onClick={handlePapersSubmit}
                      disabled={(paperLinks.length === 0 && paperFiles.length === 0) || isLoading}
                      className="flex-1 bg-gray-800 hover:bg-gray-700"
                    >
                      {isLoading ? "Analyzing..." : `Continue${(paperLinks.length + paperFiles.length) > 0 ? ` (${paperLinks.length + paperFiles.length})` : ""}`}
                    </Button>
                  </div>
                  
                  {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Node count indicator */}
      <AnimatePresence>
        {nodes.length > 0 && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="fixed bottom-6 left-6 px-4 py-2 rounded-full bg-white/90 backdrop-blur-sm border border-gray-200"
            style={{ boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}
          >
            <span className="text-sm text-gray-600">
              <strong className="text-gray-800">{nodes.length}</strong> knowledge nodes
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}
