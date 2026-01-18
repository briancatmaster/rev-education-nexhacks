"""
PDF Processing Service
Extracts text and images from PDFs while preserving structure.
Uses PyMuPDF (fitz) for robust PDF parsing.
"""
import fitz  # PyMuPDF
import base64
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import io


@dataclass
class ExtractedImage:
    """Represents an image extracted from a PDF."""
    page_number: int
    index: int
    base64_data: str
    width: int
    height: int
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    alt_text: str = ""


@dataclass
class PDFExtraction:
    """Result of PDF extraction containing text and images."""
    text: str
    images: List[ExtractedImage]
    page_count: int
    has_figures: bool
    image_placeholder_text: str  # Text with [IMAGE_N] placeholders


class PDFProcessor:
    """
    Extracts text and images from PDFs.

    Images are returned as base64-encoded PNGs for direct use with
    Claude's multimodal capabilities.
    """

    def __init__(
        self,
        min_image_size: int = 100,
        max_image_dimension: int = 2048,
        extract_images: bool = True
    ):
        """
        Initialize PDF processor.

        Args:
            min_image_size: Minimum width/height to include an image (filters icons)
            max_image_dimension: Maximum dimension before downscaling images
            extract_images: Whether to extract images at all
        """
        self.min_image_size = min_image_size
        self.max_image_dimension = max_image_dimension
        self.extract_images = extract_images

    async def extract_content(self, pdf_bytes: bytes) -> PDFExtraction:
        """
        Extract text and images from PDF bytes.

        Args:
            pdf_bytes: Raw PDF file content

        Returns:
            PDFExtraction with text, images, and metadata
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        full_text_parts = []
        images = []
        image_index = 0

        try:
            for page_num, page in enumerate(doc):
                # Extract text with layout preservation
                page_text = page.get_text("text")

                # Extract images if enabled
                if self.extract_images:
                    page_images, image_index = self._extract_page_images(
                        doc, page, page_num, image_index
                    )
                    images.extend(page_images)

                    # Add image placeholders to text
                    for img in page_images:
                        page_text += f"\n[IMAGE_{img.index}]\n"

                full_text_parts.append(page_text)
        finally:
            doc.close()

        # Join with page breaks for context
        full_text = "\n\n---PAGE BREAK---\n\n".join(full_text_parts)

        return PDFExtraction(
            text=full_text,
            images=images,
            page_count=len(full_text_parts),
            has_figures=len(images) > 0,
            image_placeholder_text=full_text
        )

    def _extract_page_images(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_num: int,
        start_index: int
    ) -> tuple[List[ExtractedImage], int]:
        """
        Extract images from a single page.

        Args:
            doc: The PDF document
            page: The page to extract from
            page_num: Page number (0-indexed)
            start_index: Starting index for image numbering

        Returns:
            Tuple of (list of ExtractedImage, next available index)
        """
        images = []
        image_index = start_index

        try:
            image_list = page.get_images(full=True)
        except Exception:
            # Some pages may have corrupted image data
            return images, image_index

        for img_info in image_list:
            try:
                xref = img_info[0]

                # Extract image as pixmap
                pix = fitz.Pixmap(doc, xref)

                # Skip small images (likely icons, bullets, etc.)
                if pix.width < self.min_image_size or pix.height < self.min_image_size:
                    pix = None
                    continue

                # Convert CMYK to RGB if needed
                if pix.n >= 5:  # CMYK or with alpha
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                # Downscale if too large
                if pix.width > self.max_image_dimension or pix.height > self.max_image_dimension:
                    scale = min(
                        self.max_image_dimension / pix.width,
                        self.max_image_dimension / pix.height
                    )
                    new_width = int(pix.width * scale)
                    new_height = int(pix.height * scale)

                    # Create scaled pixmap
                    mat = fitz.Matrix(scale, scale)
                    # Note: For resizing we need to recreate from the page
                    # For now, keep original size but could implement resizing

                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")
                base64_data = base64.b64encode(img_bytes).decode("utf-8")

                images.append(ExtractedImage(
                    page_number=page_num + 1,  # 1-indexed for display
                    index=image_index,
                    base64_data=base64_data,
                    width=pix.width,
                    height=pix.height,
                    position={"x": 0, "y": 0},
                    alt_text=f"Figure from page {page_num + 1}"
                ))

                image_index += 1
                pix = None  # Free memory

            except Exception as e:
                # Skip problematic images
                continue

        return images, image_index

    async def extract_text_only(self, pdf_bytes: bytes) -> str:
        """
        Extract only text from PDF (faster, no images).

        Args:
            pdf_bytes: Raw PDF file content

        Returns:
            Extracted text with page breaks
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        text_parts = []
        try:
            for page in doc:
                text_parts.append(page.get_text("text"))
        finally:
            doc.close()

        return "\n\n---PAGE BREAK---\n\n".join(text_parts)

    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of token count (words * 1.3).

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        words = len(text.split())
        return int(words * 1.3)
