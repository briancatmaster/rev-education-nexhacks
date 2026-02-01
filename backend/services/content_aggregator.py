"""
Content Aggregator Service

Uses OpenRouter's gpt-4o-mini:online model to search and aggregate
educational content from YouTube, OpenAlex, Khan Academy, MIT OCW, and web.
"""
import os
import httpx
import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from .token_compression import TokenCompressionService


class ContentType(str, Enum):
    VIDEO = "video"
    READING = "reading"
    PROBLEM = "problem"
    LAB = "lab"


class SourceType(str, Enum):
    YOUTUBE = "youtube"
    OPENALEX = "openalex"
    KHAN_ACADEMY = "khan_academy"
    MIT_OCW = "mit_ocw"
    WEB = "web"
    PDF = "pdf"


@dataclass
class ContentItem:
    """A single piece of educational content."""
    content_type: ContentType
    source_type: SourceType
    title: str
    embed_url: str
    source_title: Optional[str] = None
    duration_minutes: Optional[int] = None
    description: Optional[str] = None


@dataclass
class ContentSearchResult:
    """Result of a content search."""
    success: bool
    items: List[ContentItem]
    error: Optional[str] = None


class ContentAggregator:
    """
    Aggregates educational content from multiple sources using OpenRouter's
    browsing-enabled model.
    """
    
    def __init__(self, openrouter_api_key: str, openalex_api_key: Optional[str] = None):
        self.openrouter_api_key = openrouter_api_key
        self.openalex_api_key = openalex_api_key
        self.browse_model = "openai/gpt-4o-mini:online"
        self._cache: Dict[str, List[ContentItem]] = {}
        self._yt_cache: Dict[str, List[ContentItem]] = {}
        self._compression_service: Optional[TokenCompressionService] = None
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")

        if os.getenv("TOKEN_COMPANY_API_KEY"):
            try:
                self._compression_service = TokenCompressionService()
            except Exception:
                self._compression_service = None
    
    async def search_content_for_topic(
        self,
        topic: str,
        user_background: Optional[str] = None,
        content_types: Optional[List[ContentType]] = None,
        max_items: int = 5
    ) -> ContentSearchResult:
        """
        Search for educational content on a topic.
        
        Args:
            topic: The topic to search for
            user_background: Optional user background for personalization
            content_types: Types of content to search for (default: all)
            max_items: Maximum number of items to return
            
        Returns:
            ContentSearchResult with list of ContentItems
        """
        if content_types is None:
            content_types = [ContentType.VIDEO, ContentType.READING]
        
        cache_key = f"{topic.lower()}::{','.join(sorted(ct.value for ct in content_types))}::{max_items}"
        if cache_key in self._cache:
            return ContentSearchResult(success=True, items=self._cache[cache_key])

        # Local-first search to avoid unnecessary OpenRouter calls.
        local_items = await self._search_local_sources(topic, content_types, max_items)
        if local_items:
            self._cache[cache_key] = local_items
            return ContentSearchResult(success=True, items=local_items)

        if not self.openrouter_api_key:
            return ContentSearchResult(success=False, items=[], error="OPENROUTER_API_KEY not configured")

        try:
            items = await self._search_with_openrouter(topic, user_background, content_types, max_items)
            self._cache[cache_key] = items
            return ContentSearchResult(success=True, items=items)
        except Exception as e:
            return ContentSearchResult(success=False, items=[], error=str(e))

    async def _search_local_sources(
        self,
        topic: str,
        content_types: List[ContentType],
        max_items: int
    ) -> List[ContentItem]:
        """Search local non-LLM sources first to reduce OpenRouter usage."""
        items: List[ContentItem] = []

        if ContentType.VIDEO in content_types and len(items) < max_items:
            items.extend(await self.search_youtube(topic, max_results=max_items - len(items)))

        if ContentType.READING in content_types and len(items) < max_items:
            items.extend(await self.search_openalex(topic, max_results=max_items - len(items)))

        return items[:max_items]
    
    async def _search_with_openrouter(
        self,
        topic: str,
        user_background: Optional[str],
        content_types: List[ContentType],
        max_items: int
    ) -> List[ContentItem]:
        """Use OpenRouter's browsing model to search for content."""
        
        types_str = ", ".join([ct.value for ct in content_types])
        background_context = ""
        if user_background:
            background_text, was_compressed = await self._maybe_compress_background(user_background)
            label = "User background (compressed)" if was_compressed else "User background"
            background_context = f"\n{label}: {background_text}"
        
        prompt = f"""Find educational content for learning about: "{topic}"{background_context}

Search for these types of content: {types_str}

IMPORTANT: Return ONLY embeddable content:
- YouTube videos: Return the VIDEO ID only (e.g., "dQw4w9WgXcQ" from https://youtube.com/watch?v=dQw4w9WgXcQ)
- Khan Academy: Return the full embed URL
- MIT OpenCourseWare: Return direct video or PDF URLs
- Academic papers: Return DOI or direct PDF links from OpenAlex/arXiv

For each item found, provide:
1. The exact video ID (YouTube) or embed URL
2. The title
3. Source (youtube, khan_academy, mit_ocw, openalex, web)
4. Type (video, reading, problem)
5. Estimated duration in minutes

Return a JSON array with up to {max_items} items:
[
  {{
    "type": "video",
    "source": "youtube",
    "video_id_or_url": "actual_video_id_here",
    "title": "Video Title",
    "duration_minutes": 15,
    "description": "Brief description"
  }}
]

Focus on:
1. Reputable educational channels (3Blue1Brown, Khan Academy, MIT OCW, Coursera)
2. Recent, high-quality content
3. Content that builds understanding progressively

Return ONLY the JSON array, no other text."""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://arxlearn.app",
                    "X-Title": "arXlearn"
                },
                json={
                    "model": self.browse_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                    # Enable web search plugin for real-time results
                    "plugins": [
                        {
                            "id": "web",
                            "max_results": 3,
                            "search_prompt": "Search for educational content and return accurate URLs:"
                        }
                    ]
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
        
        content_text = data["choices"][0]["message"]["content"]
        items = self._parse_content_response(content_text)
        return items

    async def _maybe_compress_background(self, text: str) -> tuple[str, bool]:
        """Compress long background context to reduce OpenRouter token usage."""
        if not self._compression_service or len(text) < 800:
            return text, False

        try:
            result = await self._compression_service.compress_for_notes(text)
        except Exception:
            return text, False

        if not result.success or result.compression_ratio >= 0.95:
            return text, False

        return result.compressed_text, True
    
    def _parse_content_response(self, response_text: str) -> List[ContentItem]:
        """Parse the OpenRouter response into ContentItems."""
        items = []
        
        # Extract JSON from response
        try:
            # Try to find JSON array in response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                raw_items = json.loads(json_match.group())
            else:
                return items
        except json.JSONDecodeError:
            return items
        
        for raw in raw_items:
            try:
                content_type = ContentType(raw.get("type", "video"))
                source_type = SourceType(raw.get("source", "web"))
                
                # Build embed URL based on source
                video_id_or_url = raw.get("video_id_or_url", "")
                embed_url = self._build_embed_url(source_type, video_id_or_url)
                
                if embed_url:
                    items.append(ContentItem(
                        content_type=content_type,
                        source_type=source_type,
                        title=raw.get("title", "Untitled"),
                        embed_url=embed_url,
                        source_title=raw.get("source_title"),
                        duration_minutes=raw.get("duration_minutes"),
                        description=raw.get("description")
                    ))
            except (ValueError, KeyError):
                continue
        
        return items
    
    def _build_embed_url(self, source_type: SourceType, video_id_or_url: str) -> Optional[str]:
        """Build an embeddable URL from source type and ID/URL."""
        if not video_id_or_url:
            return None
        
        if source_type == SourceType.YOUTUBE:
            # Extract video ID if full URL provided
            video_id = video_id_or_url
            if "youtube.com" in video_id_or_url or "youtu.be" in video_id_or_url:
                # Extract ID from various YouTube URL formats
                patterns = [
                    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
                ]
                for pattern in patterns:
                    match = re.search(pattern, video_id_or_url)
                    if match:
                        video_id = match.group(1)
                        break
            
            # Validate video ID format (11 characters, alphanumeric with - and _)
            if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                return f"https://www.youtube-nocookie.com/embed/{video_id}"
            return None
        
        elif source_type == SourceType.KHAN_ACADEMY:
            if "khanacademy.org" in video_id_or_url:
                return video_id_or_url
            return f"https://www.khanacademy.org/embed_video?v={video_id_or_url}"
        
        elif source_type == SourceType.MIT_OCW:
            return video_id_or_url  # MIT OCW URLs are usually direct
        
        elif source_type == SourceType.OPENALEX:
            # For papers, return the URL directly (could be DOI or PDF)
            if video_id_or_url.startswith("10."):
                return f"https://doi.org/{video_id_or_url}"
            return video_id_or_url
        
        else:
            return video_id_or_url
    
    async def search_youtube(self, topic: str, max_results: int = 3) -> List[ContentItem]:
        """Search YouTube for educational videos using the YouTube Data API v3, with fallback to a known library."""
        cache_key = f"{topic.lower()}::{max_results}"
        if cache_key in self._yt_cache:
            return self._yt_cache[cache_key]

        # Use well-known educational video IDs for common math topics as fallback
        KNOWN_VIDEOS = {
            "arithmetic": {"id": "NybHckSEQBI", "title": "Arithmetic - Basic Math", "channel": "The Organic Chemistry Tutor"},
            "addition": {"id": "AuX7nPBqDts", "title": "Addition and Subtraction", "channel": "Khan Academy"},
            "multiplication": {"id": "mvOkMYCygps", "title": "Multiplication Explained", "channel": "Khan Academy"},
            "division": {"id": "8xQh1r3AvXo", "title": "Division Basics", "channel": "Khan Academy"},
            "calculus": {"id": "WUvTyaaNkzM", "title": "Essence of Calculus", "channel": "3Blue1Brown"},
            "derivative": {"id": "9vKqVkMQHKk", "title": "Derivatives - Basic Rules", "channel": "The Organic Chemistry Tutor"},
            "linear algebra": {"id": "fNk_zzaMoSs", "title": "Essence of Linear Algebra", "channel": "3Blue1Brown"},
            "neural network": {"id": "aircAruvnKk", "title": "Neural Networks", "channel": "3Blue1Brown"},
            "machine learning": {"id": "ukzFI9rgwfU", "title": "Machine Learning Basics", "channel": "StatQuest"},
            "gradient descent": {"id": "IHZwWFHWa-w", "title": "Gradient Descent", "channel": "3Blue1Brown"},
            "backpropagation": {"id": "Ilg3gGewQ5U", "title": "Backpropagation", "channel": "3Blue1Brown"},
            "matrix": {"id": "kYB8IZa5AuE", "title": "Matrices Explained", "channel": "3Blue1Brown"},
            "vector": {"id": "fNk_zzaMoSs", "title": "Vectors Intro", "channel": "3Blue1Brown"},
            "chain rule": {"id": "H-ybCx8gt-8", "title": "Chain Rule", "channel": "Khan Academy"},
            "activation function": {"id": "m0pIlLfpXWE", "title": "Activation Functions", "channel": "DeepLizard"},
            "loss function": {"id": "Skc8KQgiDpY", "title": "Loss Functions", "channel": "ritvikmath"},
        }

        async def _fetch_youtube_results() -> List[ContentItem]:
            if not self.youtube_api_key:
                return []

            search_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": topic,
                "type": "video",
                "maxResults": min(max_results * 3, 25),
                "safeSearch": "moderate",
                "videoEmbeddable": "true",
                "order": "viewCount",
                "relevanceLanguage": "en",
                "regionCode": "US",
                "key": self.youtube_api_key,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(search_url, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()

            items = data.get("items", [])
            video_ids = [item.get("id", {}).get("videoId") for item in items]
            video_ids = [vid for vid in video_ids if vid]

            # Fetch details to enforce duration >= 2:30 and rank by view count.
            details_by_id = {}
            if video_ids:
                videos_url = "https://www.googleapis.com/youtube/v3/videos"
                params = {
                    "part": "contentDetails,statistics,snippet",
                    "id": ",".join(video_ids[:50]),
                    "key": self.youtube_api_key,
                }
                async with httpx.AsyncClient() as client:
                    response = await client.get(videos_url, params=params, timeout=15.0)
                    response.raise_for_status()
                    data = response.json()

                for item in data.get("items", []):
                    details_by_id[item.get("id")] = {
                        "duration": item.get("contentDetails", {}).get("duration"),
                        "views": int(item.get("statistics", {}).get("viewCount", 0)),
                        "title": item.get("snippet", {}).get("title"),
                        "channel": item.get("snippet", {}).get("channelTitle"),
                        "description": item.get("snippet", {}).get("description"),
                    }

            def _parse_iso8601_duration(duration: str) -> int:
                # Returns duration in seconds.
                if not duration:
                    return 0
                match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
                if not match:
                    return 0
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                return hours * 3600 + minutes * 60 + seconds

            results = []
            ranked = []
            for item in items:
                vid = item.get("id", {}).get("videoId")
                if not vid:
                    continue

                details = details_by_id.get(vid, {})
                duration = _parse_iso8601_duration(details.get("duration", ""))
                # Skip shorts or very short videos (< 2:30)
                if duration and duration < 150:
                    continue
                if duration and duration > 15 * 60:
                    continue

                ranked.append((details.get("views", 0), vid, details))

            ranked.sort(key=lambda item: item[0], reverse=True)

            for _, vid, details in ranked:
                results.append(ContentItem(
                    content_type=ContentType.VIDEO,
                    source_type=SourceType.YOUTUBE,
                    title=details.get("title") or "YouTube Video",
                    embed_url=f"https://www.youtube.com/embed/{vid}",
                    source_title=details.get("channel"),
                    duration_minutes=max(1, _parse_iso8601_duration(details.get("duration", "")) // 60) if details.get("duration") else None,
                    description=details.get("description")
                ))

                if len(results) >= max_results:
                    break

            return results

        # Try YouTube API first
        try:
            api_results = await _fetch_youtube_results()
            if api_results:
                self._yt_cache[cache_key] = api_results
                return api_results
        except Exception as e:
            print(f"[ContentAggregator] YouTube API search failed: {e}")

        # Fallback to known library
        topic_lower = topic.lower()
        items = []
        topic_tokens = {t for t in re.split(r"[^a-z0-9]+", topic_lower) if t}

        ranked_matches = []
        for keyword, video_data in KNOWN_VIDEOS.items():
            score = 0
            keyword_lower = keyword.lower()
            if keyword_lower in topic_lower:
                score += 3
            for token in keyword_lower.split():
                if token in topic_tokens:
                    score += 1
            if score > 0:
                ranked_matches.append((score, video_data))

        ranked_matches.sort(key=lambda item: item[0], reverse=True)

        for score, video_data in ranked_matches[:max_results]:
            items.append(ContentItem(
                content_type=ContentType.VIDEO,
                source_type=SourceType.YOUTUBE,
                title=video_data["title"],
                embed_url=f"https://www.youtube.com/embed/{video_data['id']}",
                source_title=video_data["channel"],
                duration_minutes=15
            ))

        self._yt_cache[cache_key] = items
        return items

    async def search_openalex(self, topic: str, max_results: int = 3) -> List[ContentItem]:
        """Search OpenAlex for academic papers."""
        items = []
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "search": topic,
                    "per_page": max_results,
                    "filter": "is_oa:true",  # Open access only
                    "sort": "cited_by_count:desc"
                }
                if self.openalex_api_key:
                    params["api_key"] = self.openalex_api_key
                
                response = await client.get(
                    "https://api.openalex.org/works",
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
            
            for work in data.get("results", []):
                # Get best available URL (prefer PDF)
                url = None
                if work.get("open_access", {}).get("oa_url"):
                    url = work["open_access"]["oa_url"]
                elif work.get("doi"):
                    url = f"https://doi.org/{work['doi'].replace('https://doi.org/', '')}"
                
                if url:
                    items.append(ContentItem(
                        content_type=ContentType.READING,
                        source_type=SourceType.OPENALEX,
                        title=work.get("title", "Academic Paper"),
                        embed_url=url,
                        source_title=work.get("primary_location", {}).get("source", {}).get("display_name"),
                        description=work.get("abstract")
                    ))
        except Exception as e:
            print(f"[ContentAggregator] OpenAlex search failed: {e}")
        
        return items
    
    async def generate_problem(self, topic: str, difficulty: str = "medium") -> Optional[ContentItem]:
        """Generate a practice problem for a topic using LLM."""
        prompt = f"""Create a practice problem for the topic: "{topic}"
Difficulty: {difficulty}

The problem should:
1. Test understanding of core concepts
2. Be solvable in 5-10 minutes
3. Have a clear, verifiable answer

Return JSON:
{{
  "problem": "The problem statement",
  "hints": ["Hint 1", "Hint 2"],
  "solution": "Step-by-step solution",
  "answer": "Final answer"
}}"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "openai/gpt-4o-mini",  # Non-browsing model for generation
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 1500
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                problem_data = json.loads(json_match.group())
                # Store problem data as JSON in embed_url (will be parsed by frontend)
                return ContentItem(
                    content_type=ContentType.PROBLEM,
                    source_type=SourceType.WEB,
                    title=f"Practice: {topic}",
                    embed_url=f"data:application/json,{json.dumps(problem_data)}",
                    duration_minutes=10,
                    description=problem_data.get("problem", "")[:200]
                )
        except Exception as e:
            print(f"[ContentAggregator] Problem generation failed: {e}")
        
        return None
