"""
Ollama Local LLM Client — Sprint 4 (phi3-compatible, fixed)
180s timeout | 4-strategy JSON parser | hash fallback embeddings
"""
import json, re, math, struct, hashlib
import requests
from typing import List, Dict, Any, Optional

OLLAMA_BASE_URL = "http://localhost:11434"

_PROMPT = """\
Map this database column to FHIR R4. Reply with ONE line of JSON only, no prose.

Column: {field_name} ({field_type})
FHIR resource: {fhir_resource}

Known mappings for reference:
{similar_context}

Common {fhir_resource} paths: {fhir_paths}

OUTPUT exactly this format (one line, no markdown):
{{"target_path":"Patient.birthDate","confidence":0.95,"reasoning":"date of birth field","transformation":"none"}}

transformation must be: none, format_date, map_gender, format_phone, string_to_boolean, combine_name
"""

_FHIR_PATHS: Dict[str, List[str]] = {
    "Patient": ["identifier[].value","name[].family","name[].given[]","birthDate",
                "gender","telecom[].value","address[].city","address[].postalCode","active"],
    "Encounter": ["identifier[].value","status","class.code","subject.reference",
                  "period.start","period.end","reasonCode[].text"],
    "Observation": ["identifier[].value","status","code.coding[].code",
                    "code.coding[].display","valueQuantity.value","valueQuantity.unit",
                    "effectiveDateTime","subject.reference"],
    "MedicationRequest": ["identifier[].value","status","medicationCodeableConcept.text",
                          "dosageInstruction[].text","authoredOn","subject.reference"],
}


class OllamaClient:
    def __init__(self, model: str = "phi3", base_url: str = OLLAMA_BASE_URL, timeout: int = 180):
        self.model    = model
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self._verify_connection()

    def generate_mapping_suggestion(self, source_field: Dict, similar_mappings: List[Dict],
                                    fhir_resource: str = "Patient") -> Dict[str, Any]:
        prompt = self._build_prompt(source_field, similar_mappings, fhir_resource)
        try:
            raw    = self._generate(prompt)
            result = self._parse_response(raw)
            if result["target_path"] == "unknown" and similar_mappings:
                top = similar_mappings[0]
                return {"target_path":    top["target_path"],
                        "confidence":     round(float(top.get("similarity", top.get("confidence", 0.7))), 2),
                        "reasoning":      f"Retrieval fallback: matched {top['source_field']}",
                        "transformation": top.get("transformation", "none")}
            return result
        except Exception as exc:
            if similar_mappings:
                top = similar_mappings[0]
                return {"target_path": top["target_path"],
                        "confidence":  round(float(top.get("similarity", top.get("confidence", 0.7))), 2),
                        "reasoning":   f"Ollama error ({exc}) — retrieval fallback",
                        "transformation": top.get("transformation", "none")}
            return {"target_path": "unknown", "confidence": 0.0,
                    "reasoning": f"Ollama error: {exc}", "transformation": "none"}

    def get_embedding(self, text: str) -> List[float]:
        try:
            r = requests.post(f"{self.base_url}/api/embeddings",
                              json={"model": "nomic-embed-text", "prompt": text}, timeout=30)
            if r.status_code == 200:
                return r.json()["embedding"]
        except Exception:
            pass
        return _hash_embedding(text)

    def is_available(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/api/tags", timeout=5).status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            return [m["name"] for m in
                    requests.get(f"{self.base_url}/api/tags", timeout=5).json().get("models", [])]
        except Exception:
            return []

    def _verify_connection(self):
        if not self.is_available():
            raise ConnectionError(f"Ollama not reachable at {self.base_url}. Run: ollama serve")
        models = self.list_models()
        if not any(self.model in m for m in models):
            raise ValueError(f"Model '{self.model}' not found. Available: {models}.")

    def _generate(self, prompt: str) -> str:
        resp = requests.post(f"{self.base_url}/api/generate",
                             json={"model": self.model, "prompt": prompt, "stream": False,
                                   "options": {"temperature": 0.05, "top_p": 0.9,
                                               "num_predict": 150}},
                             timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _build_prompt(self, source_field, similar_mappings, fhir_resource):
        similar_lines = "\n".join(
            f"  {m.get('source_field','?')} -> {m.get('target_path','?')}"
            for m in similar_mappings[:3]) or "  (none)"
        fhir_paths = " | ".join(_FHIR_PATHS.get(fhir_resource, ["id"])[:7])
        return _PROMPT.format(
            field_name=source_field.get("name","unknown"),
            field_type=source_field.get("type","varchar"),
            fhir_resource=fhir_resource,
            similar_context=similar_lines,
            fhir_paths=fhir_paths)

    @staticmethod
    def _parse_response(text: str) -> Dict[str, Any]:
        text = text.strip()
        # Strip markdown fences
        text = re.sub(r'```(?:json)?\s*', '', text)
        text = re.sub(r'```\s*$', '', text)

        # Strategy 1: direct json.loads
        try:
            p = json.loads(text)
            if isinstance(p, dict) and "target_path" in p:
                return _normalise(p)
        except Exception:
            pass

        # Strategy 2: flat {…} blocks (non-nested)
        for m in re.finditer(r'\{[^{}]+\}', text, re.DOTALL):
            try:
                p = json.loads(m.group())
                if "target_path" in p:
                    return _normalise(p)
            except Exception:
                continue

        # Strategy 3: balanced nested {…} then flatten
        s = _extract_outer_object(text)
        if s:
            try:
                p = json.loads(s)
                flat = _flatten(p)
                if "target_path" in flat:
                    return _normalise(flat)
            except Exception:
                pass

        # Strategy 4: regex key extraction (phi3 prose format)
        tp = _re_val(text, "target_path")
        if tp:
            return _normalise({
                "target_path":    tp,
                "confidence":     _re_val(text, "confidence") or "0.7",
                "reasoning":      _re_val(text, "reasoning")  or "",
                "transformation": _re_val(text, "transformation") or "none",
            })

        return {"target_path": "unknown", "confidence": 0.0,
                "reasoning": f"Parse failed. Raw={text[:80]}", "transformation": "none"}


def _normalise(d: dict) -> dict:
    d.setdefault("target_path", "unknown")
    d.setdefault("confidence", 0.0)
    d.setdefault("reasoning", "")
    d.setdefault("transformation", "none")
    try:
        d["confidence"] = max(0.0, min(1.0, float(d["confidence"])))
    except (ValueError, TypeError):
        d["confidence"] = 0.7
    return d

def _re_val(text: str, field: str) -> Optional[str]:
    m = re.search(rf'["\']?{field}["\']?\s*[:\s]\s*["\']?([^,"\'}}|\n\r]+)["\']?',
                  text, re.IGNORECASE)
    return m.group(1).strip().strip('"\'') if m else None

def _extract_outer_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None

def _flatten(d: dict, pref: str = "") -> dict:
    out = {}
    for k, v in d.items():
        out[k] = v
        if isinstance(v, dict):
            out.update(_flatten(v, pref+k+"."))
    return out

def _hash_embedding(text: str, dim: int = 768) -> List[float]:
    h = hashlib.sha512(text.encode()).digest()
    repeated = (h * (dim // len(h) + 1))[:dim*4]
    floats = list(struct.unpack(f"{dim}f", repeated))
    mag = math.sqrt(sum(x*x for x in floats)) or 1.0
    return [x/mag for x in floats]
