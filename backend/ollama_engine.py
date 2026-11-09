import json
from typing import Any

import httpx

from . import config


class OllamaError(RuntimeError):
    pass


class OllamaEngine:
    def __init__(self, base_url: str = config.OLLAMA_BASE_URL):
        self.base_url = base_url

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=90) as client:
            response = await client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

    async def embed(self, text: str) -> list[float]:
        result = await self._post("/api/embeddings", {"model": config.OLLAMA_EMBED_MODEL, "prompt": text})
        return result["embedding"]

    async def structured(self, system: str, prompt: str) -> dict[str, Any]:
        payload = {"model": config.OLLAMA_CHAT_MODEL, "format": "json", "stream": False, "options": {"temperature": 0}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        try:
            result = await self._post("/api/chat", payload)
        except (httpx.HTTPError, KeyError) as first_error:
            payload["model"] = config.OLLAMA_FALLBACK_MODEL
            try:
                result = await self._post("/api/chat", payload)
            except (httpx.HTTPError, KeyError) as second_error:
                raise OllamaError(str(second_error)) from first_error
        try:
            return json.loads(result["message"]["content"])
        except (KeyError, json.JSONDecodeError) as error:
            raise OllamaError("Ollama returned invalid JSON") from error

    async def cover_letter(self, prompt: str) -> str:
        payload = {"model": config.OLLAMA_CHAT_MODEL, "stream": False, "options": {"temperature": 0.2}, "messages": [{"role": "system", "content": "Write only a plain-text, 3-paragraph cover letter. Use 40-75 words, first person, and direct engineering English. Open with a specific application statement, not a generic expression of excitement. Use the role title and company only when they are supplied. If the company is missing, write 'your team' instead. Never output bracketed placeholders such as [Company Name]. Use only verified facts from the candidate profile and job description. Keep employment claims in the tense supported by the profile. Never use these words: delve, testament, tapestry, passionate, thrilled, excited, dynamic, leverage, spearhead, synergy, cutting-edge, seamlessly, pivotal, honing, eager, align, foster, realm, embark, unwavering, moreover, furthermore. Never use em-dashes, semicolons, or bullets."}, {"role": "user", "content": prompt}]}
        result = await self._post("/api/chat", payload)
        return result["message"]["content"].strip()
