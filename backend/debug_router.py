import os
import sys
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal, List, Optional

sys.path.append("/Users/rushdabaqui/Desktop/Blog_Writting_Agent/backend")

from bwa_backend import llm
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

class RouterDecision(BaseModel):
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    reason: str
    queries: List[str] = Field(default_factory=list)
    max_results_per_query: int = Field(5)
    recency_days: Optional[int] = Field(
        None, 
        description="Lookback window in days for search results. For volatile news/latest/roundups, use 7. For general recent updates, use 45. For specific historical events or past years (e.g. WWDC 2025, 2024 releases) relative to the as-of date, set to a larger lookback (e.g. 365 or 730) to avoid filtering out the relevant event information."
    )

ROUTER_SYSTEM = """You are a routing module for a technical blog planner.

Decide whether web research is needed BEFORE planning.

Guidelines for classification:
1. ONLY classify as `closed_book` (needs_research=false) if the topic is a pure evergreen/fundamental concept that does not reference any specific years, recent versions, releases, events, or fast-changing industry updates. Examples: "how to implement binary search in Python", "what is a database index".
2. Classify as `open_book` (needs_research=true) if the topic is about news, announcements, conferences (e.g., WWDC, Google I/O), specific releases, product versions, pricing, or contains words like "latest", "new", "recap", "roundup", "update", or a specific recent year (like 2025, 2026).
3. Classify as `hybrid` (needs_research=true) if it's a mix—evergreen concepts but requiring real-world up-to-date tools, libraries, or modern API versions.

CRITICAL LOOKBACK WINDOW (recency_days):
- Determine `recency_days` based on the timeframe of the topic relative to the as-of date.
- If the topic mentions a past year (e.g., 2025 conference when as-of date is 2026), set `recency_days` to at least 365 or 730 so search results published during that event are not filtered out.
- If the topic is a general news topic/weekly roundup about the latest updates, set `recency_days` to 7 or 14.

CRITICAL:
- Any topic referencing a conference (e.g., Apple WWDC, Google I/O, Microsoft Build) MUST be open_book and needs_research=true.
- Any topic referencing specific years (e.g. 2025, 2026) MUST require research (needs_research=true).
- When in doubt, prefer needs_research=true (open_book or hybrid) so the blog contains real, accurate, cited evidence rather than hallucinating.
- If needs_research is True, you MUST populate the `queries` field with 3 to 10 distinct, specific web search queries. DO NOT leave the `queries` list empty.
"""

def test_router(topic):
    decider = llm.with_structured_output(RouterDecision)
    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {topic}\nAs-of date: 2026-05-21"),
        ]
    )
    return decision

topics = [
    "major announcements from Apple WWDC 2025 conference",
    "latest key update in of 2026 google I/O meeting",
    "how to use list comprehensions in Python",
    "explaining transformer architecture in deep learning"
]

for t in topics:
    res = test_router(t)
    print(f"\nTopic: {t}")
    print("needs_research:", res.needs_research)
    print("mode:", res.mode)
    print("queries:", res.queries)
    print("recency_days:", res.recency_days)
