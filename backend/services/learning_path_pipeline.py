"""
Learning Path Pipeline Service

Handles the multi-step process of generating a knowledge DAG from user materials:
1. Batch processing of documents with Gemini
2. Meta-summary generation with compression
3. Knowledge decomposition into prerequisite tree
4. Storage to Supabase bucket
"""
import asyncio
import json
import uuid
import os
import httpx
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from pathlib import Path

from services.token_compression import TokenCompressionService


@dataclass
class BatchSummary:
    """Result of processing a batch of documents."""
    batch_index: int
    material_ids: List[str]
    summary: str
    demonstrated_knowledge: List[Dict]
    domain_expertise: List[str]


@dataclass
class PrerequisiteRelation:
    """A single prerequisite relationship with reasoning."""
    node_id: str
    relationship: str  # 'requires', 'builds_on', or 'related'
    reasoning: str


@dataclass
class LearningPathResult:
    """Final result of learning path generation."""
    success: bool
    learning_path_id: Optional[str] = None
    storage_path: Optional[str] = None
    total_nodes: int = 0
    max_depth: int = 0
    relationship_distribution: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class LearningPathPipeline:
    """
    Pipeline for generating a knowledge prerequisite DAG from user materials.

    The pipeline:
    1. Fetches all user materials (authored papers, notes, read papers, coursework)
    2. Batches and sends to Gemini for summaries (with rate limiting)
    3. Compresses summaries and generates meta-summary
    4. Decomposes into knowledge DAG with prerequisites
    5. Stores result to Supabase bucket
    """

    BATCH_SIZE = 5
    RATE_LIMIT_DELAY = 2.0  # Conservative - 2 seconds between Gemini calls

    def __init__(
        self,
        supabase_client,
        gemini_api_key: str,
        ttc_api_key: str,
        batch_size: int = 5,
        rate_limit_delay: float = 2.0
    ):
        self.supabase = supabase_client
        self.gemini_api_key = gemini_api_key
        self.compression_service = TokenCompressionService(api_key=ttc_api_key)
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay

        # Load prompts
        prompts_dir = Path(__file__).parent.parent / "prompts"
        self.batch_summary_prompt = (prompts_dir / "batch_summary.md").read_text()
        self.decomposition_prompt = (prompts_dir / "knowledge_decomposition.md").read_text()

    async def create_learning_path(
        self,
        user_id: int,
        session_id: str,
        job_id: str,
        progress_callback: Optional[Callable] = None
    ) -> LearningPathResult:
        """
        Main entry point: create a learning path from user materials.

        Args:
            user_id: User's ID
            session_id: Learning session ID
            job_id: Job tracking ID
            progress_callback: Optional callback for progress updates

        Returns:
            LearningPathResult with path ID and storage location
        """
        try:
            # Step 1: Fetch all materials
            materials = await self._fetch_materials(user_id, session_id)

            if not materials:
                return LearningPathResult(
                    success=False,
                    error="No materials found for this session"
                )

            batches = self._create_batches(materials)
            total_batches = len(batches)

            await self._update_job_status(job_id, "batch_processing", {
                "batches_processed": 0,
                "total_batches": total_batches
            })

            # Step 2: Generate batch summaries with rate limiting
            batch_summaries: List[BatchSummary] = []
            for i, batch in enumerate(batches):
                print(f"[LearningPath] Processing batch {i+1}/{total_batches}")

                summary = await self._process_batch(batch, i)
                batch_summaries.append(summary)

                await self._update_job_status(job_id, "batch_processing", {
                    "batches_processed": i + 1,
                    "total_batches": total_batches
                })

                # Rate limit between batches
                if i < total_batches - 1:
                    await asyncio.sleep(self.rate_limit_delay)

            # Step 3: Compress and create meta-summary
            await self._update_job_status(job_id, "summarizing")
            meta_summary = await self._create_meta_summary(batch_summaries)

            # Step 4: Generate knowledge DAG
            await self._update_job_status(job_id, "decomposing")
            knowledge_dag = await self._decompose_knowledge(meta_summary, batch_summaries)

            # Step 5: Store results
            await self._update_job_status(job_id, "storing")
            result = await self._store_results(
                user_id, session_id, knowledge_dag, batch_summaries
            )

            # Mark job as completed
            await self._update_job_status(job_id, "completed")

            return result

        except Exception as e:
            error_msg = str(e)
            print(f"[LearningPath] Error: {error_msg}")
            await self._update_job_status(job_id, "failed", error_message=error_msg)
            return LearningPathResult(success=False, error=error_msg)

    async def _fetch_materials(self, user_id: int, session_id: str) -> List[Dict]:
        """Fetch all processed materials for the session."""
        # Fetch from academia_materials
        result = self.supabase.table("academia_materials").select(
            "id, title, compressed_text, original_text, material_type, source_type, notes"
        ).eq("user_id", user_id).eq("session_id", session_id).execute()

        materials = []
        for row in result.data:
            # Prefer compressed text, fall back to original
            content = row.get("compressed_text") or row.get("original_text") or ""
            if content:
                materials.append({
                    "id": row["id"],
                    "title": row.get("title", "Untitled"),
                    "type": row.get("material_type", "other"),
                    "content": content,
                    "notes": row.get("notes", "")
                })

        # Also fetch from google_docs_materials
        gdocs_result = self.supabase.table("google_docs_materials").select(
            "id, title, content_snippet"
        ).eq("user_id", user_id).eq("session_id", session_id).execute()

        for row in gdocs_result.data:
            if row.get("content_snippet"):
                materials.append({
                    "id": row["id"],
                    "title": row.get("title", "Google Doc"),
                    "type": "google_doc",
                    "content": row["content_snippet"],
                    "notes": ""
                })

        print(f"[LearningPath] Found {len(materials)} materials")
        return materials

    def _create_batches(self, materials: List[Dict]) -> List[List[Dict]]:
        """Split materials into batches."""
        batches = []
        for i in range(0, len(materials), self.batch_size):
            batches.append(materials[i:i + self.batch_size])
        return batches

    async def _process_batch(self, batch: List[Dict], batch_index: int) -> BatchSummary:
        """Process a batch of documents with Gemini."""
        # Format documents for prompt
        docs_formatted = json.dumps({
            "documents": [
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "type": doc["type"],
                    "content": doc["content"][:5000]  # Limit content size
                }
                for doc in batch
            ]
        }, indent=2)

        prompt = f"""You are analyzing a batch of academic documents. Follow these instructions:

{self.batch_summary_prompt}

Here are the documents to analyze:

{docs_formatted}

Return ONLY valid JSON with no markdown formatting or code blocks."""

        response_text = await self._call_gemini(prompt)
        result = self._extract_json(response_text)

        return BatchSummary(
            batch_index=batch_index,
            material_ids=[doc["id"] for doc in batch],
            summary=result.get("summary", ""),
            demonstrated_knowledge=result.get("demonstrated_knowledge", []),
            domain_expertise=result.get("domain_expertise", [])
        )

    async def _create_meta_summary(self, batch_summaries: List[BatchSummary]) -> str:
        """Compress batch summaries into a meta-summary."""
        # Combine all batch summaries
        combined = {
            "batch_count": len(batch_summaries),
            "summaries": [
                {
                    "batch": bs.batch_index,
                    "summary": bs.summary,
                    "knowledge": bs.demonstrated_knowledge,
                    "domains": bs.domain_expertise
                }
                for bs in batch_summaries
            ]
        }

        combined_text = json.dumps(combined, indent=2)

        # Compress if large
        if len(combined_text) > 10000:
            compression_result = await self.compression_service.compress_text(
                combined_text,
                aggressiveness=0.4  # Academic preset
            )
            if compression_result.success:
                return compression_result.compressed_text

        return combined_text

    async def _decompose_knowledge(
        self,
        meta_summary: str,
        batch_summaries: List[BatchSummary]
    ) -> Dict:
        """Decompose knowledge into a prerequisite DAG with pedagogical relationships."""
        # Collect all source material IDs for reference
        all_material_ids = []
        all_demonstrated_knowledge = []
        for bs in batch_summaries:
            all_material_ids.extend(bs.material_ids)
            all_demonstrated_knowledge.extend(bs.demonstrated_knowledge)

        # Build context with demonstrated concepts
        demonstrated_str = json.dumps(all_demonstrated_knowledge[:20], indent=2)  # Limit to avoid token overflow

        prompt = f"""You are decomposing a researcher's knowledge into a prerequisite DAG with TRUE PEDAGOGICAL prerequisites. Follow these instructions:

{self.decomposition_prompt}

Here is the meta-summary of their academic work:

{meta_summary}

Demonstrated knowledge from their materials:
{demonstrated_str}

Available source material IDs for reference: {json.dumps(all_material_ids)}

CRITICAL REQUIREMENTS:
1. Prerequisites must be TRUE pedagogical dependencies (Calculus before Gradient Descent)
2. Every prerequisite relationship needs a 'reasoning' field explaining WHY
3. Use relationship types: 'requires' (strict), 'builds_on' (soft), 'related' (no dependency)
4. Ensure the graph is ACYCLIC - no circular dependencies
5. Generate 40-80 nodes with >50% 'requires' relationships

Return ONLY valid JSON with no markdown formatting or code blocks."""

        response_text = await self._call_gemini(prompt)
        result = self._extract_json(response_text)

        # Validate and enhance the result
        nodes = result.get("nodes", [])

        # Ensure all nodes have required fields and normalize prerequisites
        for node in nodes:
            if "id" not in node:
                node["id"] = f"node_{uuid.uuid4().hex[:8]}"
            if "source_material_ids" not in node:
                node["source_material_ids"] = []

            # Normalize prerequisites to new format
            node["prerequisites"] = self._normalize_prerequisites(node.get("prerequisites", []))

        # Validate pedagogical soundness
        validation_result = self._validate_pedagogical_soundness(nodes)
        if not validation_result["valid"]:
            print(f"[LearningPath] Validation warnings: {validation_result['warnings']}")

        # Calculate metadata including relationship distribution
        max_depth = max((n.get("depth", 0) for n in nodes), default=0)
        root_count = sum(1 for n in nodes if not n.get("prerequisites"))

        relationship_counts = {"requires": 0, "builds_on": 0, "related": 0}
        for node in nodes:
            for prereq in node.get("prerequisites", []):
                rel_type = prereq.get("relationship", "requires")
                relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + 1

        return {
            "nodes": nodes,
            "metadata": {
                "total_nodes": len(nodes),
                "max_depth": max_depth,
                "root_node_count": root_count,
                "relationship_distribution": relationship_counts,
                "validation": validation_result
            }
        }

    def _normalize_prerequisites(self, prerequisites: List) -> List[Dict]:
        """Normalize prerequisites to the new format with reasoning."""
        normalized = []
        for prereq in prerequisites:
            if isinstance(prereq, str):
                # Old format: just node_id string
                normalized.append({
                    "node_id": prereq,
                    "relationship": "requires",
                    "reasoning": "Legacy prerequisite - relationship inferred"
                })
            elif isinstance(prereq, dict):
                # New format or partial new format
                normalized.append({
                    "node_id": prereq.get("node_id", prereq.get("id", "")),
                    "relationship": prereq.get("relationship", "requires"),
                    "reasoning": prereq.get("reasoning", "No reasoning provided")
                })
        return normalized

    def _validate_pedagogical_soundness(self, nodes: List[Dict]) -> Dict:
        """Validate the DAG for pedagogical correctness."""
        warnings = []
        node_ids = {n["id"] for n in nodes}
        node_map = {n["id"]: n for n in nodes}

        # Check 1: Detect cycles
        cycles = self._detect_cycles(nodes)
        if cycles:
            warnings.append(f"Circular dependencies detected: {cycles[:3]}")  # Show first 3

        # Check 2: Verify all prerequisite references exist
        for node in nodes:
            for prereq in node.get("prerequisites", []):
                prereq_id = prereq.get("node_id", "")
                if prereq_id and prereq_id not in node_ids:
                    warnings.append(f"Node {node['id']} references non-existent prerequisite {prereq_id}")

        # Check 3: Check depth consistency
        for node in nodes:
            node_depth = node.get("depth", 0)
            for prereq in node.get("prerequisites", []):
                prereq_id = prereq.get("node_id", "")
                if prereq_id in node_map:
                    prereq_depth = node_map[prereq_id].get("depth", 0)
                    rel_type = prereq.get("relationship", "requires")
                    if rel_type == "requires" and prereq_depth >= node_depth:
                        warnings.append(
                            f"Depth violation: {node['label']} (depth {node_depth}) "
                            f"requires {node_map[prereq_id]['label']} (depth {prereq_depth})"
                        )

        # Check 4: Verify relationship distribution
        rel_counts = {"requires": 0, "builds_on": 0, "related": 0}
        total_rels = 0
        for node in nodes:
            for prereq in node.get("prerequisites", []):
                rel_type = prereq.get("relationship", "requires")
                rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
                total_rels += 1

        if total_rels > 0:
            requires_pct = rel_counts["requires"] / total_rels
            related_pct = rel_counts["related"] / total_rels
            if requires_pct < 0.5:
                warnings.append(f"Low 'requires' ratio: {requires_pct:.1%} (should be >50%)")
            if related_pct > 0.2:
                warnings.append(f"High 'related' ratio: {related_pct:.1%} (should be <20%)")

        # Check 5: Verify reasoning exists for 'requires' relationships
        missing_reasoning = 0
        for node in nodes:
            for prereq in node.get("prerequisites", []):
                if prereq.get("relationship") == "requires":
                    reasoning = prereq.get("reasoning", "")
                    if not reasoning or reasoning == "No reasoning provided":
                        missing_reasoning += 1

        if missing_reasoning > 0:
            warnings.append(f"{missing_reasoning} 'requires' relationships missing reasoning")

        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "relationship_counts": rel_counts
        }

    def _detect_cycles(self, nodes: List[Dict]) -> List[str]:
        """Detect cycles in the prerequisite graph using DFS."""
        node_map = {n["id"]: n for n in nodes}
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node_id: str, path: List[str]) -> bool:
            if node_id in rec_stack:
                cycle_start = path.index(node_id)
                cycles.append(" -> ".join(path[cycle_start:] + [node_id]))
                return True
            if node_id in visited:
                return False

            visited.add(node_id)
            rec_stack.add(node_id)

            node = node_map.get(node_id)
            if node:
                for prereq in node.get("prerequisites", []):
                    prereq_id = prereq.get("node_id", "")
                    if prereq_id:
                        dfs(prereq_id, path + [node_id])

            rec_stack.remove(node_id)
            return False

        for node in nodes:
            if node["id"] not in visited:
                dfs(node["id"], [])

        return cycles

    async def _store_results(
        self,
        user_id: int,
        session_id: str,
        knowledge_dag: Dict,
        batch_summaries: List[BatchSummary]
    ) -> LearningPathResult:
        """Store the learning path to database and storage bucket."""
        learning_path_id = str(uuid.uuid4())

        # Build full JSON document
        document = {
            "version": "1.0",
            "learning_path_id": learning_path_id,
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "metadata": knowledge_dag.get("metadata", {}),
            "nodes": knowledge_dag.get("nodes", []),
            "edges": self._build_edges(knowledge_dag.get("nodes", [])),
            "batch_summaries": [
                {
                    "batch_index": bs.batch_index,
                    "material_ids": bs.material_ids,
                    "domains": bs.domain_expertise
                }
                for bs in batch_summaries
            ]
        }

        # Upload to storage bucket
        storage_path = f"{user_id}/{session_id}/learning_path.json"

        try:
            self.supabase.storage.from_("learning_paths").upload(
                storage_path,
                json.dumps(document, indent=2).encode("utf-8"),
                {"content-type": "application/json"}
            )
        except Exception as e:
            # Try to remove and re-upload if exists
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                self.supabase.storage.from_("learning_paths").remove([storage_path])
                self.supabase.storage.from_("learning_paths").upload(
                    storage_path,
                    json.dumps(document, indent=2).encode("utf-8"),
                    {"content-type": "application/json"}
                )
            else:
                raise

        # Save to database
        self.supabase.table("learning_paths").insert({
            "id": learning_path_id,
            "session_id": session_id,
            "user_id": user_id,
            "storage_path": storage_path,
            "total_nodes": knowledge_dag["metadata"]["total_nodes"],
            "max_depth": knowledge_dag["metadata"]["max_depth"]
        }).execute()

        # Also store nodes in knowledge_nodes table for querying
        for node in knowledge_dag.get("nodes", []):
            self.supabase.table("knowledge_nodes").insert({
                "id": node["id"],
                "session_id": session_id,
                "learning_path_id": learning_path_id,
                "label": node.get("label", ""),
                "type": node.get("type", "concept"),
                "mastery_estimate": node.get("mastery_likelihood", 0.5),
                "depth_level": node.get("depth", 0),
                "source": "learning_path",
                "is_llm_generated": True
            }).execute()

        # Store edges in knowledge_prerequisites with reasoning
        for edge in document["edges"]:
            prereq_data = {
                "learning_path_id": learning_path_id,
                "source_node_id": edge["source"],
                "target_node_id": edge["target"],
                "relationship": edge.get("type", "requires"),
                "reasoning": edge.get("reasoning", ""),
            }
            self.supabase.table("knowledge_prerequisites").insert(prereq_data).execute()

        return LearningPathResult(
            success=True,
            learning_path_id=learning_path_id,
            storage_path=storage_path,
            total_nodes=knowledge_dag["metadata"]["total_nodes"],
            max_depth=knowledge_dag["metadata"]["max_depth"],
            relationship_distribution=knowledge_dag["metadata"].get("relationship_distribution")
        )

    def _build_edges(self, nodes: List[Dict]) -> List[Dict]:
        """Build edge list from node prerequisites with relationship types and reasoning."""
        edges = []
        for node in nodes:
            for prereq in node.get("prerequisites", []):
                if isinstance(prereq, str):
                    # Legacy format
                    edges.append({
                        "source": prereq,
                        "target": node["id"],
                        "type": "requires",
                        "reasoning": ""
                    })
                elif isinstance(prereq, dict):
                    # New format with relationship and reasoning
                    edges.append({
                        "source": prereq.get("node_id", ""),
                        "target": node["id"],
                        "type": prereq.get("relationship", "requires"),
                        "reasoning": prereq.get("reasoning", "")
                    })
        return edges

    async def _update_job_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[Dict] = None,
        error_message: Optional[str] = None
    ):
        """Update job status in database."""
        update_data = {"status": status}

        if progress:
            update_data["progress"] = progress

        if error_message:
            update_data["error_message"] = error_message

        if status == "completed":
            update_data["completed_at"] = datetime.utcnow().isoformat()

        self.supabase.table("learning_path_jobs").update(
            update_data
        ).eq("id", job_id).execute()

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API via REST."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 8192
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from response, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)

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
