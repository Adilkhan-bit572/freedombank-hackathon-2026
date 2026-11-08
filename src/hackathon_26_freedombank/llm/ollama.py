import httpx
import ollama

from .base import LLMError


class OllamaClient:
    provider = "ollama"

    def __init__(
        self,
        host: str,
        model: str,
        *,
        think: bool = False,
        num_ctx: int = 16384,
        num_predict: int = 4096,
        temperature: float = 0.0,
        timeout: float = 600.0,
    ):
        self.model = model
        self.think = think
        self.options = {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
            # Modelfiles often set presence_penalty (qwen3.5: 1.5). It penalises repeating
            # tokens, which breaks JSON where the same keys repeat for every criterion.
            "presence_penalty": 0,
            "repeat_penalty": 1.0,
        }
        self._client = ollama.Client(host=host, timeout=timeout)

    def generate_json(self, system: str, user: str, schema: dict | None = None) -> str:
        try:
            resp = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                # A JSON schema constrains decoding to our response shape; plain "json" otherwise.
                format=schema or "json",
                think=self.think,
                options=self.options,
            )
        except httpx.TimeoutException as e:
            raise LLMError(f"Ollama did not answer within the timeout (OLLAMA_TIMEOUT): {e}") from e
        except Exception as e:  # connection errors, missing model, etc.
            raise LLMError(f"Ollama request failed: {e}") from e
        if resp.done_reason == "length":
            raise LLMError(
                f"Ollama answer was cut off at {resp.eval_count} tokens "
                f"(prompt {resp.prompt_eval_count} tokens). Increase OLLAMA_NUM_PREDICT / OLLAMA_NUM_CTX."
            )
        text = resp.message.content
        if not text:
            raise LLMError("Ollama returned an empty response")
        return text
