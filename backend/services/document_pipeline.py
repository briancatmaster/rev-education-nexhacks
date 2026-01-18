"""
Complete Document Processing Pipeline
Orchestrates PDF extraction, compression, and storage.
"""
import base64
import json
import logging
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .pdf_processor import PDFProcessor, PDFExtraction
from .token_compression import TokenCompressionService, CompressionResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    """Result of full document processing pipeline."""
    material_id: str
    original_text: str
    compressed_text: str
    images: list  # List of ExtractedImage as dicts
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    mcp_ready_content: str  # JSON formatted for Claude via MCP
    success: bool
    error: Optional[str] = None


class DocumentPipeline:
    """
    Full pipeline for processing uploaded documents:
    1. Download PDF from Supabase
    2. Extract text and images using PyMuPDF
    3. Compress text using The Token Company
    4. Store results back to Supabase
    5. Format for MCP/Claude consumption
    """

    def __init__(
        self,
        supabase_client: Any,
        ttc_api_key: Optional[str] = None,
        compression_aggressiveness: float = 0.5,
        extract_images: bool = True
    ):
        """
        Initialize the document pipeline.

        Args:
            supabase_client: Initialized Supabase client
            ttc_api_key: The Token Company API key
            compression_aggressiveness: 0.0-1.0 compression intensity
            extract_images: Whether to extract images from PDFs
        """
        self.supabase = supabase_client
        self.pdf_processor = PDFProcessor(extract_images=extract_images)
        self.compression_service = TokenCompressionService(ttc_api_key)
        self.aggressiveness = compression_aggressiveness

    async def process_document(
        self,
        material_id: str,
        bucket: str,
        storage_path: str
    ) -> ProcessedDocument:
        """
        Full pipeline: download -> extract -> compress -> store -> format

        Args:
            material_id: ID of the academia_materials record
            bucket: Supabase storage bucket name
            storage_path: Path within the bucket

        Returns:
            ProcessedDocument with all processed data
        """
        try:
            # 1. Download PDF from Supabase
            response = self.supabase.storage.from_(bucket).download(storage_path)
            pdf_bytes = response

            # 2. Extract text and images
            extraction: PDFExtraction = await self.pdf_processor.extract_content(pdf_bytes)

            # 3. Compress text with The Token Company
            compression: CompressionResult = await self.compression_service.compress_text(
                text=extraction.text,
                aggressiveness=self.aggressiveness,
                preserve_placeholders=True
            )

            if not compression.success:
                # Fallback: use original text if compression fails
                compressed_text = extraction.text
                original_tokens = self.pdf_processor.estimate_tokens(extraction.text)
                compressed_tokens = original_tokens
                compression_ratio = 1.0
            else:
                compressed_text = compression.compressed_text
                original_tokens = compression.original_tokens
                compressed_tokens = compression.compressed_tokens
                compression_ratio = compression.compression_ratio

            # 4. Prepare images as serializable format
            images_data = [
                {
                    "page": img.page_number,
                    "index": img.index,
                    "base64": img.base64_data,
                    "width": img.width,
                    "height": img.height,
                    "alt": img.alt_text
                }
                for img in extraction.images
            ]

            # 5. Format for MCP/Claude consumption
            mcp_content = self._format_for_mcp(compressed_text, images_data)

            # 6. Update database record
            await self._update_material_record(
                material_id=material_id,
                original_text=extraction.text,
                compressed_text=compressed_text,
                images=images_data,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=compression_ratio
            )

            return ProcessedDocument(
                material_id=material_id,
                original_text=extraction.text,
                compressed_text=compressed_text,
                images=images_data,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=compression_ratio,
                mcp_ready_content=mcp_content,
                success=True
            )

        except Exception as e:
            return ProcessedDocument(
                material_id=material_id,
                original_text="",
                compressed_text="",
                images=[],
                original_tokens=0,
                compressed_tokens=0,
                compression_ratio=1.0,
                mcp_ready_content="",
                success=False,
                error=str(e)
            )

    async def process_text_only(
        self,
        material_id: str,
        bucket: str,
        storage_path: str
    ) -> ProcessedDocument:
        """
        Process document without image extraction (faster).

        Args:
            material_id: ID of the academia_materials record
            bucket: Supabase storage bucket name
            storage_path: Path within the bucket

        Returns:
            ProcessedDocument with text only (no images)
        """
        try:
            # Download PDF
            response = self.supabase.storage.from_(bucket).download(storage_path)
            pdf_bytes = response

            # Extract text only
            text = await self.pdf_processor.extract_text_only(pdf_bytes)

            # Compress
            compression = await self.compression_service.compress_text(
                text=text,
                aggressiveness=self.aggressiveness
            )

            if not compression.success:
                compressed_text = text
                original_tokens = self.pdf_processor.estimate_tokens(text)
                compressed_tokens = original_tokens
                compression_ratio = 1.0
            else:
                compressed_text = compression.compressed_text
                original_tokens = compression.original_tokens
                compressed_tokens = compression.compressed_tokens
                compression_ratio = compression.compression_ratio

            # Format for MCP (no images)
            mcp_content = self._format_for_mcp(compressed_text, [])

            # Update database
            await self._update_material_record(
                material_id=material_id,
                original_text=text,
                compressed_text=compressed_text,
                images=[],
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=compression_ratio
            )

            return ProcessedDocument(
                material_id=material_id,
                original_text=text,
                compressed_text=compressed_text,
                images=[],
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=compression_ratio,
                mcp_ready_content=mcp_content,
                success=True
            )

        except Exception as e:
            return ProcessedDocument(
                material_id=material_id,
                original_text="",
                compressed_text="",
                images=[],
                original_tokens=0,
                compressed_tokens=0,
                compression_ratio=1.0,
                mcp_ready_content="",
                success=False,
                error=str(e)
            )

    def _format_for_mcp(self, compressed_text: str, images: list) -> str:
        """
        Format content for Claude via MCP.

        Creates a structured JSON representation that includes:
        - Compressed text with image placeholders
        - Image references for multimodal processing

        Args:
            compressed_text: The compressed document text
            images: List of image dicts with base64 data

        Returns:
            JSON string formatted for MCP consumption
        """
        content = {
            "text": compressed_text,
            "images": [
                {
                    "index": img["index"],
                    "type": "image/png",
                    "data": img["base64"],
                    "description": img["alt"]
                }
                for img in images
            ],
            "metadata": {
                "has_figures": len(images) > 0,
                "figure_count": len(images),
                "format_version": "1.0"
            }
        }
        return json.dumps(content)

    async def _update_material_record(
        self,
        material_id: str,
        original_text: str,
        compressed_text: str,
        images: list,
        original_tokens: int,
        compressed_tokens: int,
        compression_ratio: float
    ):
        """
        Update the academia_materials record with processed data.
        Stores images as individual files and compressed content in storage bucket.
        No fallback to inline storage - errors are raised for proper handling.

        Args:
            material_id: ID of the record to update
            original_text: Full extracted text
            compressed_text: Compressed text
            images: List of extracted image dicts with base64 data
            original_tokens: Token count before compression
            compressed_tokens: Token count after compression
            compression_ratio: Compression ratio achieved
        """
        bucket_name = "compressed_documents"

        # Get user_id for storage path
        material = self.supabase.table("academia_materials").select(
            "user_id"
        ).eq("id", material_id).single().execute()
        user_id = material.data.get("user_id", "unknown")

        # 1. Upload images as individual files to storage
        image_refs = []
        for img in images:
            img_path = f"{user_id}/{material_id}/img_{img['index']}.png"

            try:
                # Decode base64 to bytes
                img_bytes = base64.b64decode(img["base64"])

                # Delete old image if exists
                try:
                    self.supabase.storage.from_(bucket_name).remove([img_path])
                except Exception:
                    pass  # File might not exist

                # Upload image
                self.supabase.storage.from_(bucket_name).upload(
                    img_path,
                    img_bytes,
                    {"content-type": "image/png"}
                )

                # Store reference (not base64 data)
                image_refs.append({
                    "index": img["index"],
                    "path": img_path,
                    "page": img.get("page"),
                    "width": img.get("width"),
                    "height": img.get("height"),
                    "alt": img.get("alt", "")
                })
                logger.info(f"Uploaded image {img['index']} to {img_path}")

            except Exception as e:
                logger.error(f"Failed to upload image {img['index']} for material {material_id}: {e}")
                raise RuntimeError(f"Image upload failed for index {img['index']}: {e}")

        # 2. Create JSON content with image references (not base64 data)
        json_content = {
            "text": compressed_text,
            "image_refs": image_refs,
            "metadata": {
                "material_id": material_id,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": compression_ratio,
                "has_figures": len(image_refs) > 0,
                "figure_count": len(image_refs),
                "processed_at": datetime.utcnow().isoformat(),
                "format_version": "2.0"  # New format with image_refs
            }
        }

        # 3. Upload compressed JSON to storage
        json_path = f"{user_id}/{material_id}.json"

        try:
            # Delete old JSON if exists
            try:
                self.supabase.storage.from_(bucket_name).remove([json_path])
            except Exception:
                pass  # File might not exist

            json_bytes = json.dumps(json_content).encode('utf-8')
            self.supabase.storage.from_(bucket_name).upload(
                json_path,
                json_bytes,
                {"content-type": "application/json"}
            )
            logger.info(f"Uploaded compressed JSON to {json_path}")

        except Exception as e:
            logger.error(f"Failed to upload compressed JSON for material {material_id}: {e}")
            raise RuntimeError(f"JSON upload failed: {e}")

        # 4. Update database with storage paths only (NO inline data)
        try:
            self.supabase.table("academia_materials").update({
                "original_text": None,
                "compressed_text": None,
                "extracted_images": None,  # Clear inline images
                "compressed_storage_bucket": bucket_name,
                "compressed_storage_path": json_path,
                "original_token_count": original_tokens,
                "compressed_token_count": compressed_tokens,
                "compression_ratio": compression_ratio,
                "compression_aggressiveness": self.aggressiveness,
                "ttc_processed": True,
                "ttc_processed_at": datetime.utcnow().isoformat(),
                "pdf_extraction_method": "pymupdf"
            }).eq("id", material_id).execute()
            logger.info(f"Updated material {material_id} with storage path {json_path}")

        except Exception as e:
            logger.error(f"Failed to update database for material {material_id}: {e}")
            raise RuntimeError(f"Database update failed: {e}")

    async def get_mcp_content_for_materials(
        self,
        material_ids: list[str],
        signed_url_expiry: int = 3600
    ) -> dict:
        """
        Get MCP-ready content for multiple materials.
        Reads from storage bucket and generates signed URLs for images.

        Args:
            material_ids: List of material IDs to retrieve
            signed_url_expiry: Expiry time in seconds for signed URLs (default 1 hour)

        Returns:
            Combined content dict for Claude with signed image URLs
        """
        materials = self.supabase.table("academia_materials").select(
            "id, title, compressed_text, extracted_images, compressed_token_count, "
            "compressed_storage_bucket, compressed_storage_path"
        ).in_("id", material_ids).eq("ttc_processed", True).execute()

        combined_content = {
            "documents": [],
            "total_tokens": 0
        }

        for material in materials.data:
            text = ""
            images = []

            storage_bucket = material.get("compressed_storage_bucket")
            storage_path = material.get("compressed_storage_path")

            if storage_bucket and storage_path:
                try:
                    response = self.supabase.storage.from_(storage_bucket).download(storage_path)
                    content = json.loads(response.decode('utf-8'))
                    text = content.get("text", "")

                    # Handle new format (v2.0) with image_refs
                    image_refs = content.get("image_refs", [])
                    if image_refs:
                        for img_ref in image_refs:
                            # Generate signed URL for each image
                            try:
                                signed_url_response = self.supabase.storage.from_(
                                    storage_bucket
                                ).create_signed_url(img_ref["path"], signed_url_expiry)

                                images.append({
                                    "index": img_ref["index"],
                                    "url": signed_url_response.get("signedURL") or signed_url_response.get("signedUrl"),
                                    "page": img_ref.get("page"),
                                    "width": img_ref.get("width"),
                                    "height": img_ref.get("height"),
                                    "description": img_ref.get("alt", "")
                                })
                            except Exception as e:
                                logger.warning(f"Failed to create signed URL for {img_ref['path']}: {e}")

                    # Handle legacy format (v1.0) with inline base64 images
                    legacy_images = content.get("images", [])
                    if legacy_images and not image_refs:
                        images = legacy_images

                except Exception as e:
                    logger.error(f"Failed to read from storage for material {material['id']}: {e}")
                    # Fall back to inline data for legacy records
                    text = material.get("compressed_text", "") or ""
                    images = material.get("extracted_images", []) or []
            else:
                # Use inline data (legacy records without storage path)
                text = material.get("compressed_text", "") or ""
                images = material.get("extracted_images", []) or []

            combined_content["documents"].append({
                "id": material["id"],
                "title": material.get("title", "Untitled"),
                "text": text,
                "images": images or []
            })
            combined_content["total_tokens"] += material.get("compressed_token_count", 0)

        return combined_content
