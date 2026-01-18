"use client"

import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import GoogleDriveConnect, { GoogleDoc } from "@/components/GoogleDriveConnect"
import ZoteroConnect, { ZoteroItem } from "@/components/ZoteroConnect"
import { supabase, getGoogleAccessToken } from "@/lib/supabase"
import LoadingSpinner from "@/components/LoadingSpinner"

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

type Scene = "topic" | "background" | "notes" | "zotero" | "coursework"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

// Position configurations for displaying nodes
const NODE_POSITIONS = [
  { x: 8, y: 12, z: 1, color: "blue" },
  { x: 25, y: 8, z: 2, color: "green" },
  { x: 15, y: 35, z: 1, color: "gray" },
  { x: 5, y: 55, z: 3, color: "blue" },
  { x: 35, y: 22, z: 2, color: "green" },
  { x: 12, y: 75, z: 1, color: "gray" },
  { x: 42, y: 45, z: 3, color: "blue" },
  { x: 28, y: 65, z: 2, color: "green" },
  { x: 8, y: 88, z: 1, color: "gray" },
  { x: 48, y: 78, z: 2, color: "blue" },
  { x: 55, y: 15, z: 1, color: "green" },
  { x: 52, y: 55, z: 3, color: "gray" },
  { x: 18, y: 48, z: 2, color: "blue" },
  { x: 38, y: 85, z: 1, color: "green" },
]

// Placeholder knowledge nodes shown on the first screen
const PLACEHOLDER_NODES = [
  { label: "Machine Learning", domain: "CS" },
  { label: "Neural Networks", domain: "AI" },
  { label: "Cognitive Science", domain: "Psychology" },
  { label: "Statistical Analysis", domain: "Math" },
  { label: "Research Methods", domain: "Academia" },
  { label: "Data Visualization", domain: "Design" },
  { label: "Natural Language", domain: "Linguistics" },
  { label: "Reinforcement Learning", domain: "AI" },
  { label: "Bayesian Inference", domain: "Statistics" },
  { label: "Computer Vision", domain: "CS" },
  { label: "Knowledge Graphs", domain: "AI" },
  { label: "Human Memory", domain: "Neuroscience" },
  { label: "Attention Mechanisms", domain: "Deep Learning" },
  { label: "Transformers", domain: "NLP" },
]

// Floating node component
function FloatingNode({
  label,
  x,
  y,
  z,
  color,
  delay,
  isUserNode = false,
  relevance,
  domain
}: {
  label: string
  x: number
  y: number
  z: number
  color: string
  delay: number
  isUserNode?: boolean
  relevance?: string
  domain?: string
}) {
  const [isHovered, setIsHovered] = useState(false)

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
      className={`absolute select-none ${isUserNode ? 'pointer-events-auto cursor-pointer' : 'pointer-events-none'}`}
      style={{
        left: `${x}%`,
        top: `${y}%`,
        zIndex: isHovered ? 100 : z
      }}
      onMouseEnter={() => isUserNode && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <motion.div
        animate={{
          y: isHovered ? 0 : [0, -6, 0],
          rotate: isHovered ? 0 : [-0.5, 0.5, -0.5]
        }}
        transition={{
          duration: isHovered ? 0.2 : 4 + z * 2,
          repeat: isHovered ? 0 : Infinity,
          ease: "easeInOut",
          delay: isHovered ? 0 : delay
        }}
      >
        <div
          className={`
            px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap
            border backdrop-blur-sm transition-all duration-200
            ${isUserNode ? colorClasses.user : colorClasses[color as keyof typeof colorClasses]}
            ${isHovered ? 'ring-2 ring-blue-400 ring-opacity-50' : ''}
          `}
          style={{
            boxShadow: isUserNode
              ? isHovered
                ? '0 8px 30px rgba(0,0,0,0.15)'
                : '0 4px 20px rgba(0,0,0,0.08)'
              : '0 2px 8px rgba(0,0,0,0.04)'
          }}
        >
          {label}
          {domain && <span className="ml-1 text-xs opacity-60">({domain})</span>}
        </div>

        {/* Tooltip showing relevance to topic */}
        <AnimatePresence>
          {isHovered && relevance && (
            <motion.div
              initial={{ opacity: 0, y: -5, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -5, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-64 p-3 rounded-xl bg-white border border-gray-200 shadow-lg text-left"
              style={{ zIndex: 101 }}
            >
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                How this helps you learn
              </p>
              <p className="text-sm text-gray-700 leading-relaxed">
                {relevance}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
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

  // Step transition state
  const [isTransitioning, setIsTransitioning] = useState(false)
  const [transitionKey, setTransitionKey] = useState(0) // Force new random icon on each transition

  // Transition to next scene with loading animation
  const transitionToScene = useCallback((nextScene: Scene, minDuration = 1200) => {
    setIsTransitioning(true)
    setTransitionKey(prev => prev + 1) // New random icon

    setTimeout(() => {
      setScene(nextScene)
      setTimeout(() => {
        setIsTransitioning(false)
      }, 300) // Small delay to let content start rendering
    }, minDuration)
  }, [])
  
  // Knowledge graph state
  const [nodes, setNodes] = useState<KnowledgeNode[]>([])
  const [allNodes, setAllNodes] = useState<KnowledgeNode[]>([]) // All nodes from database (shown before topic entry)

  // Background scene state
  const [backgroundChoice, setBackgroundChoice] = useState<"cv" | "describe" | "skip" | null>(null)
  const [description, setDescription] = useState("")
  const cvRef = useRef<HTMLInputElement>(null)
  const [cvFile, setCvFile] = useState<File | null>(null)
  
  // Notes scene state (Google Drive connection)
  const [googleDriveConnected, setGoogleDriveConnected] = useState(false)
  const [googleDocs, setGoogleDocs] = useState<GoogleDoc[]>([])

  // Zotero connection state
  const [zoteroConnected, setZoteroConnected] = useState(false)
  const [zoteroItems, setZoteroItems] = useState<ZoteroItem[]>([])

  // Papers scene state
  const [paperLinks, setPaperLinks] = useState<string[]>([])
  const [currentLink, setCurrentLink] = useState("")
  const [paperFiles, setPaperFiles] = useState<File[]>([])
  const paperFileRef = useRef<HTMLInputElement>(null)

  // Notes scene state
  const [notesDescription, setNotesDescription] = useState("")
  const [noteFiles, setNoteFiles] = useState<File[]>([])
  const noteFileRef = useRef<HTMLInputElement>(null)

  // Courses scene state
  const [courses, setCourses] = useState<string[]>([])
  const [currentCourse, setCurrentCourse] = useState("")

  // Papers authored scene state (PDFs only)
  const [authoredPaperFiles, setAuthoredPaperFiles] = useState<File[]>([])
  const authoredPaperFileRef = useRef<HTMLInputElement>(null)

  // Coursework scene state (URLs or transcript)
  const [courseworkUrls, setCourseworkUrls] = useState<string[]>([])
  const [currentCourseworkUrl, setCurrentCourseworkUrl] = useState("")
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null)
  const transcriptFileRef = useRef<HTMLInputElement>(null)

  // Initialize user on mount - restore state if returning from OAuth
  const [userReady, setUserReady] = useState(false)

  useEffect(() => {
    const initUser = async () => {
      try {
        // Check if we're returning from OAuth (URL hash has access_token or error)
        const isOAuthReturn = window.location.hash.includes("access_token") ||
                             window.location.hash.includes("error")

        // Check for saved state in localStorage
        const savedUserId = localStorage.getItem("onboarding_userId")
        const savedSessionId = localStorage.getItem("sessionId")
        const savedScene = localStorage.getItem("onboarding_scene") as Scene | null
        const savedTopic = localStorage.getItem("onboarding_topic")

        // Also check for saved nodes
        const savedNodes = localStorage.getItem("onboarding_nodes")

        if (isOAuthReturn && savedUserId && savedSessionId && savedScene) {
          // Restore state from localStorage (returning from OAuth)
          console.log("[Onboarding] OAuth return detected, restoring state from localStorage")
          setUserId(parseInt(savedUserId, 10))
          setSessionId(savedSessionId)
          setScene(savedScene)
          if (savedTopic) setCentralTopic(savedTopic)
          if (savedNodes) {
            try {
              setNodes(JSON.parse(savedNodes))
            } catch (e) {
              console.error("Failed to parse saved nodes:", e)
            }
          }
          setUserReady(true)
          // NOTE: Do NOT clear the hash here - let GoogleDriveConnect read it first
          return
        }

        // Check if we have existing state to restore (page refresh during onboarding)
        if (savedUserId && savedSessionId && savedScene) {
          setUserId(parseInt(savedUserId, 10))
          setSessionId(savedSessionId)
          setScene(savedScene)
          if (savedTopic) setCentralTopic(savedTopic)
          if (savedNodes) {
            try {
              setNodes(JSON.parse(savedNodes))
            } catch (e) {
              console.error("Failed to parse saved nodes:", e)
            }
          }
          setUserReady(true)
          return
        }

        // Fresh start - create new user
        const res = await fetch(`${API_BASE}/api/user/new`, { method: "POST" })
        const data = await res.json()
        setUserId(data.user_id)
        // Save userId for OAuth flow and page refresh
        localStorage.setItem("onboarding_userId", data.user_id.toString())
        setUserReady(true)
      } catch (e) {
        console.error("Failed to create user:", e)
        setError("Failed to connect to server. Is the backend running?")
      }
    }
    initUser()
  }, [])

  // Save state to localStorage whenever scene, topic, or nodes change (for OAuth flow preservation)
  useEffect(() => {
    if (scene && scene !== "topic") {
      localStorage.setItem("onboarding_scene", scene)
    }
    if (centralTopic) {
      localStorage.setItem("onboarding_topic", centralTopic)
    }
  }, [scene, centralTopic])

  // Save nodes to localStorage when they change
  useEffect(() => {
    if (nodes.length > 0) {
      localStorage.setItem("onboarding_nodes", JSON.stringify(nodes))
    }
  }, [nodes])

  // Clear onboarding state from localStorage when navigating away (onboarding complete)
  useEffect(() => {
    return () => {
      // Only clear if we're navigating to lessons (onboarding complete)
      // This is handled in navigate calls instead
    }
  }, [])

  // Fetch all nodes from database on initial load (shown before topic entry)
  useEffect(() => {
    const fetchAllNodes = async () => {
      try {
        const { data, error } = await supabase
          .from("knowledge_nodes")
          .select("label, domain, type, confidence, mastery_estimate, relevance_to_topic")
          .order("created_at", { ascending: false })
          .limit(14) // Limit to fit the position slots

        if (error) {
          console.error("Error fetching nodes:", error)
          return
        }

        if (data) {
          setAllNodes(data as KnowledgeNode[])
        }
      } catch (e) {
        console.error("Failed to fetch nodes:", e)
      }
    }
    fetchAllNodes()
  }, [])

  // Save nodes to localStorage whenever they change (for OAuth flow persistence)
  useEffect(() => {
    if (nodes.length > 0) {
      localStorage.setItem("onboarding_nodes", JSON.stringify(nodes))
    }
  }, [nodes])

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
      // Store state in localStorage for OAuth flow and page refresh
      localStorage.setItem("sessionId", data.session_id)
      localStorage.setItem("onboarding_topic", centralTopic)
      localStorage.setItem("onboarding_scene", "background")

      setNodes([{ label: centralTopic, type: "concept", confidence: 1.0 }])
      transitionToScene("background")
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
        localStorage.setItem("onboarding_scene", "notes")
        transitionToScene("notes")
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
        localStorage.setItem("onboarding_scene", "notes")
        transitionToScene("notes")
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
    localStorage.setItem("onboarding_scene", "notes")
    transitionToScene("notes")
  }

  // Scene 3: Notes submission (Google Drive connection + papers you've written)
  const handleNotesSubmit = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Process Google Docs if any were selected
      if (googleDocs.length > 0 && sessionId && userId) {
        const accessToken = await getGoogleAccessToken()

        const res = await fetch(`${API_BASE}/api/profile/google-docs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            documents: googleDocs,
            session_id: sessionId,
            user_id: userId,
            access_token: accessToken
          })
        })
        const data = await res.json()

        if (data.success && data.nodes) {
          setNodes(prev => [...prev, ...data.nodes])
        }
      }

      // Process authored papers if any were uploaded
      if (authoredPaperFiles.length > 0 && sessionId && userId) {
        const formData = new FormData()
        authoredPaperFiles.forEach(file => formData.append("files", file))
        formData.append("session_id", sessionId)
        formData.append("user_id", userId.toString())

        const res = await fetch(`${API_BASE}/api/profile/papers-authored`, {
          method: "POST",
          body: formData
        })
        const data = await res.json()

        if (data.success && data.nodes) {
          setNodes(prev => [...prev, ...data.nodes])
        }
      }
    } catch (e) {
      console.error("Notes/papers submission error:", e)
    } finally {
      setIsLoading(false)
    }

    localStorage.setItem("onboarding_scene", "zotero")
    transitionToScene("zotero")
  }

  const handleSkipNotes = () => {
    localStorage.setItem("onboarding_scene", "zotero")
    transitionToScene("zotero")
  }

  // Scene 4: Zotero submission
  const handleZoteroSubmit = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Process Zotero items if any were selected
      if (zoteroItems.length > 0 && sessionId && userId) {
        const res = await fetch(`${API_BASE}/api/profile/zotero-items`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            items: zoteroItems,
            session_id: sessionId,
            user_id: userId
          })
        })
        const data = await res.json()

        if (data.success && data.nodes) {
          setNodes(prev => [...prev, ...data.nodes])
        }
      }

      // Process uploaded paper files if any
      if (paperFiles.length > 0 && sessionId && userId) {
        const formData = new FormData()
        paperFiles.forEach(file => formData.append("files", file))
        formData.append("session_id", sessionId)
        formData.append("user_id", userId.toString())

        const res = await fetch(`${API_BASE}/api/profile/papers-authored`, {
          method: "POST",
          body: formData
        })
        const data = await res.json()

        if (data.success && data.nodes) {
          setNodes(prev => [...prev, ...data.nodes])
        }
      }
    } catch (e) {
      console.error("Zotero submission error:", e)
    } finally {
      setIsLoading(false)
    }

    localStorage.setItem("onboarding_scene", "coursework")
    transitionToScene("coursework")
  }

  const handleSkipZotero = () => {
    localStorage.setItem("onboarding_scene", "coursework")
    transitionToScene("coursework")
  }

  // Legacy: Papers authored submission (PDFs only)
  const addAuthoredPaperFiles = (files: FileList | null) => {
    if (files) {
      const pdfFiles = Array.from(files).filter(f => f.type === "application/pdf")
      setAuthoredPaperFiles(prev => [...prev, ...pdfFiles])
    }
  }

  const removeAuthoredPaperFile = (index: number) => {
    setAuthoredPaperFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handlePapersAuthoredSubmit = async () => {
    if (authoredPaperFiles.length === 0 || !sessionId || !userId) {
      localStorage.setItem("onboarding_scene", "coursework")
      transitionToScene("coursework")
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      authoredPaperFiles.forEach(file => formData.append("files", file))
      formData.append("session_id", sessionId)
      formData.append("user_id", userId.toString())

      const res = await fetch(`${API_BASE}/api/profile/papers-authored`, {
        method: "POST",
        body: formData
      })
      const data = await res.json()

      if (data.success && data.nodes) {
        setNodes(prev => [...prev, ...data.nodes])
      } else if (!data.success) {
        setError(data.error || "Failed to process papers")
      }

      localStorage.setItem("onboarding_scene", "coursework")
      transitionToScene("coursework")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload papers. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSkipPapersAuthored = () => {
    localStorage.setItem("onboarding_scene", "coursework")
    transitionToScene("coursework")
  }

  // Scene 5: Coursework submission (URLs via Firecrawl or transcript)
  const addCourseworkUrl = () => {
    if (currentCourseworkUrl.trim()) {
      setCourseworkUrls(prev => [...prev, currentCourseworkUrl.trim()])
      setCurrentCourseworkUrl("")
    }
  }

  const removeCourseworkUrl = (index: number) => {
    setCourseworkUrls(prev => prev.filter((_, i) => i !== index))
  }

  const handleCourseworkSubmit = async () => {
    if (courseworkUrls.length === 0 && !transcriptFile) {
      // No coursework added, complete onboarding
      clearOnboardingState()
      navigate("/lessons")
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      let allNewNodes: KnowledgeNode[] = []

      // Process coursework URLs via Firecrawl
      if (courseworkUrls.length > 0 && sessionId && userId) {
        const res = await fetch(`${API_BASE}/api/profile/coursework-urls`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            urls: courseworkUrls,
            session_id: sessionId,
            user_id: userId
          })
        })
        const data = await res.json()

        if (data.success && data.nodes) {
          allNewNodes = [...allNewNodes, ...data.nodes]
        }
      }

      // Process transcript if uploaded
      if (transcriptFile && sessionId && userId) {
        const formData = new FormData()
        formData.append("file", transcriptFile)
        formData.append("session_id", sessionId)
        formData.append("user_id", userId.toString())

        const res = await fetch(`${API_BASE}/api/profile/coursework-transcript`, {
          method: "POST",
          body: formData
        })
        const data = await res.json()

        if (data.success && data.nodes) {
          allNewNodes = [...allNewNodes, ...data.nodes]
        }
      }

      if (allNewNodes.length > 0) {
        setNodes(prev => [...prev, ...allNewNodes])
      }

      clearOnboardingState()
      navigate("/lessons")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to process coursework. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSkipCoursework = () => {
    clearOnboardingState()
    navigate("/lessons")
  }

  const clearOnboardingState = () => {
    localStorage.removeItem("onboarding_scene")
    localStorage.removeItem("onboarding_topic")
    localStorage.removeItem("onboarding_userId")
    localStorage.removeItem("onboarding_nodes")
  }

  // Legacy handlers for old scenes (papers, courses, old notes) - kept for backward compatibility
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
    // Legacy - go to zotero
    localStorage.setItem("onboarding_scene", "zotero")
    transitionToScene("zotero")
  }

  const handleSkipPapers = () => {
    localStorage.setItem("onboarding_scene", "zotero")
    transitionToScene("zotero")
  }

  const addCourse = () => {
    if (currentCourse.trim()) {
      setCourses(prev => [...prev, currentCourse.trim()])
      setCurrentCourse("")
    }
  }

  const removeCourse = (index: number) => {
    setCourses(prev => prev.filter((_, i) => i !== index))
  }

  const handleCoursesSubmit = async () => {
    localStorage.setItem("onboarding_scene", "coursework")
    transitionToScene("coursework")
  }

  const handleSkipCourses = () => {
    localStorage.setItem("onboarding_scene", "coursework")
    transitionToScene("coursework")
  }

  const addNoteFiles = (files: FileList | null) => {
    if (files) {
      setNoteFiles(prev => [...prev, ...Array.from(files)])
    }
  }

  const removeNoteFile = (index: number) => {
    setNoteFiles(prev => prev.filter((_, i) => i !== index))
  }

  // Generate placeholder nodes for the first screen (topic entry)
  const placeholderNodes = useMemo(() => {
    return PLACEHOLDER_NODES.map((node, i) => ({
      label: node.label,
      domain: node.domain,
      x: NODE_POSITIONS[i % NODE_POSITIONS.length].x,
      y: NODE_POSITIONS[i % NODE_POSITIONS.length].y,
      z: NODE_POSITIONS[i % NODE_POSITIONS.length].z,
      color: NODE_POSITIONS[i % NODE_POSITIONS.length].color,
      delay: 0.2 + i * 0.12
    }))
  }, [])

  // Generate background nodes from database (shown before topic entry if available)
  const backgroundNodes = useMemo(() => {
    // Use placeholder nodes if no database nodes available
    const nodesToShow = allNodes.length > 0 ? allNodes : PLACEHOLDER_NODES
    return nodesToShow.map((node, i) => ({
      label: node.label,
      domain: node.domain,
      x: NODE_POSITIONS[i % NODE_POSITIONS.length].x,
      y: NODE_POSITIONS[i % NODE_POSITIONS.length].y,
      z: NODE_POSITIONS[i % NODE_POSITIONS.length].z,
      color: NODE_POSITIONS[i % NODE_POSITIONS.length].color,
      delay: 0.2 + i * 0.12
    }))
  }, [allNodes])

  // Generate user nodes with positions (shown after topic entry)
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

        {/* Placeholder knowledge nodes - shown on the topic entry screen */}
        <AnimatePresence>
          {scene === "topic" && placeholderNodes.map((node, i) => (
            <FloatingNode
              key={`placeholder-${i}-${node.label}`}
              label={node.label}
              x={node.x}
              y={node.y}
              z={node.z}
              color={node.color}
              delay={node.delay}
              domain={node.domain}
            />
          ))}
        </AnimatePresence>

        {/* User-generated nodes - shown AFTER topic entry */}
        <AnimatePresence>
          {sessionId && userNodes.map((node, i) => (
            <FloatingNode
              key={`user-${i}-${node.label}`}
              label={node.label}
              x={node.x}
              y={node.y}
              z={node.z}
              color="user"
              delay={node.delay}
              isUserNode={true}
              relevance={node.relevance_to_topic}
              domain={node.domain}
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
                  Connect Google Drive, paste arXiv/DOI links, or upload PDFs
                </p>

                <div className="space-y-4">
                  {/* Google Drive Connection */}
                  {userId && sessionId && (
                    <GoogleDriveConnect
                      userId={userId}
                      sessionId={sessionId}
                      onConnect={setGoogleDriveConnected}
                      onDocumentsSelected={setGoogleDocs}
                    />
                  )}

                  {/* Zotero Connection */}
                  {userId && (
                    <ZoteroConnect
                      userId={userId}
                      onConnect={setZoteroConnected}
                      onSelectionChange={setZoteroItems}
                    />
                  )}

                  {/* Divider */}
                  {(googleDriveConnected || zoteroConnected) && (
                    <div className="flex items-center gap-3 py-2">
                      <div className="flex-1 h-px bg-gray-200" />
                      <span className="text-xs text-gray-400">or add manually</span>
                      <div className="flex-1 h-px bg-gray-200" />
                    </div>
                  )}
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
                      disabled={(paperLinks.length === 0 && paperFiles.length === 0 && googleDocs.length === 0 && zoteroItems.length === 0) || isLoading}
                      className="flex-1 bg-gray-800 hover:bg-gray-700"
                    >
                      {isLoading ? "Analyzing..." : `Continue${(paperLinks.length + paperFiles.length + googleDocs.length + zoteroItems.length) > 0 ? ` (${paperLinks.length + paperFiles.length + googleDocs.length + zoteroItems.length})` : ""}`}
                    </Button>
                  </div>
                  
                  {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
                </div>
              </div>
            </motion.div>
          )}

          {/* Scene 4: Courses & Academic History */}
          {scene === "courses" && (
            <motion.div
              key="courses"
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
                  What courses have you taken?
                </h2>
                <p className="text-gray-500 text-sm mb-6">
                  Add relevant classes, certifications, or academic programs
                </p>

                <div className="space-y-4">
                  {/* Course input */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={currentCourse}
                      onChange={(e) => setCurrentCourse(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCourse())}
                      placeholder="e.g., CS 229 Machine Learning, MIT 6.006..."
                      className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 text-sm"
                      autoFocus
                    />
                    <Button
                      onClick={addCourse}
                      disabled={!currentCourse.trim()}
                      variant="outline"
                    >
                      Add
                    </Button>
                  </div>

                  {/* Quick add suggestions */}
                  <div className="flex flex-wrap gap-2">
                    {["Linear Algebra", "Calculus", "Statistics", "Programming", "Data Structures"].map((suggestion) => (
                      !courses.includes(suggestion) && (
                        <button
                          key={suggestion}
                          onClick={() => setCourses(prev => [...prev, suggestion])}
                          className="px-3 py-1 text-xs rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
                        >
                          + {suggestion}
                        </button>
                      )
                    ))}
                  </div>

                  {/* Courses list */}
                  {courses.length > 0 && (
                    <div className="space-y-2 max-h-32 overflow-y-auto">
                      {courses.map((course, i) => (
                        <div key={`course-${i}`} className="flex items-center gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200">
                          <span className="text-sm">📚</span>
                          <span className="flex-1 text-sm text-gray-700">{course}</span>
                          <button
                            onClick={() => removeCourse(i)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-3 pt-2">
                    <Button variant="outline" onClick={handleSkipCourses} className="flex-1">
                      Skip
                    </Button>
                    <Button
                      onClick={handleCoursesSubmit}
                      disabled={isLoading}
                      className="flex-1 bg-gray-800 hover:bg-gray-700"
                    >
                      {isLoading ? "Processing..." : `Continue${courses.length > 0 ? ` (${courses.length})` : ""}`}
                    </Button>
                  </div>

                  {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
                </div>
              </div>
            </motion.div>
          )}

          {/* Scene 3: Notes (Google Drive Connection + Papers You've Written) */}
          {scene === "notes" && (
            <motion.div
              key="notes"
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
                  Connect your notes & papers
                </h2>
                <p className="text-gray-500 text-sm mb-6">
                  Import documents from Google Drive or upload papers you've written
                </p>

                <div className="space-y-4">
                  {/* Google Drive Connection */}
                  {userId && sessionId && (
                    <GoogleDriveConnect
                      userId={userId}
                      sessionId={sessionId}
                      onConnect={setGoogleDriveConnected}
                      onDocumentsSelected={setGoogleDocs}
                    />
                  )}

                  {/* Selected docs count */}
                  {googleDocs.length > 0 && (
                    <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700">
                      {googleDocs.length} document{googleDocs.length > 1 ? 's' : ''} selected from Google Drive
                    </div>
                  )}

                  {/* Divider */}
                  <div className="flex items-center gap-3 py-2">
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-xs text-gray-400">or upload papers</span>
                    <div className="flex-1 h-px bg-gray-200" />
                  </div>

                  {/* PDF Upload for papers you've written */}
                  <input
                    type="file"
                    ref={authoredPaperFileRef}
                    accept=".pdf"
                    multiple
                    onChange={(e) => addAuthoredPaperFiles(e.target.files)}
                    className="hidden"
                  />
                  <button
                    onClick={() => authoredPaperFileRef.current?.click()}
                    className="w-full p-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-gray-400 transition-all text-gray-500 hover:text-gray-600 flex flex-col items-center justify-center gap-2"
                  >
                    <span className="text-xl">📄</span>
                    <span>Upload papers you've written (PDF)</span>
                  </button>

                  {/* Authored paper files list */}
                  {authoredPaperFiles.length > 0 && (
                    <div className="space-y-2 max-h-24 overflow-y-auto">
                      {authoredPaperFiles.map((file, i) => (
                        <div key={`authored-${i}`} className="flex items-center gap-2 p-3 rounded-lg bg-purple-50 border border-purple-200">
                          <span className="text-sm">📄</span>
                          <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                          <span className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                          <button
                            onClick={() => removeAuthoredPaperFile(i)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-3 pt-2">
                    <Button variant="outline" onClick={handleSkipNotes} className="flex-1">
                      Skip
                    </Button>
                    <Button
                      onClick={handleNotesSubmit}
                      disabled={isLoading}
                      className="flex-1 bg-gray-800 hover:bg-gray-700"
                    >
                      {isLoading ? "Processing..." : "Continue"}
                    </Button>
                  </div>

                  {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
                </div>
              </div>
            </motion.div>
          )}

          {/* Scene 4: Zotero (Import from Zotero + upload papers) */}
          {scene === "zotero" && (
            <motion.div
              key="zotero"
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
                  Import from Zotero
                </h2>
                <p className="text-gray-500 text-sm mb-6">
                  Connect your Zotero library or upload papers you've written
                </p>

                <div className="space-y-4">
                  {/* Zotero Connection */}
                  {userId && (
                    <ZoteroConnect
                      userId={userId}
                      onConnect={setZoteroConnected}
                      onSelectionChange={setZoteroItems}
                    />
                  )}

                  {/* Selected Zotero items count */}
                  {zoteroItems.length > 0 && (
                    <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                      {zoteroItems.length} item{zoteroItems.length > 1 ? 's' : ''} selected from Zotero
                    </div>
                  )}

                  {/* Divider */}
                  <div className="flex items-center gap-3 py-2">
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-xs text-gray-400">or upload papers</span>
                    <div className="flex-1 h-px bg-gray-200" />
                  </div>

                  {/* PDF Upload */}
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
                    className="w-full p-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-gray-400 transition-all text-gray-500 hover:text-gray-600 flex flex-col items-center justify-center gap-2"
                  >
                    <span className="text-xl">📄</span>
                    <span>Upload papers you've written (PDF)</span>
                  </button>

                  {/* Paper files list */}
                  {paperFiles.length > 0 && (
                    <div className="space-y-2 max-h-24 overflow-y-auto">
                      {paperFiles.map((file, i) => (
                        <div key={`paper-${i}`} className="flex items-center gap-2 p-3 rounded-lg bg-purple-50 border border-purple-200">
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
                    <Button variant="outline" onClick={handleSkipZotero} className="flex-1">
                      Skip
                    </Button>
                    <Button
                      onClick={handleZoteroSubmit}
                      disabled={isLoading}
                      className="flex-1 bg-gray-800 hover:bg-gray-700"
                    >
                      {isLoading ? "Processing..." : "Continue"}
                    </Button>
                  </div>

                  {error && <p className="text-sm text-red-500 mt-4">{error}</p>}
                </div>
              </div>
            </motion.div>
          )}

          {/* Scene 5: Coursework (URLs via Firecrawl or transcript) */}
          {scene === "coursework" && (
            <motion.div
              key="coursework"
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
                  Add your coursework
                </h2>
                <p className="text-gray-500 text-sm mb-6">
                  Link course websites or upload your academic transcript
                </p>

                <div className="space-y-4">
                  {/* Course URL input */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={currentCourseworkUrl}
                      onChange={(e) => setCurrentCourseworkUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCourseworkUrl())}
                      placeholder="https://coursera.org/learn/... or course website"
                      className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 text-sm"
                    />
                    <Button
                      onClick={addCourseworkUrl}
                      disabled={!currentCourseworkUrl.trim()}
                      variant="outline"
                    >
                      Add
                    </Button>
                  </div>

                  {/* Coursework URLs list */}
                  {courseworkUrls.length > 0 && (
                    <div className="space-y-2 max-h-24 overflow-y-auto">
                      {courseworkUrls.map((url, i) => (
                        <div key={`url-${i}`} className="flex items-center gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200">
                          <span className="text-sm text-blue-500">🔗</span>
                          <span className="flex-1 text-sm text-gray-700 truncate">{url}</span>
                          <button
                            onClick={() => removeCourseworkUrl(i)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Divider */}
                  <div className="flex items-center gap-3 py-2">
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-xs text-gray-400">or upload transcript</span>
                    <div className="flex-1 h-px bg-gray-200" />
                  </div>

                  {/* Transcript upload */}
                  <input
                    type="file"
                    ref={transcriptFileRef}
                    accept=".pdf"
                    onChange={(e) => setTranscriptFile(e.target.files?.[0] || null)}
                    className="hidden"
                  />
                  {transcriptFile ? (
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-green-50 border border-green-200">
                      <span className="text-lg">✅</span>
                      <span className="flex-1 text-sm text-gray-700 truncate">{transcriptFile.name}</span>
                      <button
                        onClick={() => setTranscriptFile(null)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => transcriptFileRef.current?.click()}
                      className="w-full p-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-gray-400 transition-all text-gray-500 hover:text-gray-600 flex items-center justify-center gap-2"
                    >
                      <span>📋</span>
                      <span>Upload academic transcript (PDF)</span>
                    </button>
                  )}

                  <div className="flex gap-3 pt-2">
                    <Button variant="outline" onClick={handleSkipCoursework} className="flex-1">
                      Skip
                    </Button>
                    <Button
                      onClick={handleCourseworkSubmit}
                      disabled={isLoading}
                      className="flex-1 bg-gray-800 hover:bg-gray-700"
                    >
                      {isLoading ? "Finishing..." : "Complete Setup"}
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

      {/* Step transition overlay with random spinning icon */}
      <AnimatePresence>
        {isTransitioning && (
          <motion.div
            key={`transition-${transitionKey}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, rgba(232, 244, 248, 0.97) 0%, rgba(238, 246, 244, 0.97) 40%, rgba(232, 248, 240, 0.97) 100%)',
              backdropFilter: 'blur(8px)'
            }}
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            >
              <LoadingSpinner key={transitionKey} size={140} random />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}
