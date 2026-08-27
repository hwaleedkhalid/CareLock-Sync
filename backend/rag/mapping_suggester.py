"""
FHIR Mapping Suggester - Sprint 4 v2
Dual-model architecture:
  - mapping_model: llama3.2:3b  (lightweight, fast, for field mapping)
  - chat_model:    phi3          (richer, for RAG chatbot / Q&A)
Human-in-the-loop: all suggestions are status='pending_review' until confirmed.
"""
from typing import Dict, List, Any, Optional
from rag.ollama_client import OllamaClient
from rag.vector_store import MappingVectorStore


class MappingSuggester:
    def __init__(
        self,
        mapping_model: str = "llama3.2:3b",
        chat_model: str = "phi3",
        ollama_base_url: str = "http://localhost:11434",
        vector_store_path: str = "./databases/chroma",
        auto_load: bool = True,
    ):
        print(f"Initialising RAG engine...")
        print(f"  mapping_model : {mapping_model}  (fast/lightweight)")
        print(f"  chat_model    : {chat_model}  (richer, for chatbot)")
        self.mapping_client = OllamaClient(
            model=mapping_model, base_url=ollama_base_url, timeout=120)
        self._chat_model = chat_model
        self._ollama_base_url = ollama_base_url
        self._chat_client: Optional[OllamaClient] = None
        self.vs = MappingVectorStore(
            persist_directory=vector_store_path,
            ollama_client=self.mapping_client,
            auto_seed=auto_load,
        )
        print(f"RAG ready | mappings={self.vs.get_statistics()['total_mappings']}")


    def suggest_mapping(
        self,
        field_name: str,
        field_type: str,
        sample_values: Optional[List] = None,
        fhir_resource: str = "Patient",
        n_similar: int = 5,
    ) -> Dict[str, Any]:
        similar = self.vs.find_similar_mappings(
            field_name, field_type, fhir_resource, n_similar, 0.2)
        # Fast-path: strong retrieval match - skip LLM entirely
        if similar and similar[0]["similarity"] >= 0.88:
            top = similar[0]
            return {
                "source_field": field_name,
                "source_type": field_type,
                "fhir_resource": fhir_resource,
                "target_path": top["target_path"],
                "confidence": round(top["similarity"], 2),
                "reasoning": f"Retrieval match: '{top['source_field']}' ({top['similarity']:.0%})",
                "transformation": top.get("transformation", "none"),
                "similar_mappings": similar,
                "method": "retrieval",
                "status": "pending_review",
            }
        suggestion = self.mapping_client.generate_mapping_suggestion(
            {"name": field_name, "type": field_type,
             "sample_values": sample_values or []},
            similar, fhir_resource,
        )
        return {
            "source_field": field_name,
            "source_type": field_type,
            "fhir_resource": fhir_resource,
            **suggestion,
            "similar_mappings": similar,
            "method": "rag",
            "status": "pending_review",
        }


    def suggest_schema_mapping(
        self,
        schema: Dict[str, Any],
        fhir_resource: str = "Patient",
    ) -> Dict[str, Any]:
        table = schema.get("table_name", "unknown")
        print(f"\nGenerating suggestions: {table} -> FHIR {fhir_resource}")
        print("-" * 64)
        mappings = []
        for col in schema.get("columns", []):
            r = self.suggest_mapping(
                col["name"], col.get("type", "varchar"),
                col.get("sample_values"), fhir_resource)
            mappings.append(r)
            icon = "+" if r["confidence"] >= 0.8 else ("~" if r["confidence"] >= 0.5 else "?")
            print(f"  [{icon}] {col['name']:<22} -> {r['target_path']:<36}"
                  f" {r['confidence']:>4.0%}  [{r['method']}]")
        high = sum(1 for m in mappings if m["confidence"] >= 0.80)
        acc = high / len(mappings) * 100 if mappings else 0
        print("-" * 64)
        print(f"  Accuracy: {acc:.0f}%  ({high}/{len(mappings)} high-confidence)")
        print(f"  Status: ALL pending - awaiting review\n")
        return {
            "table_name": table,
            "fhir_resource": fhir_resource,
            "mappings": mappings,
            "statistics": {
                "total": len(mappings),
                "high": high,
                "medium": sum(1 for m in mappings if 0.5 <= m["confidence"] < 0.8),
                "low": sum(1 for m in mappings if m["confidence"] < 0.5),
            },
            "accuracy_pct": round(acc, 1),
            "status": "pending_review",
        }

    def confirm_mappings(
        self,
        mappings: List[Dict[str, Any]],
        confirmed_ids: List[str],
    ) -> Dict[str, Any]:
        saved, skipped = [], []
        for m in mappings:
            if m["source_field"] in confirmed_ids:
                self.vs.add_mapping({
                    "source_field": m["source_field"],
                    "source_type": m.get("source_type", "varchar"),
                    "target_path": m["target_path"],
                    "fhir_resource": m["fhir_resource"],
                    "transformation": m.get("transformation", "none"),
                    "confidence": m["confidence"],
                })
                saved.append(m["source_field"])
            else:
                skipped.append(m["source_field"])
        return {"saved": saved, "skipped": skipped, "total_saved": len(saved)}

    @property
    def chat_client(self) -> OllamaClient:
        if self._chat_client is None:
            self._chat_client = OllamaClient(
                model=self._chat_model,
                base_url=self._ollama_base_url,
                timeout=180,
            )
        return self._chat_client

    def chat(self, question: str, context: Optional[str] = None) -> str:
        if context is None:
            similar = self.vs.find_similar_mappings(question, "text", None, 5, 0.3)
            context = "\n".join(
                f"- {m['source_field']} -> {m['target_path']} ({m['fhir_resource']})"
                for m in similar) or "No relevant mappings found."
        prompt = f"""You are a FHIR R4 expert for CareLock healthcare data.
Answer concisely using the context below.

Context:
{context}

Question: {question}
Answer:"""
        try:
            return self.chat_client._generate(prompt).strip()
        except Exception as e:
            return f"Chat error: {e}"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mapping_model": self.mapping_client.model,
            "chat_model": self._chat_model,
            "mapping_available": self.mapping_client.is_available(),
            "chat_available": self._chat_client.is_available() if self._chat_client else None,
            **self.vs.get_statistics(),
        }

    def save_confirmed_mapping(self, source_field, source_type, target_path,
                                fhir_resource="Patient", transformation="none", confidence=1.0):
        self.vs.add_mapping({
            "source_field": source_field, "source_type": source_type,
            "target_path": target_path, "fhir_resource": fhir_resource,
            "transformation": transformation, "confidence": confidence,
        })
