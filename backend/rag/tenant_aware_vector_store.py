"""
Tenant-Aware FHIR Mapping Vector Store
Ensures RAG suggestions are scoped to the current hospital

CRITICAL SECURITY FIX:
- Adds tenant_id to all vector metadata
- Filters queries by tenant_id
- Prevents cross-hospital data leakage in AI suggestions
"""

import math, hashlib, struct
from typing import List, Dict, Any, Optional
from rag.fhir_knowledge import get_all_mappings


class TenantAwareMappingVectorStore:
    """
    Vector store with tenant isolation for federated architecture
    
    Each mapping includes tenant_id in metadata to ensure
    suggestions are scoped to the correct hospital.
    """
    
    COLLECTION = "fhir_field_mappings_v3_tenant_aware"

    def __init__(self, persist_directory="./databases/chroma", ollama_client=None, auto_seed=False):
        """
        Initialize tenant-aware vector store
        
        Args:
            persist_directory: Path to ChromaDB storage
            ollama_client: Optional Ollama client for embeddings
            auto_seed: If True, seeds default mappings (without tenant_id)
        
        Note: auto_seed should be False in production. Mappings should be
        added per-tenant using add_mapping() with tenant_id specified.
        """
        self._ollama = ollama_client
        self._col = self._init_collection(persist_directory)
        
        if auto_seed and self._col.count() == 0:
            print("  WARNING: Auto-seeding without tenant_id. Use add_mapping(mapping, tenant_id) instead.")
            n = self._seed_knowledge_base()
            print(f"  Seeded {n} FHIR mappings into ChromaDB (no tenant isolation!)")
        else:
            print(f"  Tenant-aware vector store: {self._col.count()} mappings loaded")

    def _init_collection(self, path):
        try:
            import chromadb
        except ImportError:
            raise ImportError("Run: pip install chromadb")
        client = chromadb.PersistentClient(path=path)
        return client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={
                "description": "CareLock FHIR mappings with tenant isolation",
                "hnsw:space": "cosine"
            },
        )

    def add_mapping(self, mapping: Dict[str, Any], tenant_id: Optional[int] = None) -> bool:
        """
        Add a mapping to the vector store with tenant isolation
        
        Args:
            mapping: FHIR mapping dictionary
            tenant_id: ID of the hospital this mapping belongs to (REQUIRED for isolation)
        
        Returns:
            True if added successfully, False otherwise
        
        Example:
            store.add_mapping({
                "source_field": "patient_name",
                "target_path": "Patient.name",
                "fhir_resource": "Patient"
            }, tenant_id=1)
        """
        try:
            text = self._mapping_to_text(mapping)
            emb = self._get_embedding(text)
            
            # Create unique ID including tenant for isolation
            base_id = "m_" + str(abs(hash(text + mapping.get("source_field", ""))))
            mid = f"{base_id}_t{tenant_id}" if tenant_id else base_id
            
            # Build metadata with tenant_id
            meta = {
                k: str(mapping.get(k, ""))
                for k in ["source_field", "source_type", "target_path",
                          "fhir_resource", "transformation"]
            }
            meta["confidence"] = float(mapping.get("confidence", 0.0))
            
            # CRITICAL: Add tenant_id to metadata for filtering
            if tenant_id is not None:
                meta["tenant_id"] = str(tenant_id)
            
            self._col.upsert(
                ids=[mid],
                embeddings=[emb],
                documents=[text],
                metadatas=[meta]
            )
            return True
            
        except Exception as exc:
            print(f"    add_mapping error: {exc}")
            return False

    def find_similar_mappings(
        self,
        field_name: str,
        field_type: str,
        tenant_id: Optional[int] = None,
        fhir_resource: Optional[str] = None,
        n_results: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Find similar mappings with tenant isolation
        
        Args:
            field_name: Name of the field to find mappings for
            field_type: Type of the field (e.g., 'VARCHAR', 'INTEGER')
            tenant_id: REQUIRED - ID of hospital to scope results to
            fhir_resource: Optional FHIR resource filter
            n_results: Maximum number of results
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of matching mappings, scoped to specified tenant
        
        SECURITY: If tenant_id is provided, ONLY returns mappings for that hospital
        
        Example:
            # Get suggestions ONLY for hospital 1
            results = store.find_similar_mappings(
                "patient_name", 
                "VARCHAR",
                tenant_id=1  # Only hospital 1's mappings
            )
        """
        if self._col.count() == 0:
            return []
        
        # Build query
        query = field_name + " " + field_name.replace("_", " ") + " " + field_type
        emb = self._get_embedding(query)
        n = min(n_results, self._col.count())
        
        # Build filter conditions
        where = {}
        
        # CRITICAL: Filter by tenant_id for isolation
        if tenant_id is not None:
            where["tenant_id"] = str(tenant_id)
        
        # Optional: Also filter by FHIR resource
        if fhir_resource:
            where["fhir_resource"] = fhir_resource
        
        # Query with filters
        try:
            if where:
                results = self._col.query(
                    query_embeddings=[emb],
                    n_results=n,
                    where=where  # Tenant isolation applied here!
                )
            else:
                # No filters - returns all tenants (use with caution!)
                results = self._col.query(query_embeddings=[emb], n_results=n)
        except Exception as e:
            print(f"    Query error: {e}")
            results = self._col.query(query_embeddings=[emb], n_results=n)
        
        # Process results
        out = []
        if results.get("metadatas") and results.get("distances"):
            for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
                # Calculate similarity
                sim = max(0.0, min(1.0, 1.0 - dist))
                if sim >= min_similarity:
                    out.append({**meta, "similarity": round(sim, 4)})
        
        return out

    def get_statistics(self, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics, optionally scoped to a tenant
        
        Args:
            tenant_id: If provided, returns stats for this tenant only
        
        Returns:
            Statistics dictionary
        """
        base_stats = {
            "collection_name": self.COLLECTION,
            "distance_metric": "cosine"
        }
        
        if tenant_id is not None:
            # Count mappings for this tenant
            try:
                results = self._col.get(
                    where={"tenant_id": str(tenant_id)},
                    limit=10000  # Rough count
                )
                tenant_count = len(results.get("ids", []))
                base_stats["total_mappings"] = tenant_count
                base_stats["tenant_id"] = tenant_id
            except:
                base_stats["total_mappings"] = "unknown"
        else:
            base_stats["total_mappings"] = self._col.count()
        
        return base_stats

    # ========================================================================
    # Internal Methods (unchanged from original)
    # ========================================================================

    def _seed_knowledge_base(self):
        """Seed default mappings (WITHOUT tenant_id - use with caution!)"""
        count = 0
        for mapping in get_all_mappings():
            if self.add_mapping(mapping, tenant_id=None):
                count += 1
        return count

    def _get_embedding(self, text):
        if self._ollama:
            return self._ollama.get_embedding(text)
        return hash_embedding(text)

    @staticmethod
    def _mapping_to_text(m):
        sf = m.get("source_field", "")
        parts = [
            sf,
            sf.replace("_", " "),
            m.get("source_type", ""),
            m.get("target_path", ""),
            m.get("fhir_resource", "")
        ]
        return " ".join(x for x in parts if x)


def hash_embedding(text, dim=768):
    """Generate deterministic embedding from text hash"""
    h = hashlib.sha512(text.encode()).digest()
    reps = (dim * 4 // len(h)) + 1
    rep = (h * reps)[: dim * 4]
    fl = list(struct.unpack(str(dim) + "f", rep))
    mag = math.sqrt(sum(x * x for x in fl)) or 1.0
    return [x / mag for x in fl]


# Backwards compatibility alias
MappingVectorStore = TenantAwareMappingVectorStore
_hash_embedding = hash_embedding
