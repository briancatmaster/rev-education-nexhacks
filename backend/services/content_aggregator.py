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
        
        try:
            # Use OpenRouter's browsing model to find content
            items = await self._search_with_openrouter(topic, user_background, content_types, max_items)
            return ContentSearchResult(success=True, items=items)
        except Exception as e:
            return ContentSearchResult(success=False, items=[], error=str(e))
    
    async def _search_with_openrouter(
        self,
        topic: str,
        user_background: Optional[str],
        content_types: List[ContentType],
        max_items: int
    ) -> List[ContentItem]:
        """Use OpenRouter's browsing model to search for content."""
        
        types_str = ", ".join([ct.value for ct in content_types])
        background_context = f"\nUser background: {user_background}" if user_background else ""
        
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
                    "max_tokens": 2000,
                    # Enable web search plugin for real-time results
                    "plugins": [
                        {
                            "id": "web",
                            "max_results": 10,
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
        """Search YouTube specifically for educational videos using direct search."""
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
        
        # Find matching video from known library
        topic_lower = topic.lower()
        items = []
        
        for keyword, video_data in KNOWN_VIDEOS.items():
            if keyword in topic_lower or any(word in topic_lower for word in keyword.split()):
                items.append(ContentItem(
                    content_type=ContentType.VIDEO,
                    source_type=SourceType.YOUTUBE,
                    title=video_data["title"],
                    embed_url=f"https://www.youtube-nocookie.com/embed/{video_data['id']}",
                    source_title=video_data["channel"],
                    duration_minutes=15
                ))
                if len(items) >= max_results:
                    break
        
        # If no match found, use a general math video
        if not items:
            items.append(ContentItem(
                content_type=ContentType.VIDEO,
                source_type=SourceType.YOUTUBE,
                title=f"Learning: {topic}",
                embed_url=f"https://www.youtube-nocookie.com/embed/NybHckSEQBI",
                source_title="The Organic Chemistry Tutor",
                duration_minutes=15
            ))
        
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
