"""
Token Company Integration Service
Handles text compression via The Token Company API.

API Documentation: https://thetokencompany.com
SDK: pip install tokenc
"""
import os
import re
import asyncio
import time
from typing import Optional
from dataclasses import dataclass
from functools import partial


@dataclass
class CompressionResult:
    """Result of text compression."""
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    tokens_saved: int
    compression_time: float
    success: bool
    error: Optional[str] = None


class TokenCompressionService:
    """
    Service for compressing text using The Token Company API.

    The API compresses text while preserving semantic meaning,
    achieving ~66% token reduction with maintained accuracy.
    """

    # Aggressiveness presets for different use cases
    PRESETS = {
        "conservative": 0.35,  # Preserve most detail
        "balanced": 0.55,      # Good balance with extra savings
        "aggressive": 0.75,    # Maximum savings (use sparingly)
        "academic": 0.5,       # Preserve technical detail with modest savings
        "notes": 0.65,         # Higher savings for informal notes
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        """
        Initialize the compression service.

        Args:
            api_key: The Token Company API key (or set TOKEN_COMPANY_API_KEY env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("TOKEN_COMPANY_API_KEY")
        self.timeout = timeout
        self._client = None

    @property
    def client(self):
        """Lazy-load the TokenClient."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "TOKEN_COMPANY_API_KEY not configured. "
                    "Set it in environment or pass to constructor."
                )
            try:
                from tokenc import TokenClient
                self._client = TokenClient(api_key=self.api_key, timeout=self.timeout)
            except ImportError:
                raise ImportError(
                    "tokenc package not installed. Run: pip install tokenc"
                )
        return self._client

    async def compress_text(
        self,
        text: str,
        aggressiveness: float = 0.5,
        max_output_tokens: Optional[int] = None,
        min_output_tokens: Optional[int] = None,
        preserve_placeholders: bool = True
    ) -> CompressionResult:
        """
        Compress text while optionally preserving image placeholders.

        Args:
            text: The text to compress
            aggressiveness: 0.0-1.0 compression intensity (higher = more compression)
            max_output_tokens: Optional upper limit on output tokens
            min_output_tokens: Optional lower limit on output tokens
            preserve_placeholders: Keep [IMAGE_N] markers intact

        Returns:
            CompressionResult with compressed text and metrics
        """
        start_time = time.time()

        # Handle empty or very short text
        if not text or len(text.strip()) < 50:
            return CompressionResult(
                compressed_text=text,
                original_tokens=self._estimate_tokens(text),
                compressed_tokens=self._estimate_tokens(text),
                compression_ratio=1.0,
                tokens_saved=0,
                compression_time=0,
                success=True
            )

        try:
            # If preserving placeholders, extract and replace them
            placeholders = {}
            processed_text = text

            if preserve_placeholders:
                pattern = r'\[IMAGE_\d+\]'
                matches = re.findall(pattern, text)
                for i, match in enumerate(matches):
                    placeholder_key = f"__IMG_PLACEHOLDER_{i}__"
                    placeholders[placeholder_key] = match
                    processed_text = processed_text.replace(match, placeholder_key, 1)

            # Run compression in thread pool (SDK is synchronous)
            loop = asyncio.get_event_loop()

            # Build compression kwargs
            compress_kwargs = {
                "input": processed_text,
                "aggressiveness": aggressiveness,
            }
            if max_output_tokens:
                compress_kwargs["max_output_tokens"] = max_output_tokens
            if min_output_tokens:
                compress_kwargs["min_output_tokens"] = min_output_tokens

            response = await loop.run_in_executor(
                None,
                partial(self._do_compress, **compress_kwargs)
            )

            compressed = response.output

            # Restore placeholders
            if preserve_placeholders:
                for key, original in placeholders.items():
                    compressed = compressed.replace(key, original)

            compression_time = time.time() - start_time

            return CompressionResult(
                compressed_text=compressed,
                original_tokens=response.original_input_tokens,
                compressed_tokens=response.output_tokens,
                compression_ratio=response.compression_ratio,
                tokens_saved=response.tokens_saved,
                compression_time=compression_time,
                success=True
            )

        except Exception as e:
            compression_time = time.time() - start_time
            error_msg = str(e)

            # Provide specific error messages for known issues
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                error_msg = f"Authentication failed: {error_msg}"
            elif "rate limit" in error_msg.lower():
                error_msg = f"Rate limit exceeded: {error_msg}"
            elif "timeout" in error_msg.lower():
                error_msg = f"Request timed out: {error_msg}"

            return CompressionResult(
                compressed_text=text,  # Return original on failure
                original_tokens=self._estimate_tokens(text),
                compressed_tokens=self._estimate_tokens(text),
                compression_ratio=1.0,
                tokens_saved=0,
                compression_time=compression_time,
                success=False,
                error=error_msg
            )

    def _do_compress(self, **kwargs):
        """Synchronous compression call for thread pool."""
        return self.client.compress_input(**kwargs)

    async def compress_for_academic_paper(self, text: str) -> CompressionResult:
        """
        Optimized compression settings for academic papers.

        Uses conservative settings to preserve technical terminology
        and mathematical notation.
        """
        return await self.compress_text(
            text,
            aggressiveness=self.PRESETS["academic"],
            preserve_placeholders=True
        )

    async def compress_for_notes(self, text: str) -> CompressionResult:
        """
        Optimized compression for user notes.

        Slightly more aggressive since notes are typically less formal.
        """
        return await self.compress_text(
            text,
            aggressiveness=self.PRESETS["notes"],
            preserve_placeholders=True
        )

    async def compress_for_web_content(self, text: str) -> CompressionResult:
        """
        Optimized compression for web-scraped content (Firecrawl output).

        Uses aggressive settings since web content often has redundancy.
        Preserves key structural elements while reducing token count.
        """
        return await self.compress_text(
            text,
            aggressiveness=0.7,  # Aggressive for web content
            preserve_placeholders=True
        )

    async def compress_for_textbook(self, text: str) -> CompressionResult:
        """
        Optimized compression for textbook/course content.

        Moderately aggressive - preserves educational structure.
        """
        return await self.compress_text(
            text,
            aggressiveness=0.6,
            preserve_placeholders=True
        )

    async def compress_batch(
        self,
        texts: list[str],
        aggressiveness: float = 0.5,
        preserve_placeholders: bool = True
    ) -> list[CompressionResult]:
        """
        Compress multiple texts concurrently.

        Args:
            texts: List of texts to compress
            aggressiveness: Compression intensity
            preserve_placeholders: Keep [IMAGE_N] markers

        Returns:
            List of CompressionResult for each text
        """
        tasks = [
            self.compress_text(text, aggressiveness, preserve_placeholders=preserve_placeholders)
            for text in texts
        ]
        return await asyncio.gather(*tasks)

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of token count.

        Uses word count * 1.3 as approximation for English text.
        """
        if not text:
            return 0
        return int(len(text.split()) * 1.3)

    def get_preset(self, name: str) -> float:
        """
        Get aggressiveness value for a named preset.

        Args:
            name: Preset name (conservative, balanced, aggressive, academic, notes)

        Returns:
            Aggressiveness value (0.0-1.0)
        """
        return self.PRESETS.get(name, self.PRESETS["balanced"])
