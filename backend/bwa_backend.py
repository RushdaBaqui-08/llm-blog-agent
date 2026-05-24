from __future__ import annotations

import operator
import os
import re
import time
import random
import json
import urllib.parse
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict, List, Optional, Literal, Annotated
from concurrent.futures import ThreadPoolExecutor

import httpx
from pydantic import BaseModel, Field, field_validator

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
# Blog Writer (Router → (Research?) → Orchestrator → Workers → ReducerWithImages)
# Patches image capability using your 3-node reducer flow:
#   merge_content -> decide_images -> generate_and_place_images
# ============================================================


# -----------------------------
# 1) Schemas
# -----------------------------
class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(..., description="One sentence describing what the reader should do/understand.")
    bullets: List[str] = Field(default_factory=list, max_length=10, description="List of sub-topics/bullet points for this task.")
    target_words: int = Field(..., description="Target words (120–550).")

    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: str = Field("explainer", description="Must be one of: explainer, tutorial, news_roundup, comparison, system_design")
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task]


class EvidenceItem(BaseModel):
    title: str
    url: str
    published_at: str = ""
    snippet: str = ""
    source: str = ""


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


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(default_factory=list)


# ---- Image planning schema (ported from your image flow) ----
class ImageSpec(BaseModel):
    placeholder: str = Field(..., description="e.g. [[IMAGE_1]]")
    filename: str = Field(..., description="Save under images/, e.g. qkv_flow.png")
    alt: str
    caption: str
    prompt: str = Field(..., description="Prompt to send to the image model.")
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"

    @field_validator('placeholder', mode='before')
    @classmethod
    def clean_placeholder(cls, v):
        if isinstance(v, list):
            while isinstance(v, list) and len(v) > 0:
                v = v[0]
        if not isinstance(v, str):
            v = str(v)
        v = v.strip("[] ")
        return f"[[{v}]]"


class GlobalImagePlan(BaseModel):
    md_with_placeholders: str
    images: List[ImageSpec] = Field(default_factory=list)

class State(TypedDict):
    topic: str

    # routing / research
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]

    # recency
    as_of: str
    recency_days: int

    # workers
    sections: Annotated[List[tuple[int, str]], operator.add]  # (task_id, section_md)

    # reducer/image
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]

    final: str


def retry_on_rate_limit(func, *args, **kwargs):
    max_retries = 8
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "rate limit" in err_msg.lower() or "RateLimitError" in type(e).__name__
            if is_rate_limit and attempt < max_retries - 1:
                sleep_time = delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                match = re.search(r"try again in (\d+\.?\d*)s", err_msg)
                if match:
                    sleep_time = max(sleep_time, float(match.group(1)) + 0.5)
                print(f"Rate limit hit. Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(sleep_time)
            else:
                raise e


class GroqStructuredOutputWrapper:
    def __init__(self, llm_instance, schema, **kwargs):
        # Force JSON mode for Groq structured output
        self.decider = llm_instance.with_structured_output(schema, method="json_mode", **kwargs)
        from langchain_core.output_parsers import PydanticOutputParser
        self.parser = PydanticOutputParser(pydantic_object=schema)
        self.format_instructions = self.parser.get_format_instructions()

    def invoke(self, input_messages, *args, **kwargs):
        instructions = (
            "\n\nCRITICAL: You MUST respond with a valid JSON object matching the JSON schema below.\n"
            "The output must conform strictly to the specified JSON schema structure. Do not invent extra keys.\n"
            f"{self.format_instructions}\n"
        )
        
        new_messages = []
        if isinstance(input_messages, list):
            system_msg_found = False
            for msg in input_messages:
                if isinstance(msg, SystemMessage):
                    new_messages.append(SystemMessage(content=msg.content + instructions))
                    system_msg_found = True
                else:
                    new_messages.append(msg)
            if not system_msg_found:
                new_messages.insert(0, SystemMessage(content="You are a helpful assistant.\n" + instructions))
        elif isinstance(input_messages, str):
            new_messages = [
                SystemMessage(content="You are a helpful assistant.\n" + instructions),
                HumanMessage(content=input_messages)
            ]
        else:
            new_messages = input_messages
            
        return retry_on_rate_limit(self.decider.invoke, new_messages, *args, **kwargs)


class LazyChatOpenAI:
    def __init__(self):
        self._instance = None
    
    @property
    def instance(self):
        if self._instance is None:
            openai_key = os.environ.get("OPENAI_API_KEY")
            groq_key = os.environ.get("GROQ_API_KEY")
            
            if openai_key:
                self._instance = ChatOpenAI(model="gpt-4o-mini")
            elif groq_key:
                from langchain_groq import ChatGroq
                model_name = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
                self._instance = ChatGroq(model=model_name, max_tokens=4096)
            else:
                # Fallback to ChatOpenAI so standard missing API key error is raised when used
                self._instance = ChatOpenAI(model="gpt-4o-mini")
        return self._instance

    def __getattr__(self, name):
        return getattr(self.instance, name)
        
    def invoke(self, *args, **kwargs):
        return retry_on_rate_limit(self.instance.invoke, *args, **kwargs)

    def with_structured_output(self, schema, **kwargs):
        inst = self.instance
        if inst.__class__.__name__ == "ChatGroq":
            return GroqStructuredOutputWrapper(inst, schema, **kwargs)
        else:
            return inst.with_structured_output(schema, **kwargs)

llm = LazyChatOpenAI()

# -----------------------------
# 3) Router
# -----------------------------
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

def router_node(state: State) -> dict:
    decider = llm.with_structured_output(RouterDecision)
    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {state['topic']}\nAs-of date: {state['as_of']}"),
        ]
    )

    if decision.recency_days is not None:
        recency_days = decision.recency_days
    elif decision.mode == "open_book":
        recency_days = 7
    elif decision.mode == "hybrid":
        recency_days = 45
    else:
        recency_days = 3650

    # Deduplicate queries case-insensitively while preserving order
    seen_queries = set()
    deduped_queries = []
    for q in (decision.queries or []):
        q_clean = q.strip()
        q_lower = q_clean.lower()
        if q_clean and q_lower not in seen_queries:
            seen_queries.add(q_lower)
            deduped_queries.append(q_clean)

    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": deduped_queries,
        "recency_days": recency_days,
    }

def route_next(state: State) -> str:
    return "research" if state["needs_research"] else "orchestrator"

# -----------------------------
# 4) Research (Tavily)
# -----------------------------
def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    if not os.getenv("TAVILY_API_KEY"):
        print("Tavily search skipped: TAVILY_API_KEY not set.")
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient()
        response = client.search(query=query, max_results=max_results)
        results = response.get("results") or []
        out: List[dict] = []
        for r in results:
            out.append(
                {
                    "title": r.get("title") or "",
                    "url": r.get("url") or "",
                    "snippet": r.get("content") or r.get("snippet") or "",
                    "published_at": r.get("published_date") or r.get("published_at"),
                    "source": r.get("source"),
                }
            )
        return out
    except Exception as e:
        print(f"Error during Tavily search: {e}")
        return []

def _iso_to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None

RESEARCH_SYSTEM = """You are a research synthesizer.

Given raw web search results, produce EvidenceItem objects.

Rules:
- Only include items with a non-empty url.
- Prefer relevant + authoritative sources.
- Normalize published_at to ISO YYYY-MM-DD if reliably inferable; else empty string "" (do NOT guess). Never output null for any optional string field; use an empty string "" instead.
- Keep snippets short.
- Deduplicate by URL.
"""

def research_node(state: State) -> dict:
    queries = (state.get("queries") or [])[:10]
    raw: List[dict] = []
    
    with ThreadPoolExecutor(max_workers=min(len(queries) or 1, 5)) as executor:
        results = executor.map(lambda q: _tavily_search(q, max_results=6), queries)
        for res in results:
            raw.extend(res)

    evidence: List[EvidenceItem] = []
    dedup = {}
    
    cutoff = None
    if state.get("mode") == "open_book":
        as_of = date.fromisoformat(state["as_of"])
        cutoff = as_of - timedelta(days=int(state["recency_days"]))

    for r in raw:
        url = r.get("url")
        if not url:
            continue
        if url in dedup:
            continue

        published_at = r.get("published_at")
        published_at_str = str(published_at) if published_at else ""
        
        if cutoff:
            d = _iso_to_date(published_at_str)
            if d and d < cutoff:
                continue

        item = EvidenceItem(
            title=r.get("title") or "Search Result",
            url=url,
            published_at=published_at_str,
            snippet=(r.get("snippet") or "")[:400],
            source=r.get("source") or ""
        )
        dedup[url] = item
        evidence.append(item)

    return {"evidence": evidence}

# -----------------------------
# 5) Orchestrator (Plan)
# -----------------------------
ORCH_SYSTEM = """You are a senior technical writer and developer advocate.
Produce a highly actionable outline for a technical blog post.

Requirements:
- 5–9 tasks, each with goal + 3–6 bullets + target_words.
- Tags are flexible; do not force a fixed taxonomy.

Grounding:
- closed_book: evergreen, no evidence dependence.
- hybrid: use evidence for up-to-date examples; mark those tasks requires_research=True and requires_citations=True.
- open_book: weekly/news roundup:
  - Set blog_kind="news_roundup"
  - No tutorial content unless requested
  - If evidence is weak, plan should explicitly reflect that (don’t invent events).

Output must match Plan schema.
"""

def orchestrator_node(state: State) -> dict:
    planner = llm.with_structured_output(Plan)
    mode = state.get("mode", "closed_book")
    evidence = state.get("evidence", [])

    forced_kind = "news_roundup" if mode == "open_book" else None

    plan = planner.invoke(
        [
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(
                content=(
                    f"Topic: {state['topic']}\n"
                    f"Mode: {mode}\n"
                    f"As-of: {state['as_of']} (recency_days={state['recency_days']})\n"
                    f"{'Force blog_kind=news_roundup' if forced_kind else ''}\n\n"
                    f"Evidence:\n{[e.model_dump() for e in evidence][:10]}"
                )
            ),
        ]
    )
    if forced_kind:
        plan.blog_kind = "news_roundup"

    # Post-process tasks to ensure bullets list is not empty
    for task in plan.tasks:
        if not task.bullets:
            task.bullets = [f"Discuss updates and key highlights for {task.title}."]

    return {"plan": plan}


# -----------------------------
# 6) Fanout
# -----------------------------
def fanout(state: State):
    assert state["plan"] is not None
    return [
        Send(
            "worker",
            {
                "task": task.model_dump(),
                "topic": state["topic"],
                "mode": state["mode"],
                "as_of": state["as_of"],
                "recency_days": state["recency_days"],
                "plan": state["plan"].model_dump(),
                "evidence": [e.model_dump() for e in state.get("evidence", [])],
            },
        )
        for task in state["plan"].tasks
    ]

# -----------------------------
# 7) Worker
# -----------------------------
WORKER_SYSTEM = """You are a senior technical writer and developer advocate.
Write ONE section of a technical blog post in Markdown.

Constraints:
- Cover ALL bullets in order.
- Target words ±15%.
- Output only section markdown starting with "## <Section Title>".

Scope guard:
- If blog_kind=="news_roundup", do NOT drift into tutorials (scraping/RSS/how to fetch).
  Focus on events + implications.

Grounding:
- If mode=="open_book": do not introduce any specific event/company/model/funding/policy claim unless supported by provided Evidence URLs.
  For each supported claim, attach a Markdown link ([Source](URL)).
  If unsupported, write "Not found in provided sources."
- If requires_citations==true (hybrid tasks): cite Evidence URLs for external claims.

Code:
- If requires_code==true, include at least one minimal snippet.
"""

def worker_node(payload: dict) -> dict:
    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]

    bullets_text = "\n- " + "\n- ".join(task.bullets)
    evidence_text = "\n".join(
        f"- {e.title} | {e.url} | {e.published_at or 'date:unknown'}"
        for e in evidence[:20]
    )

    section_md = llm.invoke(
        [
            SystemMessage(content=WORKER_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog title: {plan.blog_title}\n"
                    f"Audience: {plan.audience}\n"
                    f"Tone: {plan.tone}\n"
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Constraints: {plan.constraints}\n"
                    f"Topic: {payload['topic']}\n"
                    f"Mode: {payload.get('mode')}\n"
                    f"As-of: {payload.get('as_of')} (recency_days={payload.get('recency_days')})\n\n"
                    f"Section title: {task.title}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"Tags: {task.tags}\n"
                    f"requires_research: {task.requires_research}\n"
                    f"requires_citations: {task.requires_citations}\n"
                    f"requires_code: {task.requires_code}\n"
                    f"Bullets:{bullets_text}\n\n"
                    f"Evidence (ONLY cite these URLs):\n{evidence_text}\n"
                )
            ),
        ]
    ).content.strip()

    return {"sections": [(task.id, section_md)]}

# ============================================================
# 8) ReducerWithImages (subgraph)
#    merge_content -> decide_images -> generate_and_place_images
# ============================================================
def merge_content(state: State) -> dict:
    plan = state["plan"]
    if plan is None:
        raise ValueError("merge_content called without plan.")
    ordered_sections = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"
    return {"merged_md": merged_md}


DECIDE_IMAGES_SYSTEM = """You are an expert technical editor.
Decide if images/diagrams are needed for THIS blog.

Rules:
- Max 3 images total.
- Each image must materially improve understanding (diagram/flow/table-like visual, or realistic event photos).
- Insert placeholders exactly: [[IMAGE_1]], [[IMAGE_2]], [[IMAGE_3]].
- If no images needed: md_with_placeholders must equal input and images=[].
- Image Types:
  - For technical tutorials or system designs: prefer technical diagrams or code flows with short labels.
  - For news roundups or event summaries (e.g. news_roundup): prefer realistic photos or illustrations depicting the live event keynotes, presentation stages, or tool logos.
Return strictly GlobalImagePlan.
"""

def decide_images(state: State) -> dict:
    planner = llm.with_structured_output(GlobalImagePlan)
    merged_md = state["merged_md"]
    plan = state["plan"]
    assert plan is not None

    image_plan = planner.invoke(
        [
            SystemMessage(content=DECIDE_IMAGES_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Topic: {state['topic']}\n\n"
                    "Insert placeholders + propose image prompts.\n\n"
                    f"{merged_md}"
                )
            ),
        ]
    )

    return {
        "md_with_placeholders": image_plan.md_with_placeholders,
        "image_specs": [img.model_dump() for img in image_plan.images],
    }


def _gemini_generate_image_bytes(prompt: str) -> bytes:
    """
    Returns raw image bytes generated by Gemini.
    Requires: pip install google-genai
    Env var: GOOGLE_API_KEY
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    resp = client.models.generate_content(
        model="imagen-3.0-generate-002",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH",
                )
            ],
        ),
    )

    # Depending on SDK version, parts may hang off resp.candidates[0].content.parts
    parts = getattr(resp, "parts", None)
    if not parts and getattr(resp, "candidates", None):
        try:
            parts = resp.candidates[0].content.parts
        except Exception:
            parts = None

    if not parts:
        raise RuntimeError("No image content returned (safety/quota/SDK change).")

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data

    raise RuntimeError("No inline image bytes found in response.")


def _safe_slug(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "blog"


def generate_and_place_images(state: State) -> dict:
    plan = state["plan"]
    assert plan is not None

    md = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs", []) or []

    # Save metadata JSON sidecar
    metadata = {
        "mode": state.get("mode"),
        "needs_research": state.get("needs_research"),
        "queries": state.get("queries"),
        "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in state.get("evidence", [])],
        "plan": plan.model_dump() if hasattr(plan, "model_dump") else plan,
        "image_specs": image_specs,
        "sections_count": len(state.get("sections") or [])
    }
    try:
        json_path = ROOT_DIR / f"{_safe_slug(plan.blog_title)}.json"
        json_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    except Exception as json_err:
        print(f"Failed to write metadata JSON: {json_err}")

    # If no images requested, just write merged markdown
    if not image_specs:
        file_path = ROOT_DIR / f"{_safe_slug(plan.blog_title)}.md"
        file_path.write_text(md, encoding="utf-8")
        return {"final": md}

    images_dir = ROOT_DIR / "images"
    images_dir.mkdir(exist_ok=True)

    def process_image(spec):
        placeholder = spec["placeholder"]
        filename = spec["filename"]
        out_path = images_dir / filename

        # generate only if needed
        if not out_path.exists():
            try:
                img_bytes = _gemini_generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)
                return placeholder, f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
            except Exception as e:
                # graceful fallback: try to generate using Pollinations AI (free, no-key AI image generator)
                try:
                    print(f"Google Image Generation failed: {e}. Falling back to Pollinations AI...")
                    # Append style keywords to ensure we get clean animated vector illustrations
                    style_prompt = spec["prompt"] + ", clean 2D vector flat animation illustration, technical design style, modern colors"
                    encoded_prompt = urllib.parse.quote(style_prompt)
                    pollinations_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true"
                    resp = httpx.get(pollinations_url, timeout=30.0)
                    if resp.status_code == 200:
                        out_path.write_bytes(resp.content)
                        return placeholder, f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
                    else:
                        raise RuntimeError(f"HTTP {resp.status_code}")
                except Exception as pollinations_error:
                    # ultimate fallback: flat placehold.co text block
                    try:
                        clean_alt = spec.get('alt', 'AI Image')
                        clean_text = "".join([c if c.isalnum() or c == " " else "_" for c in clean_alt])
                        encoded_text = urllib.parse.quote(clean_text[:40])
                        placeholder_url = f"https://placehold.co/800x600/1e1e2e/cdd6f4.png?text={encoded_text}"
                        resp = httpx.get(placeholder_url, timeout=10.0)
                        if resp.status_code == 200:
                            out_path.write_bytes(resp.content)
                            return placeholder, f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
                        else:
                            raise RuntimeError(f"HTTP {resp.status_code}")
                    except Exception as placeholder_error:
                        # ultimate textual fallback
                        prompt_block = (
                            f"> **[IMAGE GENERATION FAILED]** {spec.get('caption','')}\n>\n"
                            f"> **Alt:** {spec.get('alt','')}\n>\n"
                            f"> **Prompt:** {spec.get('prompt','')}\n>\n"
                            f"> **Error:** {e} (Pollinations Error: {pollinations_error}, Placeholder Error: {placeholder_error})\n"
                        )
                        return placeholder, prompt_block
        else:
            return placeholder, f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"

    with ThreadPoolExecutor(max_workers=min(len(image_specs) or 1, 3)) as executor:
        results = list(executor.map(process_image, image_specs))

    unplaced_count = 0
    for placeholder, replacement in results:
        if placeholder in md:
            md = md.replace(placeholder, replacement)
        else:
            if unplaced_count == 0:
                md += "\n\n## Visual Highlights\n\n"
            md += replacement + "\n\n"
            unplaced_count += 1

    file_path = ROOT_DIR / f"{_safe_slug(plan.blog_title)}.md"
    file_path.write_text(md, encoding="utf-8")
    return {"final": md}

# build reducer subgraph
reducer_graph = StateGraph(State)
reducer_graph.add_node("merge_content", merge_content)
reducer_graph.add_node("decide_images", decide_images)
reducer_graph.add_node("generate_and_place_images", generate_and_place_images)
reducer_graph.add_edge(START, "merge_content")
reducer_graph.add_edge("merge_content", "decide_images")
reducer_graph.add_edge("decide_images", "generate_and_place_images")
reducer_graph.add_edge("generate_and_place_images", END)
reducer_subgraph = reducer_graph.compile()

# -----------------------------
# 9) Build main graph
# -----------------------------
g = StateGraph(State)
g.add_node("router", router_node)
g.add_node("research", research_node)
g.add_node("orchestrator", orchestrator_node)
g.add_node("worker", worker_node)
g.add_node("reducer", reducer_subgraph)

g.add_edge(START, "router")
g.add_conditional_edges("router", route_next, {"research": "research", "orchestrator": "orchestrator"})
g.add_edge("research", "orchestrator")

g.add_conditional_edges("orchestrator", fanout, ["worker"])
g.add_edge("worker", "reducer")
g.add_edge("reducer", END)

app = g.compile()
app

