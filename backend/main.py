from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List
from supabase import create_client, Client
from datetime import datetime
import os
import uuid
import asyncio
from dotenv import load_dotenv
from pathlib import Path
import httpx
import json
import re
import hmac
import hashlib
import base64
import time
import secrets
from urllib.parse import urlencode, quote, parse_qs

# Load .env from backend directory regardless of cwd
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TOKEN_COMPANY_API_KEY = os.getenv("TOKEN_COMPANY_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Zotero OAuth 1.0a credentials
ZOTERO_CLIENT_KEY = os.getenv("ZOTERO_CLIENT_KEY", "")
ZOTERO_CLIENT_SECRET = os.getenv("ZOTERO_CLIENT_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Supabase client (initialized early for worker)
supabase: Client = create_client(
    os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)

# Import document processing worker
from workers.document_worker import DocumentProcessingWorker

# Import Firecrawl service for chapter extraction
from services.firecrawl import FirecrawlService, FirecrawlResponse, ChapterOutline

# Import PDF processor and token compression for immediate paper processing
from services.pdf_processor import PDFProcessor
from services.token_compression import TokenCompressionService

# Import routers
from routers.google_drive import router as google_drive_router

# Global worker instance
document_worker: Optional[DocumentProcessingWorker] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    global document_worker

    # Startup: Initialize and start the document worker
    if TOKEN_COMPANY_API_KEY:
        document_worker = DocumentProcessingWorker(
            supabase_client=supabase,
            ttc_api_key=TOKEN_COMPANY_API_KEY,
            poll_interval=30,
            processing_delay=60,
            batch_size=10,
            compression_aggressiveness=0.5
        )
        asyncio.create_task(document_worker.start())
        print("[Main] Document processing worker started")
    else:
        print("[Main] TOKEN_COMPANY_API_KEY not set - document worker disabled")

    yield

    # Shutdown: Stop the worker
    if document_worker:
        await document_worker.stop()
        print("[Main] Document processing worker stopped")


app = FastAPI(title="arXlearn API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(google_drive_router)


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


# ============ Google Drive Models ============

class GoogleDriveConnectRequest(BaseModel):
    user_id: int
    access_token: str
    refresh_token: Optional[str] = None
    google_email: str
    expires_at: Optional[int] = None


class GoogleDriveDisconnectRequest(BaseModel):
    user_id: int


class GoogleDriveSearchRequest(BaseModel):
    user_id: int
    session_id: str


class GoogleDocInput(BaseModel):
    id: str
    title: str
    url: Optional[str] = None
    mimeType: Optional[str] = None
    relevanceScore: Optional[float] = None


class GoogleDocsRequest(BaseModel):
    documents: List[GoogleDocInput]
    session_id: str
    user_id: int
    access_token: Optional[str] = None  # Google OAuth access token for fetching content


# ============ Zotero OAuth Models ============

class ZoteroOAuthInitiateRequest(BaseModel):
    user_id: int


class ZoteroOAuthInitiateResponse(BaseModel):
    authorization_url: str
    state: str


class ZoteroConnectionStatus(BaseModel):
    connected: bool
    zotero_user_id: Optional[str] = None
    username: Optional[str] = None


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
    """Use Gemini to generate knowledge nodes from CV/background by extracting skills and relating them to the topic."""
    prompt = f"""You are analyzing a person's CV or background description to extract their skills and relate them to their learning topic.

INPUT:
- Learning topic they want to study: "{central_topic}"
- Their CV/Background: "{background}"

TASK:
1. Extract the key skills, competencies, and knowledge areas from their CV/background
2. For each skill, determine HOW it relates to or can help them learn their topic
3. Return 5-6 nodes that represent the bridge between what they already know and what they want to learn

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "skill name (1-2 words)",
      "domain": "broader category this skill belongs to",
      "confidence": 0.0-1.0,
      "relevance_to_topic": "How this skill helps them learn {central_topic}"
    }}
  ]
}}

EXAMPLE:
If someone has Python programming skills and wants to learn Machine Learning:
- Label: "Python", Domain: "Programming", Relevance: "Foundation for implementing ML algorithms and using libraries like scikit-learn"

CONSTRAINTS:
- Labels must be 1-2 words (the skill itself)
- Confidence reflects how strong this skill appears in their background (0.5-1.0)
- relevance_to_topic MUST explain the connection between the skill and "{central_topic}"
- Return exactly 5-6 nodes
- Focus on skills that have clear relevance to their learning topic"""

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


async def generate_single_paper_nodes(paper_title: str) -> List[dict]:
    """Lightweight Gemini call for a single paper - generates 3 key concepts from title only."""
    prompt = f"""From paper title "{paper_title}", extract 3 key concepts.
Return JSON only: {{"nodes":[{{"label":"1-2 words","type":"concept|method|theory|tool","mastery_estimate":0.7}}]}}"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result.get("nodes", [])


# ============ Zotero OAuth 1.0a Helpers ============

def generate_oauth_signature(
    http_method: str,
    url: str,
    params: dict,
    consumer_secret: str,
    token_secret: str = "",
    debug: bool = False
) -> str:
    """Generate OAuth 1.0a HMAC-SHA1 signature."""
    # Sort and encode parameters
    sorted_params = sorted(params.items())
    param_string = "&".join([f"{quote(str(k), safe='')}" + "=" + f"{quote(str(v), safe='')}" for k, v in sorted_params])

    # Create signature base string
    signature_base = "&".join([
        http_method.upper(),
        quote(url, safe=""),
        quote(param_string, safe="")
    ])

    # Create signing key
    signing_key = f"{quote(consumer_secret, safe='')}&{quote(token_secret, safe='')}"

    if debug:
        print(f"[OAuth Debug] Param string: {param_string[:100]}...")
        print(f"[OAuth Debug] Signature base: {signature_base[:150]}...")
        print(f"[OAuth Debug] Signing key (masked): {signing_key[:10]}...&{token_secret[:10] if token_secret else 'empty'}...")

    # Generate HMAC-SHA1 signature
    signature = hmac.new(
        signing_key.encode("utf-8"),
        signature_base.encode("utf-8"),
        hashlib.sha1
    ).digest()

    return base64.b64encode(signature).decode("utf-8")


def build_oauth_header(params: dict) -> str:
    """Build OAuth Authorization header from parameters."""
    oauth_params = [(k, v) for k, v in params.items() if k.startswith("oauth_")]
    header_parts = [f'{k}="{quote(str(v), safe="")}"' for k, v in sorted(oauth_params)]
    return "OAuth " + ", ".join(header_parts)


async def zotero_oauth_request_token(callback_url: str) -> tuple[str, str]:
    """Get OAuth request token from Zotero."""
    url = "https://www.zotero.org/oauth/request"

    oauth_params = {
        "oauth_consumer_key": ZOTERO_CLIENT_KEY,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": secrets.token_hex(16),
        "oauth_version": "1.0",
        "oauth_callback": callback_url,
    }

    signature = generate_oauth_signature("POST", url, oauth_params, ZOTERO_CLIENT_SECRET)
    oauth_params["oauth_signature"] = signature

    print(f"[Zotero OAuth] Requesting token with callback: {callback_url}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={
                "Authorization": build_oauth_header(oauth_params),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"[Zotero OAuth] Request token error: {response.status_code} - {response.text}")
            response.raise_for_status()

        # Parse response (oauth_token=...&oauth_token_secret=...)
        data = parse_qs(response.text)
        print(f"[Zotero OAuth] Got request token: {data['oauth_token'][0][:10]}...")
        return data["oauth_token"][0], data["oauth_token_secret"][0]


async def zotero_oauth_access_token(
    oauth_token: str,
    oauth_token_secret: str,
    oauth_verifier: str
) -> tuple[str, str, str, str]:
    """Exchange authorized request token for access token."""
    url = "https://www.zotero.org/oauth/access"

    oauth_params = {
        "oauth_consumer_key": ZOTERO_CLIENT_KEY,
        "oauth_token": oauth_token,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": secrets.token_hex(16),
        "oauth_version": "1.0",
        "oauth_verifier": oauth_verifier,
    }

    signature = generate_oauth_signature(
        "POST", url, oauth_params, ZOTERO_CLIENT_SECRET, oauth_token_secret, debug=True
    )
    oauth_params["oauth_signature"] = signature

    print(f"[Zotero OAuth] Exchanging token. oauth_token={oauth_token[:10]}..., oauth_verifier={oauth_verifier}...")

    # Build the Authorization header
    auth_header = build_oauth_header(oauth_params)
    print(f"[Zotero OAuth] Auth header: {auth_header[:100]}...")

    async with httpx.AsyncClient() as client:
        # Standard OAuth 1.0a: parameters in Authorization header
        response = await client.post(
            url,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            content="",  # Empty body for OAuth token exchange
            timeout=30.0
        )

        if response.status_code != 200:
            error_body = response.text
            print(f"[Zotero OAuth] Access token error: {response.status_code}")
            print(f"[Zotero OAuth] Error body: {error_body}")

            # Parse Zotero's OAuth error format
            if "oauth_problem=" in error_body:
                error_data = parse_qs(error_body)
                oauth_problem = error_data.get("oauth_problem", ["unknown"])[0]
                print(f"[Zotero OAuth] OAuth problem: {oauth_problem}")

                if oauth_problem == "verifier_invalid":
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid OAuth verifier. The authorization may have expired. Please try connecting again."
                    )
                elif oauth_problem == "token_rejected":
                    raise HTTPException(
                        status_code=400,
                        detail="OAuth token rejected. The request token may have expired. Please try connecting again."
                    )
                elif oauth_problem == "signature_invalid":
                    raise HTTPException(
                        status_code=400,
                        detail="OAuth signature invalid. Please contact support."
                    )

            response.raise_for_status()

        # Parse response (oauth_token=...&oauth_token_secret=...&userID=...&username=...)
        data = parse_qs(response.text)
        return (
            data["oauth_token"][0],
            data["oauth_token_secret"][0],
            data["userID"][0],
            data.get("username", [""])[0]
        )


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

            # Store in academia_materials (replaces old user_papers table)
            supabase.table("academia_materials").insert({
                "user_id": request.user_id,
                "session_id": request.session_id,
                "title": title,
                "url": paper.url,
                "material_type": "paper_read",
                "source_type": "doi_url" if paper.url else "manual_entry",
                "is_processed": False
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


@app.post("/api/profile/paper-file", response_model=NodesResponse)
async def upload_paper_file(
    session_id: str = Form(...),
    user_id: int = Form(...),
    title: str = Form(None),
    file: UploadFile = File(...)
):
    """
    Upload a paper file (PDF), compress content via Token Company, then save to Supabase.

    Aggressive token reduction strategy:
    1. Extract text from PDF immediately
    2. Compress via The Token Company API
    3. Save COMPRESSED content to Supabase (not original)
    4. Generate knowledge nodes from title
    """
    import asyncio

    try:
        # Read file and get title immediately
        file_bytes = await file.read()
        paper_title = title or (file.filename.replace(".pdf", "").replace("_", " ") if file.filename else "Uploaded Paper")

        # Prepare file path
        file_ext = Path(file.filename).suffix if file.filename else ".pdf"
        file_id = str(uuid.uuid4())
        file_path = f"{user_id}/{file_id}{file_ext}"

        # Initialize PDF processor and compression service
        pdf_processor = PDFProcessor(extract_images=False)  # Text only for speed
        compression_service = TokenCompressionService(TOKEN_COMPANY_API_KEY) if TOKEN_COMPANY_API_KEY else None

        # Extract text from PDF
        extracted_text = ""
        original_tokens = 0
        compressed_tokens = 0
        compression_ratio = 1.0
        compressed_text = ""

        try:
            extracted_text = await pdf_processor.extract_text_only(file_bytes)
            original_tokens = pdf_processor.estimate_tokens(extracted_text)

            # Compress via Token Company BEFORE saving
            if compression_service and extracted_text:
                compression_result = await compression_service.compress_for_academic_paper(extracted_text)

                if compression_result.success:
                    compressed_text = compression_result.compressed_text
                    compressed_tokens = compression_result.compressed_tokens
                    compression_ratio = compression_result.compression_ratio
                    print(f"[Paper Upload] Compressed {original_tokens} -> {compressed_tokens} tokens ({compression_ratio:.2%})")
                else:
                    # Fallback to original on compression failure
                    compressed_text = extracted_text
                    compressed_tokens = original_tokens
                    print(f"[Paper Upload] Compression failed: {compression_result.error}")
            else:
                compressed_text = extracted_text
                compressed_tokens = original_tokens

        except Exception as e:
            print(f"[Paper Upload] PDF extraction failed: {e}")
            # Continue without text extraction

        # Upload original PDF to storage in background
        def upload_to_storage():
            supabase.storage.from_("papers").upload(file_path, file_bytes, {
                "content-type": file.content_type or "application/pdf"
            })

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, upload_to_storage)

        # Store paper record with COMPRESSED content in academia_materials
        supabase.table("academia_materials").insert({
            "user_id": user_id,
            "session_id": session_id,
            "title": paper_title,
            "material_type": "paper_read",
            "source_type": "pdf_upload",
            "storage_bucket": "papers",
            "storage_path": file_path,
            "file_name": file.filename,
            "file_size_bytes": len(file_bytes),
            "compressed_text": compressed_text,  # Save compressed, not original
            "original_token_count": original_tokens,
            "compressed_token_count": compressed_tokens,
            "compression_ratio": compression_ratio,
            "compression_aggressiveness": 0.4,  # Academic preset
            "ttc_processed": True if compressed_text else False,
            "ttc_processed_at": datetime.utcnow().isoformat() if compressed_text else None,
            "pdf_extraction_method": "pymupdf",
            "is_processed": True
        }).execute()

        # Lightweight Gemini call - just title, 3 nodes
        nodes = await generate_single_paper_nodes(paper_title)

        # Store nodes (minimal inserts)
        for node in nodes:
            supabase.table("knowledge_nodes").insert({
                "session_id": session_id,
                "label": node.get("label"),
                "type": node.get("type"),
                "mastery_estimate": node.get("mastery_estimate"),
                "is_llm_generated": True
            }).execute()

        return NodesResponse(success=True, nodes=[KnowledgeNode(**n) for n in nodes])

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class GoogleDocInput(BaseModel):
    id: str
    title: str
    url: Optional[str] = None
    mimeType: Optional[str] = None
    relevanceScore: Optional[float] = None


class GoogleDocsRequest(BaseModel):
    documents: List[GoogleDocInput]
    session_id: str
    user_id: int
    access_token: Optional[str] = None  # Google OAuth access token for fetching content


@app.post("/api/profile/google-docs", response_model=NodesResponse)
async def submit_google_docs(request: GoogleDocsRequest):
    """Process selected Google Docs: fetch content, compress with Token Company, store to Supabase."""
    try:
        # Initialize compression service
        compression_service = TokenCompressionService(TOKEN_COMPANY_API_KEY) if TOKEN_COMPANY_API_KEY else None

        # Get session to retrieve central_topic
        session = supabase.table("learning_sessions").select("*").eq("id", request.session_id).single().execute()
        central_topic = session.data["central_topic"]

        # Get existing nodes
        existing_nodes_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        existing_labels = [n["label"] for n in existing_nodes_result.data]

        # Process each Google Doc
        doc_titles = []
        doc_contents = []

        for doc in request.documents:
            doc_titles.append(doc.title)
            doc_content = ""
            compressed_content = ""
            original_tokens = 0
            compressed_tokens = 0
            compression_ratio = 1.0

            # Fetch document content if access token provided
            if request.access_token:
                try:
                    async with httpx.AsyncClient() as client:
                        # Determine how to fetch based on mime type
                        if doc.mimeType == "application/vnd.google-apps.document":
                            # Export Google Doc as plain text
                            export_url = f"https://www.googleapis.com/drive/v3/files/{doc.id}/export?mimeType=text/plain"
                            response = await client.get(
                                export_url,
                                headers={"Authorization": f"Bearer {request.access_token}"},
                                timeout=30.0
                            )
                            if response.status_code == 200:
                                doc_content = response.text
                        elif doc.mimeType == "application/vnd.google-apps.spreadsheet":
                            # Export Google Sheet as CSV
                            export_url = f"https://www.googleapis.com/drive/v3/files/{doc.id}/export?mimeType=text/csv"
                            response = await client.get(
                                export_url,
                                headers={"Authorization": f"Bearer {request.access_token}"},
                                timeout=30.0
                            )
                            if response.status_code == 200:
                                doc_content = response.text
                        elif doc.mimeType in ["text/plain", "text/markdown", "text/csv"]:
                            # Download text files directly
                            download_url = f"https://www.googleapis.com/drive/v3/files/{doc.id}?alt=media"
                            response = await client.get(
                                download_url,
                                headers={"Authorization": f"Bearer {request.access_token}"},
                                timeout=30.0
                            )
                            if response.status_code == 200:
                                doc_content = response.text
                        elif doc.mimeType == "application/pdf":
                            # Download PDF and extract text
                            download_url = f"https://www.googleapis.com/drive/v3/files/{doc.id}?alt=media"
                            response = await client.get(
                                download_url,
                                headers={"Authorization": f"Bearer {request.access_token}"},
                                timeout=60.0
                            )
                            if response.status_code == 200:
                                pdf_processor = PDFProcessor(extract_images=False)
                                doc_content = await pdf_processor.extract_text_only(response.content)
                except Exception as fetch_err:
                    print(f"[GoogleDocs] Failed to fetch content for {doc.title}: {fetch_err}")

            # Compress content with Token Company if we have content
            if doc_content and compression_service:
                try:
                    compression_result = await compression_service.compress_for_notes(doc_content)
                    if compression_result.success:
                        compressed_content = compression_result.compressed_text
                        original_tokens = compression_result.original_tokens
                        compressed_tokens = compression_result.compressed_tokens
                        compression_ratio = compression_result.compression_ratio
                    else:
                        compressed_content = doc_content
                        original_tokens = compression_service._estimate_tokens(doc_content)
                        compressed_tokens = original_tokens
                except Exception as comp_err:
                    print(f"[GoogleDocs] Compression failed for {doc.title}: {comp_err}")
                    compressed_content = doc_content
            elif doc_content:
                compressed_content = doc_content

            # Store compressed content to Supabase storage
            storage_path = None
            if compressed_content:
                try:
                    storage_path = f"{request.user_id}/{request.session_id}/google_docs/{doc.id}.json"
                    content_json = json.dumps({
                        "text": compressed_content,
                        "metadata": {
                            "doc_id": doc.id,
                            "title": doc.title,
                            "mime_type": doc.mimeType,
                            "original_tokens": original_tokens,
                            "compressed_tokens": compressed_tokens,
                            "compression_ratio": compression_ratio
                        }
                    })
                    try:
                        supabase.storage.from_("compressed_documents").upload(
                            storage_path,
                            content_json.encode(),
                            {"content-type": "application/json"}
                        )
                    except:
                        supabase.storage.from_("compressed_documents").update(
                            storage_path,
                            content_json.encode(),
                            {"content-type": "application/json"}
                        )
                except Exception as store_err:
                    print(f"[GoogleDocs] Failed to store content for {doc.title}: {store_err}")
                    storage_path = None

            # Store in google_docs_materials table with compression stats
            try:
                supabase.table("google_docs_materials").upsert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "google_doc_id": doc.id,
                    "title": doc.title,
                    "url": doc.url,
                    "mime_type": doc.mimeType,
                    "relevance_score": doc.relevanceScore,
                    "is_selected": True,
                    "compressed_storage_path": storage_path,
                    "original_tokens": original_tokens,
                    "compressed_tokens": compressed_tokens,
                    "compression_ratio": compression_ratio,
                    "is_processed": bool(compressed_content)
                }, on_conflict="session_id,google_doc_id").execute()
            except Exception as e:
                print(f"[GoogleDocs] Failed to store doc metadata: {e}")

            if doc_content:
                doc_contents.append({"title": doc.title, "content": doc_content[:2000]})  # Preview for node generation

        # Generate nodes from document titles AND content using Gemini
        titles_formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(doc_titles)])
        content_preview = "\n\n".join([f"=== {d['title']} ===\n{d['content']}" for d in doc_contents[:5]]) if doc_contents else "No content fetched"
        existing_formatted = ", ".join(existing_labels) if existing_labels else "None yet"

        prompt = f"""You are analyzing a researcher's Google Drive documents to map their knowledge graph.

INPUT:
- Central research question: "{central_topic}"
- Existing knowledge nodes: {existing_formatted}
- Documents found:
{titles_formatted}

CONTENT PREVIEW (first 2000 chars of each):
{content_preview[:8000]}

TASK:
Based on both the titles AND the actual content, identify up to 15 specific concepts, methods, or theories this researcher has notes on or understands.

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "concept name (1-3 words)",
      "type": "concept" | "method" | "theory" | "tool",
      "domain": "field/subject area",
      "relevance_to_topic": "brief explanation of how this relates to their research question",
      "mastery_estimate": 0.0-1.0
    }}
  ]
}}"""

        response_text = await call_gemini(prompt)
        result = extract_json_from_response(response_text)
        nodes = result.get("nodes", [])

        # Store nodes in database
        for node in nodes:
            supabase.table("knowledge_nodes").insert({
                "session_id": request.session_id,
                "label": node.get("label"),
                "type": node.get("type"),
                "domain": node.get("domain"),
                "mastery_estimate": node.get("mastery_estimate"),
                "relevance_to_topic": node.get("relevance_to_topic"),
                "source": "google_drive",
                "is_llm_generated": True
            }).execute()

        return NodesResponse(success=True, nodes=[KnowledgeNode(**n) for n in nodes])

    except Exception as e:
        import traceback
        traceback.print_exc()
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


# ============ Zotero OAuth Endpoints ============

@app.post("/api/zotero/oauth/initiate", response_model=ZoteroOAuthInitiateResponse)
async def zotero_oauth_initiate(request: ZoteroOAuthInitiateRequest):
    """Initiate Zotero OAuth flow. Returns URL to redirect user to."""
    if not ZOTERO_CLIENT_KEY or not ZOTERO_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Zotero OAuth not configured")

    try:
        # Callback URL that Zotero will redirect to after user authorizes
        callback_url = f"{FRONTEND_URL}/zotero/callback"

        # Get request token from Zotero
        oauth_token, oauth_token_secret = await zotero_oauth_request_token(callback_url)

        # Generate state token for CSRF protection
        state_token = secrets.token_urlsafe(32)

        # Store temporary OAuth state in database
        supabase.table("zotero_oauth_states").insert({
            "state_token": state_token,
            "oauth_token": oauth_token,
            "oauth_token_secret": oauth_token_secret,
            "user_id": request.user_id,
        }).execute()

        # Build authorization URL
        authorization_url = f"https://www.zotero.org/oauth/authorize?oauth_token={oauth_token}&library_access=1&notes_access=1&write_access=0"

        return ZoteroOAuthInitiateResponse(
            authorization_url=authorization_url,
            state=state_token
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/zotero/oauth/callback")
async def zotero_oauth_callback(oauth_token: str, oauth_verifier: str, state: str):
    """Handle Zotero OAuth callback. Exchange tokens and store connection."""
    try:
        print(f"[Zotero Callback] Received oauth_token={oauth_token[:10]}..., oauth_verifier={oauth_verifier[:10]}..., state={state[:10]}...")

        # Look up the OAuth state
        state_result = supabase.table("zotero_oauth_states").select("*").eq("state_token", state).single().execute()
        if not state_result.data:
            print(f"[Zotero Callback] State not found: {state}")
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

        state_data = state_result.data
        user_id = state_data["user_id"]
        stored_oauth_token = state_data["oauth_token"]
        oauth_token_secret = state_data["oauth_token_secret"]
        expires_at = state_data.get("expires_at")

        # Check if state has expired
        if expires_at:
            from datetime import timezone
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires_dt:
                print(f"[Zotero Callback] State expired at {expires_at}")
                # Clean up expired state
                supabase.table("zotero_oauth_states").delete().eq("state_token", state).execute()
                raise HTTPException(status_code=400, detail="OAuth state expired. Please try connecting again.")

        # Verify the oauth_token matches what we stored
        if stored_oauth_token != oauth_token:
            print(f"[Zotero Callback] Token mismatch! Stored: {stored_oauth_token[:10]}..., Received: {oauth_token[:10]}...")
            raise HTTPException(status_code=400, detail="OAuth token mismatch")

        print(f"[Zotero Callback] State valid. User ID: {user_id}")
        print(f"[Zotero Callback] oauth_token_secret from DB: {oauth_token_secret[:10] if oauth_token_secret else 'EMPTY'}...")
        print(f"[Zotero Callback] oauth_verifier: {oauth_verifier}")

        # Exchange for access token
        access_token, access_token_secret, zotero_user_id, username = await zotero_oauth_access_token(
            oauth_token, oauth_token_secret, oauth_verifier
        )

        # Check if connection already exists
        existing = supabase.table("zotero_connections").select("id").eq("user_id", user_id).execute()

        if existing.data:
            # Update existing connection
            supabase.table("zotero_connections").update({
                "zotero_user_id": zotero_user_id,
                "oauth_token": access_token,
                "oauth_token_secret": access_token_secret,
                "username": username,
            }).eq("user_id", user_id).execute()
        else:
            # Create new connection
            supabase.table("zotero_connections").insert({
                "user_id": user_id,
                "zotero_user_id": zotero_user_id,
                "oauth_token": access_token,
                "oauth_token_secret": access_token_secret,
                "username": username,
            }).execute()

        # Clean up OAuth state
        supabase.table("zotero_oauth_states").delete().eq("state_token", state).execute()

        return {
            "success": True,
            "zotero_user_id": zotero_user_id,
            "username": username
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/zotero/status/{user_id}", response_model=ZoteroConnectionStatus)
async def zotero_connection_status(user_id: int):
    """Check if user has connected their Zotero account."""
    try:
        result = supabase.table("zotero_connections").select("zotero_user_id, username").eq("user_id", user_id).execute()

        if result.data and len(result.data) > 0:
            return ZoteroConnectionStatus(
                connected=True,
                zotero_user_id=result.data[0].get("zotero_user_id"),
                username=result.data[0].get("username")
            )

        return ZoteroConnectionStatus(connected=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/zotero/disconnect/{user_id}")
async def zotero_disconnect(user_id: int):
    """Disconnect user's Zotero account."""
    try:
        supabase.table("zotero_connections").delete().eq("user_id", user_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/zotero/items/{user_id}")
async def get_zotero_items(user_id: int, limit: int = 100):
    """Fetch items from user's Zotero library."""
    try:
        # Get user's Zotero connection
        connection = supabase.table("zotero_connections").select("*").eq("user_id", user_id).single().execute()

        if not connection.data:
            raise HTTPException(status_code=404, detail="Zotero not connected")

        zotero_user_id = connection.data["zotero_user_id"]
        oauth_token = connection.data["oauth_token"]

        if not oauth_token:
            raise HTTPException(status_code=400, detail="Invalid Zotero connection - missing token")

        # Fetch items from Zotero API
        url = f"https://api.zotero.org/users/{zotero_user_id}/items"
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Zotero-API-Version": "3"
        }
        params = {
            "limit": limit,
            "sort": "dateModified",
            "direction": "desc",
            "itemType": "-attachment"  # Exclude attachments
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)

            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="Zotero access denied - please reconnect")

            response.raise_for_status()
            items = response.json()

        # Transform items to a simpler format
        result = []
        for item in items:
            data = item.get("data", {})
            if data.get("itemType") == "attachment":
                continue

            creators = data.get("creators", [])
            authors = [
                f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                for c in creators
                if c.get("creatorType") == "author"
            ]

            result.append({
                "key": item.get("key"),
                "title": data.get("title", "Untitled"),
                "itemType": data.get("itemType", "unknown"),
                "creators": authors,
                "date": data.get("date"),
                "url": data.get("url"),
                "DOI": data.get("DOI"),
                "abstractNote": data.get("abstractNote", "")[:500] if data.get("abstractNote") else None
            })

        return {"items": result, "total": len(result)}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/worker/status")
async def get_worker_status():
    """Get document processing worker status and statistics."""
    if document_worker:
        return {
            "enabled": True,
            **document_worker.get_stats()
        }
    return {
        "enabled": False,
        "reason": "TOKEN_COMPANY_API_KEY not configured"
    }


# ============ Zotero Items Processing ============

class ZoteroItemInput(BaseModel):
    key: str
    title: str
    itemType: str
    creators: Optional[List[str]] = None
    date: Optional[str] = None
    url: Optional[str] = None
    DOI: Optional[str] = None
    abstractNote: Optional[str] = None


class ZoteroItemsRequest(BaseModel):
    items: List[ZoteroItemInput]
    session_id: str
    user_id: int


@app.post("/api/profile/zotero-items", response_model=NodesResponse)
async def submit_zotero_items(request: ZoteroItemsRequest):
    """Process selected Zotero items and generate knowledge nodes."""
    try:
        # Get session to retrieve central_topic
        session = supabase.table("learning_sessions").select("*").eq("id", request.session_id).single().execute()
        central_topic = session.data["central_topic"]

        # Get existing nodes
        existing_nodes_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        existing_labels = [n["label"] for n in existing_nodes_result.data]

        # Store Zotero items and collect titles
        paper_titles = []
        for item in request.items:
            paper_titles.append(item.title)

            # Store in academia_materials table
            try:
                supabase.table("academia_materials").insert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "title": item.title,
                    "material_type": "paper_read",
                    "source_type": "zotero",
                    "external_id": item.key,
                    "external_url": item.url or (f"https://doi.org/{item.DOI}" if item.DOI else None),
                    "abstract_text": item.abstractNote,
                    "authors": item.creators,
                    "publication_date": item.date,
                    "is_processed": False  # No full text available from Zotero metadata
                }).execute()
            except Exception as e:
                print(f"[Zotero] Failed to store item: {e}")

        # Generate nodes from paper titles using Gemini
        if len(paper_titles) > 5:
            # For many papers, use batch processing
            nodes = await generate_paper_nodes(central_topic, existing_labels, paper_titles)
        else:
            # For few papers, generate nodes individually
            all_nodes = []
            for title in paper_titles:
                paper_nodes = await generate_single_paper_nodes(title)
                all_nodes.extend(paper_nodes)
            nodes = all_nodes

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
                "source": "zotero",
                "is_llm_generated": True
            }).execute()

        return NodesResponse(success=True, nodes=[KnowledgeNode(**n) for n in nodes])

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============ Firecrawl Textbook Extraction Endpoints ============

class ExtractChaptersRequest(BaseModel):
    url: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    save_to_db: bool = True


class ExtractChaptersResponse(BaseModel):
    success: bool
    url: str
    chapters: List[dict] = []
    metadata: Optional[dict] = None
    compressed_markdown: Optional[str] = None
    original_tokens: Optional[int] = None
    compressed_tokens: Optional[int] = None
    compression_ratio: Optional[float] = None
    error: Optional[str] = None


class ScrapeUrlRequest(BaseModel):
    url: str
    formats: List[str] = ["markdown"]
    only_main_content: bool = True


@app.post("/api/extract-chapters", response_model=ExtractChaptersResponse)
async def extract_textbook_chapters(request: ExtractChaptersRequest):
    """
    Extract chapter outlines from ANY textbook or course URL with token compression.

    Just pass a URL - works with Khan Academy, OpenStax, Coursera, etc.
    Uses Firecrawl to scrape the page, Gemini to parse chapters,
    and The Token Company to compress content before saving.

    Args:
        url: The textbook or course URL to extract chapters from
        session_id: Optional - store extracted chapters in session
        user_id: Optional - associate with user
        save_to_db: Whether to save chapters to database (default: true)
    """
    try:
        firecrawl = FirecrawlService(ttc_api_key=TOKEN_COMPANY_API_KEY)

        result = await firecrawl.extract_chapters(url=request.url, compress=True)

        if not result.success:
            return ExtractChaptersResponse(
                success=False,
                url=request.url,
                error=result.error
            )

        # Optionally store chapters in database with COMPRESSED markdown
        if request.save_to_db and request.session_id and request.user_id:
            for chapter in result.chapters:
                supabase.table("textbook_chapters").insert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "source_url": request.url,
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "subtopics": chapter.subtopics,
                    "chapter_url": chapter.url,
                }).execute()

            # Store the compressed content in a new table for the session
            if result.compressed_markdown:
                supabase.table("scraped_content").upsert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "source_url": request.url,
                    "content_type": "textbook_chapters",
                    "compressed_content": result.compressed_markdown,
                    "original_tokens": result.original_tokens,
                    "compressed_tokens": result.compressed_tokens,
                    "compression_ratio": result.compression_ratio,
                }, on_conflict="session_id,source_url").execute()

        return ExtractChaptersResponse(
            success=True,
            url=request.url,
            chapters=[c.model_dump() for c in result.chapters],
            metadata=result.metadata,
            compressed_markdown=result.compressed_markdown,
            original_tokens=result.original_tokens,
            compressed_tokens=result.compressed_tokens,
            compression_ratio=result.compression_ratio
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scrape")
async def scrape_url(request: ScrapeUrlRequest):
    """
    Scrape any URL and return content as markdown with token compression.

    Generic endpoint for scraping any webpage content.
    Returns both original and compressed markdown for efficiency.
    """
    try:
        firecrawl = FirecrawlService(ttc_api_key=TOKEN_COMPANY_API_KEY)

        result = await firecrawl.scrape_url(
            url=request.url,
            formats=request.formats,
            only_main_content=request.only_main_content,
            compress=True  # Always compress scraped content
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chapters/{session_id}")
async def get_session_chapters(session_id: str):
    """Get all extracted textbook chapters for a session."""
    try:
        result = supabase.table("textbook_chapters").select("*").eq("session_id", session_id).execute()
        return {"chapters": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# NEW ONBOARDING ENDPOINTS - Papers Authored & Coursework
# =============================================================================

class PapersAuthoredResponse(BaseModel):
    success: bool
    materials: List[dict] = []
    nodes: List[KnowledgeNode] = []
    error: Optional[str] = None


@app.post("/api/profile/papers-authored", response_model=PapersAuthoredResponse)
async def submit_papers_authored(
    files: List[UploadFile] = File(...),
    session_id: str = Form(...),
    user_id: int = Form(...)
):
    """
    Upload PDFs of papers the user has authored.
    Extracts text and images, compresses with Token Company, stores to Supabase.
    """
    try:
        pdf_processor = PDFProcessor(extract_images=True)
        compression_service = TokenCompressionService(TOKEN_COMPANY_API_KEY) if TOKEN_COMPANY_API_KEY else None

        # Get session for central_topic
        session = supabase.table("learning_sessions").select("central_topic").eq("id", session_id).single().execute()
        central_topic = session.data.get("central_topic", "")

        materials = []
        all_nodes = []

        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                continue

            pdf_bytes = await file.read()
            paper_title = file.filename.replace('.pdf', '').replace('_', ' ')

            # Extract text and images
            extraction = await pdf_processor.extract_content(pdf_bytes)

            # Compress text with Token Company
            compressed_text = extraction.text
            original_tokens = pdf_processor.estimate_tokens(extraction.text)
            compressed_tokens = original_tokens
            compression_ratio = 1.0

            if compression_service and extraction.text:
                compression_result = await compression_service.compress_for_academic_paper(extraction.text)
                if compression_result.success:
                    compressed_text = compression_result.compressed_text
                    original_tokens = compression_result.original_tokens
                    compressed_tokens = compression_result.compressed_tokens
                    compression_ratio = compression_result.compression_ratio

            # Upload PDF to storage
            storage_path = f"{user_id}/{session_id}/authored/{file.filename}"
            try:
                supabase.storage.from_("user-documents").upload(
                    storage_path,
                    pdf_bytes,
                    {"content-type": "application/pdf"}
                )
            except Exception as e:
                # File might already exist, try to update
                try:
                    supabase.storage.from_("user-documents").update(
                        storage_path,
                        pdf_bytes,
                        {"content-type": "application/pdf"}
                    )
                except:
                    pass

            # Upload images to storage and collect refs
            image_refs = []
            for img in extraction.images:
                img_path = f"{user_id}/{session_id}/authored/img_{img.index}.png"
                try:
                    img_bytes = base64.b64decode(img.base64_data)
                    supabase.storage.from_("compressed_documents").upload(
                        img_path,
                        img_bytes,
                        {"content-type": "image/png"}
                    )
                    image_refs.append({
                        "index": img.index,
                        "path": img_path,
                        "page": img.page_number,
                        "width": img.width,
                        "height": img.height
                    })
                except:
                    pass

            # Store compressed JSON to storage
            json_content = {
                "text": compressed_text,
                "image_refs": image_refs,
                "metadata": {
                    "original_tokens": original_tokens,
                    "compressed_tokens": compressed_tokens,
                    "compression_ratio": compression_ratio,
                    "has_figures": len(image_refs) > 0,
                    "figure_count": len(image_refs)
                }
            }
            json_path = f"{user_id}/{session_id}/authored/{file.filename.replace('.pdf', '')}.json"
            try:
                supabase.storage.from_("compressed_documents").upload(
                    json_path,
                    json.dumps(json_content).encode('utf-8'),
                    {"content-type": "application/json"}
                )
            except:
                pass

            # Create material record
            material_id = str(uuid.uuid4())
            material_data = {
                "id": material_id,
                "session_id": session_id,
                "user_id": user_id,
                "material_type": "paper_authored",
                "title": paper_title,
                "source_type": "pdf_upload",
                "storage_bucket": "user-documents",
                "storage_path": storage_path,
                "file_name": file.filename,
                "file_size_bytes": len(pdf_bytes),
                "is_processed": True,
                "ttc_processed": True if compression_service else False,
                "original_token_count": original_tokens,
                "compressed_token_count": compressed_tokens,
                "compression_ratio": compression_ratio,
                "compressed_storage_bucket": "compressed_documents",
                "compressed_storage_path": json_path,
                "pdf_extraction_method": "pymupdf"
            }
            supabase.table("academia_materials").insert(material_data).execute()
            materials.append(material_data)

            # Generate nodes from paper title
            nodes = await generate_single_paper_nodes(paper_title)
            for node in nodes:
                node["source"] = "paper_authored"
                supabase.table("knowledge_nodes").insert({
                    "session_id": session_id,
                    "label": node.get("label"),
                    "type": node.get("type"),
                    "domain": node.get("domain"),
                    "mastery_estimate": 0.8,  # Higher mastery for authored papers
                    "relevance_to_topic": f"From your authored paper: {paper_title}",
                    "source": "paper_authored",
                    "is_llm_generated": True
                }).execute()
                all_nodes.append(KnowledgeNode(**node))

        return PapersAuthoredResponse(
            success=True,
            materials=materials,
            nodes=all_nodes
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return PapersAuthoredResponse(success=False, error=str(e))


class CourseworkUrlRequest(BaseModel):
    urls: List[str]
    session_id: str
    user_id: int


class CourseworkUrlResponse(BaseModel):
    success: bool
    scraped_count: int = 0
    chapters: List[dict] = []
    nodes: List[KnowledgeNode] = []
    error: Optional[str] = None


@app.post("/api/profile/coursework-urls", response_model=CourseworkUrlResponse)
async def submit_coursework_urls(request: CourseworkUrlRequest):
    """
    Scrape coursework URLs using Firecrawl.
    Extracts chapters/content, compresses with Token Company, stores to Supabase.
    """
    try:
        firecrawl = FirecrawlService(ttc_api_key=TOKEN_COMPANY_API_KEY)

        # Get session for central_topic
        session = supabase.table("learning_sessions").select("central_topic").eq("id", request.session_id).single().execute()
        central_topic = session.data.get("central_topic", "")

        all_chapters = []
        all_nodes = []
        scraped_count = 0

        for url in request.urls:
            try:
                # Scrape URL and extract chapters
                result = await firecrawl.extract_chapters(
                    url=url,
                    use_gemini_parsing=True,
                    gemini_api_key=GEMINI_API_KEY,
                    compress=True
                )

                if not result.success:
                    continue

                scraped_count += 1

                # Store scraped content
                content_id = str(uuid.uuid4())
                supabase.table("scraped_content").insert({
                    "id": content_id,
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "source_url": url,
                    "content_type": "course_material",
                    "raw_content_preview": result.raw_markdown[:2000] if result.raw_markdown else None,
                    "compressed_content": result.compressed_markdown or "",
                    "original_tokens": result.original_tokens or 0,
                    "compressed_tokens": result.compressed_tokens or 0,
                    "compression_ratio": result.compression_ratio or 1.0,
                    "scraper_type": "firecrawl",
                    "page_title": result.metadata.get("title") if result.metadata else None,
                    "page_metadata": result.metadata
                }).execute()

                # Store chapters
                for chapter in result.chapters:
                    chapter_data = {
                        "session_id": request.session_id,
                        "user_id": request.user_id,
                        "scraper_id": content_id,
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "subtopics": chapter.subtopics,
                        "source_url": url,
                        "chapter_url": chapter.url
                    }
                    supabase.table("textbook_chapters").insert(chapter_data).execute()
                    all_chapters.append(chapter_data)

                # Generate nodes from chapter titles
                chapter_titles = [ch.title for ch in result.chapters[:10]]  # Limit to 10
                if chapter_titles:
                    nodes = await generate_coursework_nodes(central_topic, chapter_titles)
                    for node in nodes:
                        supabase.table("knowledge_nodes").insert({
                            "session_id": request.session_id,
                            "label": node.get("label"),
                            "type": node.get("type", "concept"),
                            "domain": node.get("domain"),
                            "mastery_estimate": 0.3,  # Lower mastery - content to learn
                            "relevance_to_topic": node.get("relevance_to_topic"),
                            "source": "coursework",
                            "is_llm_generated": True
                        }).execute()
                        all_nodes.append(KnowledgeNode(**node))

            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue

        return CourseworkUrlResponse(
            success=True,
            scraped_count=scraped_count,
            chapters=all_chapters,
            nodes=all_nodes
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return CourseworkUrlResponse(success=False, error=str(e))


@app.post("/api/profile/coursework-transcript", response_model=NodesResponse)
async def submit_coursework_transcript(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    user_id: int = Form(...)
):
    """
    Upload academic transcript PDF.
    Extracts courses, compresses text with Token Company, stores to Supabase.
    """
    try:
        pdf_processor = PDFProcessor(extract_images=False)
        compression_service = TokenCompressionService(TOKEN_COMPANY_API_KEY) if TOKEN_COMPANY_API_KEY else None

        # Get session for central_topic
        session = supabase.table("learning_sessions").select("central_topic").eq("id", session_id).single().execute()
        central_topic = session.data.get("central_topic", "")

        pdf_bytes = await file.read()

        # Extract text from transcript
        text = await pdf_processor.extract_text_only(pdf_bytes)

        # Compress text with Token Company
        compressed_text = text
        original_tokens = pdf_processor.estimate_tokens(text) if text else 0
        compressed_tokens = original_tokens
        compression_ratio = 1.0

        if compression_service and text:
            try:
                compression_result = await compression_service.compress_for_notes(text)
                if compression_result.success:
                    compressed_text = compression_result.compressed_text
                    original_tokens = compression_result.original_tokens
                    compressed_tokens = compression_result.compressed_tokens
                    compression_ratio = compression_result.compression_ratio
            except Exception as comp_err:
                print(f"[Transcript] Compression failed: {comp_err}")

        # Use Gemini to extract courses from transcript
        courses = await extract_courses_from_transcript(text)

        # Upload transcript PDF to storage
        storage_path = f"{user_id}/{session_id}/transcript/{file.filename}"
        try:
            supabase.storage.from_("user-documents").upload(
                storage_path,
                pdf_bytes,
                {"content-type": "application/pdf"}
            )
        except:
            pass

        # Store compressed content to storage
        compressed_storage_path = f"{user_id}/{session_id}/transcript/{file.filename.replace('.pdf', '')}_compressed.json"
        try:
            content_json = json.dumps({
                "text": compressed_text,
                "courses": courses,
                "metadata": {
                    "original_tokens": original_tokens,
                    "compressed_tokens": compressed_tokens,
                    "compression_ratio": compression_ratio,
                    "course_count": len(courses) if courses else 0
                }
            })
            try:
                supabase.storage.from_("compressed_documents").upload(
                    compressed_storage_path,
                    content_json.encode(),
                    {"content-type": "application/json"}
                )
            except:
                supabase.storage.from_("compressed_documents").update(
                    compressed_storage_path,
                    content_json.encode(),
                    {"content-type": "application/json"}
                )
        except Exception as store_err:
            print(f"[Transcript] Failed to store compressed content: {store_err}")
            compressed_storage_path = None

        # Store as material with compression stats
        supabase.table("academia_materials").insert({
            "session_id": session_id,
            "user_id": user_id,
            "material_type": "educational_course",
            "title": "Academic Transcript",
            "source_type": "pdf_upload",
            "storage_bucket": "user-documents",
            "storage_path": storage_path,
            "compressed_storage_bucket": "compressed_documents",
            "compressed_storage_path": compressed_storage_path,
            "file_name": file.filename,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "compression_ratio": compression_ratio,
            "is_processed": True
        }).execute()

        # Generate nodes from courses
        all_nodes = []
        if courses:
            nodes = await generate_transcript_nodes(central_topic, courses)
            for node in nodes:
                supabase.table("knowledge_nodes").insert({
                    "session_id": session_id,
                    "label": node.get("label"),
                    "type": node.get("type", "concept"),
                    "domain": node.get("domain"),
                    "confidence": node.get("confidence", 0.7),
                    "mastery_estimate": node.get("mastery_estimate", 0.6),
                    "relevance_to_topic": node.get("relevance_to_topic"),
                    "source": "transcript",
                    "is_llm_generated": True
                }).execute()
                all_nodes.append(KnowledgeNode(**node))

        return NodesResponse(success=True, nodes=all_nodes)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


async def generate_coursework_nodes(central_topic: str, chapter_titles: List[str]) -> List[dict]:
    """Generate knowledge nodes from coursework chapter titles."""
    titles_formatted = "\n".join([f"- {t}" for t in chapter_titles])

    prompt = f"""You are analyzing coursework chapters to identify concepts relevant to a learning topic.

INPUT:
- Learning topic: "{central_topic}"
- Course chapters:
{titles_formatted}

TASK:
Identify 4-6 key concepts from these chapters that are relevant to the learning topic.

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "concept name (1-3 words)",
      "type": "concept",
      "domain": "broader category",
      "relevance_to_topic": "How this concept relates to {central_topic}"
    }}
  ]
}}

CONSTRAINTS:
- Focus on concepts that bridge the coursework to the learning topic
- Return 4-6 nodes
- Labels should be concise (1-3 words)"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result.get("nodes", [])


async def extract_courses_from_transcript(transcript_text: str) -> List[str]:
    """Extract course names from academic transcript text."""
    prompt = f"""Extract all course names/titles from this academic transcript.

TRANSCRIPT TEXT:
{transcript_text[:10000]}

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "courses": [
    "Course Name 1",
    "Course Name 2"
  ]
}}

CONSTRAINTS:
- Extract actual course names, not grades or credits
- Include course codes if present (e.g., "CS 229 Machine Learning")
- Return at most 30 courses"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result.get("courses", [])


async def generate_transcript_nodes(central_topic: str, courses: List[str]) -> List[dict]:
    """Generate knowledge nodes from transcript courses."""
    courses_formatted = "\n".join([f"- {c}" for c in courses[:20]])  # Limit to 20 courses

    prompt = f"""You are analyzing a student's completed coursework to identify their existing knowledge.

INPUT:
- Learning topic they want to study: "{central_topic}"
- Courses they've completed:
{courses_formatted}

TASK:
Identify 5-8 knowledge areas from these courses that are relevant to their learning topic.
Focus on skills and concepts that will help them learn "{central_topic}".

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "knowledge area (1-2 words)",
      "type": "concept",
      "domain": "broader category",
      "confidence": 0.7,
      "mastery_estimate": 0.6,
      "relevance_to_topic": "How this knowledge helps them learn {central_topic}"
    }}
  ]
}}

CONSTRAINTS:
- Labels should be concise (1-2 words)
- confidence reflects how certain the course covers this topic
- mastery_estimate reflects expected proficiency from taking the course
- Return 5-8 nodes that bridge their coursework to their learning goal"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result.get("nodes", [])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
