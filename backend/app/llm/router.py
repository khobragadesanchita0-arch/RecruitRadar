from app.core.config import settings
from app.llm.provider import LLMProvider
from app.llm.fake import FakeLLM

_llm_instance: LLMProvider | None = None

def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance is None:
        if settings.llm_provider == "fake":
            _llm_instance = FakeLLM(dim=settings.embedding_dim)
        else:
            # Fallback to FakeLLM if real credentials are not supplied
            _llm_instance = FakeLLM(dim=settings.embedding_dim)
    return _llm_instance
