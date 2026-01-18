"""
Google Drive integration service with Claude-powered document selection.
"""

import httpx
import json
import re
import os
from typing import List, Optional
from datetime import datetime


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def extract_json_from_response(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code blocks."""
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


async def call_claude(prompt: str, system: str = "") -> str:
    """Call Claude API via REST (Anthropic API)."""
    if not ANTHROPIC_API_KEY:
        print("[GoogleDrive] WARNING: ANTHROPIC_API_KEY not configured, using fallback")
        # Return a minimal fallback response for testing
        return '{"selected_documents": [], "search_terms": []}'

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }

    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient() as client:
            print(f"[GoogleDrive] Calling Claude API...")
            response = await client.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            result = data["content"][0]["text"]
            print(f"[GoogleDrive] Claude API response received ({len(result)} chars)")
            return result
    except httpx.HTTPStatusError as e:
        print(f"[GoogleDrive] Claude API HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"[GoogleDrive] Claude API error: {e}")
        raise


async def search_google_drive(access_token: str, query: str) -> List[dict]:
    """Search Google Drive for documents matching the query."""
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Escape single quotes in the query
    safe_query = query.replace("'", "\\'")

    # Search for documents (Google Docs, PDFs, text files)
    params = {
        "q": f"fullText contains '{safe_query}' and (mimeType='application/vnd.google-apps.document' or mimeType='application/pdf' or mimeType='text/plain')",
        "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
        "pageSize": 50,
        "orderBy": "modifiedTime desc"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])


async def list_google_drive_docs(access_token: str) -> List[dict]:
    """List recent documents from Google Drive."""
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "q": "mimeType='application/vnd.google-apps.document' or mimeType='application/pdf'",
        "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
        "pageSize": 100,
        "orderBy": "modifiedTime desc"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])


async def use_claude_to_select_relevant_docs(
    central_topic: str,
    documents: List[dict],
    existing_nodes: List[str]
) -> tuple[List[dict], List[str]]:
    """Use Claude to intelligently select the most relevant documents for the research topic."""

    if not documents:
        return [], []

    docs_formatted = "\n".join([
        f"{i+1}. {doc['name']} (Type: {doc.get('mimeType', 'unknown')})"
        for i, doc in enumerate(documents)
    ])

    nodes_formatted = ", ".join(existing_nodes) if existing_nodes else "None yet"

    system = """You are a research assistant helping to identify relevant documents for academic research.
Your task is to analyze document titles and select those most likely to be relevant to the user's research topic.
Be selective - only choose documents that are clearly related to the research question or background knowledge areas."""

    prompt = f"""Research Topic: "{central_topic}"

Existing Knowledge Areas: {nodes_formatted}

Available Documents:
{docs_formatted}

TASK:
Analyze these document titles and select the ones most relevant to the research topic.
Consider documents that might contain:
- Background knowledge for the topic
- Related concepts, methods, or theories
- Literature reviews or papers on similar topics
- Notes or summaries related to the research area

OUTPUT FORMAT (strict JSON only, no explanation):
{{
  "selected_documents": [
    {{
      "index": <1-based index of document>,
      "relevance_score": <0.0-1.0 how relevant>,
      "reason": "<brief reason why relevant>"
    }}
  ],
  "search_terms": ["<additional search terms to find more relevant docs>"]
}}

CONSTRAINTS:
- Select only documents with relevance_score > 0.5
- Maximum 20 documents
- Include 3-5 additional search terms for deeper searching"""

    response_text = await call_claude(prompt, system)
    result = extract_json_from_response(response_text)

    # Map selected documents back to original data
    selected = []
    for item in result.get("selected_documents", []):
        idx = item.get("index", 0) - 1  # Convert to 0-based
        if 0 <= idx < len(documents):
            doc = documents[idx]
            selected.append({
                "id": doc["id"],
                "title": doc["name"],
                "url": doc.get("webViewLink", ""),
                "mimeType": doc.get("mimeType", ""),
                "relevanceScore": item.get("relevance_score", 0.5),
                "reason": item.get("reason", "")
            })

    # Store search terms for potential additional searching
    search_terms = result.get("search_terms", [])

    return selected, search_terms


async def generate_search_terms_for_topic(central_topic: str, existing_nodes: List[str]) -> List[str]:
    """Use Claude to generate search terms for finding relevant documents in Google Drive."""

    nodes_formatted = ", ".join(existing_nodes) if existing_nodes else "None yet"

    system = "You are a research assistant generating search terms to find relevant documents."

    prompt = f"""Research Topic: "{central_topic}"
Existing Knowledge Areas: {nodes_formatted}

Generate 5-10 search terms that would help find relevant documents in Google Drive for this research topic.
Include:
- Key concepts from the topic
- Related methodologies
- Important theories
- Relevant field-specific terminology

OUTPUT FORMAT (strict JSON only):
{{
  "search_terms": ["term1", "term2", "term3", ...]
}}"""

    response_text = await call_claude(prompt, system)
    result = extract_json_from_response(response_text)
    return result.get("search_terms", [central_topic])


async def comprehensive_document_search(
    access_token: str,
    central_topic: str,
    existing_nodes: List[str]
) -> tuple[List[dict], List[str]]:
    """
    Perform a comprehensive search using Claude-generated search terms,
    then let Claude select the most relevant documents.

    Falls back to simple keyword search if Claude API is not configured.
    """
    print(f"[GoogleDrive] Starting comprehensive search for topic: {central_topic}")
    print(f"[GoogleDrive] ANTHROPIC_API_KEY configured: {bool(ANTHROPIC_API_KEY)}")

    # Step 1: Generate search terms - use Claude if available, otherwise simple keywords
    search_terms = []
    if ANTHROPIC_API_KEY:
        try:
            search_terms = await generate_search_terms_for_topic(central_topic, existing_nodes)
            print(f"[GoogleDrive] Generated {len(search_terms)} search terms via Claude: {search_terms[:5]}")
        except Exception as e:
            print(f"[GoogleDrive] Failed to generate search terms: {e}")

    if not search_terms:
        # Fallback: extract keywords from topic
        search_terms = [central_topic] + central_topic.split()[:3]
        print(f"[GoogleDrive] Using fallback search terms: {search_terms}")

    # Step 2: Search Google Drive with each term and collect unique documents
    all_documents = {}
    for term in search_terms[:5]:  # Limit to 5 searches to avoid rate limits
        try:
            print(f"[GoogleDrive] Searching for: '{term}'")
            docs = await search_google_drive(access_token, term)
            print(f"[GoogleDrive] Found {len(docs)} docs for '{term}'")
            for doc in docs:
                if doc["id"] not in all_documents:
                    all_documents[doc["id"]] = doc
        except Exception as e:
            print(f"[GoogleDrive] Search failed for term '{term}': {e}")
            continue

    # Also get recent documents
    try:
        recent_docs = await list_google_drive_docs(access_token)
        print(f"[GoogleDrive] Found {len(recent_docs)} recent docs")
        for doc in recent_docs:
            if doc["id"] not in all_documents:
                all_documents[doc["id"]] = doc
    except Exception as e:
        print(f"[GoogleDrive] Failed to list recent docs: {e}")

    print(f"[GoogleDrive] Total unique documents found: {len(all_documents)}")

    # Step 3: Select relevant documents
    unique_docs = list(all_documents.values())

    if not unique_docs:
        print("[GoogleDrive] No documents found in Google Drive")
        return [], search_terms

    # Try Claude selection if API key is configured
    if ANTHROPIC_API_KEY:
        try:
            selected_docs, additional_terms = await use_claude_to_select_relevant_docs(
                central_topic, unique_docs, existing_nodes
            )
            print(f"[GoogleDrive] Claude selected {len(selected_docs)} relevant documents")
            return selected_docs, search_terms + additional_terms
        except Exception as e:
            print(f"[GoogleDrive] Claude selection failed: {e}")

    # Fallback: return first 10 documents sorted by modification time
    print(f"[GoogleDrive] Using fallback: returning first 10 recent documents")
    selected_docs = [
        {
            "id": doc["id"],
            "title": doc["name"],
            "url": doc.get("webViewLink", ""),
            "mimeType": doc.get("mimeType", ""),
            "relevanceScore": 0.5,
        }
        for doc in unique_docs[:10]
    ]

    return selected_docs, search_terms
