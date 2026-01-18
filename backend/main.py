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


# ============ Learning Path Models ============

class LearningPathRequest(BaseModel):
    session_id: str
    user_id: int


class ConceptNode(BaseModel):
    name: str
    description: str
    is_prerequisite: bool = False
    prerequisites: List[str] = []
    difficulty_level: int = 1  # 1-5
    estimated_hours: float = 1.0
    is_known: bool = False  # True if user already knows this from papers
    source_papers: List[str] = []  # Titles of papers that cover this


class LearningPathResponse(BaseModel):
    success: bool
    domain: str = ""
    subdomain: str = ""
    concepts: List[ConceptNode] = []
    knowledge_gaps: List[str] = []  # Concepts user hasn't learned
    known_concepts: List[str] = []  # Concepts user already knows
    learning_path_order: List[str] = []  # Ordered list of concepts to learn
    total_estimated_hours: float = 0.0
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


# =============================================================================
# PREREQUISITES GENERATION - True Prerequisites for Learning Path
# =============================================================================

class PrerequisiteItem(BaseModel):
    name: str
    description: str
    confidence: float = 0.8
    order_index: int = 0
    is_foundational: bool = False


class PrerequisitesGenerateRequest(BaseModel):
    session_id: str
    user_id: int


class PrerequisitesGenerateResponse(BaseModel):
    success: bool
    prerequisites: List[PrerequisiteItem] = []
    needs_confirmation: List[PrerequisiteItem] = []
    error: Optional[str] = None


class PrerequisitesConfirmRequest(BaseModel):
    session_id: str
    user_id: int
    confirmed_prerequisites: List[str]
    rejected_prerequisites: List[str] = []


class PrerequisitesConfirmResponse(BaseModel):
    success: bool
    total_topics: int = 0
    error: Optional[str] = None


async def generate_prerequisites_for_topic(central_topic: str, user_background: List[str]) -> dict:
    """Use Gemini to generate true prerequisites for learning a topic."""
    background_formatted = "\n".join([f"- {b}" for b in user_background]) if user_background else "None provided"

    prompt = f"""You are an expert educator creating a learning path for a student.

STUDENT WANTS TO LEARN: "{central_topic}"

STUDENT'S EXISTING KNOWLEDGE:
{background_formatted}

TASK:
Identify the TRUE PREREQUISITES needed to understand "{central_topic}". These should be:
1. Foundational concepts that MUST be understood first
2. Ordered from most basic to most advanced
3. Realistic - what would a textbook chapter sequence look like?

For each prerequisite, assess:
- confidence: How confident are you this is truly needed? (0.0-1.0)
  - 0.9-1.0: Absolutely essential
  - 0.7-0.9: Very important
  - 0.5-0.7: Helpful but debatable (mark for user confirmation)
  - Below 0.5: Don't include

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "prerequisites": [
    {{
      "name": "prerequisite topic (2-5 words)",
      "description": "One sentence explaining what this covers and why it's needed",
      "confidence": 0.0-1.0,
      "order_index": 0,
      "is_foundational": true/false
    }}
  ]
}}

CONSTRAINTS:
- Return 8-15 prerequisites, ordered from foundational to advanced
- is_foundational=true for the first 3-5 most basic concepts
- Be specific: "Linear Algebra Basics" not just "Math"
- Consider what someone would need to read in a textbook BEFORE the target topic
- Skip anything the student already knows based on their background"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result


@app.post("/api/prerequisites/generate", response_model=PrerequisitesGenerateResponse)
async def generate_prerequisites(request: PrerequisitesGenerateRequest):
    """Generate true prerequisites for the user's learning topic."""
    try:
        # Get session for central topic
        session = supabase.table("learning_sessions").select("central_topic").eq("id", request.session_id).single().execute()
        if not session.data:
            raise HTTPException(status_code=404, detail="Session not found")

        central_topic = session.data["central_topic"]

        # Get user's existing knowledge from knowledge_nodes
        knowledge_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        user_background = [n["label"] for n in knowledge_result.data if n.get("label")]

        # Generate prerequisites via Gemini
        result = await generate_prerequisites_for_topic(central_topic, user_background)
        prerequisites_data = result.get("prerequisites", [])

        prerequisites = []
        needs_confirmation = []

        for i, p in enumerate(prerequisites_data):
            prereq = PrerequisiteItem(
                name=p.get("name", ""),
                description=p.get("description", ""),
                confidence=p.get("confidence", 0.8),
                order_index=i,
                is_foundational=p.get("is_foundational", False)
            )
            prerequisites.append(prereq)

            # Flag low-confidence items for user confirmation
            if 0.5 <= prereq.confidence < 0.7:
                needs_confirmation.append(prereq)

        return PrerequisitesGenerateResponse(
            success=True,
            prerequisites=prerequisites,
            needs_confirmation=needs_confirmation
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return PrerequisitesGenerateResponse(success=False, error=str(e))


@app.post("/api/prerequisites/confirm", response_model=PrerequisitesConfirmResponse)
async def confirm_prerequisites(request: PrerequisitesConfirmRequest):
    """Confirm prerequisites and create lesson topics."""
    try:
        # Get session
        session = supabase.table("learning_sessions").select("central_topic").eq("id", request.session_id).single().execute()
        if not session.data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Store confirmed prerequisites as lesson_topics
        for i, prereq_name in enumerate(request.confirmed_prerequisites):
            # Check if topic already exists
            existing = supabase.table("lesson_topics").select("id").eq("session_id", request.session_id).eq("topic_name", prereq_name).execute()

            if not existing.data:
                supabase.table("lesson_topics").insert({
                    "session_id": request.session_id,
                    "topic_name": prereq_name,
                    "order_index": i,
                    "is_confirmed": True,
                    "mastery_level": 0.0
                }).execute()

        return PrerequisitesConfirmResponse(
            success=True,
            total_topics=len(request.confirmed_prerequisites)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return PrerequisitesConfirmResponse(success=False, error=str(e))


# =============================================================================
# LEARNING PATH GENERATION - Gap Analysis & Concept Decomposition
# =============================================================================

async def generate_learning_path_analysis(
    central_topic: str,
    paper_titles: List[str],
    existing_knowledge: List[str]
) -> dict:
    """
    Use Gemini to:
    1. Identify the research domain based on paper titles
    2. Decompose the topic into sub-concepts with prerequisites
    3. Determine which concepts user knows (from papers) vs gaps
    """
    papers_formatted = "\n".join([f"- {t}" for t in paper_titles]) if paper_titles else "None"
    knowledge_formatted = "\n".join([f"- {k}" for k in existing_knowledge]) if existing_knowledge else "None"

    prompt = f"""You are an expert academic advisor analyzing a researcher's knowledge to create a personalized learning path.

INPUT:
- Research question/topic: "{central_topic}"
- Papers the user has read:
{papers_formatted}
- Existing knowledge nodes from their background:
{knowledge_formatted}

TASK:
1. DOMAIN IDENTIFICATION: Based on the papers read and topic, identify the primary research domain and subdomain.
   - Consider overlaps: e.g., "CS Education" if they read both CS and Education papers
   - Be specific: not just "Computer Science" but "Machine Learning" or "Natural Language Processing"

2. CONCEPT DECOMPOSITION: Break down the research topic into 15-25 specific sub-concepts that someone would need to learn to deeply understand it.
   - Include foundational prerequisites (mark as is_prerequisite: true)
   - Include advanced concepts specific to the topic
   - Order them from foundational to advanced

3. KNOWLEDGE GAP ANALYSIS: For each concept, determine if the user's papers likely cover it.
   - Mark is_known: true if their paper titles suggest they've learned this
   - Mark is_known: false if this is a gap in their knowledge

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "domain": "primary research domain",
  "subdomain": "specific subdomain or intersection",
  "concepts": [
    {{
      "name": "concept name (2-4 words)",
      "description": "1-2 sentence explanation of what this concept covers",
      "is_prerequisite": true/false,
      "prerequisites": ["list", "of", "concept", "names", "that must be learned first"],
      "difficulty_level": 1-5,
      "estimated_hours": number of hours to learn,
      "is_known": true/false,
      "source_papers": ["titles of papers that cover this concept"]
    }}
  ],
  "learning_path_order": ["ordered", "list", "of", "concept", "names", "to", "learn"]
}}

CONSTRAINTS:
- Return 15-25 concepts total
- Prerequisites should be listed first in the learning_path_order
- difficulty_level: 1=foundational, 2=intermediate, 3=advanced, 4=expert, 5=cutting-edge
- estimated_hours should be realistic (1-20 hours per concept)
- source_papers must only include exact titles from the user's paper list
- is_known should be true ONLY if the user's papers clearly cover this concept
- Concepts with is_known=true should NOT be in learning_path_order (they already know it)"""

    response_text = await call_gemini(prompt)
    result = extract_json_from_response(response_text)
    return result


@app.post("/api/learning-path/generate", response_model=LearningPathResponse)
async def generate_learning_path(request: LearningPathRequest):
    """
    Generate a personalized learning path based on user's reading history.

    This endpoint:
    1. Fetches all papers the user has read
    2. Uses Gemini to identify their research domain
    3. Decomposes the topic into sub-concepts and prerequisites
    4. Identifies knowledge gaps (concepts not covered by papers)
    5. Stores results in Supabase for monitoring
    """
    try:
        # Get session to retrieve central_topic
        session = supabase.table("learning_sessions").select("*").eq("id", request.session_id).single().execute()
        if not session.data:
            raise HTTPException(status_code=404, detail="Session not found")

        central_topic = session.data["central_topic"]

        # Fetch all papers the user has read for this session
        papers_result = supabase.table("academia_materials").select("title, material_type").eq("session_id", request.session_id).eq("user_id", request.user_id).execute()

        paper_titles = [
            p["title"] for p in papers_result.data
            if p.get("title") and p.get("material_type") == "paper_read"
        ]

        # Get existing knowledge nodes from background
        knowledge_result = supabase.table("knowledge_nodes").select("label, domain, type").eq("session_id", request.session_id).execute()

        existing_knowledge = [n["label"] for n in knowledge_result.data if n.get("label")]

        # Generate learning path using Gemini
        analysis = await generate_learning_path_analysis(
            central_topic=central_topic,
            paper_titles=paper_titles,
            existing_knowledge=existing_knowledge
        )

        # Extract results
        domain = analysis.get("domain", "")
        subdomain = analysis.get("subdomain", "")
        concepts_data = analysis.get("concepts", [])
        learning_path_order = analysis.get("learning_path_order", [])

        # Separate known concepts from gaps
        known_concepts = []
        knowledge_gaps = []
        concepts = []
        total_hours = 0.0

        for c in concepts_data:
            concept = ConceptNode(
                name=c.get("name", ""),
                description=c.get("description", ""),
                is_prerequisite=c.get("is_prerequisite", False),
                prerequisites=c.get("prerequisites", []),
                difficulty_level=c.get("difficulty_level", 1),
                estimated_hours=c.get("estimated_hours", 1.0),
                is_known=c.get("is_known", False),
                source_papers=c.get("source_papers", [])
            )
            concepts.append(concept)

            if concept.is_known:
                known_concepts.append(concept.name)
            else:
                knowledge_gaps.append(concept.name)
                total_hours += concept.estimated_hours

        # Store in topic_concepts table
        concepts_json = [c.model_dump() for c in concepts]

        # Check if entry already exists
        existing_tc = supabase.table("topic_concepts").select("id").eq("session_id", request.session_id).eq("user_id", request.user_id).execute()

        if existing_tc.data:
            # Update existing
            supabase.table("topic_concepts").update({
                "research_topic": central_topic,
                "concepts": {
                    "domain": domain,
                    "subdomain": subdomain,
                    "concepts": concepts_json,
                    "learning_path_order": learning_path_order
                },
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", existing_tc.data[0]["id"]).execute()
            topic_concepts_id = existing_tc.data[0]["id"]
        else:
            # Create new
            tc_result = supabase.table("topic_concepts").insert({
                "session_id": request.session_id,
                "user_id": request.user_id,
                "research_topic": central_topic,
                "concepts": {
                    "domain": domain,
                    "subdomain": subdomain,
                    "concepts": concepts_json,
                    "learning_path_order": learning_path_order
                }
            }).execute()
            topic_concepts_id = tc_result.data[0]["id"]

        # Store knowledge similarity/gap analysis
        existing_uks = supabase.table("user_knowledge_similarity").select("id").eq("session_id", request.session_id).eq("user_id", request.user_id).execute()

        knowledge_data = {
            "known_concepts": [{"name": k, "source": "papers"} for k in known_concepts],
            "knowledge_gaps": knowledge_gaps,
            "total_known": len(known_concepts),
            "total_gaps": len(knowledge_gaps),
            "coverage_percentage": len(known_concepts) / max(len(concepts), 1) * 100
        }

        if existing_uks.data:
            supabase.table("user_knowledge_similarity").update({
                "topic_concepts_id": topic_concepts_id,
                "known_concepts": knowledge_data,
                "learning_path_suggestion": f"Focus on {len(knowledge_gaps)} concepts: {', '.join(learning_path_order[:5])}{'...' if len(learning_path_order) > 5 else ''}",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", existing_uks.data[0]["id"]).execute()
        else:
            supabase.table("user_knowledge_similarity").insert({
                "session_id": request.session_id,
                "user_id": request.user_id,
                "topic_concepts_id": topic_concepts_id,
                "known_concepts": knowledge_data,
                "learning_path_suggestion": f"Focus on {len(knowledge_gaps)} concepts: {', '.join(learning_path_order[:5])}{'...' if len(learning_path_order) > 5 else ''}"
            }).execute()

        return LearningPathResponse(
            success=True,
            domain=domain,
            subdomain=subdomain,
            concepts=concepts,
            knowledge_gaps=knowledge_gaps,
            known_concepts=known_concepts,
            learning_path_order=learning_path_order,
            total_estimated_hours=total_hours
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return LearningPathResponse(success=False, error=str(e))


@app.get("/api/learning-path/{session_id}")
async def get_learning_path(session_id: str):
    """Get the stored learning path for a session."""
    try:
        # Get topic concepts
        tc_result = supabase.table("topic_concepts").select("*").eq("session_id", session_id).single().execute()

        if not tc_result.data:
            raise HTTPException(status_code=404, detail="Learning path not found. Generate one first.")

        # Get knowledge similarity
        uks_result = supabase.table("user_knowledge_similarity").select("*").eq("session_id", session_id).single().execute()

        return {
            "topic_concepts": tc_result.data,
            "knowledge_analysis": uks_result.data if uks_result.data else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Prerequisites & Lesson Endpoints ============

# Load OpenRouter API key for content aggregation
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
PREREQ_LOW_THRESHOLD = float(os.getenv("PREREQ_LOW_THRESHOLD", "0.3"))
PREREQ_HIGH_THRESHOLD = float(os.getenv("PREREQ_HIGH_THRESHOLD", "0.7"))

# Import content aggregator
from services.content_aggregator import ContentAggregator, ContentType, SourceType


class ActivityItem(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    activity_type: str
    title: str
    embed_url: str
    source_type: str
    source_title: Optional[str] = None
    duration_minutes: Optional[int] = None
    order_index: int
    is_problem: bool = False
    problem_data: Optional[dict] = None


class NextActivityResponse(BaseModel):
    success: bool
    activity: Optional[ActivityItem] = None
    topic_progress: Optional[dict] = None
    is_topic_complete: bool = False
    is_course_complete: bool = False
    error: Optional[str] = None


class CompleteActivityRequest(BaseModel):
    session_id: str
    user_id: int
    activity_id: str
    user_response: Optional[str] = None  # For problem answers
    feedback: Optional[str] = None  # "confused" or "too_easy"


class CompleteActivityResponse(BaseModel):
    success: bool
    mastery_updated: bool = False
    new_mastery_level: float = 0.0
    topic_complete: bool = False
    error: Optional[str] = None


@app.get("/api/prerequisites/{session_id}")
async def get_prerequisites(session_id: str):
    """Get all prerequisites for a session."""
    try:
        result = supabase.table("lesson_topics").select("*").eq("session_id", session_id).order("order_index").execute()
        return {"prerequisites": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lesson/next-activity", response_model=NextActivityResponse)
async def get_next_activity(session_id: str, user_id: int):
    """
    Get the next activity for the user to complete.
    Returns ONE activity at a time with embedded content.
    """
    try:
        # Get current topic (first incomplete, confirmed topic)
        topics_result = supabase.table("lesson_topics").select("*").eq("session_id", session_id).eq("is_confirmed", True).is_("completed_at", "null").order("order_index").limit(1).execute()
        
        if not topics_result.data:
            # Check if course is complete
            all_topics = supabase.table("lesson_topics").select("id").eq("session_id", session_id).eq("is_confirmed", True).execute()
            completed_topics = supabase.table("lesson_topics").select("id").eq("session_id", session_id).eq("is_confirmed", True).not_.is_("completed_at", "null").execute()
            
            if len(all_topics.data) > 0 and len(all_topics.data) == len(completed_topics.data):
                return NextActivityResponse(success=True, is_course_complete=True)
            
            return NextActivityResponse(success=False, error="No topics found. Generate prerequisites first.")
        
        current_topic = topics_result.data[0]
        topic_id = current_topic["id"]
        topic_name = current_topic["topic_name"]
        
        # Check for existing incomplete activity
        existing_activity = supabase.table("lesson_activities").select("*").eq("topic_id", topic_id).eq("completed", False).order("order_index").limit(1).execute()
        
        if existing_activity.data:
            activity = existing_activity.data[0]
            
            # Parse problem data if it's a problem type
            problem_data = None
            is_problem = activity["activity_type"] == "problem"
            if is_problem and activity["embed_url"] and activity["embed_url"].startswith("data:application/json,"):
                try:
                    problem_data = json.loads(activity["embed_url"].replace("data:application/json,", ""))
                except:
                    pass
            
            return NextActivityResponse(
                success=True,
                activity=ActivityItem(
                    id=activity["id"],
                    topic_id=topic_id,
                    topic_name=topic_name,
                    activity_type=activity["activity_type"],
                    title=activity["title"],
                    embed_url=activity["embed_url"],
                    source_type=activity["source_type"],
                    source_title=activity.get("source_title"),
                    duration_minutes=activity.get("duration_minutes"),
                    order_index=activity["order_index"],
                    is_problem=is_problem,
                    problem_data=problem_data
                ),
                topic_progress={
                    "topic_name": topic_name,
                    "mastery_level": current_topic["mastery_level"],
                    "order_index": current_topic["order_index"]
                }
            )
        
        # No existing activity - need to generate new ones
        # Count completed activities for this topic
        completed_count = supabase.table("lesson_activities").select("id").eq("topic_id", topic_id).eq("completed", True).execute()
        activity_count = len(completed_count.data)
        
        # Check if topic should be marked complete (mastery threshold)
        if current_topic["mastery_level"] >= 0.8 or activity_count >= 5:
            # Mark topic as complete
            supabase.table("lesson_topics").update({
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", topic_id).execute()
            
            return NextActivityResponse(
                success=True,
                is_topic_complete=True,
                topic_progress={
                    "topic_name": topic_name,
                    "mastery_level": current_topic["mastery_level"],
                    "order_index": current_topic["order_index"]
                }
            )
        
        # Generate new activity using content aggregator
        if not OPENROUTER_API_KEY:
            return NextActivityResponse(success=False, error="OPENROUTER_API_KEY not configured")
        
        aggregator = ContentAggregator(OPENROUTER_API_KEY, os.getenv("OPENALEX_API_KEY"))
        
        # Determine activity type based on count
        if activity_count == 0:
            # First activity: video
            content_items = await aggregator.search_youtube(topic_name, max_results=1)
        elif activity_count == 1:
            # Second activity: reading
            content_items = await aggregator.search_openalex(topic_name, max_results=1)
        elif activity_count % 3 == 2:
            # Every third activity: problem
            problem = await aggregator.generate_problem(topic_name)
            content_items = [problem] if problem else []
        else:
            # Mix of videos and readings
            search_result = await aggregator.search_content_for_topic(topic_name, max_items=1)
            content_items = search_result.items
        
        if not content_items:
            # Fallback: try general search
            search_result = await aggregator.search_content_for_topic(topic_name, max_items=1)
            content_items = search_result.items
        
        if not content_items:
            return NextActivityResponse(success=False, error=f"Could not find content for topic: {topic_name}")
        
        content = content_items[0]
        
        # Store the new activity
        new_activity = supabase.table("lesson_activities").insert({
            "topic_id": topic_id,
            "activity_type": content.content_type.value,
            "title": content.title,
            "embed_url": content.embed_url,
            "source_type": content.source_type.value,
            "source_title": content.source_title,
            "duration_minutes": content.duration_minutes,
            "order_index": activity_count,
            "completed": False
        }).execute()
        
        activity = new_activity.data[0]
        
        # Parse problem data if it's a problem type
        problem_data = None
        is_problem = content.content_type == ContentType.PROBLEM
        if is_problem and content.embed_url and content.embed_url.startswith("data:application/json,"):
            try:
                problem_data = json.loads(content.embed_url.replace("data:application/json,", ""))
            except:
                pass
        
        return NextActivityResponse(
            success=True,
            activity=ActivityItem(
                id=activity["id"],
                topic_id=topic_id,
                topic_name=topic_name,
                activity_type=content.content_type.value,
                title=content.title,
                embed_url=content.embed_url,
                source_type=content.source_type.value,
                source_title=content.source_title,
                duration_minutes=content.duration_minutes,
                order_index=activity_count,
                is_problem=is_problem,
                problem_data=problem_data
            ),
            topic_progress={
                "topic_name": topic_name,
                "mastery_level": current_topic["mastery_level"],
                "order_index": current_topic["order_index"]
            }
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return NextActivityResponse(success=False, error=str(e))


@app.post("/api/lesson/complete-activity", response_model=CompleteActivityResponse)
async def complete_activity(request: CompleteActivityRequest):
    """
    Mark an activity as complete and update mastery level.
    """
    try:
        # Get the activity
        activity_result = supabase.table("lesson_activities").select("*, lesson_topics(*)").eq("id", request.activity_id).single().execute()
        
        if not activity_result.data:
            raise HTTPException(status_code=404, detail="Activity not found")
        
        activity = activity_result.data
        topic_id = activity["topic_id"]
        
        # Mark activity as complete
        supabase.table("lesson_activities").update({
            "completed": True,
            "completed_at": datetime.utcnow().isoformat(),
            "user_response": request.user_response
        }).eq("id", request.activity_id).execute()
        
        # Get topic and calculate new mastery
        topic_result = supabase.table("lesson_topics").select("*").eq("id", topic_id).single().execute()
        topic = topic_result.data
        
        # Count completed activities
        completed = supabase.table("lesson_activities").select("id").eq("topic_id", topic_id).eq("completed", True).execute()
        completed_count = len(completed.data)
        
        # Calculate mastery based on completed activities (simple formula)
        # Each activity adds ~0.2 to mastery, capped at 1.0
        base_mastery = completed_count * 0.2
        
        # Adjust based on feedback
        if request.feedback == "confused":
            # Reduce mastery gain when confused
            base_mastery = max(0, base_mastery - 0.1)
        elif request.feedback == "too_easy":
            # Boost mastery when content is too easy
            base_mastery = base_mastery + 0.15
        
        new_mastery = min(1.0, base_mastery)
        
        # Update topic mastery
        supabase.table("lesson_topics").update({
            "mastery_level": new_mastery
        }).eq("id", topic_id).execute()
        
        # Check if topic is complete
        topic_complete = new_mastery >= 0.8 or completed_count >= 5
        
        if topic_complete:
            supabase.table("lesson_topics").update({
                "completed_at": datetime.utcnow().isoformat()
            }).eq("id", topic_id).execute()
        
        return CompleteActivityResponse(
            success=True,
            mastery_updated=True,
            new_mastery_level=new_mastery,
            topic_complete=topic_complete
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return CompleteActivityResponse(success=False, error=str(e))


@app.post("/api/lesson/skip-topic")
async def skip_topic(session_id: str, user_id: int):
    """Skip the current topic and move to the next one."""
    try:
        # Get current topic
        topics_result = supabase.table("lesson_topics").select("*").eq("session_id", session_id).eq("is_confirmed", True).is_("completed_at", "null").order("order_index").limit(1).execute()
        
        if not topics_result.data:
            return {"success": False, "error": "No active topic to skip"}
        
        current_topic = topics_result.data[0]
        
        # Mark as complete (skipped)
        supabase.table("lesson_topics").update({
            "completed_at": datetime.utcnow().isoformat(),
            "mastery_level": 0.0  # No mastery for skipped topics
        }).eq("id", current_topic["id"]).execute()
        
        return {"success": True, "skipped_topic": current_topic["topic_name"]}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/lesson/progress/{session_id}")
async def get_lesson_progress(session_id: str):
    """Get overall lesson progress for a session."""
    try:
        # Get all topics
        topics = supabase.table("lesson_topics").select("*").eq("session_id", session_id).eq("is_confirmed", True).order("order_index").execute()
        
        total = len(topics.data)
        completed = sum(1 for t in topics.data if t.get("completed_at"))
        avg_mastery = sum(t.get("mastery_level", 0) for t in topics.data) / max(total, 1)
        
        return {
            "success": True,
            "total_topics": total,
            "completed_topics": completed,
            "average_mastery": avg_mastery,
            "progress_percentage": (completed / max(total, 1)) * 100,
            "topics": topics.data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LESSON CONTENT AGGREGATION - Full lesson with problems from math sources
# =============================================================================

class LessonContentRequest(BaseModel):
    session_id: str
    user_id: int
    topic_id: Optional[str] = None  # If None, use current topic


class MathProblem(BaseModel):
    problem: str
    hints: List[str] = []
    solution: str = ""
    answer: str = ""
    source: str = ""
    source_url: str = ""
    difficulty: str = "medium"
    latex_content: bool = True


class VideoEmbed(BaseModel):
    video_id: str
    title: str
    source: str = "youtube"
    embed_url: str


class LessonContentResponse(BaseModel):
    success: bool
    topic_name: str = ""
    lesson_content: str = ""  # Markdown formatted lesson text
    video: Optional[VideoEmbed] = None  # Embedded video for the topic
    problems: List[MathProblem] = []
    error: Optional[str] = None
    abstraction_level: int = 3  # 1-5, where 1 is simplest


class SimplifyContentRequest(BaseModel):
    session_id: str
    topic_id: Optional[str] = None
    target_abstraction_level: int = 2  # 1-5, where 1 is simplest
    current_content: Optional[str] = None  # Optional: existing content to simplify


class SimplifyContentResponse(BaseModel):
    success: bool
    topic_name: str = ""
    simplified_content: str = ""
    abstraction_level: int = 2
    error: Optional[str] = None


async def generate_simplified_lesson(
    topic: str,
    user_background: List[str],
    abstraction_level: int = 2,
    current_content: Optional[str] = None
) -> str:
    """
    Generate lesson content at a specified abstraction level.

    Levels:
    1 = ELI5 (Explain Like I'm 5) - Very simple analogies, no jargon
    2 = Beginner - Simple language, basic examples, minimal formulas
    3 = Intermediate - Standard explanation with some formulas
    4 = Advanced - Technical language, full mathematical treatment
    5 = Expert - Research-level, assumes prior knowledge
    """
    background_str = ", ".join(user_background[:5]) if user_background else "general audience"

    level_descriptions = {
        1: """EXPLAIN LIKE I'M NEW TO THIS:
- Use simple everyday analogies (like cooking, sports, etc.)
- Avoid ALL technical jargon - use plain words only
- No mathematical formulas at all
- Short sentences, friendly tone
- Focus on intuition and "why this matters"
- Use concrete, visual examples""",

        2: """BEGINNER LEVEL:
- Simple language with minimal jargon
- When introducing a term, immediately explain it
- Only basic formulas (if needed), always explained step-by-step
- Use relatable real-world examples
- Build concepts gradually
- Include helpful analogies""",

        3: """INTERMEDIATE LEVEL (STANDARD):
- Balance of conceptual and technical explanation
- Include relevant formulas with explanations
- Assume basic familiarity with the domain
- Connect to prerequisite knowledge
- Include worked examples""",

        4: """ADVANCED LEVEL:
- Technical language is appropriate
- Full mathematical derivations when relevant
- Assume solid foundation in prerequisites
- Include edge cases and nuances
- Reference related advanced concepts""",

        5: """EXPERT/RESEARCH LEVEL:
- Assume comprehensive background knowledge
- Full mathematical rigor
- Discuss cutting-edge variations
- Include research context and open problems
- Reference literature where appropriate"""
    }

    level_desc = level_descriptions.get(abstraction_level, level_descriptions[3])

    context_prompt = ""
    if current_content:
        context_prompt = f"""

The student was previously shown this content but found it confusing:
---
{current_content[:2000]}
---

Your task is to explain the SAME concepts but at a SIMPLER level.
Focus on what might have confused them and make it clearer."""

    prompt = f"""Create a lesson on: "{topic}"

Target audience: Student with background in {background_str}
ABSTRACTION LEVEL: {abstraction_level}/5

{level_desc}
{context_prompt}

Write the lesson in proper Markdown format. This will be rendered in a web browser.

FORMATTING RULES:
- Use # for main title, ## for section headers, ### for subsections  
- Use **text** for bold (important terms)
- Use *text* for italic (emphasis)
- Use - or * at the start of lines for bullet points (with space after)
- Use 1. 2. 3. for numbered lists
- {"Avoid complex formulas, use simple analogies instead" if abstraction_level <= 2 else "For math: use single $ for inline (e.g., $x^2$) and double $$ for display math"}
- Do NOT escape asterisks or markdown characters
- Do NOT wrap in code blocks

CONTENT:
1. A welcoming introduction connecting to what they might know
2. Core concepts at the appropriate level
3. {"Simple analogies and everyday examples" if abstraction_level <= 2 else "Mathematical formulas with explanations"}
4. {"Step-by-step walkthroughs with lots of explanation" if abstraction_level <= 2 else "Examples with solutions"}
5. Key takeaways in simple terms

Match complexity to level {abstraction_level}. About {"400-600" if abstraction_level <= 2 else "600-900"} words.
Output ONLY the Markdown lesson content."""

    response = await call_gemini(prompt)
    return response


async def generate_lesson_text(topic: str, user_background: List[str]) -> str:
    """Generate comprehensive lesson text using Gemini."""
    background_str = ", ".join(user_background[:5]) if user_background else "general audience"

    prompt = f"""Create a comprehensive lesson on: "{topic}"

Target audience: Student with background in {background_str}

CRITICAL: Output raw Markdown text directly. Do NOT wrap the output in ```markdown``` or any code fences.

FORMATTING RULES:
- Use # for main title, ## for section headers, ### for subsections
- Use **text** for bold (important terms)
- Use *text* for italic (emphasis)  
- Use - or * for bullet points (with space after)
- Use 1. 2. 3. for numbered lists
- For math: use $x^2$ for inline math, and $$ on separate lines for display math
- Do NOT escape markdown characters with backslashes
- Do NOT wrap the entire output in triple backticks

CONTENT STRUCTURE:
1. Brief introduction (why this matters)
2. Key concepts with headers and bullet points
3. Mathematical formulas in LaTeX
4. Examples with step-by-step solutions
5. Summary of takeaways

About 600-1000 words. Start directly with the content - no code fences."""

    response = await call_gemini(prompt)
    return response


async def scrape_math_problems_from_sources(topic: str, num_problems: int = 5) -> List[dict]:
    """
    Use OpenRouter's browse model to find math problems from educational sources.
    Sources: Paul's Math Notes, MIT OCW, AoPS, Khan Academy
    """
    if not OPENROUTER_API_KEY:
        return []

    prompt = f"""Find practice problems for the topic: "{topic}"

Search these educational sources:
1. Paul's Math Notes (tutorial.math.lamar.edu)
2. MIT OpenCourseWare (ocw.mit.edu)
3. Art of Problem Solving (artofproblemsolving.com)
4. Khan Academy (khanacademy.org)

For each problem found, extract:
- The complete problem statement (include any LaTeX math notation)
- Hints if available
- The solution or answer
- The source URL

Return a JSON array with {num_problems} problems:
[
  {{
    "problem": "Problem statement with $LaTeX$ math notation",
    "hints": ["Hint 1", "Hint 2"],
    "solution": "Step-by-step solution with $LaTeX$",
    "answer": "Final answer",
    "source": "Paul's Math Notes",
    "source_url": "https://...",
    "difficulty": "easy/medium/hard"
  }}
]

IMPORTANT:
- Preserve all mathematical notation in LaTeX format
- Include complete problem statements
- If you can't find actual problems, generate realistic ones in the style of these sources
- Return ONLY the JSON array"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://arxlearn.app",
                    "X-Title": "arXlearn"
                },
                json={
                    "model": "openai/gpt-4o-mini:online",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 3000,
                    # Enable web search plugin for real results from educational sites
                    "plugins": [
                        {
                            "id": "web",
                            "max_results": 10,
                            "search_prompt": f"Search for math practice problems about {topic} from tutorial.math.lamar.edu, ocw.mit.edu, artofproblemsolving.com, khanacademy.org:"
                        }
                    ]
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]

        # Extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            problems = json.loads(json_match.group())
            return problems
    except Exception as e:
        print(f"[LessonContent] Problem scraping failed: {e}")

    return []


@app.post("/api/lesson/content", response_model=LessonContentResponse)
async def get_lesson_content(request: LessonContentRequest):
    """
    Get full lesson content with aggregated text, video, and math problems.
    This endpoint generates lesson content asynchronously - call it to start
    generation and it returns immediately with partial content if available.
    """
    try:
        # Get current topic if not specified
        if request.topic_id:
            topic_result = supabase.table("lesson_topics").select("*").eq("id", request.topic_id).single().execute()
        else:
            topic_result = supabase.table("lesson_topics").select("*").eq("session_id", request.session_id).eq("is_confirmed", True).is_("completed_at", "null").order("order_index").limit(1).execute()
            if topic_result.data:
                topic_result.data = topic_result.data[0] if isinstance(topic_result.data, list) else topic_result.data

        if not topic_result.data:
            return LessonContentResponse(success=False, error="No active topic found")

        topic_data = topic_result.data if isinstance(topic_result.data, dict) else topic_result.data[0]
        topic_name = topic_data["topic_name"]

        # Get user's background knowledge
        knowledge_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        user_background = [n["label"] for n in knowledge_result.data if n.get("label")]

        # Create content aggregator for video search
        aggregator = ContentAggregator(OPENROUTER_API_KEY, os.getenv("OPENALEX_API_KEY")) if OPENROUTER_API_KEY else None

        # Generate lesson text, fetch video, and scrape problems in parallel
        import asyncio
        lesson_task = asyncio.create_task(generate_lesson_text(topic_name, user_background))
        problems_task = asyncio.create_task(scrape_math_problems_from_sources(topic_name, 5))
        video_task = asyncio.create_task(aggregator.search_youtube(topic_name, max_results=1)) if aggregator else None

        # Wait for all with timeout (don't block indefinitely)
        try:
            tasks = [lesson_task, problems_task]
            if video_task:
                tasks.append(video_task)
            
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=45.0
            )
            
            lesson_content = results[0] if not isinstance(results[0], Exception) else "Loading lesson content..."
            raw_problems = results[1] if not isinstance(results[1], Exception) else []
            video_results = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
        except asyncio.TimeoutError:
            # Return partial content if we have it
            lesson_content = "Loading lesson content..."
            raw_problems = []
            video_results = []

        # Convert raw problems to MathProblem objects
        problems = []
        for p in raw_problems:
            problems.append(MathProblem(
                problem=p.get("problem", ""),
                hints=p.get("hints", []),
                solution=p.get("solution", ""),
                answer=p.get("answer", ""),
                source=p.get("source", "Generated"),
                source_url=p.get("source_url", ""),
                difficulty=p.get("difficulty", "medium"),
                latex_content=True
            ))

        # Extract video embed info
        video_embed = None
        if video_results and len(video_results) > 0:
            video = video_results[0]
            # Extract video ID from embed URL
            video_id = ""
            if video.embed_url and "youtube" in video.embed_url:
                # Extract ID from URL like https://www.youtube-nocookie.com/embed/VIDEO_ID
                parts = video.embed_url.split("/")
                video_id = parts[-1] if parts else ""
            
            if video_id:
                video_embed = VideoEmbed(
                    video_id=video_id,
                    title=video.title,
                    source="youtube",
                    embed_url=video.embed_url
                )

        return LessonContentResponse(
            success=True,
            topic_name=topic_name,
            lesson_content=lesson_content,
            video=video_embed,
            problems=problems
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return LessonContentResponse(success=False, error=str(e))


@app.post("/api/lesson/simplify-content", response_model=SimplifyContentResponse)
async def simplify_lesson_content(request: SimplifyContentRequest):
    """
    Regenerate lesson content at a lower abstraction level.
    Called when user is confused and clicks "Simplify" button.

    Abstraction levels:
    1 = ELI5 (Explain Like I'm 5) - Very simple analogies, no jargon
    2 = Beginner - Simple language, basic examples, minimal formulas
    3 = Intermediate - Standard explanation with some formulas
    4 = Advanced - Technical language, full mathematical treatment
    5 = Expert - Research-level, assumes prior knowledge
    """
    try:
        # Validate abstraction level
        target_level = max(1, min(5, request.target_abstraction_level))

        # Get topic info
        if request.topic_id:
            topic_result = supabase.table("lesson_topics").select("*").eq("id", request.topic_id).single().execute()
        else:
            topic_result = supabase.table("lesson_topics").select("*").eq("session_id", request.session_id).eq("is_confirmed", True).is_("completed_at", "null").order("order_index").limit(1).execute()
            if topic_result.data:
                topic_result.data = topic_result.data[0] if isinstance(topic_result.data, list) else topic_result.data

        if not topic_result.data:
            return SimplifyContentResponse(success=False, error="No active topic found")

        topic_data = topic_result.data if isinstance(topic_result.data, dict) else topic_result.data[0]
        topic_name = topic_data["topic_name"]

        # Get user's background knowledge
        knowledge_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        user_background = [n["label"] for n in knowledge_result.data if n.get("label")]

        # Generate simplified content
        simplified_content = await generate_simplified_lesson(
            topic=topic_name,
            user_background=user_background,
            abstraction_level=target_level,
            current_content=request.current_content
        )

        return SimplifyContentResponse(
            success=True,
            topic_name=topic_name,
            simplified_content=simplified_content,
            abstraction_level=target_level
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return SimplifyContentResponse(success=False, error=str(e))


@app.get("/api/lesson/current-topic/{session_id}")
async def get_current_topic(session_id: str):
    """Get the current active topic for a session."""
    try:
        topic_result = supabase.table("lesson_topics").select("*").eq("session_id", session_id).eq("is_confirmed", True).is_("completed_at", "null").order("order_index").limit(1).execute()

        if not topic_result.data:
            # Check if all topics are complete
            all_topics = supabase.table("lesson_topics").select("*").eq("session_id", session_id).eq("is_confirmed", True).execute()
            if all_topics.data and all(t.get("completed_at") for t in all_topics.data):
                return {"success": True, "course_complete": True, "topic": None}
            return {"success": False, "error": "No active topic"}

        return {"success": True, "course_complete": False, "topic": topic_result.data[0]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
