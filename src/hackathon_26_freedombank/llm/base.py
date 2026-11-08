from typing import Protocol


class LLMError(Exception):
    """The LLM could not be reached or returned an error.

    `retryable` is True for temporary failures (rate limit, overload) worth retrying later.
    """

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class LLMClient(Protocol):
    provider: str
    model: str

    def generate_json(self, system: str, user: str, schema: dict | None = None) -> str:
        """Send a system + user prompt and return the model's raw (JSON) text.
        `schema` is an optional JSON schema of the expected answer (providers may ignore it)."""
        ...
