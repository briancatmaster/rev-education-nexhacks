"""
Google Drive API endpoints for authentication and document search.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os

from supabase import create_client, Client

from services.google_drive_service import (
    comprehensive_document_search,
    list_google_drive_docs,
    use_claude_to_select_relevant_docs,
)

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)

router = APIRouter(prefix="/api/google-drive", tags=["Google Drive"])


# ============ Pydantic Models ============

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


class GoogleDocsProcessRequest(BaseModel):
    documents: List[GoogleDocInput]
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


# ============ API Endpoints ============

@router.post("/connect")
async def connect_google_drive(request: GoogleDriveConnectRequest):
    """Store Google Drive OAuth tokens for a user."""
    try:
        # Check if user already has a connection
        existing = supabase.table("google_drive_connections").select("id").eq("user_id", request.user_id).execute()

        expires_at = None
        if request.expires_at:
            expires_at = datetime.fromtimestamp(request.expires_at, tz=timezone.utc).isoformat()

        data = {
            "user_id": request.user_id,
            "google_email": request.google_email,
            "access_token": request.access_token,
            "refresh_token": request.refresh_token,
            "token_expires_at": expires_at,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing.data:
            # Update existing connection
            supabase.table("google_drive_connections").update(data).eq("user_id", request.user_id).execute()
        else:
            # Create new connection
            data["created_at"] = datetime.now(timezone.utc).isoformat()
            supabase.table("google_drive_connections").insert(data).execute()

        return {"success": True, "message": "Google Drive connected successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect_google_drive(request: GoogleDriveDisconnectRequest):
    """Disconnect Google Drive for a user."""
    try:
        supabase.table("google_drive_connections").update({
            "is_active": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("user_id", request.user_id).execute()

        return {"success": True, "message": "Google Drive disconnected"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{user_id}")
async def get_connection_status(user_id: int):
    """Check if user has Google Drive connected."""
    try:
        result = supabase.table("google_drive_connections").select("google_email, is_active, created_at").eq("user_id", user_id).eq("is_active", True).execute()

        if result.data:
            return {
                "connected": True,
                "email": result.data[0]["google_email"],
                "connected_at": result.data[0]["created_at"]
            }
        return {"connected": False}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-relevant-docs")
async def search_relevant_documents(request: GoogleDriveSearchRequest):
    """
    Use Claude to intelligently search and select relevant Google Drive documents
    based on the user's research topic.
    """
    try:
        # Get user's Google Drive connection
        connection = supabase.table("google_drive_connections").select("access_token").eq("user_id", request.user_id).eq("is_active", True).single().execute()

        if not connection.data:
            raise HTTPException(status_code=400, detail="Google Drive not connected")

        access_token = connection.data["access_token"]

        # Get session details
        session = supabase.table("learning_sessions").select("central_topic").eq("id", request.session_id).single().execute()

        if not session.data:
            raise HTTPException(status_code=404, detail="Session not found")

        central_topic = session.data["central_topic"]

        # Get existing knowledge nodes
        nodes_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        existing_nodes = [n["label"] for n in nodes_result.data] if nodes_result.data else []

        # Perform comprehensive search using Claude
        selected_docs, search_terms = await comprehensive_document_search(
            access_token=access_token,
            central_topic=central_topic,
            existing_nodes=existing_nodes
        )

        # Store selected documents in database
        for doc in selected_docs:
            try:
                supabase.table("google_docs_materials").upsert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "google_doc_id": doc["id"],
                    "title": doc["title"],
                    "url": doc.get("url"),
                    "mime_type": doc.get("mimeType"),
                    "relevance_score": doc.get("relevanceScore"),
                    "search_query": central_topic,
                    "is_selected": True,
                }, on_conflict="session_id,google_doc_id").execute()
            except Exception as e:
                print(f"[GoogleDrive] Failed to store doc {doc['id']}: {e}")

        return {
            "success": True,
            "documents": selected_docs,
            "search_terms_used": search_terms,
            "total_found": len(selected_docs)
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-docs")
async def process_google_docs(request: GoogleDocsProcessRequest):
    """
    Process selected Google Docs and generate knowledge nodes.
    This is called when the user submits their document selection.
    """
    try:
        # Get session details
        session = supabase.table("learning_sessions").select("central_topic").eq("id", request.session_id).single().execute()

        if not session.data:
            raise HTTPException(status_code=404, detail="Session not found")

        central_topic = session.data["central_topic"]

        # Get existing nodes
        nodes_result = supabase.table("knowledge_nodes").select("label").eq("session_id", request.session_id).execute()
        existing_nodes = [n["label"] for n in nodes_result.data] if nodes_result.data else []

        # Generate nodes from document titles using Gemini (similar to papers)
        from services.google_drive_service import call_claude

        doc_titles = [doc.title for doc in request.documents]
        titles_formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(doc_titles)])

        prompt = f"""You are analyzing a researcher's Google Drive documents to map their knowledge graph.

INPUT:
- Central research question: "{central_topic}"
- Existing knowledge nodes: {", ".join(existing_nodes) if existing_nodes else "None yet"}
- Documents found (titles only):
{titles_formatted}

TASK:
Identify up to 15 specific concepts, methods, or theories this researcher likely has notes on or understands based on these documents.

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "nodes": [
    {{
      "label": "concept name (1-3 words)",
      "type": "concept" | "method" | "theory" | "tool",
      "parent_node": "label of existing node this connects to, or null",
      "mastery_estimate": 0.0-1.0
    }}
  ]
}}"""

        response_text = await call_claude(prompt)
        from services.google_drive_service import extract_json_from_response
        result = extract_json_from_response(response_text)
        nodes = result.get("nodes", [])

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
                "source": "google_drive",
                "is_llm_generated": True
            }).execute()

        return {
            "success": True,
            "nodes": [KnowledgeNode(**n) for n in nodes]
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class FetchDocContentRequest(BaseModel):
    user_id: int
    doc_id: str
    mime_type: str
    access_token: Optional[str] = None  # Optional - will fetch from DB if not provided


@router.post("/fetch-doc-content")
async def fetch_doc_content(request: FetchDocContentRequest):
    """
    Fetch the content of a single Google Drive document.
    Uses the provided access token or fetches from stored connection.
    """
    import httpx

    try:
        # Get access token - either from request or from stored connection
        access_token = request.access_token
        if not access_token:
            # Fetch from database
            connection = supabase.table("google_drive_connections").select("access_token").eq("user_id", request.user_id).eq("is_active", True).single().execute()
            if not connection.data:
                raise HTTPException(status_code=400, detail="Google Drive not connected")
            access_token = connection.data["access_token"]

        content = ""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            if request.mime_type == "application/vnd.google-apps.document":
                # Export Google Doc as plain text
                export_url = f"https://www.googleapis.com/drive/v3/files/{request.doc_id}/export?mimeType=text/plain"
                response = await client.get(export_url, headers=headers, timeout=30.0)
                if response.status_code == 200:
                    content = response.text
                else:
                    print(f"[GoogleDrive] Export failed for doc {request.doc_id}: {response.status_code} - {response.text}")

            elif request.mime_type == "application/vnd.google-apps.spreadsheet":
                # Export Google Sheet as CSV
                export_url = f"https://www.googleapis.com/drive/v3/files/{request.doc_id}/export?mimeType=text/csv"
                response = await client.get(export_url, headers=headers, timeout=30.0)
                if response.status_code == 200:
                    content = response.text

            elif request.mime_type in ["text/plain", "text/markdown", "text/csv"]:
                # Download text files directly
                download_url = f"https://www.googleapis.com/drive/v3/files/{request.doc_id}?alt=media"
                response = await client.get(download_url, headers=headers, timeout=30.0)
                if response.status_code == 200:
                    content = response.text

            elif request.mime_type == "application/pdf":
                # Download PDF - return a note that PDF content needs special processing
                download_url = f"https://www.googleapis.com/drive/v3/files/{request.doc_id}?alt=media"
                response = await client.get(download_url, headers=headers, timeout=60.0)
                if response.status_code == 200:
                    # Try to extract text from PDF
                    try:
                        import fitz  # PyMuPDF
                        pdf_doc = fitz.open(stream=response.content, filetype="pdf")
                        text_parts = []
                        for page in pdf_doc:
                            text_parts.append(page.get_text())
                        content = "\n".join(text_parts)
                        pdf_doc.close()
                    except Exception as pdf_err:
                        print(f"[GoogleDrive] PDF extraction failed: {pdf_err}")
                        content = "[PDF content - extraction failed]"

        return {
            "success": True,
            "content": content[:10000] if content else "",  # Limit to 10k chars
            "doc_id": request.doc_id,
            "truncated": len(content) > 10000 if content else False
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
