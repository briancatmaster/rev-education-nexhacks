"""
Firecrawl Integration Service

Firecrawl scrapes any URL and returns structured data.
This service handles extracting chapter outlines from textbooks/courses.

No setup required - just pass any URL and get chapters back.
Now includes token compression via The Token Company API.
"""

import httpx
import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from .token_compression import TokenCompressionService, CompressionResult


class ChapterOutline(BaseModel):
    chapter_number: Optional[str] = None
    title: str
    subtopics: List[str] = []
    page_number: Optional[str] = None
    url: Optional[str] = None


class FirecrawlResponse(BaseModel):
    success: bool
    url: str
    chapters: List[ChapterOutline] = []
    raw_markdown: Optional[str] = None
    compressed_markdown: Optional[str] = None
    original_tokens: Optional[int] = None
    compressed_tokens: Optional[int] = None
    compression_ratio: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class FirecrawlService:
    """Service for extracting content from any URL using Firecrawl with token compression."""

    BASE_URL = "https://api.firecrawl.dev/v1"

    def __init__(self, api_key: Optional[str] = None, ttc_api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY", "")
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY is required")

        # Initialize token compression service
        ttc_key = ttc_api_key or os.getenv("TOKEN_COMPANY_API_KEY")
        self.compression_service = TokenCompressionService(ttc_key) if ttc_key else None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def scrape_url(
        self,
        url: str,
        formats: List[str] = ["markdown"],
        only_main_content: bool = True,
        timeout: float = 60.0,
        compress: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape a URL and return content in specified formats with token compression.

        Args:
            url: The URL to scrape
            formats: Output formats (markdown, html, links, etc.)
            only_main_content: Exclude headers/footers/navs
            timeout: Request timeout in seconds
            compress: Whether to compress the content via The Token Company

        Returns:
            Scraped content with metadata and compression stats
        """
        api_url = f"{self.BASE_URL}/scrape"

        payload = {
            "url": url,
            "formats": formats,
            "onlyMainContent": only_main_content,
            "blockAds": True,
            "removeBase64Images": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                headers=self._get_headers(),
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()

        # Apply token compression if enabled and service is available
        if compress and self.compression_service and result.get("success"):
            data = result.get("data", {})
            markdown = data.get("markdown", "")

            if markdown:
                compression_result = await self.compression_service.compress_for_web_content(markdown)

                if compression_result.success:
                    # Add compression data to result
                    result["data"]["compressed_markdown"] = compression_result.compressed_text
                    result["data"]["original_tokens"] = compression_result.original_tokens
                    result["data"]["compressed_tokens"] = compression_result.compressed_tokens
                    result["data"]["compression_ratio"] = compression_result.compression_ratio
                    result["data"]["tokens_saved"] = compression_result.tokens_saved
                else:
                    # Compression failed, keep original
                    result["data"]["compression_error"] = compression_result.error

        return result

    async def extract_with_schema(
        self,
        urls: List[str],
        schema: Dict[str, Any],
        prompt: Optional[str] = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Extract structured data from URLs using a JSON schema.

        Args:
            urls: List of URLs to extract from
            schema: JSON Schema defining the data structure
            prompt: Optional guidance for extraction
            timeout: Request timeout in seconds

        Returns:
            Extracted structured data
        """
        api_url = f"{self.BASE_URL}/extract"

        payload = {
            "urls": urls,
            "schema": schema,
            "enableWebSearch": False,
            "ignoreInvalidURLs": True,
        }

        if prompt:
            payload["prompt"] = prompt

        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                headers=self._get_headers(),
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

    async def extract_chapters(
        self,
        url: str,
        use_gemini_parsing: bool = True,
        gemini_api_key: Optional[str] = None,
        compress: bool = True
    ) -> FirecrawlResponse:
        """
        Extract chapter outline from any textbook/course URL with token compression.

        Args:
            url: The textbook or course URL
            use_gemini_parsing: Use Gemini to parse markdown into chapters
            gemini_api_key: Gemini API key (uses env var if not provided)
            compress: Whether to compress the content via The Token Company

        Returns:
            FirecrawlResponse with extracted chapters and compression stats
        """
        try:
            # Scrape the page content as markdown (with compression disabled initially)
            result = await self.scrape_url(
                url=url,
                formats=["markdown"],
                only_main_content=True,
                compress=False  # We'll compress after parsing
            )

            if not result.get("success"):
                return FirecrawlResponse(
                    success=False,
                    url=url,
                    error=result.get("error", "Scrape failed")
                )

            data = result.get("data", {})
            markdown = data.get("markdown", "")
            metadata = data.get("metadata", {})

            if not markdown:
                return FirecrawlResponse(
                    success=False,
                    url=url,
                    error="No content extracted from page"
                )

            # Parse chapters from markdown using Gemini
            if use_gemini_parsing:
                chapters = await self._parse_chapters_with_gemini(
                    markdown,
                    gemini_api_key or os.getenv("GEMINI_API_KEY", "")
                )
            else:
                # Basic parsing without AI
                chapters = self._parse_chapters_basic(markdown)

            # Apply token compression to the raw markdown
            compressed_markdown = None
            original_tokens = None
            compressed_tokens = None
            compression_ratio = None

            if compress and self.compression_service and markdown:
                compression_result = await self.compression_service.compress_for_textbook(markdown)

                if compression_result.success:
                    compressed_markdown = compression_result.compressed_text
                    original_tokens = compression_result.original_tokens
                    compressed_tokens = compression_result.compressed_tokens
                    compression_ratio = compression_result.compression_ratio

            return FirecrawlResponse(
                success=True,
                url=url,
                chapters=chapters,
                raw_markdown=markdown[:5000] if len(markdown) > 5000 else markdown,
                compressed_markdown=compressed_markdown,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=compression_ratio,
                metadata=metadata
            )

        except httpx.HTTPStatusError as e:
            return FirecrawlResponse(
                success=False,
                url=url,
                error=f"Firecrawl API error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            return FirecrawlResponse(
                success=False,
                url=url,
                error=str(e)
            )

    async def _parse_chapters_with_gemini(
        self,
        markdown: str,
        api_key: str
    ) -> List[ChapterOutline]:
        """Use Gemini to extract structured chapter data from markdown."""
        import json
        import re

        # Truncate if too long
        max_chars = 30000
        if len(markdown) > max_chars:
            markdown = markdown[:max_chars] + "\n...[truncated]"

        prompt = f"""Extract the chapter/unit outline from this course or textbook content.

CONTENT:
{markdown}

Return a JSON array of chapters/units with this exact structure:
{{
  "chapters": [
    {{
      "chapter_number": "1" or "Unit 1" or null if not numbered,
      "title": "Chapter or unit title",
      "subtopics": ["List", "of", "subtopics", "or lessons"],
      "url": "URL if available, otherwise null"
    }}
  ]
}}

Rules:
- Extract ALL chapters/units/modules you can find
- Include nested lessons or subtopics in the subtopics array
- If no clear numbering, leave chapter_number as null
- Return valid JSON only, no markdown or explanation"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        # Extract text from Gemini response
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        # Parse JSON from response
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)

        text = text.strip()
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(text[start:end])
            else:
                return []

        chapters = []
        for item in result.get("chapters", []):
            chapters.append(ChapterOutline(
                chapter_number=item.get("chapter_number"),
                title=item.get("title", "Untitled"),
                subtopics=item.get("subtopics", []),
                url=item.get("url")
            ))

        return chapters

    def _parse_chapters_basic(self, markdown: str) -> List[ChapterOutline]:
        """Basic chapter extraction from markdown headers."""
        import re

        chapters = []
        lines = markdown.split('\n')

        current_chapter = None
        subtopics = []

        for line in lines:
            # Match h1/h2 headers
            h1_match = re.match(r'^#\s+(.+)$', line)
            h2_match = re.match(r'^##\s+(.+)$', line)
            h3_match = re.match(r'^###\s+(.+)$', line)

            if h1_match or h2_match:
                # Save previous chapter
                if current_chapter:
                    chapters.append(ChapterOutline(
                        title=current_chapter,
                        subtopics=subtopics
                    ))
                    subtopics = []

                current_chapter = (h1_match or h2_match).group(1).strip()

            elif h3_match and current_chapter:
                subtopics.append(h3_match.group(1).strip())

        # Don't forget last chapter
        if current_chapter:
            chapters.append(ChapterOutline(
                title=current_chapter,
                subtopics=subtopics
            ))

        return chapters
