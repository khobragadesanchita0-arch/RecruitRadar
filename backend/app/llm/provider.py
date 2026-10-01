import abc
import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

class LLMResponse(BaseModel):
    content: str
    parsed_json: Optional[Dict[str, Any]] = None
    usage: LLMUsage = LLMUsage()
    model: str = "fake-model"

class LLMProvider(abc.ABC):
    @abc.abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """Generates structured response validated against Pydantic schema T with 1 repair attempt."""
        pass

    @abc.abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 250,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Generates text response with token and cost tracking."""
        pass

    @abc.abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a list of strings."""
        pass
