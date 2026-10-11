"""Load optional general-purpose integrations only when requested."""


def __getattr__(name):
    if name == "RAG":
        from tools.rag import RAG
        return RAG
    if name == "search_web":
        from tools.web_search import search_web
        return search_web
    if name == "mcp_client":
        from tools.mcp_client import mcp_client
        return mcp_client
    raise AttributeError(name)

__all__ = ["RAG", "search_web", "mcp_client"]
