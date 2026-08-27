# FHIR Mapping Vector Store - ChromaDB 1.x cosine distance, Sprint 4
# KEY FIX: hnsw:space=cosine + similarity = 1.0-dist (not 1-dist/2)
# Works with raw unnormalized nomic-embed-text vectors (magnitude ~22)
import math, hashlib, struct
from typing import List, Dict, Any, Optional
from rag.fhir_knowledge import get_all_mappings


class MappingVectorStore:
    COLLECTION = "fhir_field_mappings_v2"

    def __init__(self, persist_directory="./databases/chroma", ollama_client=None, auto_seed=True):
        self._ollama = ollama_client
        self._col    = self._init_collection(persist_directory)
        if auto_seed and self._col.count() == 0:
            n = self._seed_knowledge_base()
            print(f"  Seeded {n} FHIR mappings into ChromaDB")
        else:
            print(f"  Vector store: {self._col.count()} mappings loaded")

    def _init_collection(self, path):
        try:
            import chromadb
        except ImportError:
            raise ImportError("Run: pip install chromadb")
        client = chromadb.PersistentClient(path=path)
        return client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"description": "CareLock FHIR mappings", "hnsw:space": "cosine"},
        )

    def _seed_knowledge_base(self):
        count = 0
        for mapping in get_all_mappings():
            if self.add_mapping(mapping):
                count += 1
        return count

    def add_mapping(self, mapping):
        try:
            text = self._mapping_to_text(mapping)
            emb  = self._get_embedding(text)
            mid  = "m_" + str(abs(hash(text + mapping.get("source_field", ""))))
            meta = {k: str(mapping.get(k, ""))
                    for k in ["source_field", "source_type", "target_path",
                              "fhir_resource", "transformation"]}
            meta["confidence"] = float(mapping.get("confidence", 0.0))
            self._col.upsert(ids=[mid], embeddings=[emb], documents=[text], metadatas=[meta])
            return True
        except Exception as exc:
            print(f"    add_mapping error: {exc}")
            return False

    def find_similar_mappings(self, field_name, field_type, fhir_resource=None,
                              n_results=5, min_similarity=0.0):
        if self._col.count() == 0:
            return []
        query = field_name + " " + field_name.replace("_", " ") + " " + field_type
        emb   = self._get_embedding(query)
        n     = min(n_results, self._col.count())
        try:
            where   = {"fhir_resource": fhir_resource} if fhir_resource else None
            results = self._col.query(query_embeddings=[emb], n_results=n, where=where)
        except Exception:
            results = self._col.query(query_embeddings=[emb], n_results=n)
        out = []
        if results.get("metadatas") and results.get("distances"):
            for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
                # cosine distance in [0,2]; cosine_similarity = 1 - distance
                sim = max(0.0, min(1.0, 1.0 - dist))
                if sim >= min_similarity:
                    out.append({**meta, "similarity": round(sim, 4)})
        return out

    def get_statistics(self):
        return {"total_mappings": self._col.count(),
                "collection_name": self.COLLECTION,
                "distance_metric": "cosine"}

    def _get_embedding(self, text):
        if self._ollama:
            return self._ollama.get_embedding(text)
        return hash_embedding(text)

    @staticmethod
    def _mapping_to_text(m):
        sf    = m.get("source_field", "")
        parts = [sf, sf.replace("_", " "), m.get("source_type", ""),
                 m.get("target_path", ""), m.get("fhir_resource", "")]
        return " ".join(x for x in parts if x)


def hash_embedding(text, dim=768):
    h   = hashlib.sha512(text.encode()).digest()
    # Need dim*4 bytes; sha512 = 64 bytes, so repeat ceil(dim*4/64) times
    reps = (dim * 4 // len(h)) + 1
    rep  = (h * reps)[: dim * 4]
    fl   = list(struct.unpack(str(dim) + "f", rep))
    mag  = math.sqrt(sum(x * x for x in fl)) or 1.0
    return [x / mag for x in fl]

# backwards-compat alias
_hash_embedding = hash_embedding
