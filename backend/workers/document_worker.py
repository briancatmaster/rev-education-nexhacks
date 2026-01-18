"""
Background Worker for Document Processing
Automatically processes uploaded documents using Token Company compression.

This worker polls for unprocessed documents and processes them in the background,
allowing uploads to return immediately while processing happens asynchronously.

Usage:
    # Start the worker
    python -m workers.document_worker

    # Or integrate into FastAPI startup
    from workers.document_worker import DocumentProcessingWorker
    worker = DocumentProcessingWorker(supabase_client, pipeline)
    asyncio.create_task(worker.start())
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.document_pipeline import DocumentPipeline


class DocumentProcessingWorker:
    """
    Background worker that automatically processes uploaded documents.

    The worker polls the database for documents that:
    - Have a stored file (storage_path is not null)
    - Have not been processed by Token Company (ttc_processed = false)
    - Were uploaded more than a configurable delay ago (to avoid race conditions)

    Processing happens in sequence to avoid overwhelming the Token Company API.
    """

    def __init__(
        self,
        supabase_client,
        pipeline: Optional[DocumentPipeline] = None,
        poll_interval: int = 30,
        processing_delay: int = 60,
        batch_size: int = 10,
        ttc_api_key: Optional[str] = None,
        compression_aggressiveness: float = 0.5
    ):
        """
        Initialize the document processing worker.

        Args:
            supabase_client: Initialized Supabase client
            pipeline: DocumentPipeline instance (created if not provided)
            poll_interval: Seconds between polling for new documents
            processing_delay: Seconds to wait after upload before processing
            batch_size: Maximum documents to process per poll
            ttc_api_key: Token Company API key
            compression_aggressiveness: Default compression level (0.0-1.0)
        """
        self.supabase = supabase_client
        self.poll_interval = poll_interval
        self.processing_delay = processing_delay
        self.batch_size = batch_size
        self.running = False

        if pipeline:
            self.pipeline = pipeline
        else:
            self.pipeline = DocumentPipeline(
                supabase_client=supabase_client,
                ttc_api_key=ttc_api_key or os.getenv("TOKEN_COMPANY_API_KEY"),
                compression_aggressiveness=compression_aggressiveness
            )

        # Statistics
        self.processed_count = 0
        self.failed_count = 0
        self.total_tokens_saved = 0

    async def start(self):
        """Start the background processing loop."""
        self.running = True
        print(f"[DocumentWorker] Starting with {self.poll_interval}s poll interval")

        while self.running:
            try:
                await self._process_pending_documents()
            except Exception as e:
                print(f"[DocumentWorker] Error in processing loop: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the background processing loop."""
        self.running = False
        print(f"[DocumentWorker] Stopping. Processed: {self.processed_count}, "
              f"Failed: {self.failed_count}, Tokens saved: {self.total_tokens_saved}")

    async def _process_pending_documents(self):
        """Find and process unprocessed documents."""
        # Calculate cutoff time (documents must be older than this to be processed)
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.processing_delay)

        try:
            # Query for unprocessed documents
            pending = self.supabase.table("academia_materials").select(
                "id, storage_bucket, storage_path, title"
            ).eq(
                "ttc_processed", False
            ).not_.is_(
                "storage_path", "null"
            ).lt(
                "created_at", cutoff_time.isoformat()
            ).limit(
                self.batch_size
            ).execute()

            if not pending.data:
                return

            print(f"[DocumentWorker] Found {len(pending.data)} documents to process")

            for material in pending.data:
                await self._process_single_document(material)

        except Exception as e:
            print(f"[DocumentWorker] Error fetching pending documents: {e}")

    async def _process_single_document(self, material: dict):
        """Process a single document."""
        material_id = material["id"]
        title = material.get("title", "Untitled")

        print(f"[DocumentWorker] Processing: {title} ({material_id})")

        try:
            result = await self.pipeline.process_document(
                material_id=material_id,
                bucket=material["storage_bucket"],
                storage_path=material["storage_path"]
            )

            if result.success:
                tokens_saved = result.original_tokens - result.compressed_tokens
                self.processed_count += 1
                self.total_tokens_saved += tokens_saved

                print(f"[DocumentWorker] Success: {title} - "
                      f"Saved {tokens_saved} tokens "
                      f"({result.compression_ratio:.1%} ratio)")
            else:
                self.failed_count += 1
                print(f"[DocumentWorker] Failed: {title} - {result.error}")

                # Mark as failed to avoid retrying forever
                self._mark_processing_failed(material_id, result.error)

        except Exception as e:
            self.failed_count += 1
            print(f"[DocumentWorker] Error processing {title}: {e}")
            self._mark_processing_failed(material_id, str(e))

    def _mark_processing_failed(self, material_id: str, error: str):
        """Mark a document as failed processing (to avoid infinite retries)."""
        try:
            # Store error in a way that doesn't trigger reprocessing
            # We set ttc_processed to True but with error info in the text field
            self.supabase.table("academia_materials").update({
                "ttc_processed": True,
                "ttc_processed_at": datetime.utcnow().isoformat(),
                "compressed_text": f"[PROCESSING_ERROR] {error}",
                "compression_ratio": 1.0
            }).eq("id", material_id).execute()
        except Exception as e:
            print(f"[DocumentWorker] Error marking failure: {e}")

    def get_stats(self) -> dict:
        """Get current worker statistics."""
        return {
            "running": self.running,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "total_tokens_saved": self.total_tokens_saved,
            "poll_interval": self.poll_interval,
            "batch_size": self.batch_size
        }


async def main():
    """
    Standalone entry point for running the worker.

    Loads environment from .env and starts the processing loop.
    """
    from dotenv import load_dotenv
    from supabase import create_client

    # Load environment
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    # Initialize Supabase
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)

    supabase = create_client(supabase_url, supabase_key)

    # Check for Token Company API key
    ttc_key = os.getenv("TOKEN_COMPANY_API_KEY")
    if not ttc_key:
        print("Warning: TOKEN_COMPANY_API_KEY not set. Compression will fail.")

    # Create and start worker
    worker = DocumentProcessingWorker(
        supabase_client=supabase,
        ttc_api_key=ttc_key,
        poll_interval=30,
        processing_delay=60,
        batch_size=10,
        compression_aggressiveness=0.5
    )

    # Handle shutdown gracefully
    try:
        await worker.start()
    except KeyboardInterrupt:
        print("\n[DocumentWorker] Shutting down...")
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
