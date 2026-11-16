"""Live web verification via Tavily."""
import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

_client = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _client


def search(query: str, max_results: int = 5) -> list[dict]:
    r = _get_client().search(
        query=query,
        search_depth=os.getenv("TAVILY_DEPTH", "basic"),
        max_results=max_results,
        include_answer=False,
    )
    return [
        {
            "title": x.get("title"),
            "url": x.get("url"),
            "content": (x.get("content") or "")[:1200],
            "score": x.get("score"),
            "published_date": x.get("published_date"),
        }
        for x in r.get("results", [])
    ]
