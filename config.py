"""Configuration — all settings from environment variables."""
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Text generation / routing / tool decisions (DeepSeek).
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

# Image understanding (Qwen-VL via Alibaba Cloud Bailian, Beijing region).
# Credentials and endpoints are independent; never reuse the text model key.
VISION_API_KEY = os.getenv("VISION_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
VISION_BASE_URL = os.getenv("VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3-vl-plus")

# Vector DB (Pinecone)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX   = os.getenv("PINECONE_INDEX", "vector")
AFTERSALES_PINECONE_INDEX = os.getenv("AFTERSALES_PINECONE_INDEX", PINECONE_INDEX)
AFTERSALES_PINECONE_NAMESPACE = os.getenv("AFTERSALES_PINECONE_NAMESPACE", "")

# Web Search (Tavily)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Database (Neon PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")

# MCP Server
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://deploy-9ugq.onrender.com/mcp")

# Observability (LangSmith)
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "langgraph-agent")
LANGCHAIN_TRACING = os.getenv("LANGCHAIN_TRACING_V2", "false")

# Agent Tuning
MAX_ITERATIONS    = int(os.getenv("MAX_ITERATIONS", "5"))
RETRIEVER_K       = int(os.getenv("RETRIEVER_K", "5"))
RETRIEVER_FETCH_K = int(os.getenv("RETRIEVER_FETCH_K", "20"))

#silicon_flow embedding api_key
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_EMBEDDING_MODEL = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")

# Business rules are local; policy retrieval uses Pinecone and SiliconFlow.
AGENT_MODE = os.getenv("AGENT_MODE", "aftersales")
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "postgres" if DATABASE_URL else "memory")
AFTERSALES_DEMO_DATE = date.fromisoformat(os.getenv("AFTERSALES_DEMO_DATE", "2026-10-11"))
AFTERSALES_DB_PATH = Path(os.getenv("AFTERSALES_DB_PATH", str(Path(__file__).resolve().parent / "data" / "aftersales.sqlite3")))



# Validation
def validate():
    if AGENT_MODE not in {"aftersales", "general"}:
        raise ValueError("AGENT_MODE must be aftersales or general")
    if MEMORY_BACKEND not in {"memory", "postgres"}:
        raise ValueError("MEMORY_BACKEND must be memory or postgres")
    if MAX_ITERATIONS < 1:
        raise ValueError("MAX_ITERATIONS must be at least 1")
    required = {"DEEPSEEK_API_KEY": DEEPSEEK_API_KEY}
    if MEMORY_BACKEND == "postgres":
        required["DATABASE_URL"] = DATABASE_URL
    if AGENT_MODE == "general":
        required.update(PINECONE_API_KEY=PINECONE_API_KEY, TAVILY_API_KEY=TAVILY_API_KEY,
                        SILICONFLOW_API_KEY=SILICONFLOW_API_KEY)
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise EnvironmentError(f"Missing env vars: {missing}. See .env.aftersales.example")
