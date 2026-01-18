"""
Google Drive MCP Server

Provides access to Google Drive documents for Claude via MCP protocol.
Requires user to have connected their Google Drive account first.
"""

import asyncio
import os
import httpx
from typing import Any
from datetime import datetime

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
)
from mcp.server.stdio import stdio_server
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Create the MCP server
server = Server("google-drive")


async def get_google_access_token(user_id: int) -> str | None:
    """Get the Google Drive access token for a user from the database."""
    if not supabase:
        return None

    try:
        result = supabase.table("google_drive_connections").select("access_token").eq("user_id", user_id).eq("is_active", True).single().execute()
        if result.data:
            return result.data["access_token"]
    except Exception as e:
        print(f"[GoogleDrive MCP] Error getting access token: {e}")

    return None


async def fetch_google_doc_content(access_token: str, doc_id: str) -> str:
    """Fetch the content of a Google Doc."""
    # Export Google Doc as plain text
    url = f"https://www.googleapis.com/drive/v3/files/{doc_id}/export"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"mimeType": "text/plain"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)

        if response.status_code == 200:
            return response.text
        elif response.status_code == 403:
            # File might not be a Google Doc, try to download directly
            download_url = f"https://www.googleapis.com/drive/v3/files/{doc_id}?alt=media"
            response = await client.get(download_url, headers=headers, timeout=30.0)
            if response.status_code == 200:
                return response.text
            return f"Error: Unable to fetch document content (status {response.status_code})"
        else:
            return f"Error: Unable to fetch document (status {response.status_code})"


async def search_google_drive(access_token: str, query: str) -> list[dict]:
    """Search Google Drive for documents matching the query."""
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}

    safe_query = query.replace("'", "\\'")

    params = {
        "q": f"fullText contains '{safe_query}' and (mimeType='application/vnd.google-apps.document' or mimeType='application/pdf' or mimeType='text/plain')",
        "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
        "pageSize": 20,
        "orderBy": "modifiedTime desc"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])


async def list_recent_docs(access_token: str, limit: int = 50) -> list[dict]:
    """List recent documents from Google Drive."""
    url = "https://www.googleapis.com/drive/v3/files"
    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "q": "mimeType='application/vnd.google-apps.document' or mimeType='application/pdf'",
        "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
        "pageSize": limit,
        "orderBy": "modifiedTime desc"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])


# ============ MCP Resources ============

@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available Google Drive document resources."""
    # Resources are dynamically generated based on session's selected docs
    resources = []

    if supabase:
        try:
            # Get all selected Google docs from all active sessions
            result = supabase.table("google_docs_materials").select("google_doc_id, title, session_id").eq("is_selected", True).execute()

            for doc in result.data or []:
                resources.append(
                    Resource(
                        uri=f"gdrive://{doc['google_doc_id']}",
                        name=doc["title"],
                        description=f"Google Drive document: {doc['title']}",
                        mimeType="text/plain"
                    )
                )
        except Exception as e:
            print(f"[GoogleDrive MCP] Error listing resources: {e}")

    return resources


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a Google Drive document by its URI."""
    if not uri.startswith("gdrive://"):
        raise ValueError(f"Invalid Google Drive URI: {uri}")

    doc_id = uri.replace("gdrive://", "")

    if not supabase:
        return "Error: Supabase not configured"

    try:
        # Get the document info and user_id from the database
        doc_result = supabase.table("google_docs_materials").select("user_id, title").eq("google_doc_id", doc_id).single().execute()

        if not doc_result.data:
            return f"Error: Document {doc_id} not found in database"

        user_id = doc_result.data["user_id"]
        title = doc_result.data["title"]

        # Get the user's access token
        access_token = await get_google_access_token(user_id)
        if not access_token:
            return f"Error: No Google Drive connection found for user {user_id}"

        # Fetch the document content
        content = await fetch_google_doc_content(access_token, doc_id)

        return f"# {title}\n\n{content}"

    except Exception as e:
        return f"Error reading document: {e}"


# ============ MCP Tools ============

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Google Drive tools."""
    return [
        Tool(
            name="search_google_drive",
            description="Search Google Drive for documents matching a query. Requires user_id of a user with connected Google Drive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID to search Google Drive for"
                    },
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant documents"
                    }
                },
                "required": ["user_id", "query"]
            }
        ),
        Tool(
            name="list_recent_google_docs",
            description="List recent documents from a user's Google Drive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID to list documents for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of documents to return (default: 20)",
                        "default": 20
                    }
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="get_google_doc_content",
            description="Get the full text content of a Google Drive document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID who owns the document"
                    },
                    "doc_id": {
                        "type": "string",
                        "description": "The Google Drive document ID"
                    }
                },
                "required": ["user_id", "doc_id"]
            }
        ),
        Tool(
            name="get_session_google_docs",
            description="Get all Google Drive documents selected for a learning session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The learning session ID"
                    }
                },
                "required": ["session_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    """Execute a Google Drive tool."""

    if name == "search_google_drive":
        user_id = arguments.get("user_id")
        query = arguments.get("query", "")

        access_token = await get_google_access_token(user_id)
        if not access_token:
            return [TextContent(type="text", text=f"Error: No Google Drive connection found for user {user_id}")]

        try:
            docs = await search_google_drive(access_token, query)
            if not docs:
                return [TextContent(type="text", text=f"No documents found matching '{query}'")]

            result_text = f"Found {len(docs)} documents matching '{query}':\n\n"
            for doc in docs:
                result_text += f"- **{doc['name']}**\n"
                result_text += f"  ID: {doc['id']}\n"
                result_text += f"  Type: {doc.get('mimeType', 'unknown')}\n"
                result_text += f"  URL: {doc.get('webViewLink', 'N/A')}\n\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error searching Google Drive: {e}")]

    elif name == "list_recent_google_docs":
        user_id = arguments.get("user_id")
        limit = arguments.get("limit", 20)

        access_token = await get_google_access_token(user_id)
        if not access_token:
            return [TextContent(type="text", text=f"Error: No Google Drive connection found for user {user_id}")]

        try:
            docs = await list_recent_docs(access_token, limit)
            if not docs:
                return [TextContent(type="text", text="No recent documents found")]

            result_text = f"Recent {len(docs)} documents:\n\n"
            for doc in docs:
                result_text += f"- **{doc['name']}**\n"
                result_text += f"  ID: {doc['id']}\n"
                result_text += f"  Modified: {doc.get('modifiedTime', 'N/A')}\n\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error listing documents: {e}")]

    elif name == "get_google_doc_content":
        user_id = arguments.get("user_id")
        doc_id = arguments.get("doc_id")

        access_token = await get_google_access_token(user_id)
        if not access_token:
            return [TextContent(type="text", text=f"Error: No Google Drive connection found for user {user_id}")]

        try:
            content = await fetch_google_doc_content(access_token, doc_id)
            return [TextContent(type="text", text=content)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching document: {e}")]

    elif name == "get_session_google_docs":
        session_id = arguments.get("session_id")

        if not supabase:
            return [TextContent(type="text", text="Error: Supabase not configured")]

        try:
            result = supabase.table("google_docs_materials").select("*").eq("session_id", session_id).eq("is_selected", True).execute()

            if not result.data:
                return [TextContent(type="text", text=f"No Google Drive documents found for session {session_id}")]

            result_text = f"Google Drive documents for session {session_id}:\n\n"
            for doc in result.data:
                result_text += f"- **{doc['title']}**\n"
                result_text += f"  ID: {doc['google_doc_id']}\n"
                result_text += f"  Relevance: {doc.get('relevance_score', 'N/A')}\n"
                result_text += f"  URL: {doc.get('url', 'N/A')}\n\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching session documents: {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the Google Drive MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
