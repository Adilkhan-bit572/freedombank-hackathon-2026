from google import genai
from google.genai import types

from .base import LLMError


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.model = model
        self._client = genai.Client(api_key=api_key)

    def generate_json(self, system: str, user: str, schema: dict | None = None) -> str:  # schema: unused
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                ),
            )
        except Exception as e:  # SDK raises several error types; normalise them
            code = getattr(e, "code", None) or getattr(e, "status_code", None)
            retryable = code in (429, 500, 503) or any(
                s in str(e) for s in ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "429", "503")
            )
            raise LLMError(f"Gemini request failed: {e}", retryable=retryable) from e
        if not resp.text:
            raise LLMError("Gemini returned an empty response")
        return resp.text
