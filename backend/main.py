from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from supabase import create_client, Client
import os
import uuid
from dotenv import load_dotenv
from pathlib import Path
import httpx
import json
import re

# Load .env from backend directory regardless of cwd
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

app = FastAPI(title="arXlearn API", version="1.0.0")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
supabase: Client = create_client(
    os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)



# ============ Pydantic Models ============

class UserResponse(BaseModel):
    user_id: int


class SessionCreateRequest(BaseModel):
    user_id: int
    central_topic: str


class SessionResponse(BaseModel):
    session_id: str
    user_id: int
    central_topic: str


class BackgroundRequest(BaseModel):
    description: str
    session_id: str
    user_id: int


class KnowledgeNode(BaseModel):
    label: str
    domain: Optional[str] = None
    type: Optional[str] = None
    confidence: Optional[float] = None
    mastery_estimate: Optional[float] = None
    relevance_to_topic: Optional[str] = None
    parent_node: Optional[str] = None
    source_papers: Optional[List[int]] = None


class NodesResponse(BaseModel):
    success: bool
    nodes: List[KnowledgeNode]
    error: Optional[str] = None


class PaperInput(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None


class PapersRequest(BaseModel):
    papers: List[PaperInput]
    session_id: str
    user_id: int


# ============ Helper Functions ============

def extract_json_from_response(text: str) -> dict:
    """Extract JSON from Gemini response, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        text = json_match.group(1)
    
    # Clean up and parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise


async def call_gemini(prompt: str) -> str:
    """Call Gemini API via REST."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def generate_background_nodes(central_topic: str, background: str) -> List[dict]:
    """Use Gemini to generate knowledge nodes from background."""
    prompt = f"""You are analyzing a researcher's background to identify their core competency areas.

INPUT:
- Central research question: "{central_topic}"
- Background: "{background}"

TASK:
Identify exactly 4 high-level knowledge domains this person likely has expertise in, based on their background. These should be domains RELEVANT to their central research question.

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "single word or two-word phrase",
      "domain": "broader category",
      "confidence": 0.0-1.0,
      "relevance_to_topic": "one sentence"
    }}
  ]
}}

CONSTRAINTS:
- Labels must be 1-2 words maximum
- Confidence reflects how certain you are they know this
- Only return domains with confidence > 0.5
- Return exactly 4 nodes"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result.get("nodes", [])


async def generate_paper_nodes(central_topic: str, existing_nodes: List[str], paper_titles: List[str]) -> List[dict]:
    """Use Gemini to generate knowledge nodes from papers."""
    titles_formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(paper_titles)])
    existing_formatted = ", ".join(existing_nodes) if existing_nodes else "None yet"
    
    prompt = f"""You are analyzing a researcher's reading history to map their knowledge graph.

INPUT:
- Central research question: "{central_topic}"
- Existing knowledge nodes: {existing_formatted}
- Papers read (titles only):
{titles_formatted}

TASK:
Identify exactly 20 specific concepts, methods, or theories this researcher likely understands based on these papers. These should be:
- More specific than the existing background nodes
- Directly relevant to understanding their central research question
- Represent actual learnable concepts (not paper titles)

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "concept name (1-3 words)",
      "type": "concept" | "method" | "theory" | "tool",
      "parent_node": "label of existing node this connects to, or null",
      "source_papers": [indices of papers that teach this],
      "mastery_estimate": 0.0-1.0
    }}
  ]
}}

CONSTRAINTS:
- Exactly 20 nodes
- Each node must connect to either the center or an existing node
- Labels must be 1-3 words
- mastery_estimate: 0.8+ if multiple papers cover it, 0.5-0.7 if one paper"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result.get("nodes", [])


# ============ API Endpoints ============

@app.post("/api/user/new", response_model=UserResponse)
async def create_user():
    """Create a new user for hackathon testing."""
    result = supabase.table("users").insert({}).execute()
    return UserResponse(user_id=result.data[0]["id"])


@app.post("/api/session/create", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new learning session with central topic."""
    session_id = str(uuid.uuid4())
    
    result = supabase.table("learning_sessions").insert({
        "id": session_id,
        "user_id": request.user_id,
        "central_topic": request.central_topic,
        "is_llm_generated": False
    }).execute()
    
    return SessionResponse(
        session_id=session_id,
        user_id=request.user_id,
        central_topic=request.central_topic
    )


@app.post("/api/profile/cv", response_model=NodesResponse)
async def upload_cv(
    session_id: str = Form(...),
    user_id: int = Form(...),
    file: UploadFile = File(...)
):
    """Upload CV, extract text, and generate knowledge nodes."""
    try:
        # Get session to retrieve central_topic
        session = supabase.table("learning_sessions").select("*").eq("id", session_id).single().execute()
        central_topic = session.data["central_topic"]
        
        # Upload file to storage
        file_bytes = await file.read()
        file_path = f"{user_id}/{file.filename}"
        
        supabase.storage.from_("cvs").upload(file_path, file_bytes, {
            "content-type": file.content_type or "application/pdf"
        })
        
        # For now, use filename as placeholder text (real impl would use pdf2text)
        cv_text = f"CV uploaded: {file.filename}"
        
        # Store profile
        supabase.table("user_profiles").insert({
            "user_id": user_id,
            "cv_url": file_path,
            "cv_text": cv_text,
            "is_llm_generated": False
        }).execute()
        
        # Generate nodes using Gemini
        nodes = await generate_background_nodes(central_topic, cv_text)
        
        # Store nodes in database
        for node in nodes:
            supabase.table("knowledge_nodes").insert({
                "session_id": session_id,
                "label": node.get("label"),
                "type": "domain",
                "domain": node.get("domain"),
                "confidence": node.get("confidence"),
                "relevance_to_topic": node.get("relevance_to_topic"),
                "is_llm_generated": True
            }).execute()
        
        return NodesResponse(success=True, nodes=[KnowledgeNode(**n) for n in nodes])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile/background", response_model=NodesResponse)
async def submit_background(request: BackgroundRequest):
    """Submit background description and generate knowledge nodes."""
    try:
        # Get session to retrieve central_topic
        session = supabase.table("learning_sessions").select("*").eq("id", request.session_id).single().execute()
        central_topic = session.data["central_topic"]
        
        # Store profile
        supabase.table("user_profiles").insert({
            "user_id": request.user_id,
            "background_description": request.description,
            "is_llm_generated": False
        }).execute()
        
        # Generate nodes using Gemini
        nodes = await generate_background_nodes(central_topic, request.description)
        
        # Store nodes in database
        for node in nodes:
            supabase.table("knowledge_nodes").insert({
                "session_id": request.session_id,
                "label": node.get("label"),
                "type": "domain",
                "domain": node.get("domain"),
                "confidence": node.get("confidence"),
                "relevance_to_topic": node.get("relevance_to_topic"),
                "is_llm_generated": True
            }).execute()
        
        return NodesResponse(success=True, nodes=[KnowledgeNode(**n) for n in nodes])
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile/papers", response_model=NodesResponse)
async def submit_papers(request: PapersRequest):
    """Submit papers and generate knowledge nodes."""
    try:
        # Get session to retrieve central_topic
        session = supabase.table("learning_sessions").select("*").eq("id", request.session_id).single().execute()
        central_topic = session.data["central_topic"]
        
        # Get existing nodes
        existing_nodes_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        existing_labels = [n["label"] for n in existing_nodes_result.data]
        
        # Store papers and collect titles
        paper_titles = []
        for paper in request.papers:
            title = paper.title or paper.url or "Untitled"
            paper_titles.append(title)
            
            supabase.table("user_papers").insert({
                "user_id": request.user_id,
                "session_id": request.session_id,
                "title": title,
                "url": paper.url,
                "is_llm_generated": False
            }).execute()
        
        # Generate nodes using Gemini
        nodes = await generate_paper_nodes(central_topic, existing_labels, paper_titles)
        
        # Store nodes in database
        for node in nodes:
            # Find parent node ID if specified
            parent_id = None
            if node.get("parent_node"):
                parent_result = supabase.table("knowledge_nodes").select("id").eq("session_id", request.session_id).eq("label", node["parent_node"]).execute()
                if parent_result.data:
                    parent_id = parent_result.data[0]["id"]
            
            supabase.table("knowledge_nodes").insert({
                "session_id": request.session_id,
                "label": node.get("label"),
                "type": node.get("type"),
                "parent_node_id": parent_id,
                "mastery_estimate": node.get("mastery_estimate"),
                "source_papers": node.get("source_papers"),
                "is_llm_generated": True
            }).execute()
        
        return NodesResponse(success=True, nodes=[KnowledgeNode(**n) for n in nodes])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/nodes")
async def get_session_nodes(session_id: str):
    """Get all knowledge nodes for a session."""
    result = supabase.table("knowledge_nodes").select("*").eq("session_id", session_id).execute()
    return {"nodes": result.data}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    result = supabase.table("learning_sessions").select("*").eq("id", session_id).single().execute()
    return result.data


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
