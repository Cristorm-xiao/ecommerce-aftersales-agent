"""LLM and embedding instances — imported across all nodes."""
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
import config

_text_base = dict(base_url=config.DEEPSEEK_BASE_URL, api_key=config.DEEPSEEK_API_KEY,
                  model=config.DEEPSEEK_MODEL)

# ChatOpenAI does not preserve DeepSeek's reasoning_content. Keep both
# text models in non-thinking mode so function calls use standard messages.
_text_options = (
    {"extra_body": {"thinking": {"type": "disabled"}}}
    if "deepseek" in config.DEEPSEEK_MODEL.lower() else {}
)

answer_LLM = ChatOpenAI(
    **_text_base,
    **_text_options,
)
router_LLM = ChatOpenAI(**_text_base, temperature=0, **_text_options)

# Independent Qwen-VL client; optional so text-only chat needs no vision key.
# DeepSeek-specific thinking options are intentionally not passed here.
vision_LLM = ChatOpenAI(
    base_url=config.VISION_BASE_URL,
    api_key=config.VISION_API_KEY,
    model=config.VISION_MODEL,
) if config.VISION_API_KEY else None


class MockEmbeddings(Embeddings):
    """Placeholder embeddings — no external API required.
    Returns fixed-size zero vectors so RAG runs without OpenAI credentials.
    Dimension (1536) matches OpenAI's text-embedding-3-small for Pinecone index compatibility.
    Replace with a real embedding model when ready for production RAG quality.
    """
    _DIM = 1536

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._DIM for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * self._DIM


embeddings = OpenAIEmbeddings(
    model = config.SILICONFLOW_EMBEDDING_MODEL,
    api_key = config.SILICONFLOW_API_KEY,
    base_url = "https://api.siliconflow.cn/v1",
    check_embedding_ctx_length = False,
    chunk_size = 32,
) if config.SILICONFLOW_API_KEY else None
