"""
Custom MCP Server for Document Retrieval
Provides compressed documents with images to Claude via MCP protocol.

This server exposes processed academic materials as MCP resources,
allowing Claude to access token-compressed text and preserved images.

Usage:
    python -m mcp.document_server

Environment Variables:
    SUPABASE_URL: Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY: Service role key for Supabase
"""
import os
import json
import asyncio
from typing import Any
from supabase import create_client

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Resource,
        TextContent,
        ImageContent,
        Tool,
        CallToolResult,
        ListResourcesResult,
        ReadResourceResult,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("Warning: MCP SDK not installed. Run: pip install mcp")


class DocumentMCPServer:
    """
    MCP Server that provides access to compressed academic documents.

    Resources:
        - document://{material_id} - Individual processed documents

    Tools:
        - get_session_documents - List all documents for a session
        - search_documents - Search documents by title/content
    """

    def __init__(self):
        if not MCP_AVAILABLE:
            raise ImportError("MCP SDK required. Install with: pip install mcp")

        self.server = Server("arxlearn-documents")
        self.supabase = None
        self._setup_handlers()

    def _get_supabase(self):
        """Lazy-load Supabase client."""
        if self.supabase is None:
            url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

            if not url or not key:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
                )

            self.supabase = create_client(url, key)
        return self.supabase

    def _setup_handlers(self):
        """Set up MCP request handlers."""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List all processed documents as resources."""
            try:
                supabase = self._get_supabase()
                materials = supabase.table("academia_materials").select(
                    "id, title, compressed_token_count, material_type"
                ).eq("ttc_processed", True).execute()

                return [
                    Resource(
                        uri=f"document://{m['id']}",
                        name=m.get("title") or "Untitled Document",
                        description=(
                            f"Compressed {m.get('material_type', 'document')} "
                            f"({m.get('compressed_token_count', 0)} tokens)"
                        ),
                        mimeType="application/json"
                    )
                    for m in materials.data
                ]
            except Exception as e:
                print(f"Error listing resources: {e}")
                return []

        @self.server.read_resource()
        async def read_resource(uri: str) -> list[TextContent | ImageContent]:
            """Read a document resource with text and images."""
            try:
                material_id = uri.replace("document://", "")
                supabase = self._get_supabase()

                material = supabase.table("academia_materials").select("*").eq(
                    "id", material_id
                ).single().execute()

                if not material.data:
                    return [TextContent(text="Document not found")]

                if not material.data.get("ttc_processed"):
                    return [TextContent(
                        text="Document has not been processed yet. "
                             "Use the /api/documents/process endpoint first."
                    )]

                content_parts = []

                # Add document metadata
                metadata = {
                    "title": material.data.get("title", "Untitled"),
                    "material_type": material.data.get("material_type"),
                    "original_tokens": material.data.get("original_token_count"),
                    "compressed_tokens": material.data.get("compressed_token_count"),
                    "compression_ratio": material.data.get("compression_ratio"),
                }

                # Add compressed text
                compressed_text = material.data.get("compressed_text", "")
                content_parts.append(TextContent(
                    text=f"## Document: {metadata['title']}\n\n"
                         f"**Type:** {metadata['material_type']}\n"
                         f"**Tokens:** {metadata['compressed_tokens']} "
                         f"(compressed from {metadata['original_tokens']})\n\n"
                         f"---\n\n{compressed_text}"
                ))

                # Add images if present
                images = material.data.get("extracted_images", [])
                for img in images:
                    content_parts.append(ImageContent(
                        type="image",
                        data=img.get("base64", ""),
                        mimeType="image/png",
                    ))

                return content_parts

            except Exception as e:
                return [TextContent(text=f"Error reading document: {e}")]

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="get_session_documents",
                    description=(
                        "Get all processed documents for a learning session. "
                        "Returns document IDs, titles, and token counts."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "The learning session UUID"
                            }
                        },
                        "required": ["session_id"]
                    }
                ),
                Tool(
                    name="get_document_content",
                    description=(
                        "Get the full compressed content of a specific document "
                        "including text and image references."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "material_id": {
                                "type": "string",
                                "description": "The material UUID"
                            }
                        },
                        "required": ["material_id"]
                    }
                ),
                Tool(
                    name="search_documents",
                    description=(
                        "Search processed documents by title. "
                        "Returns matching documents with their IDs."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for document titles"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum results to return",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_compression_stats",
                    description=(
                        "Get compression statistics for a session showing "
                        "total tokens saved and compression ratios."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "The learning session UUID"
                            }
                        },
                        "required": ["session_id"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                supabase = self._get_supabase()

                if name == "get_session_documents":
                    session_id = arguments.get("session_id")
                    materials = supabase.table("academia_materials").select(
                        "id, title, compressed_text, compressed_token_count, material_type"
                    ).eq("session_id", session_id).eq("ttc_processed", True).execute()

                    result = {
                        "session_id": session_id,
                        "documents": [
                            {
                                "id": m["id"],
                                "title": m.get("title", "Untitled"),
                                "type": m.get("material_type"),
                                "tokens": m.get("compressed_token_count", 0),
                                "preview": (
                                    m.get("compressed_text", "")[:200] + "..."
                                    if len(m.get("compressed_text", "")) > 200
                                    else m.get("compressed_text", "")
                                )
                            }
                            for m in materials.data
                        ],
                        "total_count": len(materials.data),
                        "total_tokens": sum(
                            m.get("compressed_token_count", 0)
                            for m in materials.data
                        )
                    }
                    return [TextContent(text=json.dumps(result, indent=2))]

                elif name == "get_document_content":
                    material_id = arguments.get("material_id")
                    material = supabase.table("academia_materials").select(
                        "id, title, compressed_text, extracted_images, "
                        "compressed_token_count, original_token_count"
                    ).eq("id", material_id).eq("ttc_processed", True).single().execute()

                    if not material.data:
                        return [TextContent(
                            text=json.dumps({"error": "Document not found or not processed"})
                        )]

                    result = {
                        "id": material.data["id"],
                        "title": material.data.get("title"),
                        "text": material.data.get("compressed_text", ""),
                        "image_count": len(material.data.get("extracted_images", [])),
                        "tokens": material.data.get("compressed_token_count"),
                        "original_tokens": material.data.get("original_token_count")
                    }
                    return [TextContent(text=json.dumps(result, indent=2))]

                elif name == "search_documents":
                    query = arguments.get("query", "")
                    limit = arguments.get("limit", 10)

                    # Simple title search using ilike
                    materials = supabase.table("academia_materials").select(
                        "id, title, compressed_token_count, material_type"
                    ).eq("ttc_processed", True).ilike(
                        "title", f"%{query}%"
                    ).limit(limit).execute()

                    result = {
                        "query": query,
                        "results": [
                            {
                                "id": m["id"],
                                "title": m.get("title", "Untitled"),
                                "type": m.get("material_type"),
                                "tokens": m.get("compressed_token_count", 0)
                            }
                            for m in materials.data
                        ],
                        "count": len(materials.data)
                    }
                    return [TextContent(text=json.dumps(result, indent=2))]

                elif name == "get_compression_stats":
                    session_id = arguments.get("session_id")
                    materials = supabase.table("academia_materials").select(
                        "original_token_count, compressed_token_count, ttc_processed"
                    ).eq("session_id", session_id).execute()

                    total_original = 0
                    total_compressed = 0
                    processed = 0

                    for m in materials.data:
                        if m.get("ttc_processed"):
                            total_original += m.get("original_token_count", 0)
                            total_compressed += m.get("compressed_token_count", 0)
                            processed += 1

                    result = {
                        "session_id": session_id,
                        "total_documents": len(materials.data),
                        "processed_documents": processed,
                        "total_original_tokens": total_original,
                        "total_compressed_tokens": total_compressed,
                        "tokens_saved": total_original - total_compressed,
                        "compression_ratio": (
                            total_compressed / total_original
                            if total_original > 0 else 1.0
                        ),
                        "savings_percentage": (
                            (1 - total_compressed / total_original) * 100
                            if total_original > 0 else 0
                        )
                    }
                    return [TextContent(text=json.dumps(result, indent=2))]

                else:
                    return [TextContent(text=json.dumps({"error": f"Unknown tool: {name}"}))]

            except Exception as e:
                return [TextContent(text=json.dumps({"error": str(e)}))]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)


def main():
    """Entry point for the MCP server."""
    if not MCP_AVAILABLE:
        print("Error: MCP SDK not installed. Run: pip install mcp")
        return

    server = DocumentMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
